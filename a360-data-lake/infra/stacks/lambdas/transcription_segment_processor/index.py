"""segment_processor.py
────────────────────
Triggered by Kinesis records with event_type == 'consultation_end'.

Aggregates every segment row for that consultation from DynamoDB,
retains the detailed fields, and writes a compressed JSON artifact
to the “transcriptions” S3 bucket.
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Final

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Attr, Key

logger = Logger(service="transcript-aggregator")
tracer = Tracer(service="transcript-aggregator")
metrics = Metrics(namespace="TranscriptionService", service="transcript-aggregator")

TRANSCRIPT_TABLE: Final[str] = os.environ["TRANSCRIPT_TABLE"]
TRANSCRIPTION_BUCKET: Final[str] = os.environ["TRANSCRIPTION_BUCKET"]
BEDROCK_MODEL_ID: Final[str] = os.environ["BEDROCK_MODEL_ID"]
DB_CLUSTER_ARN: Final[str] = os.environ["DB_CLUSTER_ARN"]
DB_SECRET_ARN: Final[str] = os.environ["DB_SECRET_ARN"]
DB_NAME: Final[str] = os.environ["DB_NAME"]

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TRANSCRIPT_TABLE)
s3 = boto3.client("s3")
rds = boto3.client("rds-data")


def _event_meta(
    name: str,
    consultation_id: str,
    event_id: str | None,
) -> dict[str, Any]:
    """Build a metadata payload for JSON artifacts stored in attachments.file_metadata.

    Args:
      name: Human-readable name (e.g., "Recognized Intents").
      consultation_id: Consultation UUID (no "trs#" prefix).
      event_id: Provider event identifier (Kinesis eventID if available).

    Returns:
      dict: Metadata dictionary to persist alongside the artifact.
    """
    return {
        "name": name,
        "source": "kinesis_event",
        "event_id": event_id,
        "eventTimestamp": datetime.now(UTC).isoformat(),
        "consultation_id": consultation_id,
    }


@tracer.capture_method
def _unwrap_ddb(val):
    """Convert the DynamoDB 'typed' JSON (M/L/N/S) into plain Python objects.
    Works recursively and preserves Decimals as floats.

    Args:
        val: The DynamoDB value to unwrap.

    Returns:
        The unwrapped value as a plain Python object.
    """
    if isinstance(val, dict) and len(val) == 1:
        t, v = next(iter(val.items()))
        if t == "N":
            return float(v)
        if t == "S":
            return v
        if t == "M":
            return {k: _unwrap_ddb(x) for k, x in v.items()}
        if t == "L":
            return [_unwrap_ddb(x) for x in v]
    if isinstance(val, dict):
        return {k: _unwrap_ddb(x) for k, x in val.items()}
    if isinstance(val, list):
        return [_unwrap_ddb(x) for x in val]
    return val


@tracer.capture_method
def get_dg_artefacts(consultation_id: str) -> dict[str, Any]:
    """Aggregate Deepgram artefacts for one consultation **and normalise**
    them to the flat JSON you want on S3.

    Args:
        consultation_id: The ID of the consultation to query.

    Returns:
        A dictionary containing the aggregated artefacts:
        - intents: List of intent segments
        - sentiments: List of sentiment segments and average sentiment
        - entities: List of entities (currently empty)
    """
    pk = f"trs#{consultation_id}"
    out: dict[str, Any] = {
        "intents": {"segments": []},
        "sentiments": {"segments": [], "average": {}},
        "entities": [],
    }

    # Query with pagination to get all items
    items = []
    kwargs = {
        "KeyConditionExpression": Key("consultation_id").eq(pk),
        "ProjectionExpression": "segment_id, analysis",
        "FilterExpression": Attr("analysis").exists(),
    }

    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))

        last_evaluated_key = resp.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
        kwargs["ExclusiveStartKey"] = last_evaluated_key

    for item in items:
        segment_id = item.get("segment_id")
        plain_data = _unwrap_ddb(item["analysis"])

        for seg in plain_data.get("intents", {}).get("segments", []):
            intents_list = seg.get("intents", [])
            if not intents_list:
                continue
            best_intent = max(intents_list, key=lambda i: i.get("confidence_score", 0))
            out["intents"]["segments"].append(
                {
                    "start_word": seg.get("start_word"),
                    "end_word": seg.get("end_word"),
                    "text": seg.get("text"),
                    "intent": best_intent.get("intent"),
                    "confidence_score": best_intent.get("confidence_score"),
                },
            )

        sentiments = plain_data.get("sentiments", {}).get("segments", [])
        if sentiments:
            out["sentiments"]["segments"].extend(sentiments)
            out["sentiments"]["average"] = plain_data["sentiments"].get("average", {})

        for entity in plain_data.get("entities", []):
            entity["segment"] = segment_id
            out["entities"].append(entity)

    return out


def _decimal_to_float(o):
    """Convert Decimal to float for JSON serialization.

    Args:
        o: The object to convert.

    Returns:
        float: The converted value if o is a Decimal.
    """
    if isinstance(o, Decimal):
        return float(o)
    msg = f"Type {o.__class__.__name__} not serializable"
    raise TypeError(msg)


@tracer.capture_method
def query_segments(consultation_id: str) -> list[dict[str, Any]]:
    """Return all segment items (ordered) for one consultation.

    Args:
        consultation_id: The ID of the consultation to query.

    Returns:
        A list of segment items from DynamoDB for the specified consultation.

    Raises:
        ClientError: If the query fails, an error is logged.
        ValueError: If the consultation_id is empty.
    """
    pk = f"trs#{consultation_id}"

    # Query with pagination to get all items
    items = []
    kwargs = {
        "KeyConditionExpression": Key("consultation_id").eq(pk)
        & Key("segment_id").begins_with("segment#"),
        "ScanIndexForward": True,
    }

    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))

        last_evaluated_key = resp.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
        kwargs["ExclusiveStartKey"] = last_evaluated_key

    return items


def _alt(
    transcript: str,
    speaker: int | str,
    words: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an alternative block.
    • Always include transcript & speaker
    • Include words only when a non-empty list is supplied
    Args:
        transcript: The transcript text.
        speaker: The speaker ID (int or str).
        words: Optional list of word objects, defaults to None.

    Returns:
        A dictionary representing the alternative block with transcript, speaker, and optionally words.
    """
    alt = {
        "transcript": transcript,
        "speaker": speaker,
    }
    if words:
        alt["words"] = words
    return alt


