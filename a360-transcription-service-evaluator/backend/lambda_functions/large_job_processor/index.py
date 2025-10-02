"""
Large Job Processor Lambda function.

This function processes jobs that exceed token limits from SQS queue.
Based on Claude Sonnet 4 with 64,000 token output limit.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths

logger = Logger()

# Initialize AWS clients
dynamodb_client = boto3.client("dynamodb")
bedrock_client = boto3.client("bedrock-runtime")

# Environment variables
JOBS_TABLE = os.environ.get("JOBS_TABLE_NAME", "voice-actor-jobs")

# Claude Sonnet 4 configuration based on Anthropic documentation
# https://docs.anthropic.com/en/docs/about-claude/models/all-models
BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
MAX_OUTPUT_TOKENS = 64000  # Claude Sonnet 4 supports up to 64k output tokens
LARGE_JOB_THRESHOLD_WORDS = 6000  # Queue jobs above this word count


def _update_job_status(
    job_id: str,
    status: str,
    result: Dict[str, Any] = None,
    error: str = None,
) -> None:
    """Update job status in DynamoDB."""
    try:
        item = {
            "job_id": {"S": job_id},
            "status": {"S": status},
            "updated_at": {"S": datetime.now(timezone.utc).isoformat()},
        }

        if result:
            item["result"] = {"S": json.dumps(result)}

        if error:
            item["error"] = {"S": error}

        # Get existing job to preserve user_id and request_data
        existing_response = dynamodb_client.get_item(
            TableName=JOBS_TABLE, Key={"job_id": {"S": job_id}}
        )

        if "Item" in existing_response:
            existing_item = existing_response["Item"]
            if "user_id" in existing_item:
                item["user_id"] = existing_item["user_id"]
            if "request_data" in existing_item:
                item["request_data"] = existing_item["request_data"]
            if "created_at" in existing_item:
                item["created_at"] = existing_item["created_at"]

        dynamodb_client.put_item(TableName=JOBS_TABLE, Item=item)

        logger.info(
            "Job status updated",
            extra={"job_id": job_id, "status": status},
        )
    except Exception as e:
        logger.error(
            "Failed to update job status", extra={"job_id": job_id, "error": str(e)}
        )


def _get_job_details(job_id: str) -> Dict[str, Any]:
    """Get job details from DynamoDB."""
    try:
        response = dynamodb_client.get_item(
            TableName=JOBS_TABLE, Key={"job_id": {"S": job_id}}
        )

        if "Item" not in response:
            return {}

        item = response["Item"]
        result = {
            "job_id": job_id,
            "status": item["status"]["S"],
            "user_id": item.get("user_id", {}).get("S"),
        }

        if "request_data" in item:
            result["request_data"] = json.loads(item["request_data"]["S"])

        return result
    except Exception as e:
        logger.error(
            "Failed to get job details", extra={"job_id": job_id, "error": str(e)}
        )
        return {}


def _generate_with_bedrock(prompt: str, target_word_count: int) -> str:
    """Generate content using Bedrock with optimized token limits for Claude Sonnet 4."""
    try:
        # Calculate output tokens needed - Claude Sonnet 4 supports up to 64k tokens
        estimated_output_tokens = min(int(target_word_count * 1.3), MAX_OUTPUT_TOKENS)

        logger.info(
            "Starting Bedrock generation with Claude Sonnet 4",
            extra={
                "model_id": BEDROCK_MODEL_ID,
                "target_word_count": target_word_count,
                "estimated_output_tokens": estimated_output_tokens,
                "max_tokens_available": MAX_OUTPUT_TOKENS,
            },
        )

        # Use Converse API with Claude Sonnet 4
        response = bedrock_client.converse(
            modelId=BEDROCK_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={
                "maxTokens": estimated_output_tokens,
                "temperature": 0.7,
                "topP": 0.9,
            },
        )

        response_status = response.get("ResponseMetadata", {}).get(
            "HTTPStatusCode", "Unknown"
        )
        logger.info(
            "Bedrock converse successful in large job processor",
            extra={
                "response_status": response_status,
                "full_response_structure": {
                    "keys": list(response.keys()),
                    "output_keys": list(response.get("output", {}).keys())
                    if "output" in response
                    else "NO_OUTPUT",
                    "message_keys": list(
                        response.get("output", {}).get("message", {}).keys()
                    )
                    if "output" in response and "message" in response.get("output", {})
                    else "NO_MESSAGE",
                },
            },
        )

        # Validate response structure before extraction
        if "output" not in response:
            logger.error(
                "Large job processor: Bedrock response missing 'output' field",
                extra={"response_keys": list(response.keys())},
            )
            return ""

        if "message" not in response["output"]:
            logger.error(
                "Large job processor: Bedrock response missing 'message' field",
                extra={"output_keys": list(response["output"].keys())},
            )
            return ""

        # Extract content
        output_message = response["output"]["message"]

        if "content" not in output_message or not output_message["content"]:
            logger.error(
                "Large job processor: Bedrock response missing or empty 'content' field",
                extra={"message_keys": list(output_message.keys())},
            )
            return ""

        if (
            not output_message["content"][0]
            or "text" not in output_message["content"][0]
        ):
            logger.error(
                "Large job processor: Bedrock response content missing 'text' field",
                extra={
                    "content_structure": output_message["content"][0]
                    if output_message["content"]
                    else "EMPTY_CONTENT"
                },
            )
            return ""

        content = output_message["content"][0]["text"]

        logger.info(
            "Bedrock generation completed",
            extra={
                "content_word_count": len(content.split()),
                "usage": response.get("usage", {}),
                "stop_reason": response.get("stopReason", "not_provided"),
                "content_preview": content[:200] if content else "EMPTY",
            },
        )

        return content

    except Exception as e:
        logger.error(
            "Bedrock generation failed",
            extra={"error_type": type(e).__name__, "error_message": str(e)},
            exc_info=True,
        )
        return ""


def process_large_job(job_data: Dict[str, Any]) -> None:
    """Process a large job that was queued due to token limits."""
    job_id = job_data["job_id"]
    request_data = job_data["request_data"]

    try:
        logger.info(
            "Processing large job",
            extra={"job_id": job_id, "request_data": request_data},
        )

        # Update status to processing
        _update_job_status(job_id, "processing")

        # Extract parameters
        vertical = request_data.get("medical_vertical", "aesthetic_medicine")
        word_count = int(request_data.get("target_word_count", 1000))
        language = request_data.get("language", "english")
        difficulty_level = request_data.get("difficulty_level", "intermediate")
        encounter_type = request_data.get("encounter_type", "initial_consultation")

        # Build the same prompt structure as the main API
        language_instruction = ""
        if language.lower() != "english":
            language_instruction = f"\n\nLANGUAGE REQUIREMENT: Generate the ENTIRE conversation in {language.upper()}. All dialogue must be in {language} - both Doctor and Patient speech."

        encounter_instruction = ""
        encounter_display = encounter_type.replace("_", " ").title()
        if encounter_type == "initial_consultation":
            encounter_instruction = f"\n\nENCOUNTER TYPE: {encounter_display}\n- Patient is meeting the doctor for the first time regarding their concern\n- Include thorough medical history taking and initial examination\n- Focus on understanding the patient's concerns and expectations\n- Establish rapport and explain treatment options"
        elif encounter_type == "follow_up":
            encounter_instruction = f"\n\nENCOUNTER TYPE: {encounter_display}\n- Patient is returning to review progress from previous treatment\n- Discuss how they've been feeling since last visit\n- Review treatment results and any side effects\n- Adjust treatment plan as needed"
        elif encounter_type == "treatment_session":
            encounter_instruction = f"\n\nENCOUNTER TYPE: {encounter_display}\n- Patient is here for an active treatment procedure\n- Explain the procedure step-by-step during treatment\n- Include consent confirmation and comfort checks\n- Discuss immediate post-treatment care"

        prompt = f"""You are an expert medical writer creating realistic {vertical} consultation scripts for speech-to-text transcription training.

