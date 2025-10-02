"""Consultation enrichment processor using Amazon Bedrock for analytics.

Generates enriched analytics and clinical insights from embeddings and
PHI-redacted transcripts using Claude Sonnet 4. Stores results in gold.
"""

import json
import os
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Optional PowerTools import for testing compatibility
try:
    from aws_lambda_powertools import Logger, Metrics, Tracer
    from aws_lambda_powertools.metrics import MetricUnit

    tracer = Tracer(service="consultation-enrichment")
    logger = Logger(service="consultation-enrichment")
    metrics = Metrics(
        namespace="ConsultationPipeline",
        service="consultation-enrichment",
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
bedrock_client = boto3.client("bedrock-runtime")
dynamodb_client = boto3.client("dynamodb")
sns_client = boto3.client("sns")

SILVER_BUCKET = os.environ["SILVER_BUCKET"]
GOLD_BUCKET = os.environ["GOLD_BUCKET"]
CONSULTATION_METADATA_TABLE = os.environ["CONSULTATION_METADATA_TABLE"]
PIPELINE_COMPLETION_TOPIC_ARN = os.environ["PIPELINE_COMPLETION_TOPIC_ARN"]
CLAUDE_MODEL_ID = os.environ.get(
    "CLAUDE_MODEL_ID",
    "anthropic.claude-sonnet-4-20250514-v1:0",
)
MAX_ANALYSIS_TEXT_LENGTH = 15000


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    try:
        consultation_info = extract_consultation_info_from_event(event)
        if not consultation_info:
            logger.warning("Could not extract consultation information from event")
            return {"statusCode": 400, "body": "Invalid event format"}

        result = process_consultation_enrichment(consultation_info)
        metrics.add_metric(
            name="ConsultationsProcessed",
            unit=MetricUnit.Count,
            value=1,
        )
        if result.get("status") == "success":
            metrics.add_metric(
                name="ConsultationsSuccessful",
                unit=MetricUnit.Count,
                value=1,
            )
        else:
            metrics.add_metric(
                name="ConsultationsFailed",
                unit=MetricUnit.Count,
                value=1,
            )
        return {"statusCode": 200, "body": json.dumps({"result": result})}
    except Exception:
        logger.exception("Error processing consultation enrichment")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


@tracer.capture_method
def extract_consultation_info_from_event(
    event: dict[str, Any],
) -> dict[str, str] | None:
    if event.get("source") == "consultation.pipeline":
        detail = event.get("detail", {})
        if isinstance(detail, str):
            detail = json.loads(detail)
        return {
            "consultation_id": detail.get("consultationId", ""),
            "tenant_id": detail.get("tenantId", ""),
            "gold_key": detail.get("goldKey", ""),
            "embeddings_generated": str(detail.get("embeddingsGenerated", 0)),
            "source": "eventbridge",
        }
    if "consultation_id" in event:
        return {
            "consultation_id": event["consultation_id"],
            "tenant_id": event.get("tenant_id", ""),
            "gold_key": event.get("gold_key", ""),
            "embeddings_generated": str(event.get("embeddings_generated", 0)),
            "source": "direct_invocation",
        }
    return None


@tracer.capture_method
def process_consultation_enrichment(
    consultation_info: dict[str, str],
) -> dict[str, Any]:
    consultation_id = consultation_info["consultation_id"]
    tenant_id = consultation_info["tenant_id"]
    try:
        silver_key = (
            f"transcripts/{tenant_id}/{consultation_id}/phi_redacted_transcript.json"
        )
        transcript_data = get_transcript_data(silver_key)
        if not transcript_data:
            return {"status": "error", "error": "Failed to retrieve transcript data"}

        embeddings_key = (
            f"embeddings/{tenant_id}/{consultation_id}/conversation_embeddings.json"
        )
        embeddings_data = get_embeddings_data(embeddings_key)

        conversation_text = extract_conversation_for_analysis(transcript_data)
        if not conversation_text:
            return {
                "status": "skipped",
                "reason": "No conversation text available for analysis",
            }

        insights = generate_clinical_insights(conversation_text, embeddings_data)
        enhanced_metrics = calculate_enhanced_metrics(
            transcript_data,
            embeddings_data,
            insights,
        )

        enrichment_document = create_enrichment_document(
            consultation_id,
            tenant_id,
            transcript_data,
            embeddings_data,
            insights,
            enhanced_metrics,
        )

        analytics_key = (
            f"analytics/{tenant_id}/{consultation_id}/enriched_insights.json"
        )
        store_enrichment_document(analytics_key, enrichment_document)
        update_consultation_metadata(
            consultation_id,
            tenant_id,
            insights,
            enhanced_metrics,
        )
        publish_pipeline_completion(
            consultation_id,
            tenant_id,
            enrichment_document,
            analytics_key,
        )

        return {
            "status": "success",
            "consultation_id": consultation_id,
            "tenant_id": tenant_id,
            "analytics_key": analytics_key,
            "quality_score": insights.get("consultation_quality_score", 0),
            "consultation_type": insights.get("consultation_type", "unknown"),
        }
    except Exception as e:
        logger.exception(
            f"Error processing enrichment for consultation {consultation_id}",
        )
        return {"status": "error", "consultation_id": consultation_id, "error": str(e)}


@tracer.capture_method
def get_transcript_data(silver_key: str) -> dict[str, Any] | None:
    try:
        response = s3_client.get_object(Bucket=SILVER_BUCKET, Key=silver_key)
        return json.loads(response["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.warning(f"Transcript not found: {silver_key}")
        else:
            logger.exception(f"Error retrieving transcript: {e}")
        return None
    except Exception:
        logger.exception("Unexpected error retrieving transcript")
        return None


@tracer.capture_method
def get_embeddings_data(embeddings_key: str) -> dict[str, Any] | None:
    try:
        response = s3_client.get_object(Bucket=GOLD_BUCKET, Key=embeddings_key)
        return json.loads(response["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.info(f"Embeddings not found (optional): {embeddings_key}")
        else:
            logger.exception(f"Error retrieving embeddings: {e}")
        return None
    except Exception:
        logger.exception("Unexpected error retrieving embeddings")
        return None


@tracer.capture_method
def extract_conversation_for_analysis(transcript_data: dict[str, Any]) -> str:
    parts: list[str] = []
    if "conversation" in transcript_data:
        for turn in transcript_data["conversation"]:
            text = (turn.get("text", "") or "").strip()
            if text and not turn.get("phi_warning"):
                parts.append(f"{turn.get('speaker', 'Unknown')}: {text}")
    elif "transcript" in transcript_data:
        text = (transcript_data["transcript"] or "").strip()
        if text:
            parts.append(text)
    conversation_text = "\n".join(parts)
    if len(conversation_text) > MAX_ANALYSIS_TEXT_LENGTH:
        conversation_text = (
            conversation_text[:MAX_ANALYSIS_TEXT_LENGTH] + "\n[TRUNCATED FOR ANALYSIS]"
        )
    return conversation_text


@tracer.capture_method
def generate_clinical_insights(
    conversation_text: str,
    embeddings_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompt = build_clinical_analysis_prompt(conversation_text, embeddings_data)
    claude_text = call_claude_for_analysis(prompt)
    return parse_claude_response(claude_text)


def build_clinical_analysis_prompt(
    conversation_text: str,
    embeddings_data: dict[str, Any] | None = None,
) -> str:
    prompt = f"""Analyze this clinical consultation transcript and provide comprehensive insights for healthcare workflow optimization.

TRANSCRIPT TO ANALYZE:
{conversation_text}

Provide valid JSON with fields including consultation_type, topics_discussed, treatments_mentioned, patient_concerns, clinical_recommendations, sentiment_analysis, consultation_quality_score, duration_appropriateness.
"""
    if embeddings_data:
        stats = embeddings_data.get("statistics", {})
        metadata = embeddings_data.get("phi_redaction", {})
        prompt += f"\nAdditional context: segments={stats.get('total_segments', '?')} phi_entities={metadata.get('entities_found', '?')}"
    prompt += "\nRespond ONLY with valid JSON."
    return prompt


def call_claude_for_analysis(prompt: str) -> str:
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4000,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
    }
    response = bedrock_client.invoke_model(
        modelId=CLAUDE_MODEL_ID,
        body=json.dumps(request_body).encode("utf-8"),
        contentType="application/json",
        accept="application/json",
    )
    body = json.loads(response["body"].read())
    content = body.get("content", [])
    return content[0].get("text", "") if content else "{}"


def parse_claude_response(response_text: str) -> dict[str, Any]:
    cleaned = response_text.strip()
    cleaned = cleaned.removeprefix("```json")
    cleaned = cleaned.removesuffix("```")
    cleaned = cleaned.strip()
    return json.loads(cleaned or "{}")


@tracer.capture_method
def calculate_enhanced_metrics(
    transcript_data: dict[str, Any],
    _embeddings_data: dict[str, Any] | None,
    insights: dict[str, Any],
) -> dict[str, Any]:
    phi_info = transcript_data.get("phi_redaction", {})
    metrics: dict[str, Any] = {
        "phi_metrics": {
            "entities_found": phi_info.get("entities_found", 0),
            "entity_types": phi_info.get("entity_types", []),
        },
    }
    return metrics


@tracer.capture_method
def create_enrichment_document(
    consultation_id: str,
    tenant_id: str,
    transcript_data: dict[str, Any],
    embeddings_data: dict[str, Any] | None,
    insights: dict[str, Any],
    enhanced_metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "consultation_id": consultation_id,
        "tenant_id": tenant_id,
        "processed_at": datetime.now(UTC).isoformat(),
        "clinical_insights": insights,
        "enhanced_metrics": enhanced_metrics,
        "data_quality": {
            "has_phi_redaction": transcript_data.get("phi_redaction", {}).get(
                "entities_found",
                0,
            )
            > 0,
            "has_embeddings": embeddings_data is not None,
        },
    }


@tracer.capture_method
def store_enrichment_document(key: str, enrichment_data: dict[str, Any]) -> None:
    s3_client.put_object(
        Bucket=GOLD_BUCKET,
        Key=key,
        Body=json.dumps(enrichment_data, indent=2),
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )


@tracer.capture_method
def update_consultation_metadata(
    consultation_id: str,
    _tenant_id: str,
    insights: dict[str, Any],
    _enhanced_metrics: dict[str, Any],
) -> None:
    try:
        dynamodb_client.update_item(
            TableName=CONSULTATION_METADATA_TABLE,
            Key={
                "ConsultationId": {"S": consultation_id},
            },
            UpdateExpression="SET QualityScore = :quality, ConsultationType = :type, EnrichmentProcessedAt = :ts, ProcessingStage = :stage",
            ExpressionAttributeValues={
                ":quality": {"N": str(insights.get("consultation_quality_score", 0))},
                ":type": {"S": insights.get("consultation_type", "unknown")},
                ":ts": {"S": datetime.now(UTC).isoformat()},
                ":stage": {"S": "ENRICHMENT_COMPLETED"},
            },
        )
    except Exception:
        logger.exception("Error updating consultation metadata")


@tracer.capture_method
def publish_pipeline_completion(
    consultation_id: str,
    tenant_id: str,
    _enrichment_document: dict[str, Any],
    analytics_key: str,
) -> None:
    try:
        completion_message = {
            "eventType": "CONSULTATION_PIPELINE_COMPLETED",
            "consultationId": consultation_id,
            "tenantId": tenant_id,
            "completedAt": datetime.now(UTC).isoformat(),
            "analyticsKey": analytics_key,
        }
        sns_client.publish(
            TopicArn=PIPELINE_COMPLETION_TOPIC_ARN,
            Message=json.dumps(completion_message),
        )
    except Exception:
        logger.exception("Error publishing pipeline completion")
