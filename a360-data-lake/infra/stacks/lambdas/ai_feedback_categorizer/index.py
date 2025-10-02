import datetime
import json
import os
import re
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

DB_CLUSTER_ARN = os.environ["DB_CLUSTER_ARN"]
DB_SECRET_ARN = os.environ["DB_SECRET_ARN"]
DB_NAME = os.environ["DB_NAME"]
MODEL_ARN = os.environ["MODEL_ARN"]

logger = Logger(service="ai_feedback_categorizer")
tracer = Tracer(service="ai_feedback_categorizer")
metrics = Metrics(
    namespace="AIFeedbackProcessingService",
    service="ai_feedback_categorizer",
)
rds_client = boto3.client("rds-data")
bedrock_runtime_client = boto3.client("bedrock-runtime")


@tracer.capture_method
def extract_events_data(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extracts and validates SQS messages from the EventBridge Pipe event

    Args:
        events: EventBridge Pipe event

    Returns:
        List of extracted SQS messages
    """
    events_data = []
    required_keys = {"feedback_id", "rating", "comment"}
    for event in events:
        if not isinstance(event, dict) or event.get("eventSource") != "aws:sqs":
            continue
        event_body = event["body"]
        try:
            event_data = json.loads(event_body)
        except json.JSONDecodeError:
            logger.exception(
                "Failed to de-serialize the event body from JSON. Skipping...",
                extra={"event_body": event_body},
            )
            continue
        if not isinstance(event_data, dict):
            logger.error(
                "Encountered event with non-dictionary data. Skipping...",
                extra={"event_data": event_data},
            )
            continue
        if missing_keys := required_keys - event_data.keys():
            logger.error(
                f"Encountered event with the following keys missing: '{missing_keys}'. Skipping...",
                extra={"event_data": event_data},
            )
            continue
        events_data.append(event_data)
    return events_data


@tracer.capture_method
def rds_execute_statement(sql: str, **kwargs) -> dict[str, Any]:
    """Executes SQL statement with RDS Data API

    Args:
        sql: SQL statement
        kwargs: Additional arguments passed to the `execute_statement` call

    Returns:
        Response from the `execute_statement` call
    """
    return rds_client.execute_statement(
        resourceArn=DB_CLUSTER_ARN,
        secretArn=DB_SECRET_ARN,
        sql=sql,
        database=DB_NAME,
        **kwargs,
    )


@tracer.capture_method
def select_categories_by_rating(rating: str) -> list[dict[str, str]]:
    """Selects AI feedback categories from the DB with the specified rating

    Args:
        rating: Category rating

    Returns:
        List of dictionaries representing retrieved categories. Each dictionary contains
            `name` and `description` keys
    """
    sql = """\
    SELECT name, description from ai_feedback_categories
    WHERE rating = CAST(:rating AS ai_feedback_rating) and is_active
    ORDER BY sort_order, name
    """
    sql_params = [{"name": "rating", "value": {"stringValue": rating}}]
    try:
        result = rds_execute_statement(
            sql,
            parameters=sql_params,
            formatRecordsAs="JSON",
        )
    except Exception:
        logger.exception(
            "An error occurred during selecting categories from the DB:",
            extra={"rating": rating},
        )
        raise
    return json.loads(result["formattedRecords"])


@tracer.capture_method
def extract_between_tags(tag: str, source: str, *, strip: bool = True) -> list[str]:
    """Extracts content enclosed between specified XML-like tags in a string.

    Args:
        tag: The tag name to search for.
        source: The input string containing tagged content.
        strip: Whether to strip leading/trailing whitespace from each result.

    Returns:
        A list of strings extracted from within the given tags.
    """
    ext_list = re.findall(f"<{tag}>(.+?)</{tag}>", source, re.DOTALL)
    if strip:
        ext_list = [e.strip() for e in ext_list]
    return ext_list


@tracer.capture_method
def categorize_comment(comment: str, categories: list[dict[str, str]]) -> list[str]:
    """Categorizes the comment into one or more provided categories.

    Args:
        comment: Feedback comment
        categories: List of dictionaries representing the categories. Each dictionary
            must contain `name` and `description` keys

    Returns:
        A list of categories the feedback is assigned. If none of the categories were
            classified, an empty list is returned
    """
    if len(categories) == 0:
        msg = "At least one category must be provided"
        raise ValueError(msg)
    categories_str = "\n".join(
        [f"  - {cat['name']} - {cat['description']}" for cat in categories],
    )
    prompt = f"""\
You will be acting as a user feedback classification system. Your task is to analyze the user's feedback on our AI responses in the aesthetic medicine domain and assign it to one or more categories.

Instructions:
1. Carefully analyze the following user feedback:

<feedback>
{comment}
</feedback>

2. Categorize the feedback into one or more following categories:
{categories_str}

3. Your output MUST contain 2 sections:
  1. Provide your reasoning about what categories the feedback should be assigned to in the <reasoning> tags
  2. Provide the final categories in the <categories> tags. You MUST output ONLY category names exactly as they are given to you, one category per line. If none of the categories capture what the feedback is about or the feedback doesn't make any sense (e.g., if the user intentionally specified some random text), you MUST leave the <categories> tags empty."""
    assistant_prefill = "<reasoning>"

    try:
        response = bedrock_runtime_client.converse(
            modelId=MODEL_ARN,
            messages=[
                {"role": "user", "content": [{"text": prompt}]},
                {"role": "assistant", "content": [{"text": assistant_prefill}]},
            ],
            inferenceConfig={"maxTokens": 500, "temperature": 0.0},
        )
    except Exception:
        logger.exception(
            "An error occurred during comment categorization:",
            extra={"comment": comment},
        )
        raise
    tracer.put_metadata("bedrock_response", response)
    completion = response["output"]["message"]["content"][0]["text"]
    try:
        comment_cats = extract_between_tags("categories", completion)[0]
    except IndexError:
        comment_cats = ""
    if not comment_cats:
        return []
    return [cat.strip() for cat in comment_cats.split("\n")]


@tracer.capture_method
def update_comment_categories(feedback_id: str, categories: list[str]) -> None:
    """Update AI feedback metadata in the DB with comment categories

    Args:
        feedback_id: Feedback ID
        categories: Feedback comment categories
    """
    metadata = {
        "categories": categories,
        "processed_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
    }
    sql = """\
    UPDATE ai_feedback
    SET feedback_metadata = (
        jsonb_set(
            feedback_metadata::jsonb,
            '{comment}',
            :comment_metadata::jsonb,
            true
        )::json
    )
    WHERE id = :feedback_id
    """
    sql_params = [
        {"name": "comment_metadata", "value": {"stringValue": json.dumps(metadata)}},
        {"name": "feedback_id", "value": {"stringValue": feedback_id}},
    ]
    try:
        rds_execute_statement(sql, parameters=sql_params)
    except Exception:
        logger.exception(
            "An error occurred while updating comment categories in the DB:",
            extra={"feedback_id": feedback_id, "comment_metadata": metadata},
        )
        raise


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: list[dict[str, Any]], context: LambdaContext):
    """Categorizes AI feedback comments and stores the results in the DB

    Args:
        events: EventBridge Pipe event with SQS messages
        context: Lambda execution context.
    """
    logger.info(f"Extracting data from {len(event)} events")
    events_data = extract_events_data(event)
    if len(events_data) == 0:
        return {"statusCode": 400, "message": "Invalid event format"}
    logger.info(f"Processing {len(events_data)} feedback comments")
    successful_feedback = []
    failed_feedback = []
    rating_to_categories = {}
    for event_data in events_data:
        metrics.add_metric(name="ProcessedEvents", unit="Count", value=1)
        if len(event_data["comment"]) <= 5:
            logger.info(
                "Feedback comment is too short. Skipping...",
                extra={"event_data": event_data},
            )
            successful_feedback.append(event_data["feedback_id"])
            metrics.add_metric(name="SuccessfulEvents", unit="Count", value=1)
            continue
        rating = event_data["rating"]
        categories = rating_to_categories.get(rating)
        try:
            if categories is None:
                categories = select_categories_by_rating(rating)
                rating_to_categories[rating] = categories
            comment_cats = categorize_comment(event_data["comment"], categories)
            update_comment_categories(event_data["feedback_id"], comment_cats)
            successful_feedback.append(event_data["feedback_id"])
            metrics.add_metric(name="SuccessfulEvents", unit="Count", value=1)
        except Exception:
            logger.exception(
                "An error occurred during feedback processing:",
                extra={"event_data": event_data},
            )
            failed_feedback.append(event_data["feedback_id"])
            metrics.add_metric(name="FailedEvents", unit="Count", value=1)
    return {
        "statusCode": 200 if len(successful_feedback) >= len(failed_feedback) else 500,
        "successful_feedback": successful_feedback,
        "failed_feedback": failed_feedback,
    }
