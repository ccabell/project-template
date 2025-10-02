"""Enhanced transcript consumer with spell checking and DynamoDB storage.

This Lambda function processes Kinesis transcript stream records, applies
aesthetic medicine brand name spell checking, and stores segments in DynamoDB
for real-time querying using LMA-style partition key patterns.

The consumer preserves three transcript versions for comprehensive error analysis:
DeepgramOriginalTranscript, ProcessedTranscript, and FinalizedTranscript.

Example:
    Lambda processes Kinesis records with spell checking:

    # Input: "Patient wants zee omen treatment"
    # Output: "Patient wants Xeomin treatment" (stored in DynamoDB)
"""

import base64
import json
import os
import time
from decimal import Decimal
from urllib.parse import urlencode

import boto3
import urllib3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

logger = Logger(service="transcript-consumer", level="WARN")
tracer = Tracer(service="transcript-consumer")
metrics = Metrics(service="transcript-consumer", namespace="TranscriptProcessing")

TRANSCRIPT_SEGMENTS_TABLE = os.environ["TRANSCRIPT_TABLE"]
BEDROCK_MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
TRANSCRIPTION_BUCKET = os.environ["TRANSCRIPTION_BUCKET"]

DG_ENDPOINT = "https://api.deepgram.com/v1/read"
HEADERS = {"Authorization": f"Token {os.environ['DG_API_KEY']}"}
HEADROOM_MS = 5000

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
transcript_table = dynamodb.Table(TRANSCRIPT_SEGMENTS_TABLE)

http = urllib3.PoolManager(
    timeout=urllib3.util.Timeout(connect=10.0, read=30.0),
    maxsize=10,
    retries=3,
)


def _to_dynamo_safe(value):
    """Recursively replace float → Decimal for DynamoDB serialization.

    Args:
        value: The value to convert, can be: float, list, dict, or other types.

    Returns:
        The converted value, with floats replaced by Decimals.

    """
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_to_dynamo_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_dynamo_safe(v) for k, v in value.items()}
    return value


SYSTEM_PROMPT = """<role>
You are a specialist medical proof-reader focused on aesthetic-medicine brands and terms.
</role>

<task>
Identify and correct ONLY obvious misspellings of brand names and proper nouns in medical transcriptions.
</task>

<context>
- Aesthetic medicine involves treatments using branded products and devices
- Transcriptions often contain phonetic misspellings of brand names
- Brand names MUST be spelled exactly as registered, including diacritical marks
- Common brands include: Botox, Xeomin, Juvederm, Restylane, Dysport, NEOFIRM, JOURNÉE, HYALIS+, AFTERCARE, Ellansé
- Medical terminology and common words should be left unchanged unless clearly wrong
</context>

<brand_corrections>
<example>zee omen → Xeomin</example>
<example>bow talks → Botox</example>
<example>juva derm → Juvederm</example>
<example>new firm → NEOFIRM</example>
<example>dis port → Dysport</example>
<example>restilin → Restylane</example>
<example>journey cream → JOURNÉE cream</example>
<example>hi Alice serum → HYALIS+ serum</example>
<example>after care → AFTERCARE</example>
</brand_corrections>

<critical_instructions>
- ONLY correct obvious misspellings of known aesthetic medicine brand names
- PRESERVE all punctuation, spacing, and capitalization exactly as provided
- DO NOT change medical terminology, anatomy terms, or procedure names
- DO NOT change common English words even if they seem unusual in context
- DO NOT rephrase or restructure sentences
- DO NOT add any explanations, notes, or additional text
- DO NOT add parentheses or any notation about what was corrected
- DO NOT correct numbers, measurements, or dosages
- When in doubt, leave the original text unchanged
- Make minimal changes - only fix clear brand name misspellings
</critical_instructions>

<preservation_examples>
<example>Patient says "bow talks" → Patient says "Botox" (only brand name changed)</example>
<example>Patient wants "zee omen treatment" → Patient wants "Xeomin treatment" (minimal change)</example>
<example>Apply "new firm" cream → Apply "NEOFIRM" cream (preserve context)</example>
</preservation_examples>

<output_format>
You MUST respond with ONLY valid JSON following this exact schema:
{
  "corrected": "transcription with minimal corrections applied only to brand names"
}

Generate ONLY the JSON object. NO markdown formatting, code blocks, preamble, or additional text.
</output_format>"""


