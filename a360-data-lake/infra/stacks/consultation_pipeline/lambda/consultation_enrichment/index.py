"""Consultation enrichment processor using Amazon Bedrock for analytics.

This Lambda function generates enriched analytics and clinical insights from
consultation embeddings and PHI-redacted transcripts using Claude Sonnet 4.
The enriched data is stored in the gold layer for downstream analytics,
reporting, and business intelligence applications.

The function implements comprehensive consultation analysis including sentiment,
quality scoring, clinical workflow optimization, and patient experience metrics.
"""

import json
import os
import re
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.config import Config
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
    tracer = Tracer(service="consultation-enrichment")
    logger = Logger(service="consultation-enrichment")
    metrics = Metrics(
        namespace="ConsultationPipeline",
        service="consultation-enrichment",
    )
else:
    tracer = MockTracer()
    logger = MockLogger()
    metrics = MockMetrics()

# Initialize AWS clients
_sdk_config = Config(
    connect_timeout=3,
    read_timeout=30,
    retries={"max_attempts": 3, "mode": "standard"},
    user_agent_extra="a360-consultation-enrichment/1.0",
)
s3_client = boto3.client("s3", config=_sdk_config)
bedrock_client = boto3.client(
    "bedrock-runtime",
    config=Config(
        read_timeout=int(os.environ.get("ANALYSIS_TIMEOUT_SECONDS", "120")),
        connect_timeout=10,
        retries={"max_attempts": 3, "mode": "standard"},
    ),
)
dynamodb_client = boto3.client("dynamodb", config=_sdk_config)
sns_client = boto3.client("sns", config=_sdk_config)

# Environment variables
SILVER_BUCKET = os.environ["SILVER_BUCKET"]
GOLD_BUCKET = os.environ["GOLD_BUCKET"]
CONSULTATION_METADATA_TABLE = os.environ["CONSULTATION_METADATA_TABLE"]
PIPELINE_COMPLETION_TOPIC_ARN = os.environ["PIPELINE_COMPLETION_TOPIC_ARN"]

# Analysis configuration
CLAUDE_MODEL_ID = os.environ.get(
    "CLAUDE_MODEL_ID",
    "anthropic.claude-sonnet-4-20250514-v1:0",
)
MAX_ANALYSIS_TEXT_LENGTH = 15000  # Claude context optimization
ANALYSIS_TIMEOUT_SECONDS = 120

# Helper: restrict IDs to safe characters (no slashes/dots for directory traversal protection)
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:-]{0,127}$")


def _is_safe_identifier(value: str) -> bool:
    return bool(_SAFE_ID_RE.fullmatch(value))


def _safe_int_clamp(value, min_val: int, max_val: int, default: int) -> int:
    """Safely convert value to int and clamp within range."""
    try:
        if value is None:
            return default
        return max(min_val, min(max_val, int(value)))
    except (ValueError, TypeError):
        return default


