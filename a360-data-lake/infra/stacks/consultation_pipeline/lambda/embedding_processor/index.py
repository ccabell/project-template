"""Embedding processor for consultation transcripts.

This function generates embeddings for PHI-redacted consultation transcripts
using Amazon Bedrock and Cohere Embed English v3. It processes conversation
turns and stores the embeddings in the gold layer for analytics and search.
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
    tracer = Tracer(service="consultation-embedding")
    logger = Logger(service="consultation-embedding")
    metrics = Metrics(
        namespace="ConsultationPipeline",
        service="consultation-embedding",
    )
else:
    tracer = MockTracer()
    logger = MockLogger()
    metrics = MockMetrics()

# Initialize AWS clients
s3_client = boto3.client("s3")
bedrock_client = boto3.client("bedrock-runtime")
dynamodb_client = boto3.client("dynamodb")
eventbridge_client = boto3.client("events")

# Environment variables
SILVER_BUCKET = os.environ["SILVER_BUCKET"]
GOLD_BUCKET = os.environ["GOLD_BUCKET"]
CONSULTATION_METADATA_TABLE = os.environ["CONSULTATION_METADATA_TABLE"]

# Configuration
COHERE_MODEL_ID = os.environ.get("COHERE_EMBED_MODEL_ID", "cohere.embed-english-v3")
BATCH_SIZE = 10  # Process embeddings in batches
MIN_TEXT_LENGTH = 10  # Skip very short texts


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle embedding generation for consultation transcripts.

    Args:
        event: EventBridge event from PHI detection completion or direct invocation.
        context: Lambda context object.

    Returns:
        Response dictionary with processing status.
    """
    try:
        # Extract consultation information from event
        consultation_info = extract_consultation_info_from_event(event)

        if not consultation_info:
            logger.warning("Could not extract consultation information from event")
            return {"statusCode": 400, "body": "Invalid event format"}

        consultation_id = consultation_info["consultation_id"]
        tenant_id = consultation_info["tenant_id"]

        logger.info(
            f"Processing embeddings for consultation {consultation_id} (tenant: {tenant_id})",
        )

        # Process the consultation embeddings
        result = process_consultation_embeddings(consultation_info)

        # Update metrics
        metrics.add_metric(
            name="EmbeddingJobsProcessed",
            unit=MetricUnit.Count,
            value=1,
        )

        if result["status"] == "success":
            metrics.add_metric(
                name="EmbeddingJobsSuccessful",
                unit=MetricUnit.Count,
                value=1,
            )
            metrics.add_metric(
                name="EmbeddingsGenerated",
                unit=MetricUnit.Count,
                value=result.get("embeddings_generated", 0),
            )
        else:
            metrics.add_metric(
                name="EmbeddingJobsFailed",
                unit=MetricUnit.Count,
                value=1,
            )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Embedding processing completed successfully",
                    "consultation_id": consultation_id,
                    "result": result,
                },
            ),
        }

    except Exception as e:
        logger.exception("Error processing embeddings")
        metrics.add_metric(
            name="EmbeddingProcessingErrors",
            unit=MetricUnit.Count,
            value=1,
        )

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
def extract_consultation_info_from_event(
    event: dict[str, Any],
) -> dict[str, str] | None:
    """Extract consultation information from various event sources.

    Args:
        event: Lambda event data.

    Returns:
        Dictionary with consultation info or None if extraction fails.
    """
    # Handle EventBridge event from PHI detection completion
    if event.get("source") == "consultation.pipeline":
        detail = event.get("detail", {})
        if isinstance(detail, str):
            detail = json.loads(detail)

        return {
            "consultation_id": detail.get("consultationId", ""),
            "tenant_id": detail.get("tenantId", ""),
            "silver_key": detail.get("silverKey", ""),
            "phi_entities_found": detail.get("phiEntitiesFound", 0),
            "source": "eventbridge",
        }

    # Handle direct invocation
    if "consultation_id" in event:
        return {
            "consultation_id": event["consultation_id"],
            "tenant_id": event.get("tenant_id", ""),
            "silver_key": event.get("silver_key", ""),
            "phi_entities_found": event.get("phi_entities_found", 0),
            "source": "direct_invocation",
        }

    return None