@tracer.capture_method
def dg_read_sync(text, intents=True, sentiment=True):
    """Analyze text using Deepgram's `/v1/read` endpoint synchronously.

    Args:
        text (str): The text to analyze.
        intents (bool): Whether to include intent analysis.
        sentiment (bool): Whether to include sentiment analysis.

    Returns:
        dict: Analysis results containing intents, sentiment, and other metadata.

    Raises:
        RuntimeError: If the Deepgram API request fails.
    """
    params = {"language": "en"}
    if intents:
        params["intents"] = "true"
    if sentiment:
        params["sentiment"] = "true"

    url = f"{DG_ENDPOINT}?{urlencode(params)}"

    try:
        r = http.request(
            "POST",
            url,
            headers=HEADERS,
            body=text,
        )
        if r.status != 200:
            msg = f"Deepgram HTTP {r.status}"
            raise RuntimeError(msg)
        return json.loads(r.data).get("results", {})
    except Exception as e:
        logger.exception(
            f"Deepgram API request failed: {e}",
            extra={
                "url": url,
                "text_length": len(text) if text else 0,
            },
        )
        return {}


@tracer.capture_method
def apply_spelling_correction(text: str) -> tuple[str, float]:
    """Apply aesthetic medicine brand name spelling corrections.

    Args:
        text: Input transcript text

    Returns:
        Tuple of corrected text and processing time in milliseconds
    """
    if not text or len(text.strip()) < 3:
        return text, 0.0

    start_ns = time.time_ns()

    try:
        user_prompt = f"""## Task
                    Identify and correct ONLY obvious brand name misspellings in the following medical transcription.
                    Preserve all other text exactly as written.
                    ## Input Text
                    {text}
                    ## Output Requirements
                    Return only the JSON object with minimal corrections applied solely to aesthetic medicine brand
                    names."""

        response = bedrock.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[
                {"role": "user", "content": [{"text": user_prompt}]},
                {"role": "assistant", "content": [{"text": "{"}]},
            ],
            inferenceConfig={
                "temperature": 0.0,
                "topP": 1.0,
                "maxTokens": 2048,
                "stopSequences": ["}"],
            },
        )

        elapsed_ms = (time.time_ns() - start_ns) / 1_000_000
        json_str = response["output"]["message"]["content"][0]["text"].strip()

        if not json_str.startswith("{"):
            json_str = "{" + json_str + "}"

        parsed = json.loads(json_str)

        if "corrected" not in parsed:
            logger.warning(
                "Bedrock response missing 'corrected' key, using original text",
            )
            return text, elapsed_ms

        corrected_text = parsed["corrected"]

        original_words = text.split()
        corrected_words = corrected_text.split()
        word_diff = abs(len(original_words) - len(corrected_words))
        char_diff_ratio = abs(len(text) - len(corrected_text)) / max(len(text), 1)

        if word_diff > 1:
            logger.info(f"Word difference >1 ({word_diff}), keeping original")
            return text, elapsed_ms
        if char_diff_ratio > 0.1:
            logger.info(
                f"Character difference >10% ({char_diff_ratio:.3f}), keeping original",
            )
            return text, elapsed_ms
        if corrected_text != text:
            logger.info(
                f"Applied spelling corrections: word_diff={word_diff}, char_ratio={char_diff_ratio:.3f}",
            )
        return corrected_text, elapsed_ms

    except Exception as e:
        logger.exception(f"Spelling correction failed: {e}")
        return text, 0.0