def _safe_float(value, default: float) -> float:
    """Safely convert value to float with fallback."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle consultation enrichment and analytics generation.

    This function can be triggered by:
    1. EventBridge events from embedding completion
    2. Direct invocation with consultation details
    3. Scheduled batch processing

    Args:
        event: Event data containing consultation information.
        context: Lambda context object.

    Returns:
        Response dictionary with processing status and metadata.
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
            "Processing enrichment for consultation",
            extra={"consultation_id": consultation_id, "tenant_id": tenant_id},
        )

        # Process the consultation enrichment
        result = process_consultation_enrichment(consultation_info)

        # Update metrics
        metrics.add_metric(
            name="ConsultationsProcessed",
            unit=MetricUnit.Count,
            value=1,
        )

        if result["status"] == "success":
            metrics.add_metric(
                name="ConsultationsSuccessful",
                unit=MetricUnit.Count,
                value=1,
            )
            metrics.add_metric(
                name="QualityScore",
                unit=MetricUnit.Count,
                value=result.get("quality_score", 0),
            )
        else:
            metrics.add_metric(
                name="ConsultationsFailed",
                unit=MetricUnit.Count,
                value=1,
            )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Consultation enrichment completed successfully",
                    "consultation_id": consultation_id,
                    "result": result,
                },
            ),
        }

    except Exception as e:
        logger.exception("Error processing consultation enrichment")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)

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
    # Handle EventBridge event from embedding completion
    if event.get("source") == "consultation.pipeline":
        detail = event.get("detail", {})
        if isinstance(detail, str):
            try:
                detail = json.loads(detail)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in event.detail")
                return None
        consultation_id = (detail.get("consultationId") or "").strip()
        tenant_id = (detail.get("tenantId") or "").strip()
        if (
            not consultation_id
            or not tenant_id
            or not _is_safe_identifier(consultation_id)
            or not _is_safe_identifier(tenant_id)
        ):
            logger.warning(
                "Invalid/missing identifiers in EventBridge event",
                extra={"consultation_id": consultation_id, "tenant_id": tenant_id},
            )
            return None
        return {
            "consultation_id": consultation_id,
            "tenant_id": tenant_id,
            "silver_key": detail.get("silverKey", ""),
            "gold_key": detail.get("goldKey", ""),
            "embeddings_generated": int(detail.get("embeddingsGenerated", 0) or 0),
            "source": "eventbridge",
        }

    # Handle direct invocation
    if "consultation_id" in event:
        consultation_id = str(event.get("consultation_id") or "").strip()
        tenant_id = str(event.get("tenant_id") or "").strip()
        if (
            not consultation_id
            or not tenant_id
            or not _is_safe_identifier(consultation_id)
            or not _is_safe_identifier(tenant_id)
        ):
            logger.warning(
                "Missing/invalid consultation_id or tenant_id on direct invocation",
                extra={"consultation_id": consultation_id, "tenant_id": tenant_id},
            )
            return None
        return {
            "consultation_id": consultation_id,
            "tenant_id": tenant_id,
            "silver_key": str(event.get("silver_key") or ""),
            "gold_key": str(event.get("gold_key") or ""),
            "embeddings_generated": int(event.get("embeddings_generated", 0) or 0),
            "source": "direct_invocation",
        }

    return None


@tracer.capture_method
def process_consultation_enrichment(
    consultation_info: dict[str, str],
) -> dict[str, Any]:
    """Process consultation for enrichment and analytics generation.

    Args:
        consultation_info: Dictionary with consultation details.

    Returns:
        Processing result with status and metadata.
    """
    consultation_id = consultation_info["consultation_id"]
    tenant_id = consultation_info["tenant_id"]

    # Validate IDs against safe pattern to prevent directory traversal
    if not _is_safe_identifier(consultation_id):
        logger.error(f"Invalid consultation_id: {consultation_id}")
        raise ValueError(f"Invalid consultation_id contains unsafe characters: {consultation_id}")

    if not _is_safe_identifier(tenant_id):
        logger.error(f"Invalid tenant_id: {tenant_id}")
        raise ValueError(f"Invalid tenant_id contains unsafe characters: {tenant_id}")

    try:
        # Retrieve PHI-redacted transcript for analysis
        silver_key = (
            consultation_info.get("silver_key")
            or f"transcripts/{tenant_id}/{consultation_id}/phi_redacted_transcript.json"
        )
        expected_transcript_prefix = f"transcripts/{tenant_id}/{consultation_id}/"
        if consultation_info.get("silver_key") and (
            not silver_key.startswith(expected_transcript_prefix) or ".." in silver_key
        ):
            logger.warning(
                "Ignoring silver_key outside expected prefix",
                extra={
                    "provided_key": silver_key,
                    "expected_prefix": expected_transcript_prefix,
                },
            )
            silver_key = f"{expected_transcript_prefix}phi_redacted_transcript.json"
        transcript_data = get_transcript_data(silver_key)

        if not transcript_data:
            return {
                "status": "error",
                "error": "Failed to retrieve transcript data",
            }

        # Retrieve embeddings data for enhanced analysis
        embeddings_key = (
            consultation_info.get("gold_key")
            or f"embeddings/{tenant_id}/{consultation_id}/conversation_embeddings.json"
        )
        expected_embeddings_prefix = f"embeddings/{tenant_id}/{consultation_id}/"
        if consultation_info.get("gold_key") and (
            not embeddings_key.startswith(expected_embeddings_prefix)
            or ".." in embeddings_key
        ):
            logger.warning(
                "Ignoring gold_key outside expected prefix",
                extra={
                    "provided_key": embeddings_key,
                    "expected_prefix": expected_embeddings_prefix,
                },
            )
            embeddings_key = f"{expected_embeddings_prefix}conversation_embeddings.json"
        embeddings_data = get_embeddings_data(embeddings_key)

        # Extract conversation text for analysis
        conversation_text = extract_conversation_for_analysis(transcript_data)
        if not conversation_text:
            return {
                "status": "skipped",
                "reason": "No conversation text available for analysis",
            }

        logger.info(
            "Analyzing conversation text",
            extra={"length": len(conversation_text)},
        )

        # Generate comprehensive insights using Claude Sonnet 4
        insights = generate_clinical_insights(conversation_text, embeddings_data)

        # Perform additional analytical processing
        enhanced_metrics = calculate_enhanced_metrics(
            transcript_data,
            embeddings_data,
            insights,
        )

        # Create comprehensive enrichment document
        enrichment_document = create_enrichment_document(
            consultation_id,
            tenant_id,
            transcript_data,
            embeddings_data,
            insights,
            enhanced_metrics,
        )

        # Store enrichment in gold layer
        analytics_key = (
            f"analytics/{tenant_id}/{consultation_id}/enriched_insights.json"
        )
        store_enrichment_document(analytics_key, enrichment_document)

        # Update consultation metadata
        update_consultation_metadata(
            consultation_id,
            tenant_id,
            insights,
            enhanced_metrics,
        )

        # Publish pipeline completion
        embedded_count = int(consultation_info.get("embeddings_generated", 0))
        if enrichment_document.get("embeddings_generated") is not None:
            embedded_count = int(enrichment_document["embeddings_generated"])
        publish_pipeline_completion(
            consultation_id,
            tenant_id,
            enrichment_document,
            analytics_key,
            embedded_count,
        )

        logger.info(
            f"Enrichment completed for {consultation_id}: "
            f"Quality score {insights.get('consultation_quality_score', 'N/A')}",
        )

        return {
            "status": "success",
            "consultation_id": consultation_id,
            "tenant_id": tenant_id,
            "analytics_key": analytics_key,
            "quality_score": insights.get("consultation_quality_score", 0),
            "consultation_type": insights.get("consultation_type", "unknown"),
            "topics_count": len(insights.get("topics_discussed", [])),
            "treatments_count": len(insights.get("treatments_mentioned", [])),
        }

    except Exception as e:
        logger.exception(
            f"Error processing enrichment for consultation {consultation_id}",
        )
        return {
            "status": "error",
            "consultation_id": consultation_id,
            "error": str(e),
        }


@tracer.capture_method
def get_transcript_data(silver_key: str) -> dict[str, Any] | None:
    """Retrieve PHI-redacted transcript from silver bucket."""
    try:
        response = s3_client.get_object(
            Bucket=SILVER_BUCKET,
            Key=silver_key,
        )

        transcript_data = json.loads(response["Body"].read())
        logger.info("Retrieved transcript data", extra={"silver_key": silver_key})

        return transcript_data

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.warning(f"Transcript not found: {silver_key}")
        else:
            logger.exception(f"Error retrieving transcript: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error retrieving transcript: {e}")
        return None


@tracer.capture_method
def get_embeddings_data(embeddings_key: str) -> dict[str, Any] | None:
    """Retrieve embeddings data from gold bucket."""
    try:
        response = s3_client.get_object(
            Bucket=GOLD_BUCKET,
            Key=embeddings_key,
        )

        embeddings_data = json.loads(response["Body"].read())
        logger.info(
            "Retrieved embeddings data",
            extra={"embeddings_key": embeddings_key},
        )

        return embeddings_data

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.info(
                "Embeddings not found (optional)",
                extra={"embeddings_key": embeddings_key},
            )
        else:
            logger.exception(f"Error retrieving embeddings: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error retrieving embeddings: {e}")
        return None


@tracer.capture_method
def extract_conversation_for_analysis(transcript_data: dict[str, Any]) -> str:
    """Extract and prepare conversation text for Claude analysis."""
    conversation_parts = []

    if "conversation" in transcript_data:
        for turn in transcript_data["conversation"]:
            speaker = turn.get("speaker", "Unknown")
            text = turn.get("text", "").strip()

            if text and not turn.get("phi_warning"):  # Skip PHI-redacted turns
                conversation_parts.append(f"{speaker}: {text}")

    elif "transcript" in transcript_data:
        transcript_value = transcript_data["transcript"]
        if transcript_value is not None:
            text = str(transcript_value).strip()
            if text:
                conversation_parts.append(text)

    conversation_text = "\n".join(conversation_parts)

    # Truncate if too long for Claude analysis
    if len(conversation_text) > MAX_ANALYSIS_TEXT_LENGTH:
        logger.info(
            "Truncating conversation text",
            extra={
                "original_length": len(conversation_text),
                "truncated_length": MAX_ANALYSIS_TEXT_LENGTH,
            },
        )
        conversation_text = conversation_text[:MAX_ANALYSIS_TEXT_LENGTH]
        conversation_text += "\n[TRUNCATED FOR ANALYSIS]"

    return conversation_text


@tracer.capture_method
def generate_clinical_insights(
    conversation_text: str,
    embeddings_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate comprehensive clinical insights using Claude Sonnet 4."""
    try:
        # Build comprehensive analysis prompt
        analysis_prompt = build_clinical_analysis_prompt(
            conversation_text,
            embeddings_data,
        )

        # Call Claude Sonnet 4 via Bedrock
        claude_response = call_claude_for_analysis(analysis_prompt)

        # Parse and validate response
        insights = parse_claude_response(claude_response)

        # Add analysis metadata
        insights["analysis_metadata"] = {
            "model_id": CLAUDE_MODEL_ID,
            "analyzed_at": datetime.now(UTC).isoformat(),
            "text_length": len(conversation_text),
            "has_embeddings": embeddings_data is not None,
            "truncated": "[TRUNCATED FOR ANALYSIS]" in conversation_text,
        }

        return insights

    except Exception as e:
        logger.exception("Error generating clinical insights")

        # Return minimal fallback insights
        return {
            "consultation_type": "unknown",
            "topics_discussed": [],
            "treatments_mentioned": [],
            "patient_concerns": [],
            "clinical_recommendations": [],
            "sentiment_analysis": {"overall_satisfaction": "unknown"},
            "consultation_quality_score": 0,
            "duration_appropriateness": "unknown",
            "error": str(e),
            "analysis_metadata": {
                "model_id": CLAUDE_MODEL_ID,
                "analyzed_at": datetime.now(UTC).isoformat(),
                "text_length": len(conversation_text),
                "has_embeddings": embeddings_data is not None,
                "analysis_failed": True,
            },
        }


