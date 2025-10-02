from __future__ import annotations

import base64
import json
import os
import struct
import subprocess
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, Final

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

SERVICE = "audio_transformation"
tracer = Tracer(service=SERVICE)
logger = Logger(service=SERVICE)
metrics = Metrics(namespace="TranscriptionService", service=SERVICE)

RAW_BUCKET: Final[str] = os.environ["RAW_BUCKET_NAME"]
OUT_BUCKET: Final[str] = os.environ["MP3_BUCKET_NAME"]
TABLE_NAME: Final[str] = os.environ["AWS_DYNAMODB_SESSION_TABLE"]

DB_CLUSTER_ARN: Final[str] = os.environ["DB_CLUSTER_ARN"]
DB_SECRET_ARN: Final[str] = os.environ["DB_SECRET_ARN"]
DB_NAME: Final[str] = os.environ["DB_NAME"]

ATTACHMENT_TYPE_AUDIO: Final[int] = 4

PCM_SR, PCM_CH, PCM_BPS = 48_000, 1, 16

s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb").Table(TABLE_NAME)
rds = boto3.client("rds-data")

# TTL values for DynamoDB items
LOCK_TTL = 300
# seconds - how long per-consultation aggregation lock lives
CHUNK_TTL = 86_400


def _lock(cid: str) -> bool:
    """Attempt to acquire a short-lived lock item
    (consultation_id = cid, metadata = aggregation#lock).

    Args:
        cid (str): Consultation ID for which the lock should be acquired.

    Returns:
        bool: True if the lock was acquired, False otherwise.
    """
    try:
        ddb.put_item(
            Item={
                "consultation_id": cid,
                "metadata": "aggregation#lock",
                "ttl": int(time.time()) + LOCK_TTL,
            },
            ConditionExpression="attribute_not_exists(consultation_id)",
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def _unlock(cid: str) -> None:
    """Release the per-consultation aggregation lock. Any errors are suppressed to
    ensure graceful completion.

    Args:
        cid (str): Consultation ID for which the lock should be released.
    """
    with suppress(ClientError):
        ddb.delete_item(
            Key={"consultation_id": cid, "metadata": "aggregation#lock"},
        )


def _mark_chunk(cid: str, etag: str) -> bool:
    """Mark an S3 object (identified by its ETag) as processed. Acts as a
    deduplication guard against at-least-once S3 notifications.

    Args:
        cid (str): Consultation ID.
        etag (str): S3 object's ETag.

    Returns:
        bool: True if this chunk was NOT seen before; False if duplicate.
    """
    try:
        ddb.put_item(
            Item={
                "consultation_id": cid,
                "metadata": f"chunk#{etag}",
                "ttl": int(time.time()) + CHUNK_TTL,
            },
            ConditionExpression="attribute_not_exists(consultation_id)",
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def build_wav_header(num_frames: int) -> bytes:
    """Build a WAV header for PCM audio data.

    Args:
        num_frames (int): Number of audio frames in the PCM data.

    Returns:
        bytes: The WAV header as a byte string.
    """
    byte_rate = PCM_SR * PCM_CH * PCM_BPS // 8
    block_align = PCM_CH * PCM_BPS // 8
    data_size = num_frames * block_align
    riff_size = 36 + data_size
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        PCM_CH,
        PCM_SR,
        byte_rate,
        block_align,
        PCM_BPS,
        b"data",
        data_size,
    )


def convert_wav_to_mp3(pcm: bytes) -> bytes:
    """Convert raw PCM audio data to MP3 format using ffmpeg.
    This function uses ffmpeg to encode the PCM data into MP3 format.

    Args:
        pcm (bytes): Raw PCM audio data.

    Returns:
        bytes: The MP3 audio data.

    Raises:
        subprocess.CalledProcessError: If ffmpeg fails to convert the audio.
    """
    # Security: using hardcoded ffmpeg path with validated arguments
    return subprocess.check_output(  # noqa: S603
        [
            "/opt/bin/ffmpeg",
            "-f",
            "s16le",
            "-ar",
            str(PCM_SR),
            "-ac",
            str(PCM_CH),
            "-i",
            "pipe:0",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "4",
            "-f",
            "mp3",
            "pipe:1",
        ],
        input=pcm,
        stderr=subprocess.DEVNULL,
        timeout=120,
    )


def list_s3(prefix: str, bucket: str) -> list[str]:
    """List all S3 object keys under a given prefix in a bucket.

    Args:
        prefix (str): The S3 prefix to search under.
        bucket (str): The name of the S3 bucket.

    Returns:
        List[str]: A list of S3 object keys under the specified prefix.

    Raises:
        botocore.exceptions.ClientError: If the S3 operation fails.
    """
    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys += [o["Key"] for o in page.get("Contents", [])]
    return keys


def load_json(bucket: str, key: str) -> Any:
    """Load a JSON object from S3.

    Args:
        bucket (str): The name of the S3 bucket.
        key (str): The S3 object key to load.

    """
    try:
        return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchKey":
            return None
        raise


def get_final_transcript_key(cid: str, bucket: str) -> str:
    """Return the full S3 key of the transcript that ends with *final.json*
    for the given consultation, or a placeholder path if none exists yet.

    Args:
        cid (str): Consultation ID to search for.
        bucket (str): S3 bucket name where transcripts are stored.

    Returns:
        str: The S3 key of the final transcript JSON file.
    """
    prefix = f"{cid}/transcript/"
    keys = list_s3(prefix, bucket)
    finals = sorted(k for k in keys if k.endswith("final.json"))
    if finals:
        return finals[-1]
    date_str = datetime.now(UTC).strftime("%Y-%m-%d-%H-%M-%S")
    return f"{prefix}{date_str}-final.json"


def store_attachment_in_db(meta: dict[str, Any], mp3_key: str, size: int) -> None:
    """Insert or update the **single** audio-attachment row for a consultation.

    The partial UNIQUE index on ``attachments`` (`consultation_id` where
    ``attachment_type = 4``) guarantees only one audio row per consultation.
    This function therefore performs a single atomic UPSERT.

    Args:
        meta: Metadata attributes for the attachment.
        mp3_key: S3 key of the MP3 file.
        size: Size of the MP3 file in bytes.

    Returns:
        None

    Raises:
        botocore.exceptions.ClientError: Propagated if the Aurora Data API call fails.
    """
    file_ext: Final[str] = "mp3"
    consultation_id: str = meta["metadataAttributes"]["consultationId"]

    upsert_sql = """
        INSERT INTO attachments (
            id,
            attachment_type,
            file_path,
            file_size,
            file_extension,
            file_metadata,
            created_at,
            updated_at,
            consultation_id
        )
        VALUES (
            :id,
            :atype,
            :fpath,
            :fsize,
            :fext,
            :fmeta::jsonb,
            NOW(),
            NOW(),
            :cid
        )
        ON CONFLICT (consultation_id)
        WHERE attachment_type = 4
        DO UPDATE SET
            file_path     = EXCLUDED.file_path,
            file_size     = EXCLUDED.file_size,
            file_metadata = EXCLUDED.file_metadata,
            updated_at    = NOW();
    """

    params = [
        {"name": "id", "value": {"stringValue": str(uuid.uuid4())}},
        {"name": "atype", "value": {"longValue": ATTACHMENT_TYPE_AUDIO}},
        {"name": "fpath", "value": {"stringValue": mp3_key}},
        {"name": "fsize", "value": {"longValue": size}},
        {"name": "fext", "value": {"stringValue": file_ext}},
        {"name": "fmeta", "value": {"stringValue": json.dumps(meta)}},
        {"name": "cid", "value": {"stringValue": consultation_id}},
    ]

    try:
        rds.execute_statement(
            resourceArn=DB_CLUSTER_ARN,
            secretArn=DB_SECRET_ARN,
            sql=upsert_sql,
            database=DB_NAME,
            parameters=params,
        )
        logger.info(
            "Audio attachment upserted",
            extra={"consultation_id": consultation_id, "bytes": size},
        )
    except ClientError:
        logger.exception("Failed to upsert attachment for %s", consultation_id)
        raise


def aggregate_and_store(cid: str):
    """Aggregate audio data for a given consultation ID (cid) from S3,
    convert it to WAV and MP3 formats, and store the results in S3
    and DynamoDB.

    Args:
        cid (str): Consultation ID to aggregate audio for.

    Raises:
        botocore.exceptions.ClientError: If S3 or DynamoDB operations fail.

    """
    logger.info("Aggregate audio for %s", cid)

    json_keys = list_s3(f"{cid}/", RAW_BUCKET)
    if not json_keys:
        logger.warning("No ND-JSON found for %s", cid)
        return

    pcm = bytearray()
    first_meta: dict[str, Any] = {}
    for key in sorted(json_keys):
        if not key.endswith(".json"):
            continue
        body = s3.get_object(Bucket=RAW_BUCKET, Key=key)["Body"].read()
        for line in body.splitlines():
            if not line:
                continue
            rec = json.loads(line)
            audio_b64 = rec.get("audio_raw")
            if audio_b64:
                pcm += base64.b64decode(audio_b64)
            if not first_meta and rec.get("meta"):
                first_meta = rec["meta"]

    if not pcm:
        logger.warning("Empty audio for %s", cid)
        return

    date_str = datetime.now(UTC).strftime("%Y-%m-%d-%H-%M-%S")
    base_key = f"{cid}/audio/{date_str}-consultation-final"
    wav_key = f"{base_key}.wav"
    mp3_key = f"{base_key}.mp3"
    meta_key = f"{cid}/metadata/{date_str}-audio-metadata.json"

    wav_bytes = build_wav_header(len(pcm) // 2) + pcm
    mp3_ok = False
    try:
        mp3_bytes = convert_wav_to_mp3(pcm)
        mp3_ok = True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        logger.exception("FFmpeg failed or timed out, skipping MP3")
        metrics.add_metric(name="FFmpegErrors", unit="Count", value=1)
        mp3_bytes = b""

    s3.put_object(
        Bucket=OUT_BUCKET,
        Key=wav_key,
        Body=wav_bytes,
        ContentType="audio/wav",
    )
    if mp3_ok:
        s3.put_object(
            Bucket=OUT_BUCKET,
            Key=mp3_key,
            Body=mp3_bytes,
            ContentType="audio/mpeg",
        )

    audio_prefix = f"{cid}/audio/"
    old_keys = list_s3(audio_prefix, OUT_BUCKET)

    for k in old_keys:
        if (
            k.endswith(("-consultation-final.wav", "-consultation-final.mp3"))
        ) and k not in (wav_key, mp3_key):
            try:
                s3.delete_object(Bucket=OUT_BUCKET, Key=k)
                logger.info("Deleted outdated artefact %s", k)
            except ClientError as exc:
                logger.warning("Unable to delete %s: %s", k, exc)

    meta_out = {
        "metadataAttributes": {
            "organizationId": first_meta.get("tenantId"),
            "expertId": first_meta.get("expertId"),
            "patientId": first_meta.get("patientId"),
            "consultationId": cid,
            "consultationDate": first_meta.get("consultationDate"),
            "startedAt": first_meta.get("startedAt"),
            "finishedAt": date_str,
            "sampleRate": PCM_SR,
            "audioFormat": "mp3" if mp3_ok else "wav",
            "byte_size": (len(mp3_bytes) if mp3_ok else len(wav_bytes)),
        },
    }
    s3.put_object(
        Bucket=OUT_BUCKET,
        Key=meta_key,
        Body=json.dumps(meta_out).encode(),
        ContentType="application/json",
    )

    if mp3_ok:
        ddb.update_item(
            Key={"consultation_id": cid, "metadata": "audio#final"},
            UpdateExpression=(
                "SET wav_key=:w, mp3_key=:m, "
                "byte_size_mp3=:bmp3, byte_size_wav=:bwav, "
                "#ts=:t, expiry_time=:e"
            ),
            ExpressionAttributeNames={"#ts": "timestamp"},
            ExpressionAttributeValues={
                ":w": wav_key,
                ":m": mp3_key,
                ":bmp3": len(mp3_bytes),
                ":bwav": len(wav_bytes),
                ":t": int(time.time()),
                ":e": int(time.time()) + 86_400,
            },
        )
    else:
        ddb.update_item(
            Key={"consultation_id": cid, "metadata": "audio#final"},
            UpdateExpression=(
                "SET wav_key=:w, byte_size_wav=:bwav, #ts=:t, expiry_time=:e"
            ),
            ExpressionAttributeNames={"#ts": "timestamp"},
            ExpressionAttributeValues={
                ":w": wav_key,
                ":bwav": len(wav_bytes),
                ":t": int(time.time()),
                ":e": int(time.time()) + 86_400,
            },
        )

    if mp3_ok:
        store_attachment_in_db(meta_out, mp3_key, len(mp3_bytes))

    logger.info("Aggregation complete for %s", cid)
    metrics.add_metric(name="FilesProcessed", unit="Count", value=1)


@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], _: LambdaContext) -> dict[str, Any]:
    """Process S3 ObjectCreated events emitted when the Firehose delivery stream
    writes a raw audio chunk. Each event triggers a full rebuild of the
    cumulative WAV/MP3 for the consultation.

    Concurrency & idempotency:
        * `_mark_chunk()` filters duplicate S3 events (same ETag).
        * `_lock()` serialises aggregation so only one encoder runs per
          consultation at a time.
    """
    processed = 0
    for rec in event.get("Records", []):
        if rec.get("eventSource") != "aws:s3":
            continue

        key = rec["s3"]["object"]["key"]
        cid = key.split("/", 1)[0]
        etag = rec["s3"]["object"]["eTag"]

        if not _mark_chunk(cid, etag):
            logger.debug("Duplicate chunk %s for %s - skipped", etag, cid)
            continue

        if not _lock(cid):
            logger.debug("Aggregation lock busy for %s - skipping", cid)
            continue

        try:
            aggregate_and_store(cid)
            processed += 1
        finally:
            _unlock(cid)

    return {"statusCode": 200, "processed": processed}
