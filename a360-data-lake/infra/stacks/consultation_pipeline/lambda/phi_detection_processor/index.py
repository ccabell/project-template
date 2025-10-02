"""PHI detection processor for consultation transcripts.

This function processes consultation transcripts using Amazon Comprehend Medical
to detect and redact Protected Health Information (PHI). It takes raw transcripts
from the bronze layer and produces PHI-redacted versions in the silver layer.
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

    POWERTOOLS_AVAILABLE = True
except ImportError:
    POWERTOOLS_AVAILABLE = False

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

        def debug(self, msg, **kwargs):
            pass

        def inject_lambda_context(
            self,
            log_event=False,
            correlation_id_path=None,
            clear_state=False,
        ):
            def decorator(func):
                return func

            return decorator

    class MockTracer:
        def capture_lambda_handler(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def capture_method(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    class MockMetrics:
        def add_metric(self, *args, **kwargs):
            pass

        def add_metadata(self, *args, **kwargs):
            pass

        def log_metrics(
            self,
            capture_cold_start_metric=False,
            raise_on_empty_metrics=False,
        ):
            def decorator(func):
                return func

            return decorator

    class MetricUnit:
        Count = "Count"
        Seconds = "Seconds"
        Bytes = "Bytes"
        Milliseconds = "Milliseconds"

    Logger = MockLogger
    Metrics = MockMetrics
    Tracer = MockTracer

# Initialize PowerTools instances
if POWERTOOLS_AVAILABLE:
    tracer = Tracer(service="consultation-phi-detection")
    logger = Logger(service="consultation-phi-detection")
    metrics = Metrics(
        namespace="ConsultationPipeline",
        service="consultation-phi-detection",
    )
else:
    tracer = MockTracer()
    logger = MockLogger()
    metrics = MockMetrics()

# Initialize AWS clients
s3_client = boto3.client("s3")
comprehend_medical_client = boto3.client("comprehendmedical")
dynamodb_client = boto3.client("dynamodb")
eventbridge_client = boto3.client("events")

# Environment variables
BRONZE_BUCKET = os.environ["BRONZE_BUCKET"]
SILVER_BUCKET = os.environ["SILVER_BUCKET"]
CONSULTATION_METADATA_TABLE = os.environ["CONSULTATION_METADATA_TABLE"]
PHI_DETECTION_TOPIC_ARN = os.environ["PHI_DETECTION_TOPIC_ARN"]

# Configuration
PHI_CONFIDENCE_THRESHOLD = 0.8
MAX_TEXT_LENGTH = 20000  # Comprehend Medical API limit


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle PHI detection and redaction for consultation transcripts.

    Args:
        event: S3 event data or direct invocation parameters.
        context: Lambda context object.

    Returns:
        Response dictionary with processing status.
    """
    try:
        # Process S3 event records
        for record in event.get("Records", []):
            if record.get("eventSource") == "aws:s3":
                process_transcript_s3_event(record)

        # Handle direct invocation
        if "consultation_id" in event:
            process_transcript_direct(event)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "PHI detection processing completed"}),
        }

    except Exception as e:
        logger.exception("Error processing PHI detection")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "Internal server error",
                    "message": str(e),
                },
            ),
        }


@tracer.capture_method
def process_transcript_s3_event(record: dict[str, Any]) -> None:
    """Process transcript from S3 event.

    Args:
        record: S3 event record.
    """
    s3_info = record["s3"]
    bucket_name = s3_info["bucket"]["name"]
    object_key = s3_info["object"]["key"]

    logger.info(f"Processing transcript: s3://{bucket_name}/{object_key}")

    # Extract consultation ID and tenant ID from object key
    # Expected format: transcripts/{tenant_id}/{consultation_id}/final_transcript.json
    if object_key.endswith("/final_transcript.json"):
        parts = object_key.split("/")
        if len(parts) >= 4 and parts[0] == "transcripts":
            tenant_id = parts[1]
            consultation_id = parts[2]
            process_consultation_transcript(consultation_id, tenant_id=tenant_id)
        else:
            logger.warning(f"Invalid transcript object key format: {object_key}, expected: transcripts/{{tenant_id}}/{{consultation_id}}/final_transcript.json")
    else:
        logger.warning(f"Invalid transcript object key format: {object_key}")


@tracer.capture_method
def process_transcript_direct(event: dict[str, Any]) -> None:
    """Process transcript from direct invocation.

    Args:
        event: Direct invocation event with consultation_id.
    """
    consultation_id = event["consultation_id"]
    logger.info(f"Processing transcript for consultation {consultation_id}")
    process_consultation_transcript(consultation_id)