@tracer.capture_method
def build_clinical_analysis_prompt(
    conversation_text: str,
    embeddings_data: dict[str, Any] | None = None,
) -> str:
    """Build comprehensive analysis prompt for Claude."""
    # Base prompt structure
    prompt = f"""Analyze this clinical consultation transcript and provide comprehensive insights for healthcare workflow optimization.

TRANSCRIPT TO ANALYZE:
{conversation_text}

ANALYSIS REQUIREMENTS:
Provide a detailed JSON response with the following structure and insights:

{{
    "consultation_type": "string (initial, follow-up, procedure, emergency, cosmetic, etc.)",
    "topics_discussed": ["list", "of", "main", "clinical", "topics"],
    "treatments_mentioned": ["list", "of", "treatments", "procedures", "discussed"],
    "patient_concerns": ["list", "of", "patient", "questions", "concerns"],
    "clinical_recommendations": ["list", "of", "provider", "recommendations"],
    "sentiment_analysis": {{
        "overall_satisfaction": "positive/neutral/negative",
        "patient_comfort_level": "high/medium/low",
        "provider_empathy_score": 1-10,
        "communication_clarity": "excellent/good/fair/poor"
    }},
    "consultation_quality_score": "integer 1-10 based on thoroughness and patient care",
    "duration_appropriateness": "appropriate/too_short/too_long",
    "workflow_insights": {{
        "time_management": "assessment of time allocation",
        "documentation_completeness": "assessment of information gathering",
        "patient_education_quality": "assessment of patient education provided"
    }},
    "clinical_efficiency": {{
        "information_gathering_score": 1-10,
        "decision_making_clarity": 1-10,
        "follow_up_planning": 1-10
    }},
    "patient_experience": {{
        "wait_time_mentions": "any mentions of wait times",
        "comfort_level_indicators": "indicators of patient comfort",
        "satisfaction_indicators": "indicators of patient satisfaction"
    }},
    "risk_factors": ["list", "of", "any", "potential", "risk", "factors", "mentioned"],
    "follow_up_requirements": ["list", "of", "follow-up", "items", "discussed"]
}}

ANALYSIS FOCUS:
- Clinical workflow optimization
- Patient experience and satisfaction
- Healthcare quality metrics
- Communication effectiveness
- Operational efficiency insights
- Risk identification and management

"""

    # Add embeddings context if available
    if embeddings_data:
        stats = embeddings_data.get("statistics", {})
        metadata = embeddings_data.get("metadata", {})

        prompt += f"""
ADDITIONAL CONTEXT FROM EMBEDDINGS ANALYSIS:
- Total conversation segments: {stats.get("total_segments", "unknown")}
- Unique speakers: {metadata.get("unique_speakers", "unknown")}
- Total words: {metadata.get("total_words", "unknown")}
- Conversation duration: {metadata.get("conversation_duration", "unknown")} seconds
- PHI redaction performed: {metadata.get("has_phi_redaction", False)}

Consider this quantitative data in your qualitative analysis.
"""

    prompt += """
CRITICAL INSTRUCTIONS:
1. Respond ONLY with valid JSON - no additional text or markdown
2. Ensure all numerical scores are integers between the specified ranges
3. Be specific and actionable in recommendations
4. Focus on healthcare workflow and patient experience optimization
5. Consider both clinical quality and operational efficiency
"""

    return prompt