Generate a natural consultation dialogue between a Doctor and Patient for {vertical}.
{language_instruction}
{encounter_instruction}

TARGET WORD COUNT: {word_count} words EXACTLY
This is absolutely critical - you must generate exactly {word_count} words, no more, no less.

STRICT REQUIREMENTS:
1. WORD COUNT: Generate exactly {word_count} words total
2. FORMAT: Only "Doctor: " and "Patient: " lines, alternating naturally
3. STYLE: {difficulty_level} level medical terminology
4. FLOW: Natural medical consultation conversation
5. PRONUNCIATIONS: For challenging medical terms that could be misheard by speech-to-text, include phonetic pronunciation in parentheses immediately after the word

PHONETIC PRONUNCIATION GUIDELINES:
- Add phonetics for terms likely to be misunderstood by ASR systems
- Use format: "difficult_term (foh-NET-ik)"
- Focus on: drug names, anatomical terms, medical procedures with unusual spellings
- Examples: "pterygium (ter-IJ-ee-um)", "quinsy (KWIN-zee)", "phlegmon (FLEG-mon)"
- Only add pronunciations for genuinely challenging terms, not common medical words

WORD COUNT STRATEGY:
- Count as you write to reach exactly {word_count} words
- {word_count} words requires careful pacing and detailed exchanges
- Adjust sentence length and detail to hit the exact target
- Phonetic pronunciations count toward total word count

