"""Embedding processor using Cohere Embed English v3 via Amazon Bedrock.

Processes PHI-redacted transcripts from silver to generate embeddings stored in gold.
"""

import json
import os
from datetime import UTC, datetime
from os import getenv
from typing import Any
from urllib.parse import unquote_plus

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# Optional PowerTools import for testing compatibility
try:
    from aws_lambda_powertools import Logger, Metrics, Tracer
    from aws_lambda_powertools.metrics import MetricUnit

    tracer = Tracer(service="consultation-embedding")
    logger = Logger(service="consultation-embedding")
    metrics = Metrics(
        namespace="ConsultationPipeline",
        service="consultation-embedding",
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

_BOTO_CFG = Config(
    read_timeout=10,
    connect_timeout=3,
    retries={"max_attempts": 3, "mode": "standard"},
)
s3_client = boto3.client("s3", config=_BOTO_CFG)
bedrock_client = boto3.client("bedrock-runtime", config=_BOTO_CFG)
dynamodb_client = boto3.client("dynamodb", config=_BOTO_CFG)
events_client = boto3.client("events", config=_BOTO_CFG)
opensearch_client = None  # lazy init

SILVER_BUCKET = os.environ["SILVER_BUCKET"]
GOLD_BUCKET = os.environ["GOLD_BUCKET"]
CONSULTATION_METADATA_TABLE = os.environ["CONSULTATION_METADATA_TABLE"]
COHERE_EMBED_MODEL_ID = os.environ.get(
    "COHERE_EMBED_MODEL_ID",
    "cohere.embed-english-v3",
)
OPENSEARCH_ENDPOINT = getenv("OPENSEARCH_ENDPOINT")

EMBEDDING_BATCH_SIZE = 96
MAX_INPUT_TOKENS = 512
MIN_TEXT_LEN_CHARS = 10
MAX_SNIPPET_CHARS = 200


@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        consultation_info = extract_consultation_info_from_event(event)
        if not consultation_info:
            logger.warning("Could not extract consultation information from event")
            return {"statusCode": 400, "body": "Invalid event format"}

        result = process_consultation_embeddings(consultation_info)
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
                name="EmbeddingsGenerated",
                unit=MetricUnit.Count,
                value=result.get("embeddings_count", 0),
            )
        else:
            metrics.add_metric(
                name="ConsultationsFailed",
                unit=MetricUnit.Count,
                value=1,
            )
        return {"statusCode": 200, "body": json.dumps({"result": result})}
    except Exception:
        logger.exception("Error processing embedding generation")
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
        consultation_id = detail.get("consultationId") or ""
        tenant_id = detail.get("tenantId") or ""
        silver_key = detail.get("silverKey") or ""
        if not consultation_id or not tenant_id:
            return None
        return {
            "consultation_id": consultation_id,
            "tenant_id": tenant_id,
            "silver_key": silver_key,
            "source": "eventbridge",
        }
    if "consultation_id" in event:
        consultation_id = str(event.get("consultation_id") or "").strip()
        tenant_id = str(event.get("tenant_id") or "").strip()
        silver_key = str(event.get("silver_key") or "")
        if not consultation_id or not tenant_id:
            logger.warning("Missing consultation_id or tenant_id on direct invocation")
            return None
        return {
            "consultation_id": consultation_id,
            "tenant_id": tenant_id,
            "silver_key": silver_key,
            "source": "direct_invocation",
        }
    if "Records" in event:
        for record in event["Records"]:
            if record.get("eventSource") == "aws:s3":
                s3_info = record.get("s3", {})
                bucket_name = s3_info.get("bucket", {}).get("name")
                obj = s3_info.get("object", {})
                # Prefer urlDecodedKey when present; otherwise decode 'key'
                object_key = obj.get("urlDecodedKey") or obj.get("key", "")
                object_key = unquote_plus(object_key)
                if bucket_name == SILVER_BUCKET and object_key.endswith(
                    "phi_redacted_transcript.json",
                ):
                    parts = object_key.split("/")
                    if len(parts) >= 4 and parts[0] == "transcripts":
                        return {
                            "consultation_id": parts[2],
                            "tenant_id": parts[1],
                            "silver_key": object_key,
                            "source": "s3_event",
                        }
    return None