@tracer.capture_method
def call_claude_for_analysis(prompt: str) -> str:
    """Call Claude Sonnet 4 via Bedrock for analysis."""
    try:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                },
            ],
        }

        response = bedrock_client.invoke_model(
            modelId=CLAUDE_MODEL_ID,
            body=json.dumps(request_body).encode("utf-8"),
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())

        # Extract text from Claude's response
        content = response_body.get("content", [])
        if content and len(content) > 0:
            return content[0].get("text", "")

        return ""

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.exception(f"Bedrock API error {error_code}: {e}")
        raise
    except Exception:
        logger.exception("Unexpected error calling Claude")
        raise


@tracer.capture_method
def parse_claude_response(response_text: str) -> dict[str, Any]:
    """Parse and validate Claude's JSON response."""
    try:
        # Clean up response text (remove markdown formatting if present)
        cleaned_text = response_text.strip()
        cleaned_text = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            cleaned_text,
            flags=re.IGNORECASE,
        )
        cleaned_text = re.sub(r"\s*```\s*$", "", cleaned_text)

        # Parse JSON
        insights = json.loads(cleaned_text)

        # Validate and provide defaults for required fields
        return {
            "consultation_type": insights.get("consultation_type", "unknown"),
            "topics_discussed": insights.get("topics_discussed", []),
            "treatments_mentioned": insights.get("treatments_mentioned", []),
            "patient_concerns": insights.get("patient_concerns", []),
            "clinical_recommendations": insights.get("clinical_recommendations", []),
            "sentiment_analysis": insights.get("sentiment_analysis", {}),
            "consultation_quality_score": _safe_int_clamp(
                insights.get("consultation_quality_score"),
                1,
                10,
                5,
            ),
            "duration_appropriateness": insights.get(
                "duration_appropriateness",
                "unknown",
            ),
            "workflow_insights": insights.get("workflow_insights", {}),
            "clinical_efficiency": insights.get("clinical_efficiency", {}),
            "patient_experience": insights.get("patient_experience", {}),
            "risk_factors": insights.get("risk_factors", []),
            "follow_up_requirements": insights.get("follow_up_requirements", []),
        }

    except json.JSONDecodeError as e:
        logger.exception(f"Failed to parse Claude JSON response: {e}")
        logger.debug(f"Raw response: {response_text[:500]}...")
        raise
    except Exception:
        logger.exception("Error parsing Claude response")
        raise


