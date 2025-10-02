"""Textract Job Completion Processor.

Handles SNS notifications from Amazon Textract asynchronous jobs. Retrieves
job results and stores output artifacts in the silver bucket. Emits a pipeline
event for PII redaction completion.
"""

import json
import os
from datetime import UTC, datetime
from typing import Any

import boto3

# Optional PowerTools import for testing compatibility
try:
    from aws_lambda_powertools import Logger, Metrics, Tracer
    from aws_lambda_powertools.metrics import MetricUnit

    tracer = Tracer(service="consultation-textract-completion")
    logger = Logger(service="consultation-textract-completion")
    metrics = Metrics(
        namespace="ConsultationPipeline",
        service="consultation-textract-completion",
    )
except ImportError:
    # Mock objects for testing environments
    class MockLogger:
        def info(self, msg, **kwargs):
            pass

        def error(self, msg, **kwargs):
            pass

        def warning(self, msg, **kwargs):
            pass

        def exception(self, msg, **kwargs):
            pass

        def inject_lambda_context(
            self,
            func=None,
            log_event=False,
            correlation_id_path=None,
            clear_state=False,
        ):
            if func is None:
                # Called with parentheses like @logger.inject_lambda_context()
                def decorator(f):
                    def wrapper(*func_args, **func_kwargs):
                        return f(*func_args, **func_kwargs)

                    return wrapper

                return decorator

            # Called without parentheses like @logger.inject_lambda_context
            def wrapper(*func_args, **func_kwargs):
                return func(*func_args, **func_kwargs)

            return wrapper

    class MockTracer:
        def capture_lambda_handler(self, func=None, *args, **kwargs):
            if func is None:
                # Called with parentheses like @tracer.capture_lambda_handler()
                def decorator(f):
                    def wrapper(*func_args, **func_kwargs):
                        return f(*func_args, **func_kwargs)

                    return wrapper

                return decorator

            # Called without parentheses like @tracer.capture_lambda_handler
            def wrapper(*func_args, **func_kwargs):
                return func(*func_args, **func_kwargs)

            return wrapper

        def capture_method(self, func=None, *args, **kwargs):
            if func is None:
                # Called with parentheses like @tracer.capture_method()
                def decorator(f):
                    def wrapper(*func_args, **func_kwargs):
                        return f(*func_args, **func_kwargs)

                    return wrapper

                return decorator

            # Called without parentheses like @tracer.capture_method
            def wrapper(*func_args, **func_kwargs):
                return func(*func_args, **func_kwargs)

            return wrapper

    class MockMetrics:
        def add_metric(self, *args, **kwargs):
            pass

        def add_metadata(self, *args, **kwargs):
            pass

        def log_metrics(
            self,
            func=None,
            capture_cold_start_metric=False,
            raise_on_empty_metrics=False,
        ):
            if func is None:
                # Called with parentheses like @metrics.log_metrics()
                def decorator(f):
                    def wrapper(*func_args, **func_kwargs):
                        return f(*func_args, **func_kwargs)

                    return wrapper

                return decorator

            # Called without parentheses like @metrics.log_metrics
            def wrapper(*func_args, **func_kwargs):
                return func(*func_args, **func_kwargs)

            return wrapper

    class MetricUnit:
        Count = "Count"
        Seconds = "Seconds"
        Bytes = "Bytes"

    tracer = MockTracer()
    logger = MockLogger()
    metrics = MockMetrics()

s3_client = boto3.client("s3")
textract_client = boto3.client("textract")
events_client = boto3.client("events")
macie_client = boto3.client("macie2")
dynamodb_client = boto3.client("dynamodb")

