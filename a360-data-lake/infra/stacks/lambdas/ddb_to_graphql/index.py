from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.types import TypeDeserializer
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.httpsession import URLLib3Session

REGION: str = os.environ["REGION"]
GRAPHQL_ENDPOINT: str = os.environ["GRAPHQL_ENDPOINT"]
SERVICE: str = "appsync"
TABLE_NAME: str = str(os.environ["TABLE_NAME"])

_session = boto3.Session()
_http = URLLib3Session()
_deserializer = TypeDeserializer()

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="A360/DdbToGraphql", service=SERVICE)


def _decimal_default(obj: Any) -> Any:
    """JSON serializer for DynamoDB Decimals.

    Args:
        obj: Object to serialize.

    Returns:
        float: Converted Decimal to float.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    msg = f"Type {type(obj)} not serializable"
    raise TypeError(msg)


MUTATION = """
mutation AddSeg($input: AddTranscriptSegmentInput!) {
  addTranscriptSegment(input: $input) {
    consultationId
    segmentIndex
    timestamp
    speaker {
      role
      name
      voiceProfileId
    }
    finalizedTranscript
    startTime
  }
}
"""

UPDATE_MUTATION = """
mutation UpdateSeg($input: UpdateTranscriptSegmentInput!) {
  updateTranscriptSegment(input: $input) {
    consultationId
    segmentIndex
    finalizedTranscript
    enrichments {
      sentimentAnalysis {
        text
        sentiment
        confidence
      }
      entityExtraction {
        entities {
          text
          category
          confidence
          position {
            start
            end
          }
        }
      }
      intentsAnalysis {
        intents {
          intent
          text
          confidence
        }
      }
    }
  }
}
"""

END_SESSION_MUTATION = """
mutation EndSession($input: EndTranscriptSessionInput!) {
  endTranscriptSession(input: $input) {
    consultationId
    processedAt
    transcriptAttachmentId
    totalSegments
  }
}
"""


def _to_end_session_input(ddb: dict[str, Any]) -> dict[str, Any]:
    """Map end record to EndTranscriptSessionInput.

    Args:
        ddb: Deserialized DynamoDB image map.

    Returns:
        Dict[str, Any]: Payload for the GraphQL EndTranscriptSessionInput, containing:
            - consultationId (str)
            - processedAt (ISO 8601 timestamp)
            - transcriptAttachmentId (str)
            - totalSegments (int)
    """
    cid = ddb.get("consultation_id", "")
    segment_count = int(ddb.get("segment_id", "end#0").split("#")[1])

    raw_processed_at = ddb.get("ProcessedAt", 0)
    if isinstance(raw_processed_at, Decimal):
        processed_at_timestamp = float(raw_processed_at)
    else:
        processed_at_timestamp = float(raw_processed_at)

    return {
        "consultationId": cid,
        "processedAt": datetime.fromtimestamp(processed_at_timestamp, tz=UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "transcriptAttachmentId": ddb.get("transcriptAttachmentId", ""),
        "totalSegments": segment_count,
    }


def _sign_and_post(body: dict[str, Any]) -> dict[str, Any]:
    """Sign and POST a GraphQL request.

    Args:
        body: GraphQL JSON payload with `query` and `variables`.

    Returns:
        Parsed JSON response.

    Raises:
        RuntimeError: If HTTP status is non-2xx or GraphQL returns errors.
    """
    frozen = _session.get_credentials().get_frozen_credentials()
    payload = json.dumps(body, default=_decimal_default)
    req = AWSRequest(
        method="POST",
        url=GRAPHQL_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    SigV4Auth(frozen, SERVICE, REGION).add_auth(req)
    resp = _http.send(req.prepare())
    if resp.status >= 300:
        response_text = resp.data.decode("utf-8")
        msg = f"HTTP {resp.status}: {response_text}"
        raise RuntimeError(msg)

    response_text = resp.data.decode("utf-8")
    data = json.loads(response_text)
    if "errors" in data:
        msg = f"GraphQL errors: {json.dumps(data['errors'])}"
        raise RuntimeError(msg)
    return data


def _retry_post(
    body: dict[str, Any],
    attempts: int = 3,
    backoff: float = 0.2,
) -> dict[str, Any]:
    """Retry wrapper for `_sign_and_post`.

    Args:
        body: GraphQL request body.
        attempts: Maximum attempts.
        backoff: Initial backoff in seconds (exponential).

    Returns:
        GraphQL response dict.

    Raises:
        RuntimeError: Final failure after all retries.
    """
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return _sign_and_post(body)
        except Exception as exc:
            last_exc = exc
            sleep = backoff * (2**i)
            logger.warning(
                "GraphQL post failed, retrying",
                extra={"error": str(exc), "attempt": i + 1, "sleep": sleep},
            )
            time.sleep(sleep)
    msg = f"Failed after {attempts} attempts"
    raise RuntimeError(msg) from last_exc


def extract_segment_number(segment_id: str) -> int:
    """Extract numeric index from SegmentId like 'segment-000000' -> 0
    Args:
        segment_id: Segment ID string, e.g. 'segment-000000'.

    Returns:
        int: Extracted segment index, or 0 if parsing fails.
    """
    try:
        if segment_id.startswith("segment-"):
            return int(segment_id.split("-")[1])
        return 0
    except (ValueError, IndexError):
        return 0


def _deserialize_ddb_image(new_image: dict[str, Any]) -> dict[str, Any]:
    """Convert DynamoDB Stream `NewImage` map into a native dict.

    Args:
        new_image: Value of `record['dynamodb']['NewImage']`.

    Returns:
        Dict with Python-native types.
    """
    return {k: _deserializer.deserialize(v) for k, v in new_image.items()}


def _to_add_input(ddb: dict[str, Any]) -> dict[str, Any]:
    """Map a DynamoDB image to AddTranscriptSegmentInput.

    Args:
        ddb: Deserialized DynamoDB image map.

    Returns:
        Dict[str, Any]: Payload for the GraphQL AddTranscriptSegmentInput, containing:
            - consultationId (str)
            - segmentIndex (int)
            - timestamp (str)
            - speaker (dict with role, name, voiceProfileId)
            - finalizedTranscript (str)
            - startTime (float)
    """
    cid = ddb.get("consultation_id", "")
    cid = cid.removeprefix("trs#")
    sp = ddb.get("speaker", {}) or {}
    timestamp = datetime.now(UTC).isoformat()

    return {
        "consultationId": cid,
        "segmentIndex": extract_segment_number(
            ddb.get("segment_id", ddb.get("SegmentId", "segment-000000")),
        ),
        "timestamp": timestamp,
        "speaker": {
            "role": sp.get("role", "UNKNOWN"),
            "name": sp.get("name", "Speaker 0"),
            "voiceProfileId": sp.get("voiceProfileId", "xxx123"),
        },
        "finalizedTranscript": ddb.get("FinalizedTranscript", ""),
        "startTime": float(ddb.get("StartTime", 0.0)),
    }


def _to_update_input(ddb: dict[str, Any]) -> dict[str, Any]:
    """Map a DynamoDB image to UpdateTranscriptSegmentInput with enrichments.

    Args:
        ddb: Deserialized DynamoDB image map, including the 'Analysis' field.

    Returns:
        Dict[str, Any]: Payload for the GraphQL UpdateTranscriptSegmentInput, containing:
            - consultationId (str)
            - segmentIndex (int)
            - finalizedTranscript (str)
            - enrichments (dict of SentimentAnalysisInput, IntentsAnalysisInput, EntityExtractionInput)
    """
    cid = ddb.get("consultation_id", "")
    cid = cid.removeprefix("trs#")

    seg_index_raw = ddb.get("segment_index")
    if seg_index_raw is None:
        seg_index_raw = extract_segment_number(
            ddb.get("segment_id", ddb.get("SegmentId", "segment-000000")),
        )
    inp: dict[str, Any] = {
        "consultationId": cid,
        "segmentIndex": int(seg_index_raw),
        "finalizedTranscript": ddb.get("FinalizedTranscript", ""),
    }

    if analysis := ddb.get("Analysis"):
        enrichments: dict[str, Any] = {}

        # SentimentAnalysisInput
        if segs := analysis.get("sentiments", {}).get("segments", []):
            mapped_sentiments = [
                {
                    "text": seg.get("text", ""),
                    "sentiment": seg.get("sentiment", "").upper(),
                    "confidence": float(seg.get("sentiment_score", 0.0)),
                }
                for seg in segs
            ]
            enrichments["sentimentAnalysis"] = mapped_sentiments

        # IntentsAnalysisInput
        segments = analysis.get("intents", {}).get("segments", [])
        if segments:
            mapped_intents = []
            for seg in segments:
                segment_text = seg.get("text", "")
                for intent_obj in seg.get("intents", []):
                    mapped_intents.append(
                        {
                            "text": segment_text,
                            "intent": intent_obj.get("intent", ""),
                            "confidence": float(
                                intent_obj.get("confidence_score", 0.0),
                            ),
                        },
                    )

            if mapped_intents:
                enrichments["intentsAnalysis"] = {
                    "intents": mapped_intents,
                }

        # EntityExtractionInput
        entities = analysis.get("entities", [])
        if entities:
            mapped_entities = [
                {
                    "text": ent.get("value", ""),
                    "category": ent.get("label", ""),
                    "confidence": float(ent.get("confidence", 0.0)),
                    "position": {
                        "start": int(ent.get("start_word", 0)),
                        "end": int(ent.get("end_word", 0)),
                    },
                }
                for ent in entities
            ]
            enrichments["entityExtraction"] = {"entities": mapped_entities}

        inp["enrichments"] = enrichments

    return inp


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Lambda entry point.

    Processes DynamoDB Stream records (INSERT/MODIFY) and posts a GraphQL mutation
    for each segment to trigger AppSync subscriptions.

    Args:
        event: Lambda event containing DynamoDB stream batch.
        context: Lambda runtime context.

    Returns:
        Dictionary with publish statistics.

    Raises:
        RuntimeError: If GraphQL posting repeatedly fails.
    """
    published = 0
    skipped = 0

    for rec in event.get("Records", []):
        ev = rec.get("eventName")
        if ev not in {"INSERT", "MODIFY"}:
            skipped += 1
            continue

        new_image = rec.get("dynamodb", {}).get("NewImage")
        if not new_image:
            skipped += 1
            continue

        deserialized = _deserialize_ddb_image(new_image)

        # avoid re-publishing same record
        if deserialized.get("published_by_lambda"):
            logger.info(
                "Skipping already published segment",
                extra={
                    "consultationId": deserialized.get("consultation_id", ""),
                    "segmentId": deserialized.get("segment_id", ""),
                },
            )
            skipped += 1
            continue

        segment_id = deserialized.get("segment_id", "")
        if segment_id.startswith("end#"):
            body = {
                "query": END_SESSION_MUTATION,
                "variables": {"input": _to_end_session_input(deserialized)},
            }
            _retry_post(body)
            published += 1
            continue

        if ev == "INSERT":
            body = {
                "query": MUTATION,
                "variables": {"input": _to_add_input(deserialized)},
            }
        else:
            body = {
                "query": UPDATE_MUTATION,
                "variables": {"input": _to_update_input(deserialized)},
            }

        # Extract operation metadata for logging (avoid logging PHI)
        operation = "unknown"
        consultation_id = None
        segment_index = None
        segment_count = None

        if segment_id.startswith("end#"):
            operation = "end_session"
        elif ev == "INSERT":
            operation = "add"
        else:
            operation = "update"

        # Extract consultation ID from deserialized data
        consultation_id = deserialized.get("consultation_id", "")
        if consultation_id.startswith("trs#"):
            consultation_id = consultation_id.removeprefix("trs#")

        # Extract segment info from segment_id
        if segment_id and "-" in segment_id:
            try:
                parts = segment_id.split("-")
                if len(parts) >= 2:
                    segment_index = int(parts[1]) if parts[1].isdigit() else None
                    segment_count = (
                        int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
                    )
            except (ValueError, IndexError):
                pass

        logger.debug(
            "GraphQL operation metadata",
            extra={
                "operation": operation,
                "consultationId": consultation_id or None,
                "segment_index": segment_index,
                "segment_count": segment_count,
            },
        )

        _retry_post(body)
        published += 1
        metrics.add_metric("SegmentsPublished", unit=MetricUnit.Count, value=1)

        # mark as published to avoid races
        try:
            table_name = TABLE_NAME
            if table_name:
                dynamo = _session.resource("dynamodb").Table(table_name)
                dynamo.update_item(
                    Key={
                        "consultation_id": deserialized["consultation_id"],
                        "segment_id": deserialized["segment_id"],
                    },
                    UpdateExpression="SET published_by_lambda = :t",
                    ExpressionAttributeValues={":t": True},
                )
        except Exception as e:
            logger.debug("Failed to mark record as published", extra={"error": str(e)})

    return {"published": published, "skipped": skipped}