FORMAT RULES:
- Each line starts with "Doctor: " or "Patient: " only
- No stage directions, asterisks, or extra formatting
- Natural conversation flow for {vertical} consultation
- Include phonetic pronunciations where appropriate for transcription training

REMEMBER: The total word count must be exactly {word_count} words. Count carefully as you write."""

        # Generate content using Claude Sonnet 4
        content = _generate_with_bedrock(prompt, word_count)

        if not content or len(content.split()) < 50:
            error_msg = f"Failed to generate sufficient content for large job. Got {len(content.split()) if content else 0} words."
            logger.error(error_msg, extra={"job_id": job_id})
            _update_job_status(job_id, "failed", error=error_msg)
            return

        # Calculate final metrics
        actual_word_count = len(content.split())

        # Create result similar to main API
        result = {
            "success": True,
            "script_id": f"{vertical}_large_{word_count}w_{job_id[-8:]}",
            "content": content,
            "word_count": actual_word_count,
            "metadata": {
                "generation_type": "large_job_queued",
                "target_word_count": word_count,
                "actual_word_count": actual_word_count,
                "processing_method": "sqs_queue",
                "medical_vertical": vertical,
                "language": language,
                "difficulty_level": difficulty_level,
            },
            "message": f"Generated {actual_word_count} word {vertical} consultation script (large job processing)",
        }

        # Update job as completed
        _update_job_status(job_id, "completed", result=result)

        logger.info(
            "Large job completed successfully",
            extra={
                "job_id": job_id,
                "target_words": word_count,
                "actual_words": actual_word_count,
            },
        )

    except Exception as e:
        error_msg = f"Large job processing failed: {str(e)}"
        logger.error(
            error_msg,
            extra={"job_id": job_id, "error": str(e)},
            exc_info=True,
        )
        _update_job_status(job_id, "failed", error=error_msg)


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for processing large jobs from SQS."""
    try:
        logger.info("Large job processor invoked", extra={"event": event})

        # Process SQS records
        for record in event.get("Records", []):
            try:
                # Parse SQS message
                message_body = json.loads(record["body"])
                job_id = message_body["job_id"]

                logger.info(
                    "Processing SQS message",
                    extra={"job_id": job_id, "message_id": record.get("messageId")},
                )

                # Get job details from DynamoDB
                job_data = _get_job_details(job_id)
                if not job_data:
                    logger.error(f"Job {job_id} not found in DynamoDB")
                    continue

                # Process the job
                process_large_job(job_data)

            except Exception as e:
                logger.error(
                    "Failed to process SQS record",
                    extra={"record": record, "error": str(e)},
                    exc_info=True,
                )
                # Re-raise to trigger SQS retry/DLQ
                raise

        return {"statusCode": 200, "body": "Large jobs processed successfully"}

    except Exception as e:
        logger.error(
            "Large job processor failed",
            extra={"error": str(e)},
            exc_info=True,
        )
        # Re-raise to trigger SQS retry/DLQ
        raise
