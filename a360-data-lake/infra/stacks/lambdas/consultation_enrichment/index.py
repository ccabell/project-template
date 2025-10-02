"""enrichment_lambda.py
────────────────────
Triggered by the **success destination** of the ingest Lambda.

For *each* transcript-segment row that has just been written to the
`TRANSCRIPT_TABLE`, this function:

1. Fetches the row (FinalizedTranscript + current Analysis blob)
2. Runs Comprehend medical entity detection on the transcript text

3. Appends the new entities list to `Analysis.entities`
4. Writes the merged Analysis back to the same DynamoDB item.

The Lambda is intentionally lightweight – no fan-out, no batching – because
the destination stream limits the throughput to the successful PUTs coming
from the ingest function.
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.types import TypeDeserializer

# Optional PowerTools import for testing compatibility
try:
    from aws_lambda_powertools import Logger, Metrics, Tracer
    from aws_lambda_powertools.utilities.typing import LambdaContext

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

    # Mock typing
    LambdaContext = dict

    Logger = MockLogger
    Metrics = MockMetrics
    Tracer = MockTracer

# Initialize PowerTools instances
if POWERTOOLS_AVAILABLE:
    tracer = Tracer(service="consultation-enrichment")
    logger = Logger(service="consultation-enrichment")
    metrics = Metrics(namespace="ConsultationAPI", service="consultation-enrichment")
else:
    tracer = MockTracer()
    logger = MockLogger()
    metrics = MockMetrics()

TRANSCRIPT_SEGMENTS_TABLE = os.environ["TRANSCRIPT_TABLE"]

dynamodb = boto3.resource("dynamodb")
transcript_table = dynamodb.Table(TRANSCRIPT_SEGMENTS_TABLE)
comprehend_med = boto3.client("comprehendmedical")

deser = TypeDeserializer()


def _to_dynamo_safe(val: Any) -> Any:
    """Recursively convert floats → Decimals so that a structure can be
    stored in DynamoDB without type errors.
    """
    if isinstance(val, float):
        return Decimal(str(val))
    if isinstance(val, list):
        return [_to_dynamo_safe(v) for v in val]
    if isinstance(val, dict):
        return {k: _to_dynamo_safe(v) for k, v in val.items()}
    return val


def _unwrap_ddb(attr: dict[str, Any]) -> dict[str, Any]:
    """Convert a DynamoDB-JSON map (i.e. `{'M': {...}}`) to a plain python dict.
    If the attribute is already plain, return it untouched.
    """
    if isinstance(attr, dict) and set(attr) == {"M"}:
        return deser.deserialize(attr)
    return attr


@tracer.capture_method
def apply_entities_detection(text: str) -> None | list[dict[str, Any]] | list[Any]:
    """Ask Comprehend to return entity objects for one sentence/segment.

    Parameters
    ----------
    text : str
        The finalized transcript sentence.

    Returns:
    -------
    List[Dict[str, Any]]
        Zero or more entity dictionaries exactly in the schema required.
    """
    if not text.strip():
        return []

    try:
        resp = comprehend_med.detect_entities_v2(Text=text)
        entities_out: list[dict[str, Any]] = []

        for ent in resp.get("Entities", []):
            begin = ent["BeginOffset"]
            end = ent["EndOffset"]
            entities_out.append(
                {
                    "confidence": float(ent.get("Score", 0.0)),
                    "label": ent.get("Category"),
                    "start_word": begin,
                    "end_word": end,
                    "value": ent.get("Text"),
                },
            )
            for attr in ent.get("Attributes", []):
                begin_attr = attr.get("BeginOffset", begin)
                end_attr = attr.get("EndOffset", end)
                entities_out.append(
                    {
                        "confidence": float(attr.get("Score", 0.0)),
                        "label": attr.get("Type"),
                        "start_word": begin_attr,
                        "end_word": end_attr,
                        "value": attr.get("Text"),
                    },
                )
        return entities_out
    except Exception as exc:
        logger.exception("Comprehend Medical failed", extra={"error": str(exc)})
        return []


@tracer.capture_method
def read_segment_record(cid: str, sid: str) -> tuple[str, dict[str, Any]]:
    """Fetch a single segment row by its keys.

    Returns:
    -------
    (transcript, analysis)
    """
    res = transcript_table.get_item(
        Key={"consultation_id": cid, "segment_id": sid},
        ConsistentRead=True,
    )
    item = res.get("Item", {})
    return item.get("FinalizedTranscript", ""), _unwrap_ddb(item.get("Analysis", {}))


@tracer.capture_method
def write_to_dynamo(cid: str, sid: str, analysis: dict[str, Any]) -> None:
    """Update the row's `Analysis` attribute in place."""
    transcript_table.update_item(
        Key={"consultation_id": cid, "segment_id": sid},
        UpdateExpression="SET #a = :a",
        ExpressionAttributeNames={"#a": "Analysis"},
        ExpressionAttributeValues={":a": _to_dynamo_safe(analysis)},
    )


@tracer.capture_method
def _should_process_record(img: dict[str, Any]) -> bool:
    """Decide whether the DynamoDB stream record needs enrichment.

    Args:
        img: The `NewImage` map from the DynamoDB Streams record. Attributes are
            still in DynamoDB-JSON form (i.e. wrapped with ``"M"``, ``"S"``, etc.).

    Returns:
        bool: True if the record contains an ``Analysis`` attribute but does not
        yet have an ``entities`` list (or it is empty).
    """
    if "Analysis" not in img:
        return False

    analysis = (
        deser.deserialize(img["Analysis"])
        if "M" in img["Analysis"]
        else img["Analysis"]
    )
    entities = analysis.get("entities")
    return not entities


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, int]:
    """DynamoDB-stream triggered enrichment handler.

    The function is invoked by a **DynamoDB Stream** on the
    **dev-transcript-segments** table.
    It looks for rows that already have Deepgram `analysis` data but still lack
    the `entities` list, detects entities with Bedrock, and writes them back to
    the same item.

    Parameters
    ----------
    event : dict
        A standard DynamoDB Streams batch payload
        (``event["Records"]`` is a list of records).
    context : LambdaContext
        Lambda runtime metadata (unused).

    Returns:
    -------
    dict
        A summary counter, e.g. ``{ "processed": 17, "failed": 1 }``.
    """
    processed: int = 0
    failed: int = 0
    cid_full: str | None = None
    sid_full: str | None = None
    for rec in event.get("Records", []):
        try:
            if rec.get("eventName") not in ("INSERT", "MODIFY"):
                continue

            img = rec["dynamodb"].get("NewImage", {})
            if not _should_process_record(img):
                processed += 1
                continue

            cid_full = deser.deserialize(img["consultation_id"])
            sid_full = deser.deserialize(img["segment_id"])

            transcript, analysis = read_segment_record(cid_full, sid_full)
            if not transcript:
                continue

            if analysis.get("entities"):
                processed += 1
                continue

            new_entities = apply_entities_detection(transcript)
            if not new_entities:
                processed += 1
                continue

            merged = analysis.get("entities", []) + new_entities
            analysis["entities"] = merged

            write_to_dynamo(cid_full, sid_full, analysis)
            processed += 1

        except Exception as exc:
            failed += 1
            logger.exception(
                "Enrichment failed",
                extra={
                    "consultation_id": cid_full,
                    "segment_id": sid_full,
                    "error": str(exc),
                },
            )

    metrics.add_metric("EntitiesAdded", unit="Count", value=processed)
    metrics.add_metric("EnrichmentFailed", unit="Count", value=failed)

    return {"processed": processed, "failed": failed}