@tracer.capture_method
def calculate_enhanced_metrics(
    transcript_data: dict[str, Any],
    embeddings_data: dict[str, Any] | None,
    insights: dict[str, Any],
) -> dict[str, Any]:
    """Calculate additional metrics from transcript and embeddings data."""
    computed_metrics: dict[str, Any] = {}

    # PHI redaction metrics
    phi_info = transcript_data.get("phi_redaction", {})
    computed_metrics["phi_metrics"] = {
        "entities_found": phi_info.get("entities_found", 0),
        "entity_types": phi_info.get("entity_types", []),
        "privacy_risk_score": min(10, phi_info.get("entities_found", 0)),  # Cap at 10
    }

    # Conversation metrics from embeddings
    if embeddings_data:
        embedding_metadata = embeddings_data.get("metadata", {})
        stats = embeddings_data.get("statistics", {})

        computed_metrics["conversation_metrics"] = {
            "total_words": embedding_metadata.get("total_words", 0),
            "unique_speakers": embedding_metadata.get("unique_speakers", 0),
            "average_words_per_turn": embedding_metadata.get(
                "average_words_per_turn",
                0,
            ),
            "conversation_duration": embedding_metadata.get("conversation_duration"),
            "embedding_success_rate": stats.get("success_rate", 0),
        }

        # Calculate words per minute if duration available
        duration = embedding_metadata.get("conversation_duration")
        total_words = embedding_metadata.get("total_words", 0)
        try:
            dur = float(duration) if duration is not None else 0.0
            if dur > 0:
                computed_metrics["conversation_metrics"]["words_per_minute"] = (
                    float(total_words) * 60.0
                ) / dur
        except (TypeError, ValueError):
            pass

    # Clinical quality composite score
    quality_components = {
        "claude_quality_score": insights.get("consultation_quality_score", 5),
        "clinical_efficiency_avg": calculate_average_score(
            insights.get("clinical_efficiency", {}),
        ),
        "sentiment_score": convert_sentiment_to_score(
            insights.get("sentiment_analysis", {}),
        ),
    }

    computed_metrics["composite_quality_score"] = sum(
        quality_components.values(),
    ) / len(quality_components)
    computed_metrics["quality_components"] = quality_components

    return computed_metrics