@tracer.capture_method
def build_documents(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return three dicts: final / corrected / original.

    Args:
        items: List of segment items from DynamoDB.

    Returns:
        A dictionary containing three keys: "final", "corrected", and "original",
    """
    if not items:
        return {}

    first = items[0]
    raw_pk = first.get("consultation_id", "")

    consultation_id = raw_pk.split("#", 1)[1] if raw_pk.startswith("trs#") else raw_pk

    meta = {
        "name": "Final transcript",
        "start": first.get("StartedAt", datetime.now(UTC).isoformat()),
        "consultation_id": consultation_id,
        "patient_id": first.get("patientId") or first.get("PatientId"),
        "expert_id": first.get("expertId") or first.get("ExpertId"),
    }

    final_alts, corrected_alts, original_alts = [], [], []

    for itm in items:
        speaker = itm.get("Speaker", 0)
        words = itm.get("Words", [])

        final_alts.append(
            _alt(itm.get("FinalizedTranscript", ""), speaker, words),
        )
        corrected_alts.append(
            _alt(itm.get("FinalizedTranscript", ""), speaker),
        )
        original_alts.append(
            _alt(itm.get("DeepgramOriginalTranscript", ""), speaker),
        )

    return {
        "final": {**meta, "channel": {"alternatives": final_alts}},
        "corrected": {**meta, "channel": {"alternatives": corrected_alts}},
        "original": {
            **meta,
            "name": "Original transcript",
            "channel": {"alternatives": original_alts},
        },
    }


@tracer.capture_method
def upload_json(key: str, doc: dict[str, Any]) -> tuple[str, int] | None:
    """Upload the final JSON document to S3, returning the S3 key.
    The key is structured as:
    <consultation_id>/transcript/<timestamp>-final.json.gz
    where timestamp is in the format YYYY-MM-DD-HH-MM-SS.

    Args:
        key: S3 key.
        doc: The final/original/corrected transcript document to upload.

    Returns:
        The S3 key and size of the uploaded document.

    Raises:
        Exception: If the upload fails, an error is logged.

    """
    body = gzip.compress(
        json.dumps(doc, default=_decimal_to_float, ensure_ascii=False).encode("utf-8"),
    )

    try:
        s3.put_object(
            Bucket=TRANSCRIPTION_BUCKET,
            Key=key,
            Body=body,
            ContentType="application/json",
            ContentEncoding="gzip",
            ServerSideEncryption="aws:kms",
            # If you have a dedicated CMK, surface it via env and pass SSEKMSKeyId
        )
        return key, len(body)
    except Exception as e:
        logger.exception("Failed to upload final JSON to S3", exc_info=e)


def store_attachment_in_db(meta: dict[str, Any], transcript_key: str, size: int) -> str:
    """Store attachment metadata in the database.

    Args:
        meta (dict[str, Any]): Metadata attributes for the attachment.
        transcript_key (str): S3 key for the MP3 file.
        size (int): Size of the MP3 file in bytes.

    Returns:
        str: The attachment ID generated for the stored attachment.

    Raises:
        botocore.exceptions.ClientError: If the RDS operation fails.

    """
    try:
        attachment_id = str(uuid.uuid4())
        raw_pk = meta.get("consultation_id", "")
        meta.pop("channel", None)

        if raw_pk.startswith("trs#"):
            consultation_id = raw_pk.split("#", 1)[1]
        else:
            consultation_id = raw_pk

        sql = """
        INSERT INTO attachments (
            id, attachment_type, file_path, file_size, file_extension, file_metadata,
            created_at, updated_at, consultation_id
        )
        VALUES (
            :id, :atype, :fpath, :fsize, :fext, :fmeta::jsonb, NOW(), NOW(),
            :cid
        )"""
        params = [
            {"name": "id", "value": {"stringValue": attachment_id}},
            {"name": "atype", "value": {"longValue": 5}},
            {"name": "fpath", "value": {"stringValue": transcript_key}},
            {"name": "fsize", "value": {"longValue": size}},
            {"name": "fext", "value": {"stringValue": "json"}},
            {
                "name": "fmeta",
                "value": {"stringValue": json.dumps(meta, default=_decimal_to_float)},
            },
            {"name": "cid", "value": {"stringValue": consultation_id}},
        ]
        rds.execute_statement(
            resourceArn=DB_CLUSTER_ARN,
            secretArn=DB_SECRET_ARN,
            sql=sql,
            database=DB_NAME,
            parameters=params,
        )
        logger.info("Attachment row stored", extra={"attachment_id": attachment_id})
        return attachment_id
    except Exception as e:
        logger.exception("Failed to store attachment in database", exc_info=e)
        raise


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    uploads = skipped = 0

    for rec in event["Records"]:
        payload = json.loads(base64.b64decode(rec["kinesis"]["data"]))

        if payload.get("event_type") != "consultation_end":
            skipped += 1
            continue

        cid = payload["consultation_id"]
        sequence = payload["sequence"]
        expected = int(payload["expected_segments"])
        attempts = 0

        try:
            while attempts < 10:
                resp = table.query(
                    KeyConditionExpression=Key("consultation_id").eq(cid),
                    ConsistentRead=True,
                    Select="COUNT",
                )
                if resp["Count"] >= expected:
                    break
                time.sleep(0.1)
                attempts += 1

            END_SK = f"end#{sequence}"
            logger.info(
                "Processing consultation end",
                extra={"consultation_id": cid, "sequence": sequence},
            )

            resp = table.get_item(Key={"consultation_id": cid, "segment_id": END_SK})

            if resp.get("Item"):
                logger.info(f"consultation_end seq={sequence} already done, skip")
                skipped += 1
                continue

            items = query_segments(cid)

            if not items:
                metrics.add_metric("AggregationsSkipped_NoSegments", "Count", 1)
                skipped += 1
                continue

            docs = build_documents(items)
            ts = datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")

            final_key, final_size = upload_json(
                f"{cid}/transcript/{ts}-final.json.gz",
                docs["final"],
            )
            upload_json(f"{cid}/transcript/{ts}-corrected.json.gz", docs["corrected"])
            original_key, original_size = upload_json(
                f"{cid}/transcript/{ts}-original.json.gz",
                docs["original"],
            )
            event_id = rec.get("eventID", str(uuid.uuid4()))

            dg = get_dg_artefacts(cid)

            intents_key = f"{cid}/deepgram_intents/{ts}-intents.json.gz"
            intents_put = upload_json(intents_key, dg["intents"])
            if intents_put:
                _, intents_size = intents_put
                intents_meta = _event_meta(
                    name="Recognized Intents",
                    consultation_id=cid,
                    event_id=event_id,
                )
                store_attachment_in_db(intents_meta, intents_key, intents_size)

            sentiments_key = f"{cid}/deepgram_sentiments/{ts}-sentiments.json.gz"
            sentiments_put = upload_json(sentiments_key, dg["sentiments"])

            if sentiments_put:
                _, sentiments_size = sentiments_put
                sentiments_meta = _event_meta(
                    name="Sentiment Analysis",
                    consultation_id=cid,
                    event_id=event_id,
                )
                store_attachment_in_db(sentiments_meta, sentiments_key, sentiments_size)

            entities_key = f"{cid}/deepgram_entities/{ts}-entities.json.gz"
            entities_put = upload_json(entities_key, dg["entities"])

            if entities_put:
                _, entities_size = entities_put
                entities_meta = _event_meta(
                    name="Extracted Entities",
                    consultation_id=cid,
                    event_id=event_id,
                )
                store_attachment_in_db(entities_meta, entities_key, entities_size)

            uploads += 1
            metrics.add_metric("FinalTranscriptUploaded", "Count", 1)
            tr_att_id = store_attachment_in_db(docs["final"], final_key, final_size)
            docs["original"]["name"] = "Original transcript"
            store_attachment_in_db(docs["original"], original_key, original_size)

            table.put_item(
                Item={
                    "consultation_id": cid,
                    "segment_id": END_SK,
                    "ProcessedAt": int(time.time()),
                    "transcriptAttachmentId": tr_att_id,
                },
                ConditionExpression="attribute_not_exists(consultation_id) AND attribute_not_exists(segment_id)",
            )

        except Exception as exc:
            logger.exception(
                "Error processing consultation end",
                extra={"consultation_id": cid, "sequence": sequence, "error": str(exc)},
            )
            metrics.add_metric("AggregationsFailed", "Count", 1)
            continue

    metrics.add_metric("ConsultationEndsProcessed", "Count", uploads)
    metrics.add_metric("RecordsSkipped", "Count", skipped)

    return {"statusCode": 200, "uploads": uploads, "skipped": skipped}