@tracer.capture_method
def process_consultation_transcript(consultation_id: str, tenant_id: str | None = None) -> None:
    """Process a consultation transcript for PHI detection and redaction.

    Args:
        consultation_id: Consultation identifier.
        tenant_id: Tenant identifier (optional, extracted from S3 key).
    """
    try:
        # Get original transcript from bronze bucket
        transcript_key = f"{consultation_id}/final_transcript.json"
        transcript_data = get_transcript_from_bronze(transcript_key)

        if not transcript_data:
            logger.warning(f"No transcript found for consultation {consultation_id}")
            return

        # Extract tenant information from metadata
        tenant_id = extract_tenant_id(transcript_data)
        if not tenant_id:
            logger.warning(f"No tenant ID found for consultation {consultation_id}")
            return

        # Extract conversation text for PHI detection
        conversation_text = extract_conversation_text(transcript_data)
        if not conversation_text:
            logger.warning(
                f"No conversation text found for consultation {consultation_id}",
            )
            return

        # Detect PHI using Comprehend Medical
        phi_entities = detect_phi_entities(conversation_text)

        # Redact PHI from transcript
        redacted_transcript = redact_phi_from_transcript(
            transcript_data,
            conversation_text,
            phi_entities,
        )

        # Store redacted transcript in silver bucket
        silver_key = (
            f"transcripts/{tenant_id}/{consultation_id}/phi_redacted_transcript.json"
        )
        store_redacted_transcript(silver_key, redacted_transcript)

        # Update consultation metadata
        update_consultation_metadata(consultation_id, tenant_id, phi_entities)

        # Publish PHI detection completion event
        publish_phi_completion_event(
            consultation_id,
            tenant_id,
            silver_key,
            len(phi_entities),
        )

        # Update metrics
        metrics.add_metric(name="TranscriptsProcessed", unit=MetricUnit.Count, value=1)
        metrics.add_metric(
            name="PHIEntitiesFound",
            unit=MetricUnit.Count,
            value=len(phi_entities),
        )

        logger.info(
            f"PHI detection completed for consultation {consultation_id}: {len(phi_entities)} entities found",
        )

    except Exception:
        logger.exception(
            f"Error processing transcript for consultation {consultation_id}",
        )
        metrics.add_metric(
            name="TranscriptProcessingErrors",
            unit=MetricUnit.Count,
            value=1,
        )
        raise


@tracer.capture_method
def get_transcript_from_bronze(transcript_key: str) -> dict[str, Any] | None:
    """Retrieve transcript from bronze bucket.

    Args:
        transcript_key: S3 object key for transcript.

    Returns:
        Transcript data or None if not found.
    """
    try:
        response = s3_client.get_object(
            Bucket=BRONZE_BUCKET,
            Key=transcript_key,
        )

        transcript_data = json.loads(response["Body"].read())
        logger.info(f"Retrieved transcript: {transcript_key}")

        return transcript_data

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.warning(f"Transcript not found: {transcript_key}")
        else:
            logger.exception(f"Error retrieving transcript: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error retrieving transcript: {e}")
        return None


@tracer.capture_method
def extract_tenant_id(transcript_data: dict[str, Any]) -> str | None:
    """Extract tenant ID from transcript metadata.

    Args:
        transcript_data: Transcript data structure.

    Returns:
        Tenant ID or None if not found.
    """
    metadata = transcript_data.get("metadataAttributes", {})
    return metadata.get("tenantId")


@tracer.capture_method
def extract_conversation_text(transcript_data: dict[str, Any]) -> str:
    """Extract conversation text from transcript data.

    Args:
        transcript_data: Transcript data structure.

    Returns:
        Formatted conversation text.
    """
    conversation_parts = []

    if "conversation" in transcript_data:
        for turn in transcript_data["conversation"]:
            speaker = turn.get("speaker", "Unknown")
            text = turn.get("text", "").strip()

            if text:
                conversation_parts.append(f"{speaker}: {text}")

    elif "transcript" in transcript_data:
        text = transcript_data["transcript"].strip()
        if text:
            conversation_parts.append(text)

    conversation_text = "\n".join(conversation_parts)

    # Truncate if too long for API
    if len(conversation_text) > MAX_TEXT_LENGTH:
        logger.info(
            f"Truncating conversation text from {len(conversation_text)} to {MAX_TEXT_LENGTH} characters",
        )
        conversation_text = conversation_text[:MAX_TEXT_LENGTH]

    return conversation_text


@tracer.capture_method
def detect_phi_entities(conversation_text: str) -> list[dict[str, Any]]:
    """Detect PHI entities using Comprehend Medical.

    Args:
        conversation_text: Text to analyze for PHI.

    Returns:
        List of PHI entities found.
    """
    try:
        response = comprehend_medical_client.detect_phi(Text=conversation_text)

        # Filter entities by confidence threshold
        phi_entities = [
            entity
            for entity in response.get("Entities", [])
            if entity.get("Score", 0) >= PHI_CONFIDENCE_THRESHOLD
        ]

        logger.info(
            f"Detected {len(phi_entities)} PHI entities (confidence >= {PHI_CONFIDENCE_THRESHOLD})",
        )

        return phi_entities

    except Exception:
        logger.exception("Error detecting PHI entities")
        return []