@tracer.capture_method
def calculate_average_score(efficiency_dict: dict[str, Any]) -> float:
    """Calculate average score from efficiency metrics."""
    scores = []
    for value in efficiency_dict.values():
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and 1 <= value <= 10
        ):
            scores.append(float(value))

    return sum(scores) / len(scores) if scores else 5.0


@tracer.capture_method
def convert_sentiment_to_score(sentiment_dict: dict[str, Any]) -> float:
    """Convert sentiment analysis to numerical score."""
    sentiment_mapping = {
        "positive": 8.0,
        "neutral": 5.0,
        "negative": 2.0,
        "excellent": 10.0,
        "good": 7.0,
        "fair": 4.0,
        "poor": 1.0,
        "high": 8.0,
        "medium": 5.0,
        "low": 2.0,
    }

    scores = []
    for value in sentiment_dict.values():
        if isinstance(value, str):
            score = sentiment_mapping.get(value.lower(), 5.0)
            scores.append(score)
        elif (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and 1 <= value <= 10
        ):
            scores.append(float(value))

    return sum(scores) / len(scores) if scores else 5.0


@tracer.capture_method
def create_enrichment_document(
    consultation_id: str,
    tenant_id: str,
    transcript_data: dict[str, Any],
    embeddings_data: dict[str, Any] | None,
    insights: dict[str, Any],
    enhanced_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Create comprehensive enrichment document for gold layer storage."""
    return {
        "consultation_id": consultation_id,
        "tenant_id": tenant_id,
        "processed_at": datetime.now(UTC).isoformat(),
        "processing_pipeline_version": "1.0.0",
        # Core insights from Claude
        "clinical_insights": insights,
        # Enhanced metrics and analytics
        "enhanced_metrics": enhanced_metrics,
        "embeddings_generated": (embeddings_data.get("statistics") or {}).get(
            "embedded_turns",
            0,
        )
        if embeddings_data
        else 0,
        # Data quality and processing information
        "data_quality": {
            "has_phi_redaction": transcript_data.get("phi_redaction", {}).get(
                "entities_found",
                0,
            )
            > 0,
            "has_embeddings": embeddings_data is not None,
            "transcript_completeness": "complete"
            if transcript_data.get("conversation")
            else "partial",
            "analysis_completeness": "complete"
            if not insights.get("error")
            else "failed",
        },
        # Processing metadata
        "processing_metadata": {
            "claude_model": CLAUDE_MODEL_ID,
            "embedding_model": embeddings_data.get("embedding_model")
            if embeddings_data
            else None,
            "phi_detection_model": transcript_data.get("phi_redaction", {}).get(
                "model_version",
            ),
            "processing_stages_completed": (
                ["pii_redaction", "phi_detection"]
                + (["embedding_generation"] if embeddings_data else [])
                + ["clinical_analysis"]
            ),
        },
    }


@tracer.capture_method
def store_enrichment_document(key: str, enrichment_data: dict[str, Any]) -> None:
    """Store enrichment document in gold bucket."""
    try:
        # Use KMS encryption if key provided, otherwise SSE-S3
        sse_args = {"ServerSideEncryption": "AES256"}
        kms_key_id = os.environ.get("GOLD_BUCKET_KMS_KEY_ID", "")
        if kms_key_id:
            sse_args = {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": kms_key_id}

        s3_client.put_object(
            Bucket=GOLD_BUCKET,
            Key=key,
            Body=json.dumps(enrichment_data, indent=2),
            ContentType="application/json",
            **sse_args,
        )

        logger.info(
            "Stored enrichment document",
            extra={"bucket": GOLD_BUCKET, "key": key},
        )

    except Exception:
        logger.exception("Error storing enrichment document")
        raise


@tracer.capture_method
def update_consultation_metadata(
    consultation_id: str,
    tenant_id: str,
    insights: dict[str, Any],
    enhanced_metrics: dict[str, Any],
) -> None:
    """Update consultation metadata with enrichment results."""
    try:
        # Update DynamoDB with enrichment results
        dynamodb_client.update_item(
            TableName=CONSULTATION_METADATA_TABLE,
            Key={
                "ConsultationId": {"S": consultation_id},
            },
            UpdateExpression="SET TenantId = :tenant, QualityScore = :quality, ConsultationType = :type, EnrichmentProcessedAt = :processed_at, ProcessingStage = :stage",
            ExpressionAttributeValues={
                ":tenant": {"S": tenant_id},
                ":quality": {
                    "N": str(enhanced_metrics.get("composite_quality_score", 0)),
                },
                ":type": {"S": insights.get("consultation_type", "unknown")},
                ":processed_at": {"S": datetime.now(UTC).isoformat()},
                ":stage": {"S": "ENRICHMENT_COMPLETED"},
            },
        )

        logger.info(
            "Updated metadata for consultation",
            extra={"consultation_id": consultation_id},
        )

    except Exception as e:
        logger.exception(f"Error updating consultation metadata: {e}")
        # Don't raise - this is not critical for the pipeline


@tracer.capture_method
def publish_pipeline_completion(
    consultation_id: str,
    tenant_id: str,
    enrichment_document: dict[str, Any],
    analytics_key: str,
    embeddings_generated: int = 0,
) -> None:
    """Publish pipeline completion notification."""
    try:
        insights = enrichment_document.get("clinical_insights", {})
        enhanced = enrichment_document.get("enhanced_metrics", {})

        # Create completion message
        completion_message = {
            "eventType": "CONSULTATION_PIPELINE_COMPLETED",
            "consultationId": consultation_id,
            "tenantId": tenant_id,
            "completedAt": datetime.now(UTC).isoformat(),
            "analyticsKey": analytics_key,
            "results": {
                "qualityScore": enhanced.get("composite_quality_score", 0),
                "consultationType": insights.get("consultation_type", "unknown"),
                "topicsCount": len(insights.get("topics_discussed", [])),
                "treatmentsCount": len(insights.get("treatments_mentioned", [])),
                "phiEntitiesRedacted": enhanced.get("phi_metrics", {}).get(
                    "entities_found",
                    0,
                ),
                "embeddingsGenerated": int(embeddings_generated),
            },
            "pipelineStages": enrichment_document.get("processing_metadata", {}).get(
                "processing_stages_completed",
                [],
            ),
        }

        # Publish to SNS
        sns_client.publish(
            TopicArn=PIPELINE_COMPLETION_TOPIC_ARN,
            Message=json.dumps(completion_message, indent=2),
            Subject=f"Consultation Pipeline Completed: {consultation_id}",
        )

        logger.info(
            "Published pipeline completion for consultation",
            extra={"consultation_id": consultation_id},
        )

    except Exception:
        logger.exception("Error publishing pipeline completion")
        # Don't raise - this is not critical
