import json
import os
import uuid
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.data_classes import (
    S3EventBridgeNotificationEvent,
    event_source,
)
from aws_lambda_powertools.utilities.typing import LambdaContext

DB_CLUSTER_ARN = os.environ["DB_CLUSTER_ARN"]
DB_SECRET_ARN = os.environ["DB_SECRET_ARN"]
DB_NAME = os.environ["DB_NAME"]

tracer = Tracer(service="transcription_handler")
logger = Logger(service="transcription_handler")
metrics = Metrics(namespace="TranscriptionService", service="transcription_handler")

s3_client = boto3.client("s3")
rds_client = boto3.client("rds-data")


@event_source(data_class=S3EventBridgeNotificationEvent)
@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(
    event: S3EventBridgeNotificationEvent,
    context: LambdaContext,  # noqa: ARG001
) -> dict[str, Any]:
    """Process S3 audio transcription EventBridge Notification and store metadata in the database.

    Triggered when transcription files are uploaded to S3. Extracts conversation
    text from the transcription, processes it, and stores metadata in PostgreSQL.

    Args:
        event: Lambda event containing S3 EventBridge Notification.
        context: Lambda runtime context.

    Returns:
        Dictionary with processing result.
    """
    bucket_name = event.detail.bucket.name
    key = event.detail.object.key
    try:
        if not key.endswith(".json") or "/transcript/" not in key:
            msg = "Unexpected key format"
            logger.error(msg, extra={"key": key})
            raise ValueError(msg)
        logger.info(
            "Processing transcription",
            extra={"bucket": bucket_name, "key": key},
        )
        metrics.add_metric(name="TranscriptionFileProcessed", unit="Count", value=1)

        with tracer.provider.in_subsegment("retrieve_transcription"):
            data = json.loads(get_json_from_s3(bucket_name, key))
            diarized_segments = group_by_speaker(data)

        if not diarized_segments:
            msg = "No transcripts found in file"
            logger.error(msg, extra={"key": key})
            metrics.add_metric(name="EmptyTranscription", unit="Count", value=1)
            raise RuntimeError(msg)

        metadata_key = key.replace("/transcript/", "/metadata/").replace(
            "-final.json",
            "-audio-metadata.json",
        )

        with tracer.provider.in_subsegment("retrieve_metadata"):
            metadata = json.loads(get_json_from_s3(bucket_name, metadata_key))

        with tracer.provider.in_subsegment("update_metadata"):
            result = update_metadata(key, metadata, diarized_segments)
    except Exception as e:
        msg = "Failed to process transcription"
        logger.exception(msg, extra={"error": str(e), "key": key})
        metrics.add_metric(name="ProcessingError", unit="Count", value=1)
        return {"statusCode": 500, "message": msg}
    return {
        "statusCode": 200,
        "message": "Transcription processing complete",
        "result": result,
    }