SILVER_BUCKET = os.environ["SILVER_BUCKET"]
JOB_STATUS_TABLE = os.environ.get("JOB_STATUS_TABLE", "")


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        for record in event.get("Records", []):
            msg = json.loads(record.get("Sns", {}).get("Message", "{}"))
            job_id = msg.get("JobId") or msg.get("jobId")
            status = msg.get("Status") or msg.get("status")
            if not job_id:
                logger.warning("Missing JobId in Textract SNS message")
                continue

            logger.info(
                f"Processing Textract completion for job {job_id} (status={status})",
            )

            # Only process jobs that completed successfully
            if status == "SUCCEEDED":
                try:
                    result = process_textract_job(job_id)
                    metrics.add_metric(
                        name="JobsProcessed",
                        unit=MetricUnit.Count,
                        value=1,
                    )

                    if result.get("status") == "success":
                        metrics.add_metric(
                            name="JobsSuccessful",
                            unit=MetricUnit.Count,
                            value=1,
                        )
                        logger.info(f"Successfully processed Textract job {job_id}")
                    else:
                        metrics.add_metric(
                            name="JobsFailed",
                            unit=MetricUnit.Count,
                            value=1,
                        )
                        logger.error(
                            f"Failed to process Textract job {job_id}: {result.get('error', 'Unknown error')}",
                        )

                except Exception as e:
                    metrics.add_metric(
                        name="JobsFailed",
                        unit=MetricUnit.Count,
                        value=1,
                    )
                    logger.exception(f"Exception processing Textract job {job_id}: {e}")
            else:
                # Job failed or is still in progress - don't process
                logger.warning(
                    f"Textract job {job_id} has non-successful status '{status}' - skipping processing",
                )
                metrics.add_metric(name="JobsSkipped", unit=MetricUnit.Count, value=1)

                if status == "FAILED":
                    metrics.add_metric(
                        name="TextractJobsFailed",
                        unit=MetricUnit.Count,
                        value=1,
                    )

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Processed Textract completion events"}),
        }
    except Exception:
        logger.exception("Error handling Textract completion event")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal error"})}


@tracer.capture_method
def process_textract_job(job_id: str) -> dict[str, Any]:
    try:
        result_pages = []
        next_token: str | None = None
        page_count = 0
        while True:
            kwargs: dict[str, Any] = {"JobId": job_id}
            if next_token:
                kwargs["NextToken"] = next_token
            resp = textract_client.get_document_analysis(**kwargs)
            result_pages.append(resp)
            page_count += 1
            next_token = resp.get("NextToken")
            if not next_token or page_count >= 50:  # safety cap
                break

        summary = {
            "job_id": job_id,
            "processed_at": datetime.now(UTC).isoformat(),
            "page_count": page_count,
            "document_metadata": result_pages[0].get("DocumentMetadata")
            if result_pages
            else {},
        }

        key_prefix = f"textract-results/{job_id}"
        s3_client.put_object(
            Bucket=SILVER_BUCKET,
            Key=f"{key_prefix}/summary.json",
            Body=json.dumps(summary, indent=2),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )

        events_client.put_events(
            Entries=[
                {
                    "Source": "consultation.pipeline",
                    "DetailType": "Textract Job Completed",
                    "Detail": json.dumps(
                        {"textractJobId": job_id, "silverPrefix": key_prefix},
                    ),
                },
            ],
        )

        try:
            job_name = f"Consultation-PII-{job_id}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
            macie_resp = macie_client.create_classification_job(
                jobType="ONE_TIME",
                name=job_name,
                managedDataIdentifierSelector="RECOMMENDED",
                s3JobDefinition={
                    "bucketDefinitions": [
                        {
                            "accountId": boto3.client("sts").get_caller_identity()[
                                "Account"
                            ],
                            "buckets": [SILVER_BUCKET],
                        },
                    ],
                    "scoping": {
                        "includes": {
                            "and": [
                                {
                                    "simpleScopeTerm": {
                                        "comparator": "STARTS_WITH",
                                        "key": "OBJECT_KEY",
                                        "values": [f"{key_prefix}/"],
                                    },
                                },
                            ],
                        },
                    },
                },
            )
            macie_job_id = macie_resp.get("jobId", "")
            if JOB_STATUS_TABLE and macie_job_id:
                dynamodb_client.put_item(
                    TableName=JOB_STATUS_TABLE,
                    Item={
                        "JobType": {"S": "MACIE"},
                        "JobId": {"S": macie_job_id},
                        "TextractJobId": {"S": job_id},
                        "SilverPrefix": {"S": key_prefix},
                        "CreatedAt": {"S": datetime.now(UTC).isoformat()},
                    },
                )
        except Exception:
            logger.warning("Macie job creation failed")

        return {"status": "success", "job_id": job_id, "silver_prefix": key_prefix}
    except Exception as e:
        logger.exception(f"Failed to process Textract job {job_id}")
        return {"status": "error", "job_id": job_id, "error": str(e)}
