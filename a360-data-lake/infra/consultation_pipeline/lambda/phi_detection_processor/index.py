"""PHI detection processor using Amazon Comprehend Medical.

Processes clinical consultation transcripts from the bronze layer to detect and
redact PHI using Comprehend Medical. Stores redacted transcripts in silver.
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

    tracer = Tracer(service="consultation-phi-detection")
    logger = Logger(service="consultation-phi-detection")
    metrics = Metrics(
        namespace="ConsultationPipeline",
        service="consultation-phi-detection",
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
comprehend_medical_client = boto3.client("comprehendmedical")
dynamodb_client = boto3.client("dynamodb")
sns_client = boto3.client("sns")
events_client = boto3.client("events")

BRONZE_BUCKET = os.environ["BRONZE_BUCKET"]
SILVER_BUCKET = os.environ["SILVER_BUCKET"]
CONSULTATION_METADATA_TABLE = os.environ["CONSULTATION_METADATA_TABLE"]
PHI_DETECTION_TOPIC_ARN = os.environ["PHI_DETECTION_TOPIC_ARN"]

PHI_CONFIDENCE_THRESHOLD = float(os.environ.get("PHI_CONFIDENCE_THRESHOLD", "0.8"))
PHI_WARNING_THRESHOLD = 0.01  # Threshold for adding phi_warning to turns
MAX_TEXT_SIZE = 20000
HUMAN_REVIEW_ENTITY_TYPES = set(
    os.environ.get("HUMAN_REVIEW_ENTITY_TYPES", "NAME,SSN,ADDRESS").split(","),
)


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        if os.environ.get("CIRCUIT_BREAKER", "closed").lower() == "open":
            logger.warning("Circuit breaker open; skipping PHI detection")
            return {
                "statusCode": 503,
                "body": json.dumps({"message": "Service temporarily disabled"}),
            }
        consultation_info = extract_consultation_info_from_event(event)
        if not consultation_info:
            logger.warning("Could not extract consultation information from event")
            return {"statusCode": 400, "body": "Invalid event format"}

        result = process_consultation_transcript(consultation_info)
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
            metrics.add_metric(
                name="PHIEntitiesDetected",
                unit=MetricUnit.Count,
                value=result.get("phi_entities_count", 0),
            )
        else:
            metrics.add_metric(
                name="ConsultationsFailed",
                unit=MetricUnit.Count,
                value=1,
            )

        return {"statusCode": 200, "body": json.dumps({"result": result})}
    except Exception:
        logger.exception("Error processing PHI detection")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


@tracer.capture_method
def extract_consultation_info_from_event(
    event: dict[str, Any],
) -> dict[str, str] | None:
    if "Records" in event:
        for record in event["Records"]:
            if record.get("eventSource") == "aws:s3":
                object_key = record.get("s3", {}).get("object", {}).get("key", "")
                if object_key.endswith("/final_transcript.json"):
                    # Extract tenant_id and consultation_id from path: transcripts/{tenant_id}/{consultation_id}/final_transcript.json
                    parts = object_key.split("/")
                    try:
                        idx = parts.index("transcripts")
                        tenant_id = parts[idx + 1]
                        consultation_id = parts[idx + 2]
                        return {
                            "consultation_id": consultation_id,
                            "tenant_id": tenant_id,
                            "source": "s3_event",
                        }
                    except (ValueError, IndexError):
                        logger.warning(f"Unexpected S3 key format: {object_key}")
                        # Fallback to original logic and lookup metadata
                        consultation_id = object_key.split("/")[0]
                        metadata = get_consultation_metadata(consultation_id)
                        if metadata:
                            return {
                                "consultation_id": consultation_id,
                                "tenant_id": metadata.get("tenantId", ""),
                                "source": "s3_event",
                            }
    if event.get("source") == "consultation.pipeline":
        detail = event.get("detail", {})
        return {
            "consultation_id": detail.get("consultationId", ""),
            "tenant_id": detail.get("tenantId", ""),
            "source": "eventbridge",
        }
    if "consultation_id" in event:
        return {
            "consultation_id": event["consultation_id"],
            "tenant_id": event.get("tenant_id", ""),
            "source": "direct_invocation",
        }
    return None


@tracer.capture_method
def get_consultation_metadata(consultation_id: str) -> dict[str, Any] | None:
    try:
        metadata_key = f"{consultation_id}/metadata.json"
        response = s3_client.get_object(Bucket=BRONZE_BUCKET, Key=metadata_key)
        metadata = json.loads(response["Body"].read())
        return metadata.get("metadataAttributes", {})
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.warning(f"Metadata not found for consultation {consultation_id}")
        else:
            logger.exception(f"Error retrieving metadata: {e}")
        return None
    except Exception:
        logger.exception("Unexpected error retrieving metadata")
        return None


@tracer.capture_method
def process_consultation_transcript(
    consultation_info: dict[str, str],
) -> dict[str, Any]:
    consultation_id = consultation_info["consultation_id"]
    tenant_id = consultation_info["tenant_id"]
    try:
        transcript_data = get_consultation_transcript(consultation_id, tenant_id)
        if not transcript_data:
            return {
                "status": "error",
                "error": "Failed to retrieve consultation transcript",
            }

        conversation_text = extract_conversation_text(transcript_data)
        if not conversation_text:
            return {
                "status": "skipped",
                "reason": "No conversation text found in transcript",
            }

        phi_detection_result = detect_phi_in_text(conversation_text)
        redacted_transcript = redact_phi_from_transcript(
            transcript_data,
            phi_detection_result,
        )

        silver_key = (
            f"transcripts/{tenant_id}/{consultation_id}/phi_redacted_transcript.json"
        )
        store_redacted_transcript(silver_key, redacted_transcript)
        store_consultation_metadata(consultation_id, tenant_id, phi_detection_result)

        try:
            if any(
                t in HUMAN_REVIEW_ENTITY_TYPES
                for t in phi_detection_result["entity_types"]
            ):
                review_topic = os.environ.get("HUMAN_REVIEW_TOPIC_ARN")
                if review_topic:
                    sns_client.publish(
                        TopicArn=review_topic,
                        Message=json.dumps(
                            {
                                "consultationId": consultation_id,
                                "tenantId": tenant_id,
                                "phiEntitiesFound": phi_detection_result[
                                    "entities_count"
                                ],
                                "entityTypes": phi_detection_result["entity_types"],
                            },
                        ),
                        Subject=f"Human review required: {consultation_id}",
                    )
        except Exception:
            logger.warning("Human review notification failed")

        publish_phi_detection_completion(
            consultation_id,
            tenant_id,
            phi_detection_result,
            silver_key,
        )

        return {
            "status": "success",
            "consultation_id": consultation_id,
            "tenant_id": tenant_id,
            "silver_key": silver_key,
            "phi_entities_count": phi_detection_result["entities_count"],
            "entity_types": phi_detection_result["entity_types"],
            "confidence_threshold": PHI_CONFIDENCE_THRESHOLD,
        }
    except Exception as e:
        logger.exception(f"Error processing consultation {consultation_id}")
        return {"status": "error", "consultation_id": consultation_id, "error": str(e)}


@tracer.capture_method
def get_consultation_transcript(
    consultation_id: str,
    tenant_id: str,
) -> dict[str, Any] | None:
    try:
        transcript_key = (
            f"transcripts/{tenant_id}/{consultation_id}/final_transcript.json"
        )
        response = s3_client.get_object(Bucket=BRONZE_BUCKET, Key=transcript_key)
        return json.loads(response["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.warning(
                f"Transcript not found for consultation {consultation_id} in tenant {tenant_id}",
            )
        else:
            logger.exception(f"Error retrieving transcript: {e}")
        return None
    except Exception:
        logger.exception("Unexpected error retrieving transcript")
        return None


@tracer.capture_method
def extract_conversation_text(transcript_data: dict[str, Any]) -> str:
    parts: list[str] = []
    if "conversation" in transcript_data:
        for turn in transcript_data["conversation"]:
            text = (turn.get("text", "") or "").strip()
            if text:
                parts.append(f"{turn.get('speaker', 'Unknown')}: {text}")
    elif "transcript" in transcript_data:
        text = (transcript_data["transcript"] or "").strip()
        if text:
            parts.append(text)
    text = "\n".join(parts)
    if len(text) > MAX_TEXT_SIZE:
        text = text[:MAX_TEXT_SIZE]
    return text


@tracer.capture_method
def detect_phi_in_text(text: str) -> dict[str, Any]:
    try:
        response = comprehend_medical_client.detect_phi(Text=text)
        all_entities = response.get("Entities", [])
        high_confidence = [
            e for e in all_entities if e.get("Score", 0) >= PHI_CONFIDENCE_THRESHOLD
        ]
        entity_types: dict[str, int] = {}
        for e in high_confidence:
            t = e.get("Type", "UNKNOWN")
            entity_types[t] = entity_types.get(t, 0) + 1
        return {
            "entities_count": len(high_confidence),
            "total_entities_found": len(all_entities),
            "entity_types": list(entity_types.keys()),
            "entity_type_counts": entity_types,
            "entities": high_confidence,
            "confidence_threshold": PHI_CONFIDENCE_THRESHOLD,
            "model_version": response.get("ModelVersion", "unknown"),
        }
    except ClientError as e:
        logger.exception(
            f"Comprehend Medical API error {e.response['Error']['Code']}: {e}",
        )
        return {
            "entities_count": 0,
            "total_entities_found": 0,
            "entity_types": [],
            "entity_type_counts": {},
            "entities": [],
            "error": f"API Error: {e.response['Error']['Code']}",
        }
    except Exception as e:
        logger.exception("Unexpected error in PHI detection")
        return {
            "entities_count": 0,
            "total_entities_found": 0,
            "entity_types": [],
            "entity_type_counts": {},
            "entities": [],
            "error": str(e),
        }


@tracer.capture_method
def redact_phi_from_transcript(
    transcript_data: dict[str, Any],
    phi_result: dict[str, Any],
) -> dict[str, Any]:
    redacted_transcript = dict(transcript_data)
    phi_entities = phi_result.get("entities", [])
    if not phi_entities:
        redacted_transcript["phi_redaction"] = {
            "processed_at": datetime.now(UTC).isoformat(),
            "entities_found": 0,
            "entities_redacted": 0,
            "confidence_threshold": PHI_CONFIDENCE_THRESHOLD,
        }
        return redacted_transcript

    sorted_entities = sorted(phi_entities, key=lambda x: x["BeginOffset"], reverse=True)

    if "conversation" in redacted_transcript:
        conversation_text = extract_conversation_text(transcript_data)
        redacted_text = redact_text_with_entities(conversation_text, sorted_entities)
        redaction_ratio = (len(conversation_text) - len(redacted_text)) / max(
            len(conversation_text),
            1,
        )

        # Split redacted text back into individual turns
        redacted_lines = redacted_text.split("\n")
        updated_conversation: list[dict[str, Any]] = []

        for i, turn in enumerate(redacted_transcript["conversation"]):
            t = dict(turn)
            original_text = (turn.get("text", "") or "").strip()

            # Find corresponding redacted line for this turn
            if i < len(redacted_lines) and original_text:
                redacted_line = redacted_lines[i]
                # Extract text after speaker prefix (e.g., "Speaker: text" -> "text")
                speaker_prefix = f"{turn.get('speaker', 'Unknown')}: "
                if redacted_line.startswith(speaker_prefix):
                    t["text"] = redacted_line[len(speaker_prefix) :]
                else:
                    t["text"] = redacted_line

            # Add phi_warning if significant redaction occurred
            if redaction_ratio > PHI_WARNING_THRESHOLD:
                t["phi_warning"] = "This turn may contain redacted PHI"
            updated_conversation.append(t)

        redacted_transcript["conversation"] = updated_conversation
    elif "transcript" in redacted_transcript:
        original_text = redacted_transcript["transcript"]
        redacted_transcript["transcript"] = redact_text_with_entities(
            original_text,
            sorted_entities,
        )

    redacted_transcript["phi_redaction"] = {
        "processed_at": datetime.now(UTC).isoformat(),
        "entities_found": phi_result["entities_count"],
        "entities_redacted": len(sorted_entities),
        "entity_types": phi_result["entity_types"],
        "entity_type_counts": phi_result["entity_type_counts"],
        "confidence_threshold": PHI_CONFIDENCE_THRESHOLD,
        "model_version": phi_result.get("model_version", "unknown"),
    }
    return redacted_transcript


@tracer.capture_method
def redact_text_with_entities(text: str, entities: list[dict[str, Any]]) -> str:
    redacted_text = text
    for entity in entities:
        start = entity["BeginOffset"]
        end = entity["EndOffset"]
        entity_type = entity.get("Type", "PHI")
        confidence = entity.get("Score", 0)
        placeholder = f"[REDACTED_{entity_type}_{confidence:.2f}]"
        redacted_text = redacted_text[:start] + placeholder + redacted_text[end:]
    return redacted_text


@tracer.capture_method
def store_redacted_transcript(key: str, transcript_data: dict[str, Any]) -> None:
    s3_client.put_object(
        Bucket=SILVER_BUCKET,
        Key=key,
        Body=json.dumps(transcript_data, indent=2),
        ContentType="application/json",
        ServerSideEncryption="AES256",
    )


@tracer.capture_method
def store_consultation_metadata(
    consultation_id: str,
    tenant_id: str,
    phi_result: dict[str, Any],
) -> None:
    item = {
        "ConsultationId": {"S": consultation_id},
        "TenantId": {"S": tenant_id},
        "ProcessedAt": {"S": datetime.now(UTC).isoformat()},
        "PHIEntitiesFound": {"N": str(phi_result["entities_count"])},
        "EntityTypes": {"SS": phi_result["entity_types"]}
        if phi_result["entity_types"]
        else {"SS": ["NONE"]},
        "ConfidenceThreshold": {"N": str(PHI_CONFIDENCE_THRESHOLD)},
        "ProcessingStage": {"S": "PHI_DETECTION_COMPLETED"},
    }
    dynamodb_client.put_item(TableName=CONSULTATION_METADATA_TABLE, Item=item)


@tracer.capture_method
def publish_phi_detection_completion(
    consultation_id: str,
    tenant_id: str,
    phi_result: dict[str, Any],
    silver_key: str,
) -> None:
    try:
        sns_message = {
            "eventType": "PHI_DETECTION_COMPLETED",
            "consultationId": consultation_id,
            "tenantId": tenant_id,
            "processedAt": datetime.now(UTC).isoformat(),
            "silverKey": silver_key,
            "phiEntitiesFound": phi_result["entities_count"],
            "entityTypes": phi_result["entity_types"],
        }
        sns_client.publish(
            TopicArn=PHI_DETECTION_TOPIC_ARN,
            Message=json.dumps(sns_message),
        )

        eventbridge_event = {
            "Source": "consultation.pipeline",
            "DetailType": "PHI Detection Completed",
            "Detail": json.dumps(
                {
                    "consultationId": consultation_id,
                    "tenantId": tenant_id,
                    "silverKey": silver_key,
                    "phiEntitiesFound": phi_result["entities_count"],
                    "entityTypes": phi_result["entity_types"],
                },
            ),
        }
        events_client.put_events(Entries=[eventbridge_event])
    except Exception:
        logger.exception("Error publishing completion events")