@tracer.capture_method
def update_metadata(
    key: str,
    metadata: dict[str, Any],
    diarized_segments: list[dict[str, Any]],
) -> dict[str, str]:
    """Update attachment metadata in the database.

    Creates entries in the attachments table for audio files and their
    corresponding transcriptions.

    Args:
        key: S3 object key of the transcription file.
        metadata: Metadata associated with the transcription.
        diarized_segments: Processed conversation segments.

    Returns:
        Dictionary containing operation results.

    Raises:
        Exception: If database operations fail.
    """
    if "/" not in key:
        logger.info("Unknown prefix format for object", extra={"key": key})
        return {"status": "skipped", "reason": "Invalid key format", "key": key}

    try:
        attachment_id = str(uuid.uuid4())
        metadata["transcript_path"] = key
        metadata["diarized_segments"] = diarized_segments

        file_paths = metadata.get("metadataAttributes", {}).get("file_paths", {})
        file_path = file_paths.get("mp3")
        if not file_path:
            file_path = file_paths.get("wav")
        if not file_path:
            file_path = key.replace("/transcript/", "/audio/").replace(
                "-final.json",
                "-audio.mp3",
            )

        file_extension = file_path.split(".")[-1] if "." in file_path else "mp3"

        chunks_processed = int(
            metadata.get("metadataAttributes", {}).get("chunksProcessed", 0),
        )
        file_size = int(chunks_processed * 960)
        consultation_id = key.split("/")[0]

        with tracer.provider.in_subsegment("db_insertion"):
            # Insert record for audio attachment
            insert_sql = """\
            INSERT INTO attachments (
                id, attachment_type, file_path, file_size, file_extension, file_metadata,
                created_at, updated_at, consultation_id
            )
            VALUES (
                :id, :attachment_type, :file_path, :file_size, :file_extension,
                :file_metadata, NOW(), NOW(), :consultation_id
            )"""
            sql_params = [
                {"name": "id", "value": {"stringValue": attachment_id}},
                {"name": "attachment_type", "value": {"longValue": 4}},
                {"name": "file_path", "value": {"stringValue": file_path}},
                {"name": "file_size", "value": {"longValue": file_size}},
                {"name": "file_extension", "value": {"stringValue": file_extension}},
                {
                    "name": "file_metadata",
                    "value": {"stringValue": json.dumps(metadata)},
                    "typeHint": "JSON",
                },
                {"name": "consultation_id", "value": {"stringValue": consultation_id}},
            ]

            rds_client.execute_statement(
                resourceArn=DB_CLUSTER_ARN,
                secretArn=DB_SECRET_ARN,
                sql=insert_sql,
                database=DB_NAME,
                parameters=sql_params,
            )

        logger.info(
            "Successfully stored attachment metadata",
            extra={
                "attachment_id": attachment_id,
                "file_path": file_path,
                "consultation_id": consultation_id,
            },
        )

        metrics.add_metric(name="AttachmentStored", unit="Count", value=1)

        return {
            "status": "success",
            "attachment_id": attachment_id,
            "consultation_id": consultation_id,
        }

    except Exception as e:
        error_msg = str(e)
        logger.exception(
            "Failed to store audio attachment",
            extra={"error": error_msg, "key": key},
        )

        metrics.add_metric(name="DatabaseError", unit="Count", value=1)

        return {"status": "error", "error": error_msg, "key": key}


@tracer.capture_method
def get_json_from_s3(bucket_name: str, key: str) -> str:
    """Get JSON content from S3 object.

    Args:
        bucket_name: S3 bucket name.
        key: S3 object key.

    Returns:
        Content of the JSON file as a string.

    Raises:
        Exception: If S3 object retrieval fails.
    """
    response = s3_client.get_object(Bucket=bucket_name, Key=key)
    return response["Body"].read().decode("utf-8")


@tracer.capture_method
def group_by_speaker(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Group transcript words by speaker.

    Processes raw transcript data and groups words by speaker ID,
    creating a chronological sequence of conversation segments.

    Args:
        data: Raw transcript data containing word-level information.

    Returns:
        List of segments with speaker ID, text content, and timestamp.
    """
    grouped_messages = []

    alternatives = data.get("channel", {}).get("alternatives", [])
    if not alternatives:
        return grouped_messages

    current_speaker = None
    current_words = []
    current_start_time = None

    for alt in alternatives:
        words = alt.get("words", [])
        for w in words:
            speaker = w.get("speaker")
            start_time = w.get("start")
            punctuated_word = w.get("punctuated_word", "")

            if current_speaker is None:
                current_speaker = speaker
                current_words = [punctuated_word]
                current_start_time = start_time
            elif speaker == current_speaker:
                current_words.append(punctuated_word)
            else:
                grouped_messages.append(
                    {
                        "text": " ".join(current_words),
                        "speaker": f"Speaker {current_speaker}",
                        "time": current_start_time,
                    },
                )

                current_speaker = speaker
                current_words = [punctuated_word]
                current_start_time = start_time

    if current_words:
        grouped_messages.append(
            {
                "text": " ".join(current_words),
                "speaker": f"Speaker {current_speaker}",
                "time": current_start_time,
            },
        )

    return grouped_messages