@tracer.capture_method
def process_consultation_embeddings(
    consultation_info: dict[str, str],
) -> dict[str, Any]:
    """Process consultation for embedding generation.

    Args:
        consultation_info: Dictionary with consultation details.

    Returns:
        Processing result with status and metadata.
    """
    consultation_id = consultation_info["consultation_id"]
    tenant_id = consultation_info["tenant_id"]

    try:
        # Get PHI-redacted transcript from silver bucket
        silver_key = (
            f"transcripts/{tenant_id}/{consultation_id}/phi_redacted_transcript.json"
        )
        transcript_data = get_redacted_transcript(silver_key)

        if not transcript_data:
            return {
                "status": "error",
                "error": "Failed to retrieve redacted transcript",
            }

        # Extract conversation turns for embedding
        conversation_turns = extract_conversation_turns(transcript_data)
        if not conversation_turns:
            return {
                "status": "skipped",
                "reason": "No conversation turns available for embedding",
            }

        logger.info(
            f"Generating embeddings for {len(conversation_turns)} conversation turns",
        )

        # Generate embeddings using Cohere Embed English v3
        embeddings_data = generate_embeddings(conversation_turns)

        # Create embeddings document
        embeddings_document = create_embeddings_document(
            consultation_id,
            tenant_id,
            transcript_data,
            embeddings_data,
        )

        # Store embeddings in gold layer
        embeddings_key = (
            f"embeddings/{tenant_id}/{consultation_id}/conversation_embeddings.json"
        )
        store_embeddings_document(embeddings_key, embeddings_document)

        # Update consultation metadata
        update_consultation_metadata(consultation_id, tenant_id, len(embeddings_data))

        # Publish embedding completion event
        publish_embedding_completion_event(
            consultation_id,
            tenant_id,
            embeddings_key,
            len(embeddings_data),
        )

        logger.info(
            f"Embedding generation completed for {consultation_id}: {len(embeddings_data)} embeddings created",
        )

        return {
            "status": "success",
            "consultation_id": consultation_id,
            "tenant_id": tenant_id,
            "embeddings_key": embeddings_key,
            "embeddings_generated": len(embeddings_data),
            "conversation_turns": len(conversation_turns),
        }

    except Exception as e:
        logger.exception(
            f"Error processing embeddings for consultation {consultation_id}",
        )
        return {
            "status": "error",
            "consultation_id": consultation_id,
            "error": str(e),
        }


@tracer.capture_method
def get_redacted_transcript(silver_key: str) -> dict[str, Any] | None:
    """Retrieve PHI-redacted transcript from silver bucket.

    Args:
        silver_key: S3 object key for redacted transcript.

    Returns:
        Transcript data or None if not found.
    """
    try:
        response = s3_client.get_object(
            Bucket=SILVER_BUCKET,
            Key=silver_key,
        )

        transcript_data = json.loads(response["Body"].read())
        logger.info(f"Retrieved redacted transcript: {silver_key}")

        return transcript_data

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.warning(f"Redacted transcript not found: {silver_key}")
        else:
            logger.exception(f"Error retrieving redacted transcript: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error retrieving redacted transcript: {e}")
        return None