@tracer.capture_method
def process_consultation_embeddings(
    consultation_info: dict[str, str],
) -> dict[str, Any]:
    consultation_id = consultation_info["consultation_id"]
    tenant_id = consultation_info["tenant_id"]
    silver_key = (
        consultation_info.get("silver_key")
        or f"transcripts/{tenant_id}/{consultation_id}/phi_redacted_transcript.json"
    )
    try:
        transcript_data = get_redacted_transcript(silver_key)
        if not transcript_data:
            return {
                "status": "error",
                "error": "Failed to retrieve PHI-redacted transcript",
            }

        segments = extract_conversation_segments(transcript_data)
        if not segments:
            return {
                "status": "skipped",
                "reason": "No conversation segments found for embedding",
            }

        embedding_results = generate_embeddings_for_segments(segments)
        embeddings_document = create_embeddings_document(
            consultation_id,
            tenant_id,
            transcript_data,
            embedding_results,
        )

        gold_key = (
            f"embeddings/{tenant_id}/{consultation_id}/conversation_embeddings.json"
        )
        store_embeddings_document(gold_key, embeddings_document)

        # Optional: index to OpenSearch for semantic search
        if OPENSEARCH_ENDPOINT:
            try:
                index_embeddings_to_opensearch(
                    consultation_id,
                    tenant_id,
                    embedding_results,
                )
            except (ConnectionError, TimeoutError, ValueError) as e:
                logger.warning(f"OpenSearch indexing failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected OpenSearch error: {e}")
        update_consultation_metadata(consultation_id, tenant_id, embedding_results)
        publish_embedding_completion(
            consultation_id,
            tenant_id,
            embedding_results,
            gold_key,
        )

        return {
            "status": "success",
            "consultation_id": consultation_id,
            "tenant_id": tenant_id,
            "gold_key": gold_key,
            "embeddings_count": embedding_results["successful_embeddings"],
            "total_turns": len(segments),
            "embedding_model": COHERE_EMBED_MODEL_ID,
        }
    except Exception as e:
        logger.exception(
            f"Error processing embeddings for consultation {consultation_id}",
        )
        return {"status": "error", "consultation_id": consultation_id, "error": str(e)}


@tracer.capture_method
def get_redacted_transcript(silver_key: str) -> dict[str, Any] | None:
    try:
        response = s3_client.get_object(Bucket=SILVER_BUCKET, Key=silver_key)
        return json.loads(response["Body"].read())
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchKey":
            logger.warning("Redacted transcript not found")
        else:
            logger.exception("Error retrieving redacted transcript")
        return None
    except Exception:
        logger.exception("Unexpected error retrieving redacted transcript")
        return None