@tracer.capture_method
def create_segment_record(payload: dict) -> dict:
    """Create DynamoDB record from Kinesis transcript payload with spell checking.

    Preserves all transcript versions for comprehensive error analysis:
    - DeepgramOriginalTranscript: Raw transcript from Deepgram without any processing
    - ProcessedTranscript: Transcript after applying spell checking corrections
    - FinalizedTranscript: Final consolidated transcript after all processing steps
        including speaker diarization and other post-stream corrections

    Args:
        payload: Decoded Kinesis record containing transcript segment data

    Returns:
        DynamoDB record with all transcript versions preserved
    """
    consultation_id = payload["consultation_id"]
    segment_timestamp = payload.get("segment_timestamp", time.time())

    pk = f"trs#{consultation_id}"
    sk = f"segment#{segment_timestamp}"

    fargate_processed = payload.get("transcript", "")

    if fargate_processed:
        corrected_transcript, spell_check_ms = apply_spelling_correction(
            fargate_processed,
        )
    else:
        corrected_transcript = fargate_processed
        spell_check_ms = 0.0

    meta = payload.get("meta", {})

    analysis = {}
    if not payload.get("is_partial", False) and corrected_transcript.strip():
        analysis = dg_read_sync(corrected_transcript)

    raw_segment_record = {
        "consultation_id": pk,
        "segment_id": payload.get(
            "segment_id",
            sk,
        ),  # Use payload segment_id or fallback to sk
        "ConsultationId": consultation_id,
        "DeepgramOriginalTranscript": fargate_processed,
        "FinalizedTranscript": corrected_transcript,
        "Speaker": payload.get("speaker", "Unknown"),
        "StartTime": payload.get("start_time", 0.0),
        "IsPartial": payload.get("is_partial", False),
        "expiry_time": int(time.time()) + (90 * 24 * 60 * 60),
        "ProcessingStatus": "spell_checked",
        "SpellCheckDurationMs": spell_check_ms,
        "HasCorrections": corrected_transcript != fargate_processed,
        "Analysis": analysis,
        "MedicalTermsDetected": [],
        "OpportunityFlags": [],
        "QuestionFlags": [],
        "OrganizationId": meta.get("organizationId", "unknown"),
        "ExpertId": meta.get("expertId", "unknown"),
        "PatientId": meta.get("patientId", "unknown"),
        "ConsultationDate": meta.get("consultationDate", "unknown"),
        "StartedAt": meta.get("startedAt", "unknown"),
        "SampleRate": meta.get("sampleRate", 48000),
        "Words": payload.get("words", []),
    }

    return _to_dynamo_safe(raw_segment_record)


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event: dict, context: LambdaContext) -> dict:
    """Process Kinesis transcript records with spell checking.

    Main Lambda handler that processes batches of Kinesis records containing
    transcript segments. Each record is spell-checked for aesthetic medicine
    brands and stored in DynamoDB using LMA-style partition key patterns.

    Args:
        event: Lambda event containing Kinesis records
        context: Lambda runtime context

    Returns:
        dict: Summary of processed and failed records, with identifiers for
              any records that failed processing.
    """
    processed_count = 0
    failed_count = 0
    total_spell_check_ms = 0.0

    failed_identifiers = []

    records = event.get("Records", [])
    logger.info(f"Processing {len(records)} Kinesis records")

    for idx, record in enumerate(records):
        seq = record["kinesis"]["sequenceNumber"]

        if context.get_remaining_time_in_millis() < HEADROOM_MS:
            logger.warning(
                "Low remaining time, deferring rest of batch",
                extra={
                    "remaining_ms": context.get_remaining_time_in_millis(),
                    "deferred_count": len(records) - idx,
                },
            )
            for r in records[idx:]:
                failed_identifiers.append(r["kinesis"]["sequenceNumber"])
            break

        try:
            encoded_data = record["kinesis"]["data"]
            decoded_data = base64.b64decode(encoded_data).decode("utf-8")
            payload = json.loads(decoded_data)

            event_type = payload.get("event_type", "transcript_segment")
            if event_type == "consultation_end":
                continue

            logger.debug(
                "Processing transcript segment",
                extra={
                    "consultation_id": payload.get("consultation_id"),
                    "segment_id": payload.get("segment_id"),
                    "is_partial": payload.get("is_partial", False),
                },
            )

            segment_record = create_segment_record(payload)
            duration_ms = float(segment_record.get("SpellCheckDurationMs", 0))
            total_spell_check_ms += duration_ms

            transcript_table.put_item(Item=segment_record)

            processed_count += 1
            metrics.add_metric(name="SegmentProcessed", unit="Count", value=1)
            metrics.add_metric(
                name="SpellCheckDuration",
                unit="Milliseconds",
                value=duration_ms,
            )
            if segment_record.get("HasCorrections", False):
                metrics.add_metric(
                    name="SpellingCorrectionsMade",
                    unit="Count",
                    value=1,
                )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.exception(
                "Failed to process Kinesis record",
                extra={"error": str(e), "sequenceNumber": seq},
            )
            failed_count += 1
            failed_identifiers.append(seq)
            metrics.add_metric(name="SegmentProcessingError", unit="Count", value=1)

        except ClientError as e:
            logger.exception(
                "DynamoDB operation failed",
                extra={
                    "error": str(e),
                    "error_code": e.response.get("Error", {}).get("Code"),
                    "sequenceNumber": seq,
                },
            )
            failed_count += 1
            failed_identifiers.append(seq)
            metrics.add_metric(name="DynamoDBError", unit="Count", value=1)

        except Exception:
            logger.exception("Unexpected error", extra={"sequenceNumber": seq})
            failed_count += 1
            failed_identifiers.append(seq)
            metrics.add_metric(name="UnexpectedError", unit="Count", value=1)

    avg_spell_check_ms = total_spell_check_ms / max(processed_count, 1)

    logger.info(
        "Transcript processing completed",
        extra={
            "processed_count": processed_count,
            "failed_count": failed_count,
            "total_records": len(records),
            "avg_spell_check_ms": round(avg_spell_check_ms, 2),
            "total_spell_check_ms": round(total_spell_check_ms, 2),
        },
    )

    return {
        "batchItemFailures": [
            {"itemIdentifier": ident} for ident in failed_identifiers
        ],
    }
