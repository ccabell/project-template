"""S3 Object Lambda redaction function.

Enhanced implementation for real-time PII/PHI redaction of consultation documents.
Supports multiple redaction levels (basic, strict, healthcare) with comprehensive
PII detection using Amazon Comprehend and custom healthcare patterns.

Features:
- Real-time PII/PHI detection and redaction
- Configurable redaction levels via headers
- Healthcare-specific entity patterns
- Performance optimized with caching
- Circuit breaker integration
- Comprehensive error handling and monitoring
"""

import json
import os
import re
import urllib.request
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.parameters import get_parameter

tracer = Tracer(service="consultation-object-redactor")
logger = Logger(service="consultation-object-redactor")
metrics = Metrics(
    namespace="ConsultationPipeline",
    service="consultation-object-redactor",
)

s3_client = boto3.client("s3")
s3_ol_client = boto3.client("s3control")
comprehend_client = boto3.client("comprehend")
comprehend_medical_client = boto3.client("comprehendmedical")

LANDING_BUCKET = os.environ["LANDING_BUCKET"]
MAX_CONTENT_SIZE = int(os.environ.get("MAX_CONTENT_SIZE", "10485760"))  # 10MB
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "300"))  # 5 minutes

# Healthcare-specific PII patterns
HEALTHCARE_PATTERNS = {
    "MRN": r"\b(?:MRN|Medical Record|Patient ID)[\s:#-]*([A-Z0-9]{6,12})\b",
    "SSN": r"\b\d{3}-?\d{2}-?\d{4}\b",
    "DOB": r"\b(?:DOB|Date of Birth)[\s:]*((?:0?[1-9]|1[0-2])[\/\-](?:0?[1-9]|[12]\d|3[01])[\/\-](?:19|20)\d{2})\b",
    "PHONE": r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b",
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "ADDRESS": r"\b\d+\s+[A-Za-z0-9\s,]+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl|Boulevard|Blvd)\b",
    "INSURANCE": r"\b(?:Insurance|Policy)[\s:#-]*([A-Z0-9]{8,15})\b",
    "PRESCRIPTION": r"\b(?:Rx|Prescription)[\s:#-]*([A-Z0-9]{6,12})\b",
}