@tracer.capture_method
def extract_conversation_segments(
    transcript_data: dict[str, Any],
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    if "conversation" in transcript_data:
        for i, turn in enumerate(transcript_data["conversation"]):
            text = (turn.get("text", "") or "").strip()
            if not text or len(text) < MIN_TEXT_LEN_CHARS:
                continue
            if turn.get("phi_warning"):
                continue
            if len(text) > MAX_INPUT_TOKENS * 4:
                text = text[: MAX_INPUT_TOKENS * 4]
            segments.append(
                {
                    "turn_index": i,
                    "speaker": turn.get("speaker", "Unknown"),
                    "text": text,
                    "start_time": turn.get("start_time"),
                    "end_time": turn.get("end_time"),
                    "duration": turn.get("duration"),
                    "word_count": len(text.split()),
                    "char_count": len(text),
                },
            )
    elif "transcript" in transcript_data:
        full_text = (transcript_data["transcript"] or "").strip()
        if full_text:
            for i, sentence in enumerate(split_text_into_sentences(full_text)):
                if len(sentence.strip()) >= MIN_TEXT_LEN_CHARS:
                    segments.append(
                        {
                            "turn_index": i,
                            "speaker": "Unknown",
                            "text": sentence.strip(),
                            "start_time": None,
                            "end_time": None,
                            "duration": None,
                            "word_count": len(sentence.split()),
                            "char_count": len(sentence),
                        },
                    )
    return segments


import re

SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")


def split_text_into_sentences(text: str) -> list[str]:
    sentences = SENTENCE_SPLIT_RE.split(text)
    return [s.strip() for s in sentences if len(s.strip()) >= MIN_TEXT_LEN_CHARS]


@tracer.capture_method
def generate_embeddings_for_segments(segments: list[dict[str, Any]]) -> dict[str, Any]:
    successful_embeddings = 0
    failed_embeddings = 0
    embedding_results: list[dict[str, Any]] = []
    for batch_start in range(0, len(segments), EMBEDDING_BATCH_SIZE):
        batch_segments = segments[batch_start : batch_start + EMBEDDING_BATCH_SIZE]
        try:
            batch_texts = [seg["text"] for seg in batch_segments]
            batch_embeddings = call_cohere_embed_api(batch_texts)
            for seg, emb in zip(batch_segments, batch_embeddings, strict=False):
                if emb is not None:
                    embedding_results.append(
                        {
                            "turn_index": seg["turn_index"],
                            "speaker": seg["speaker"],
                            "text": (seg["text"][:MAX_SNIPPET_CHARS] + "...")
                            if len(seg["text"]) > MAX_SNIPPET_CHARS
                            else seg["text"],
                            "start_time": seg.get("start_time"),
                            "end_time": seg.get("end_time"),
                            "duration": seg.get("duration"),
                            "word_count": seg["word_count"],
                            "char_count": seg["char_count"],
                            "embedding": emb,
                            "embedding_model": COHERE_EMBED_MODEL_ID,
                            "generated_at": datetime.now(UTC).isoformat(),
                        },
                    )
                    successful_embeddings += 1
                else:
                    failed_embeddings += 1
        except Exception:
            logger.exception(
                "Error processing embedding batch",
                extra={"batch_start": batch_start},
            )
            failed_embeddings += len(batch_segments)
            continue
    return {
        "successful_embeddings": successful_embeddings,
        "failed_embeddings": failed_embeddings,
        "total_segments": len(segments),
        "embeddings": embedding_results,
        "model_id": COHERE_EMBED_MODEL_ID,
    }


@tracer.capture_method
def call_cohere_embed_api(texts: list[str]) -> list[list[float] | None]:
    try:
        request_body = {
            "input_type": "search_document",
            "texts": texts,
            "embedding_types": ["float"],
            "truncate": "END",
        }
        response = bedrock_client.invoke_model(
            modelId=COHERE_EMBED_MODEL_ID,
            body=json.dumps(request_body).encode("utf-8"),
            contentType="application/json",
            accept="application/json",
        )
        body = json.loads(response["body"].read())
        raw = body.get("embeddings", [])

        # Normalize shapes and coerce invalid/empty vectors to None
        normalized: list[list[float] | None] = []
        if isinstance(raw, dict):
            raw = raw.get("float") or raw.get("embeddings") or []
        if isinstance(raw, list):
            for item in raw:
                vec = None
                if isinstance(item, dict):
                    vec = item.get("float")
                elif isinstance(item, list):
                    vec = item
                if (
                    isinstance(vec, list)
                    and len(vec) > 0
                    and all(isinstance(x, (int, float)) for x in vec)
                ):
                    normalized.append([float(x) for x in vec])
                else:
                    normalized.append(None)
        # Pad/trim to input length
        while len(normalized) < len(texts):
            normalized.append(None)
        return normalized[: len(texts)]
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.exception("Bedrock API error", extra={"error_code": error_code})
        return [None] * len(texts)
    except Exception:
        logger.exception("Unexpected error calling Cohere API")
        return [None] * len(texts)


@tracer.capture_method
def create_embeddings_document(
    consultation_id: str,
    tenant_id: str,
    transcript_data: dict[str, Any],
    embedding_results: dict[str, Any],
) -> dict[str, Any]:
    phi_redaction_info = transcript_data.get("phi_redaction", {})
    return {
        "consultation_id": consultation_id,
        "tenant_id": tenant_id,
        "processed_at": datetime.now(UTC).isoformat(),
        "embedding_model": COHERE_EMBED_MODEL_ID,
        "statistics": {
            "total_segments": embedding_results["total_segments"],
            "successful_embeddings": embedding_results["successful_embeddings"],
            "failed_embeddings": embedding_results["failed_embeddings"],
        },
        "phi_redaction": {
            "entities_found": phi_redaction_info.get("entities_found", 0),
            "entity_types": phi_redaction_info.get("entity_types", []),
            "confidence_threshold": phi_redaction_info.get("confidence_threshold", 0.0),
        },
        "embeddings": embedding_results["embeddings"],
    }


@tracer.capture_method
def store_embeddings_document(key: str, embeddings_data: dict[str, Any]) -> None:
    # Default to SSE-S3 (AES256), but switch to SSE-KMS if a key ID is set
    sse_args = {"ServerSideEncryption": "AES256"}
    kms_key_id = os.getenv("EMBEDDINGS_KMS_KEY_ID")
    if kms_key_id:
        sse_args = {
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": kms_key_id,
        }

    s3_client.put_object(
        Bucket=GOLD_BUCKET,
        Key=key,
        Body=json.dumps(embeddings_data, indent=2),
        ContentType="application/json",
        **sse_args,
    )


def index_embeddings_to_opensearch(
    consultation_id: str,
    tenant_id: str,
    embedding_results: dict[str, Any],
) -> None:
    """Bulk index embeddings into OpenSearch if endpoint configured."""
    global opensearch_client
    if opensearch_client is None:
        try:
            from opensearchpy import (  # type: ignore[import-untyped]
                OpenSearch,
                RequestsHttpConnection,
            )
            from requests_aws4auth import AWS4Auth  # type: ignore[import-untyped]
        except ImportError as e:
            logger.exception(f"OpenSearch dependencies not available: {e}")
            return

        # Configure AWS SigV4 authentication for OpenSearch
        session = boto3.Session()
        credentials = session.get_credentials()
        if credentials is None:
            logger.error("No AWS credentials available for OpenSearch")
            return

        frozen_credentials = credentials.get_frozen_credentials()
        region = os.environ.get("AWS_REGION", "us-east-1")
        service = os.environ.get("OPENSEARCH_SERVICE", "es")  # 'es' or 'aoss'
        awsauth = AWS4Auth(
            frozen_credentials.access_key,
            frozen_credentials.secret_key,
            region,
            service,
            session_token=frozen_credentials.token,
        )

        opensearch_client = OpenSearch(
            hosts=[{"host": OPENSEARCH_ENDPOINT, "port": 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )

    index_name = "clinical-conversations"
    actions = []
    for emb in embedding_results["embeddings"]:
        doc = {
            "consultation_id": consultation_id,
            "tenant_id": tenant_id,
            "turn_index": emb["turn_index"],
            "speaker": emb["speaker"],
            "text": emb["text"],
            "embedding": emb["embedding"],
            "model": COHERE_EMBED_MODEL_ID,
        }
        actions.append({"index": {"_index": index_name}})
        actions.append(doc)

    if actions:
        body = "\n".join(json.dumps(a) for a in actions) + "\n"
        resp = opensearch_client.bulk(body=body)
        if isinstance(resp, dict) and resp.get("errors"):
            logger.warning(
                "OpenSearch bulk indexing had errors",
                response_summary=resp.get("items", [])[:1],
            )


@tracer.capture_method
def update_consultation_metadata(
    consultation_id: str,
    tenant_id: str,
    embedding_results: dict[str, Any],
) -> None:
    try:
        dynamodb_client.update_item(
            TableName=CONSULTATION_METADATA_TABLE,
            Key={
                "ConsultationId": {"S": consultation_id},
            },
            UpdateExpression="SET EmbeddingsGenerated = :count, EmbeddingModel = :model, EmbeddingProcessedAt = :ts, ProcessingStage = :stage",
            ExpressionAttributeValues={
                ":count": {"N": str(embedding_results["successful_embeddings"])},
                ":model": {"S": COHERE_EMBED_MODEL_ID},
                ":ts": {"S": datetime.now(UTC).isoformat()},
                ":stage": {"S": "EMBEDDING_COMPLETED"},
            },
        )
    except Exception:
        logger.exception("Error updating consultation metadata")


@tracer.capture_method
def publish_embedding_completion(
    consultation_id: str,
    tenant_id: str,
    embedding_results: dict[str, Any],
    gold_key: str,
) -> None:
    try:
        eventbridge_event = {
            "Source": "consultation.pipeline",
            "DetailType": "Embedding Processing Completed",
            "Detail": json.dumps(
                {
                    "consultationId": consultation_id,
                    "tenantId": tenant_id,
                    "goldKey": gold_key,
                    "embeddingsGenerated": embedding_results["successful_embeddings"],
                    "totalSegments": embedding_results["total_segments"],
                    "embeddingModel": COHERE_EMBED_MODEL_ID,
                    "processedAt": datetime.now(UTC).isoformat(),
                },
            ),
        }
        event_bus_name = os.getenv("EVENT_BUS_NAME")
        if event_bus_name:
            eventbridge_event["EventBusName"] = event_bus_name
        events_client.put_events(Entries=[eventbridge_event])
    except Exception:
        logger.exception("Error publishing embedding completion event")