@tracer.capture_method
def extract_conversation_turns(transcript_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract conversation turns suitable for embedding.

    Args:
        transcript_data: Redacted transcript data.

    Returns:
        List of conversation turns with metadata.
    """
    conversation_turns = []

    if transcript_data.get("conversation"):
        for i, turn in enumerate(transcript_data["conversation"]):
            text = turn.get("text", "").strip()

            # Skip very short texts and PHI redaction markers
            if len(text) > MIN_TEXT_LENGTH and not turn.get("phi_redacted"):
                conversation_turns.append(
                    {
                        "turn_index": i,
                        "speaker": turn.get("speaker", "Unknown"),
                        "text": text,
                        "start_time": turn.get("start_time"),
                        "end_time": turn.get("end_time"),
                        "duration": turn.get("duration"),
                    },
                )

    logger.info(f"Extracted {len(conversation_turns)} conversation turns for embedding")
    return conversation_turns


@tracer.capture_method
def generate_embeddings(
    conversation_turns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate embeddings for conversation turns using Cohere.

    Args:
        conversation_turns: List of conversation turns.

    Returns:
        List of embedding data with metadata.
    """
    embeddings_data = []

    # Process in batches to optimize API calls
    for i in range(0, len(conversation_turns), BATCH_SIZE):
        batch = conversation_turns[i : i + BATCH_SIZE]
        texts = [turn["text"] for turn in batch]

        try:
            # Call Bedrock with Cohere model
            embed_request = {
                "input_type": "search_document",
                "texts": texts,
                "embedding_types": ["float"],
            }

            response = bedrock_client.invoke_model(
                modelId=COHERE_MODEL_ID,
                body=json.dumps(embed_request),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            embeddings = response_body.get("embeddings", [])

            # Combine embeddings with conversation metadata
            for _j, (turn, embedding) in enumerate(
                zip(batch, embeddings, strict=False),
            ):
                embeddings_data.append(
                    {
                        "turn_index": turn["turn_index"],
                        "speaker": turn["speaker"],
                        "text": turn["text"],
                        "start_time": turn["start_time"],
                        "end_time": turn["end_time"],
                        "duration": turn["duration"],
                        "embedding": embedding,
                        "embedding_model": COHERE_MODEL_ID,
                        "embedding_dimension": len(embedding),
                        "generated_at": datetime.now(UTC).isoformat(),
                    },
                )

        except Exception as e:
            logger.exception(
                f"Failed to generate embeddings for batch {i}-{i + len(batch) - 1}: {e}",
            )
            continue

    logger.info(f"Generated {len(embeddings_data)} embeddings using {COHERE_MODEL_ID}")
    return embeddings_data


@tracer.capture_method
def create_embeddings_document(
    consultation_id: str,
    tenant_id: str,
    transcript_data: dict[str, Any],
    embeddings_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create comprehensive embeddings document for gold layer storage.

    Args:
        consultation_id: Consultation identifier.
        tenant_id: Tenant identifier.
        transcript_data: Original transcript data.
        embeddings_data: Generated embeddings data.

    Returns:
        Complete embeddings document.
    """
    # Calculate statistics
    total_turns = len(transcript_data.get("conversation", []))
    embedded_turns = len(embeddings_data)
    success_rate = embedded_turns / total_turns if total_turns > 0 else 0

    # Calculate conversation metrics
    total_words = sum(len(turn["text"].split()) for turn in embeddings_data)
    unique_speakers = len({turn["speaker"] for turn in embeddings_data})
    avg_words_per_turn = total_words / embedded_turns if embedded_turns > 0 else 0

    return {
        "consultation_id": consultation_id,
        "tenant_id": tenant_id,
        "processed_at": datetime.now(UTC).isoformat(),
        "embedding_model": COHERE_MODEL_ID,
        "embeddings": embeddings_data,
        "statistics": {
            "total_turns": total_turns,
            "embedded_turns": embedded_turns,
            "success_rate": success_rate,
            "skipped_turns": total_turns - embedded_turns,
        },
        "metadata": {
            "total_words": total_words,
            "unique_speakers": unique_speakers,
            "average_words_per_turn": avg_words_per_turn,
            "conversation_duration": calculate_conversation_duration(embeddings_data),
            "has_phi_redaction": transcript_data.get("phi_redaction", {}).get(
                "entities_found",
                0,
            )
            > 0,
        },
    }


@tracer.capture_method
def calculate_conversation_duration(
    embeddings_data: list[dict[str, Any]],
) -> float | None:
    """Calculate total conversation duration from embeddings data.

    Args:
        embeddings_data: List of embedding data with timing information.

    Returns:
        Total duration in seconds or None if timing data unavailable.
    """
    if not embeddings_data:
        return None

    # Find earliest start time and latest end time
    start_times = [
        turn.get("start_time") for turn in embeddings_data if turn.get("start_time")
    ]
    end_times = [
        turn.get("end_time") for turn in embeddings_data if turn.get("end_time")
    ]

    if start_times and end_times:
        min_start = min(start_times)
        max_end = max(end_times)
        return max_end - min_start

    return None


@tracer.capture_method
def store_embeddings_document(
    embeddings_key: str,
    embeddings_document: dict[str, Any],
) -> None:
    """Store embeddings document in gold bucket.

    Args:
        embeddings_key: S3 object key for embeddings document.
        embeddings_document: Complete embeddings document.
    """
    try:
        s3_client.put_object(
            Bucket=GOLD_BUCKET,
            Key=embeddings_key,
            Body=json.dumps(embeddings_document, indent=2),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )

        logger.info(f"Stored embeddings document: s3://{GOLD_BUCKET}/{embeddings_key}")

    except Exception as e:
        logger.exception(f"Error storing embeddings document: {e}")
        raise


@tracer.capture_method
def update_consultation_metadata(
    consultation_id: str,
    tenant_id: str,
    embeddings_generated: int,
) -> None:
    """Update consultation metadata with embedding results.

    Args:
        consultation_id: Consultation identifier.
        tenant_id: Tenant identifier.
        embeddings_generated: Number of embeddings generated.
    """
    try:
        dynamodb_client.update_item(
            TableName=CONSULTATION_METADATA_TABLE,
            Key={
                "ConsultationId": {"S": consultation_id},
            },
            UpdateExpression="SET EmbeddingsGenerated = :embeddings, EmbeddingProcessedAt = :processed_at, ProcessingStage = :stage",
            ExpressionAttributeValues={
                ":embeddings": {"N": str(embeddings_generated)},
                ":processed_at": {"S": datetime.now(UTC).isoformat()},
                ":stage": {"S": "EMBEDDING_COMPLETED"},
            },
        )

        logger.info(f"Updated metadata for consultation {consultation_id}")

    except Exception as e:
        logger.exception(f"Error updating consultation metadata: {e}")
        # Don't raise - this is not critical for the pipeline


@tracer.capture_method
def publish_embedding_completion_event(
    consultation_id: str,
    tenant_id: str,
    embeddings_key: str,
    embeddings_generated: int,
) -> None:
    """Publish embedding completion event to EventBridge.

    Args:
        consultation_id: Consultation identifier.
        tenant_id: Tenant identifier.
        embeddings_key: S3 key for embeddings document.
        embeddings_generated: Number of embeddings generated.
    """
    try:
        event_detail = {
            "consultationId": consultation_id,
            "tenantId": tenant_id,
            "goldKey": embeddings_key,
            "embeddingsGenerated": embeddings_generated,
            "processedAt": datetime.now(UTC).isoformat(),
        }

        eventbridge_client.put_events(
            Entries=[
                {
                    "Source": "consultation.pipeline",
                    "DetailType": "Embedding Processing Completed",
                    "Detail": json.dumps(event_detail),
                },
            ],
        )

        logger.info(
            f"Published embedding completion event for consultation {consultation_id}",
        )

    except Exception as e:
        logger.exception(f"Error publishing embedding completion event: {e}")
        # Don't raise - this is not critical for the pipeline