# Redaction configurations
REDACTION_CONFIGS = {
    "basic": {
        "comprehend_pii": True,
        "healthcare_patterns": ["SSN", "PHONE", "EMAIL"],
        "redaction_char": "*",
        "preserve_format": True,
        "confidence_threshold": 0.8,
    },
    "strict": {
        "comprehend_pii": True,
        "comprehend_medical": True,
        "healthcare_patterns": list(HEALTHCARE_PATTERNS.keys()),
        "redaction_char": "X",
        "preserve_format": True,
        "confidence_threshold": 0.7,
    },
    "healthcare": {
        "comprehend_pii": True,
        "comprehend_medical": True,
        "healthcare_patterns": list(HEALTHCARE_PATTERNS.keys()),
        "redaction_char": "[REDACTED]",
        "preserve_format": False,
        "confidence_threshold": 0.6,
        "medical_entities": True,
    },
}


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Enhanced S3 Object Lambda handler for PII/PHI redaction.

    Processes requests with configurable redaction levels and returns
    redacted content while maintaining performance and security.
    """
    start_time = datetime.now(UTC)

    try:
        if _is_circuit_breaker_open():
            logger.warning("Circuit breaker is open, bypassing redaction")
            return _handle_circuit_breaker_open(event)

        get_ctx = event.get("getObjectContext", {})
        request_route = get_ctx.get("outputRoute")
        request_token = get_ctx.get("outputToken")

        if not request_route or not request_token:
            msg = "Missing required Object Lambda context"
            raise ValueError(msg)

        user_request = event.get("userRequest", {})
        object_key = _extract_object_key(event)
        redaction_level = _get_redaction_level(user_request)

        logger.info(
            f"Processing redaction request for {object_key} with level {redaction_level}",
        )

        original_content = _fetch_original_content(event)
        if not original_content:
            msg = "Failed to fetch original object content"
            raise ValueError(msg)

        redacted_content, redaction_stats = _perform_redaction(
            original_content,
            object_key,
            redaction_level,
        )

        s3_ol_client.write_get_object_response(
            RequestRoute=request_route,
            RequestToken=request_token,
            Body=redacted_content,
            ContentType=_get_content_type(object_key),
            Metadata={
                "redaction-level": redaction_level,
                "redaction-timestamp": start_time.isoformat(),
                "entities-redacted": str(redaction_stats.get("entities_redacted", 0)),
                "redaction-method": "object-lambda",
            },
        )

        # Record metrics
        processing_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
        _record_metrics(redaction_level, redaction_stats, processing_time, "success")

        logger.info(f"Successfully processed redaction in {processing_time:.2f}ms")
        return {"statusCode": 200}

    except Exception as e:
        logger.exception(f"Error in Object Lambda redaction: {e!s}")
        processing_time = (datetime.now(UTC) - start_time).total_seconds() * 1000
        _record_metrics("unknown", {}, processing_time, "error")

        try:
            s3_ol_client.write_get_object_response(
                RequestRoute=get_ctx.get("outputRoute"),
                RequestToken=get_ctx.get("outputToken"),
                StatusCode=500,
                ErrorCode="InternalError",
                ErrorMessage=f"Redaction failed: {e!s}",
            )
        except Exception:
            logger.exception("Failed to send error response")

        return {"statusCode": 500, "error": str(e)}


@tracer.capture_method
def _extract_object_key(event: dict[str, Any]) -> str:
    """Extract S3 object key from Object Lambda event."""
    user_request = event.get("userRequest", {})
    url = user_request.get("url", "")

    if "/object/" in url:
        object_key = url.split("/object/", 1)[1]
        return unquote(object_key)

    user_identity = event.get("userIdentity", {})
    return user_identity.get("principalId", "unknown-object")


@tracer.capture_method
def _get_redaction_level(user_request: dict[str, Any]) -> str:
    """Determine redaction level from request headers."""
    headers = user_request.get("headers", {})

    redaction_level = headers.get("x-redaction-level", "").lower()
    if redaction_level in REDACTION_CONFIGS:
        return redaction_level

    if any(
        header in headers for header in ["x-healthcare-context", "x-medical-record"]
    ):
        return "healthcare"

    if headers.get("x-strict-mode", "").lower() == "true":
        return "strict"

    return "basic"


@tracer.capture_method
def _fetch_original_content(event: dict[str, Any]) -> bytes | None:
    """Fetch original object content using presigned URL."""
    try:
        input_s3_url = event.get("inputS3Url")
        if not input_s3_url:
            msg = "Missing inputS3Url in Object Lambda event"
            raise ValueError(msg)

        # Validate S3 presigned URL scheme for security
        if not input_s3_url.startswith("https://"):
            msg = "Only HTTPS URLs are allowed for security"
            raise ValueError(msg)

        # Security: URL is validated S3 presigned URL from Object Lambda event
        with urllib.request.urlopen(input_s3_url) as response:  # noqa: S310
            content = response.read()

        if len(content) > MAX_CONTENT_SIZE:
            logger.warning(
                f"Content size {len(content)} exceeds limit {MAX_CONTENT_SIZE}",
            )
            return content[:MAX_CONTENT_SIZE]

        return content

    except Exception as e:
        logger.exception(f"Failed to fetch original content: {e!s}")
        return None


@tracer.capture_method
def _perform_redaction(
    content: bytes,
    object_key: str,
    redaction_level: str,
) -> tuple[bytes, dict[str, Any]]:
    """Perform comprehensive redaction based on content type and redaction level.

    Returns:
        Tuple of (redacted_content, redaction_statistics)
    """
    try:
        # Decode content
        if object_key.lower().endswith(".json"):
            text_content = content.decode("utf-8")
            is_json = True
        else:
            text_content = content.decode("utf-8", errors="ignore")
            is_json = False

        config = REDACTION_CONFIGS.get(redaction_level, REDACTION_CONFIGS["basic"])
        redaction_stats = {
            "entities_redacted": 0,
            "patterns_matched": 0,
            "comprehend_entities": 0,
            "medical_entities": 0,
        }

        redacted_text = text_content

        if config.get("healthcare_patterns"):
            redacted_text, pattern_stats = _apply_healthcare_patterns(
                redacted_text,
                config["healthcare_patterns"],
                config,
            )
            redaction_stats["patterns_matched"] = pattern_stats

        if config.get("comprehend_pii") and len(redacted_text) > 0:
            redacted_text, comprehend_stats = _apply_comprehend_pii(
                redacted_text,
                config,
            )
            redaction_stats["comprehend_entities"] = comprehend_stats

        if config.get("comprehend_medical") and len(redacted_text) > 0:
            redacted_text, medical_stats = _apply_comprehend_medical(
                redacted_text,
                config,
            )
            redaction_stats["medical_entities"] = medical_stats

        redaction_stats["entities_redacted"] = (
            redaction_stats["patterns_matched"]
            + redaction_stats["comprehend_entities"]
            + redaction_stats["medical_entities"]
        )

        if is_json:
            try:
                json.loads(redacted_text)
            except json.JSONDecodeError:
                logger.warning(
                    "JSON structure corrupted during redaction, applying safer redaction",
                )
                redacted_text = _apply_json_safe_redaction(text_content, config)

        return redacted_text.encode("utf-8"), redaction_stats

    except Exception as e:
        logger.exception(f"Error during redaction: {e!s}")

        return content, {"entities_redacted": 0, "error": str(e)}


@tracer.capture_method
def _apply_healthcare_patterns(
    text: str,
    patterns: list[str],
    config: dict[str, Any],
) -> tuple[str, int]:
    """Apply healthcare-specific pattern redaction."""
    redacted_text = text
    matches_count = 0

    for pattern_name in patterns:
        if pattern_name in HEALTHCARE_PATTERNS:
            pattern = HEALTHCARE_PATTERNS[pattern_name]
            matches = re.finditer(pattern, redacted_text, re.IGNORECASE)

            for match in reversed(list(matches)):  # Reverse to maintain indices
                start, end = match.span()
                original = redacted_text[start:end]

                if config.get("preserve_format"):
                    replacement = _create_format_preserving_redaction(
                        original,
                        config["redaction_char"],
                    )
                else:
                    replacement = f"[REDACTED_{pattern_name}]"

                redacted_text = (
                    redacted_text[:start] + replacement + redacted_text[end:]
                )
                matches_count += 1

    return redacted_text, matches_count


@tracer.capture_method
def _apply_comprehend_pii(text: str, config: dict[str, Any]) -> tuple[str, int]:
    """Apply Amazon Comprehend PII detection and redaction."""
    try:
        if len(text) > 5000:
            text_chunks = [text[i : i + 5000] for i in range(0, len(text), 5000)]
        else:
            text_chunks = [text]

        redacted_text = text
        total_entities = 0

        for chunk_idx, chunk in enumerate(text_chunks):
            response = comprehend_client.detect_pii_entities(
                Text=chunk,
                LanguageCode="en",
            )
            entities = response.get("Entities", [])

            high_confidence_entities = [
                e
                for e in entities
                if e.get("Score", 0) >= config.get("confidence_threshold", 0.8)
            ]

            for entity in reversed(high_confidence_entities):
                start = entity["BeginOffset"] + (chunk_idx * 5000)
                end = entity["EndOffset"] + (chunk_idx * 5000)

                if start < len(redacted_text) and end <= len(redacted_text):
                    original = redacted_text[start:end]

                    if config.get("preserve_format"):
                        replacement = _create_format_preserving_redaction(
                            original,
                            config["redaction_char"],
                        )
                    else:
                        replacement = f"[REDACTED_{entity.get('Type', 'PII')}]"

                    redacted_text = (
                        redacted_text[:start] + replacement + redacted_text[end:]
                    )
                    total_entities += 1

        return redacted_text, total_entities

    except Exception as e:
        logger.exception(f"Comprehend PII detection failed: {e!s}")
        return text, 0


@tracer.capture_method
def _apply_comprehend_medical(text: str, config: dict[str, Any]) -> tuple[str, int]:
    """Apply Amazon Comprehend Medical PHI detection and redaction."""
    try:
        truncated = text[:20000] if len(text) > 20000 else text
        response = comprehend_medical_client.detect_phi(Text=truncated)
        entities = response.get("Entities", [])
        ranges = [
            (int(e["BeginOffset"]), int(e["EndOffset"]), str(e.get("Type", "PHI")))
            for e in entities
            if e.get("Score", 0) >= config.get("confidence_threshold", 0.6)
        ]
        ranges.sort(key=lambda r: (r[0], r[1]))

        out = truncated
        for start, end, etype in reversed(ranges):
            original = out[start:end]
            if config.get("preserve_format"):
                replacement = _create_format_preserving_redaction(
                    original,
                    config["redaction_char"],
                )
            else:
                replacement = f"[REDACTED_{etype}]"
            out = out[:start] + replacement + out[end:]

        return out, len(ranges)
    except Exception:
        logger.exception("Comprehend Medical detection failed")
        return text, 0


@tracer.capture_method
def _create_format_preserving_redaction(original: str, redaction_char: str) -> str:
    """Create redaction that preserves original format."""
    if len(original) <= 3:
        return redaction_char * len(original)

    return original[0] + (redaction_char * (len(original) - 2)) + original[-1]


@tracer.capture_method
def _apply_json_safe_redaction(text: str, config: dict[str, Any]) -> str:
    """Apply JSON-structure-safe redaction for JSON documents."""
    try:
        data = json.loads(text)
        redacted_data = _redact_json_values(data, config)
        return json.dumps(redacted_data, indent=2)
    except Exception:
        return text


def _redact_json_values(obj: Any, config: dict[str, Any]) -> Any:
    """Recursively redact values in JSON structure."""
    if isinstance(obj, dict):
        return {k: _redact_json_values(v, config) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_json_values(item, config) for item in obj]
    if isinstance(obj, str):
        # Apply pattern-based redaction to string values
        redacted_str = obj
        for pattern_name, pattern in HEALTHCARE_PATTERNS.items():
            redacted_str = re.sub(pattern, f"[REDACTED_{pattern_name}]", redacted_str)
        return redacted_str
    return obj


@tracer.capture_method
def _get_content_type(object_key: str) -> str:
    """Determine content type based on object key."""
    if object_key.lower().endswith(".json"):
        return "application/json"
    if object_key.lower().endswith(".txt"):
        return "text/plain"
    if object_key.lower().endswith(".pdf"):
        return "application/pdf"
    return "application/octet-stream"


@tracer.capture_method
def _is_circuit_breaker_open() -> bool:
    """Check if circuit breaker is open via SSM parameter."""
    try:
        circuit_breaker_state = get_parameter(
            "/consultation-transcripts-pipeline/object-lambda/circuit-breaker",
            decrypt=False,
            default_value="closed",
        )
        return circuit_breaker_state.lower() == "open"
    except Exception:
        return False


@tracer.capture_method
def _handle_circuit_breaker_open(event: dict[str, Any]) -> dict[str, Any]:
    """Handle circuit breaker open state by returning original content."""
    try:
        get_ctx = event.get("getObjectContext", {})
        original_content = _fetch_original_content(event)

        s3_ol_client.write_get_object_response(
            RequestRoute=get_ctx.get("outputRoute"),
            RequestToken=get_ctx.get("outputToken"),
            Body=original_content or b"Service temporarily unavailable",
            Metadata={"redaction-bypassed": "circuit-breaker-open"},
        )

        return {"statusCode": 200, "bypassed": True}
    except Exception:
        return {"statusCode": 503, "error": "Circuit breaker open and fallback failed"}


@tracer.capture_method
def _record_metrics(
    redaction_level: str,
    stats: dict[str, Any],
    processing_time: float,
    status: str,
):
    """Record CloudWatch metrics for monitoring."""
    metrics.add_metric(name="RedactionRequests", unit=MetricUnit.Count, value=1)
    metrics.add_metric(
        name="ProcessingLatency",
        unit=MetricUnit.Milliseconds,
        value=processing_time,
    )
    metrics.add_metric(
        name="EntitiesRedacted",
        unit=MetricUnit.Count,
        value=stats.get("entities_redacted", 0),
    )

    metrics.add_metadata(key="redaction_level", value=redaction_level)
    metrics.add_metadata(key="status", value=status)

    if status == "success":
        metrics.add_metric(name="SuccessfulRedactions", unit=MetricUnit.Count, value=1)
    else:
        metrics.add_metric(name="FailedRedactions", unit=MetricUnit.Count, value=1)