@tracer.capture_method
def redact_phi_from_transcript(
    transcript_data: dict[str, Any],
    conversation_text: str,
    phi_entities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Redact PHI entities from transcript data.

    Args:
        transcript_data: Original transcript data.
        conversation_text: Original conversation text.
        phi_entities: PHI entities to redact.

    Returns:
        Redacted transcript data.
    """
    # Create redacted text
    redacted_text = conversation_text
    for entity in sorted(phi_entities, key=lambda x: x["BeginOffset"], reverse=True):
        start = entity["BeginOffset"]
        end = entity["EndOffset"]
        entity_type = entity["Type"]
        redacted_text = (
            redacted_text[:start] + f"[REDACTED_{entity_type}]" + redacted_text[end:]
        )

    # Create redacted transcript
    redacted_transcript = transcript_data.copy()

    # Update conversation with redacted text if structured conversation exists
    if redacted_transcript.get("conversation"):
        redacted_lines = redacted_text.split("\n")
        for i, turn in enumerate(redacted_transcript["conversation"]):
            if i < len(redacted_lines):
                parts = redacted_lines[i].split(": ", 1)
                if len(parts) == 2:
                    turn["text"] = parts[1]
                    # Mark turn as PHI redacted if it contains redaction markers
                    if "[REDACTED_" in parts[1]:
                        turn["phi_redacted"] = True

    # Add PHI redaction metadata
    redacted_transcript["phi_redaction"] = {
        "processed_at": datetime.now(UTC).isoformat(),
        "entities_found": len(phi_entities),
        "entity_types": list({e["Type"] for e in phi_entities}),
        "confidence_threshold": PHI_CONFIDENCE_THRESHOLD,
        "model_version": "comprehend-medical-20240101",
    }

    return redacted_transcript


@tracer.capture_method
def store_redacted_transcript(
    silver_key: str,
    redacted_transcript: dict[str, Any],
) -> None:
    """Store redacted transcript in silver bucket.

    Args:
        silver_key: S3 object key for redacted transcript.
        redacted_transcript: Redacted transcript data.
    """
    try:
        s3_client.put_object(
            Bucket=SILVER_BUCKET,
            Key=silver_key,
            Body=json.dumps(redacted_transcript, indent=2),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )

        logger.info(f"Stored redacted transcript: s3://{SILVER_BUCKET}/{silver_key}")

    except Exception as e:
        logger.exception(f"Error storing redacted transcript: {e}")
        raise


@tracer.capture_method
def update_consultation_metadata(
    consultation_id: str,
    tenant_id: str,
    phi_entities: list[dict[str, Any]],
) -> None:
    """Update consultation metadata with PHI detection results.

    Args:
        consultation_id: Consultation identifier.
        tenant_id: Tenant identifier.
        phi_entities: PHI entities found.
    """
    try:
        dynamodb_client.update_item(
            TableName=CONSULTATION_METADATA_TABLE,
            Key={
                "ConsultationId": {"S": consultation_id},
            },
            UpdateExpression="SET TenantId = :tenant_id, PHIEntitiesFound = :phi_count, PHIProcessedAt = :processed_at, ProcessingStage = :stage",
            ExpressionAttributeValues={
                ":tenant_id": {"S": tenant_id},
                ":phi_count": {"N": str(len(phi_entities))},
                ":processed_at": {"S": datetime.now(UTC).isoformat()},
                ":stage": {"S": "PHI_DETECTION_COMPLETED"},
            },
        )

        logger.info(f"Updated metadata for consultation {consultation_id}")

    except Exception as e:
        logger.exception(f"Error updating consultation metadata: {e}")
        # Don't raise - this is not critical for the pipeline


@tracer.capture_method
def publish_phi_completion_event(
    consultation_id: str,
    tenant_id: str,
    silver_key: str,
    phi_entities_count: int,
) -> None:
    """Publish PHI detection completion event to EventBridge.

    Args:
        consultation_id: Consultation identifier.
        tenant_id: Tenant identifier.
        silver_key: S3 key for redacted transcript.
        phi_entities_count: Number of PHI entities found.
    """
    try:
        event_detail = {
            "consultationId": consultation_id,
            "tenantId": tenant_id,
            "silverKey": silver_key,
            "phiEntitiesFound": phi_entities_count,
            "processedAt": datetime.now(UTC).isoformat(),
        }

        eventbridge_client.put_events(
            Entries=[
                {
                    "Source": "consultation.pipeline",
                    "DetailType": "PHI Detection Completed",
                    "Detail": json.dumps(event_detail),
                },
            ],
        )

        logger.info(
            f"Published PHI completion event for consultation {consultation_id}",
        )

    except Exception as e:
        logger.exception(f"Error publishing PHI completion event: {e}")
        # Don't raise - this is not critical for the pipeline
