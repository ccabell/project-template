"""
Voice Actor API Lambda function - Working version without problematic dependencies.
"""
import base64
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths
logger = Logger()
TERMINOLOGY_FILE = Path(__file__).parent / "medical_terminology.json"
try:
    with open(TERMINOLOGY_FILE, "r") as f:
        MEDICAL_TERMINOLOGY = json.load(f)
    logger.info(
        "Medical terminology loaded successfully",
        extra={
            "verticals": list(MEDICAL_TERMINOLOGY.keys()),
            "file_path": str(TERMINOLOGY_FILE),
        },
    )
except Exception as e:
    logger.error(
        "Failed to load medical terminology",
        extra={"error": str(e), "file_path": str(TERMINOLOGY_FILE)},
    )
    MEDICAL_TERMINOLOGY = {}
rds_data_client = boto3.client("rds-data")
s3_client = boto3.client("s3")
dynamodb_client = boto3.client("dynamodb")
bedrock_client = boto3.client("bedrock-runtime")
sqs_client = boto3.client("sqs")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")
RECORDINGS_BUCKET = os.environ.get("RECORDINGS_BUCKET")
SCRIPTS_BUCKET = os.environ.get("SCRIPTS_BUCKET")
BRANDS_TERMS_TABLE = os.environ.get("BRANDS_TERMS_TABLE_NAME")
MEDICAL_BRANDS_TABLE = os.environ.get("MEDICAL_BRANDS_TABLE_NAME")
MEDICAL_TERMS_TABLE = os.environ.get("MEDICAL_TERMS_TABLE_NAME")
JOBS_TABLE = os.environ.get("JOBS_TABLE_NAME", "voice-actor-jobs")
LARGE_JOBS_QUEUE_URL = os.environ.get("LARGE_JOBS_QUEUE_URL")
BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
MAX_OUTPUT_TOKENS = 64000  
LARGE_JOB_THRESHOLD_WORDS = 6000  
def _extract_user_id(event: Dict[str, Any]) -> str:
    """Extract Cognito user ID from JWT token for production use.
    This function extracts the 'sub' claim from Cognito JWT tokens, which is
    the stable, immutable user identifier recommended by AWS for access control.
    Reference: https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/use-user-ids-iam-policies-access-control-automation.html
    """
    headers = event.get("headers", {})
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("No valid Authorization header found")
        return "anonymous_user"
    try:
        token = auth_header.replace("Bearer ", "")
        import base64
        import json
        parts = token.split(".")
        if len(parts) != 3:
            logger.error("Invalid JWT token format")
            return "anonymous_user"
        payload = parts[1]
        padding = 4 - (len(payload) % 4)
        if padding != 4:
            payload += "=" * padding
        decoded_payload = base64.urlsafe_b64decode(payload)
        token_data = json.loads(decoded_payload)
        cognito_user_id = token_data.get("sub")
        if not cognito_user_id:
            logger.error(
                "No 'sub' claim found in JWT token",
                extra={"available_claims": list(token_data.keys())},
            )
            return "anonymous_user"
        import re
        if not re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            cognito_user_id,
        ):
            logger.warning(
                "Invalid Cognito user ID format", extra={"user_id": cognito_user_id}
            )
            return "anonymous_user"
        logger.info(
            "Successfully extracted Cognito user ID",
            extra={
                "user_id": cognito_user_id,
                "token_issuer": token_data.get("iss"),
                "token_audience": token_data.get("aud"),
                "username": token_data.get("cognito:username"),
                "email": token_data.get("email"),
            },
        )
        return cognito_user_id
    except json.JSONDecodeError as e:
        logger.error("Failed to decode JWT payload as JSON", extra={"error": str(e)})
    except Exception as e:
        logger.error(
            "Failed to extract Cognito user ID from JWT token",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
    logger.warning(
        "Using anonymous user fallback - this should not happen in production with proper Cognito authentication"
    )
    return "anonymous_user"
def _generate_with_bedrock(prompt: str, target_word_count: int = 1000) -> str:
    """Generate content using Bedrock Converse API with Claude Sonnet 4 token limits."""
    try:
        estimated_output_tokens = int(
            target_word_count * 1.3
        )  
        max_tokens = min(estimated_output_tokens + 1000, MAX_OUTPUT_TOKENS)  
        max_tokens = max(max_tokens, 1000)
        logger.info(
            "Starting Bedrock generation with Claude Sonnet 4",
            extra={
                "model_id": BEDROCK_MODEL_ID,
                "bedrock_region": bedrock_client.meta.region_name,
                "prompt_length": len(prompt),
                "target_word_count": target_word_count,
                "estimated_output_tokens": estimated_output_tokens,
                "max_tokens_allocated": max_tokens,
                "max_output_tokens_available": MAX_OUTPUT_TOKENS,
            },
        )
        response = bedrock_client.converse(
            modelId=BEDROCK_MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={
                "maxTokens": max_tokens,
                "temperature": 1.0,  
                "topP": 0.85,  
            },
        )
        response_status = response.get("ResponseMetadata", {}).get(
            "HTTPStatusCode", "Unknown"
        )
        logger.info(
            "Bedrock converse successful",
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
        if "output" not in response:
            logger.error(
                "Bedrock response missing 'output' field",
                extra={"response_keys": list(response.keys())},
            )
            return ""
        if "message" not in response["output"]:
            logger.error(
                "Bedrock response missing 'message' field",
                extra={"output_keys": list(response["output"].keys())},
            )
            return ""
        output_message = response["output"]["message"]
        if "content" not in output_message or not output_message["content"]:
            logger.error(
                "Bedrock response missing or empty 'content' field",
                extra={"message_keys": list(output_message.keys())},
            )
            return ""
        if (
            not output_message["content"][0]
            or "text" not in output_message["content"][0]
        ):
            logger.error(
                "Bedrock response content missing 'text' field",
                extra={
                    "content_structure": output_message["content"][0]
                    if output_message["content"]
                    else "EMPTY_CONTENT"
                },
            )
            return ""
        content = output_message["content"][0]["text"]
        logger.info(
            "Parsing Bedrock response",
            extra={
                "output_message_role": output_message["role"],
                "raw_content_length": len(content),
                "raw_content_preview": content[:200],
                "usage": response.get("usage", {}),
                "stop_reason": response.get("stopReason", "not_provided"),
            },
        )
        logger.info(
            "Using raw Bedrock output without cleaning",
            extra={
                "content_word_count": len(content.split()),
                "content_preview": content[:200],
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
def _generate_script_title(
    vertical: str,
    encounter_type: str,
    word_count: int,
    selected_terms: list,
    selected_brands: list
) -> str:
    """Generate descriptive script title using AI based on script parameters."""
    try:
        vertical_display = vertical.replace("_", " ").title()
        encounter_display = encounter_type.replace("_", " ").title()
        terms_desc = ""
        if selected_terms:
            terms_desc = f", featuring {', '.join(selected_terms[:3])}"
            if len(selected_terms) > 3:
                terms_desc += f" and {len(selected_terms) - 3} more terms"
        brands_desc = ""
        if selected_brands:
            brands_desc = f", discussing {', '.join(selected_brands[:2])}"
            if len(selected_brands) > 2:
                brands_desc += f" and {len(selected_brands) - 2} more products"
        title_prompt = f"""Generate a concise, professional title for a medical consultation script with these parameters:
- Medical Complexity: Based on selected terminology
- Word Count: {word_count:,} words{terms_desc}{brands_desc}
The title should be:
1. Professional and descriptive (8-12 words maximum)
2. Focus on the medical content and procedures discussed
3. Suitable for healthcare professionals
4. Clear about the consultation focus
Examples of good titles:
- "Post-Treatment Assessment and Care Planning"
- "Advanced Dermal Filler Technique Discussion"
- "Comprehensive Skin Analysis and Treatment Review"
Generate ONLY the title text, nothing else."""
        title_content = _generate_with_bedrock(title_prompt, target_word_count=15)
        if title_content and len(title_content.strip()) > 0:
            title = title_content.strip().strip('"').strip("'")
            return title
        else:
            return f"Medical Consultation Script ({word_count:,} words)"
    except Exception as e:
        logger.warning(
            "Failed to generate AI script title, using fallback",
            extra={"error": str(e), "vertical": vertical, "encounter_type": encounter_type}
        )
        return f"Medical Consultation Script ({word_count:,} words)"
def _store_job_status(
    job_id: str,
    status: str,
    user_id: str = None,
    request_data: Dict[str, Any] = None,
    result: Dict[str, Any] = None,
    error: str = None,
    script_title: str = None,
) -> None:
    """Store job status in DynamoDB, preserving existing fields when updating."""
    try:
        existing_item = {}
        if status != "processing":  
            try:
                response = dynamodb_client.get_item(
                    TableName=JOBS_TABLE, Key={"job_id": {"S": job_id}}
                )
                if "Item" in response:
                    existing_item = response["Item"]
            except Exception as e:
                logger.warning(f"Could not fetch existing job for update: {e}")
        item = {
            "job_id": {"S": job_id},
            "status": {"S": status},
            "updated_at": {"S": datetime.now(timezone.utc).isoformat()},
            "ttl": {
                "N": str(int(datetime.now(timezone.utc).timestamp()) + (7 * 86400))
            },  
        }
        if user_id:
            item["user_id"] = {"S": user_id}
        elif existing_item.get("user_id"):
            item["user_id"] = existing_item["user_id"]
        if request_data:
            item["request_data"] = {"S": json.dumps(request_data)}
        elif existing_item.get("request_data"):
            item["request_data"] = existing_item["request_data"]
        if existing_item.get("created_at"):
            item["created_at"] = existing_item["created_at"]
        elif status == "processing":  
            item["created_at"] = {"S": datetime.now(timezone.utc).isoformat()}
        if result:
            item["result"] = {"S": json.dumps(result)}
        if error:
            item["error"] = {"S": error}
        if script_title:
            item["script_title"] = {"S": script_title}
        dynamodb_client.put_item(TableName=JOBS_TABLE, Item=item)
        logger.info(
            "Job status stored with field preservation",
            extra={
                "job_id": job_id,
                "status": status,
                "user_id": user_id or existing_item.get("user_id", {}).get("S"),
                "preserved_fields": list(existing_item.keys()) if existing_item else [],
            },
        )
    except Exception as e:
        logger.error(
            "Failed to store job status", extra={"job_id": job_id, "error": str(e)}
        )
def _get_job_status(job_id: str) -> Dict[str, Any]:
    """Get job status from DynamoDB."""
    try:
        response = dynamodb_client.get_item(
            TableName=JOBS_TABLE, Key={"job_id": {"S": job_id}}
        )
        if "Item" not in response:
            return {"status": "not_found"}
        item = response["Item"]
        result = {
            "job_id": job_id,
            "status": item["status"]["S"],
            "updated_at": item["updated_at"]["S"],
        }
        if "created_at" in item:
            result["created_at"] = item["created_at"]["S"]
        if "request_data" in item:
            result["request_data"] = json.loads(item["request_data"]["S"])
        if "result" in item:
            result["result"] = json.loads(item["result"]["S"])
        if "error" in item:
            result["error"] = item["error"]["S"]
        if "script_title" in item:
            result["script_title"] = item["script_title"]["S"]
        return result
    except Exception as e:
        logger.error(
            "Failed to get job status", extra={"job_id": job_id, "error": str(e)}
        )
        return {"status": "error", "error": str(e)}
def _get_user_jobs(user_id: str) -> List[Dict[str, Any]]:
    """Get all jobs for a user from DynamoDB using GSI."""
    try:
        logger.info(
            "USER_ID_DEBUG: Starting job lookup",
            extra={
                "user_id_parameter": user_id,
                "user_id_type": type(user_id).__name__,
                "user_id_length": len(user_id) if user_id else 0,
            }
        )
        # Temporarily force fallback to scan to test if GSI is the issue
        raise Exception("TEMP: Forcing fallback to scan to test GSI issue")
        
        response = dynamodb_client.query(
            TableName=JOBS_TABLE,
            IndexName="UserIndex",
            KeyConditionExpression="user_id = :user_id",
            ExpressionAttributeValues={":user_id": {"S": user_id}},
            ScanIndexForward=False,  
        )
        jobs = []
        for item in response.get("Items", []):
            job_data = {
                "job_id": item["job_id"]["S"],
                "status": item["status"]["S"],
                "updated_at": item["updated_at"]["S"],
            }
            if "created_at" in item:
                job_data["created_at"] = item["created_at"]["S"]
            if "request_data" in item:
                job_data["request_data"] = json.loads(item["request_data"]["S"])
            if "result" in item:
                job_data["result"] = json.loads(item["result"]["S"])
            if "error" in item:
                job_data["error"] = item["error"]["S"]
            if "script_title" in item:
                job_data["script_title"] = item["script_title"]["S"]
            jobs.append(job_data)
        logger.info(
            "Retrieved user jobs via GSI",
            extra={
                "user_id": user_id, 
                "job_count": len(jobs), 
                "method": "GSI_query",
                "sample_job": jobs[0] if jobs else None,
                "script_title_fields": [j.get("script_title") for j in jobs[:3]]
            },
        )
        return jobs
    except Exception as e:
        logger.error(
            "Failed to get user jobs via GSI",
            extra={"user_id": user_id, "error": str(e)},
        )
        try:
            logger.warning(
                "Falling back to scan operation for user jobs",
                extra={"user_id": user_id},
            )
            response = dynamodb_client.scan(
                TableName=JOBS_TABLE,
                FilterExpression="user_id = :user_id",
                ExpressionAttributeValues={":user_id": {"S": user_id}},
            )
            
            logger.info(
                "SCAN DEBUG: Raw DynamoDB response",
                extra={
                    "user_id": user_id,
                    "total_items": len(response.get("Items", [])),
                    "raw_items_sample": response.get("Items", [])[:2] if response.get("Items") else [],
                }
            )
            
            jobs = []
            for idx, item in enumerate(response.get("Items", [])):
                logger.info(
                    f"SCAN DEBUG: Processing item {idx}",
                    extra={
                        "item_keys": list(item.keys()),
                        "has_script_title": "script_title" in item,
                        "script_title_raw": item.get("script_title"),
                        "job_id": item.get("job_id", {}).get("S", "unknown"),
                    }
                )
                
                job_data = {
                    "job_id": item["job_id"]["S"],
                    "status": item["status"]["S"],
                    "updated_at": item["updated_at"]["S"],
                }
                if "created_at" in item:
                    job_data["created_at"] = item["created_at"]["S"]
                if "request_data" in item:
                    job_data["request_data"] = json.loads(item["request_data"]["S"])
                if "result" in item:
                    job_data["result"] = json.loads(item["result"]["S"])
                if "error" in item:
                    job_data["error"] = item["error"]["S"]
                if "script_title" in item:
                    job_data["script_title"] = item["script_title"]["S"]
                    logger.info(
                        f"SCAN DEBUG: Added script_title to job_data",
                        extra={
                            "job_id": job_data["job_id"],
                            "script_title_value": job_data["script_title"],
                        }
                    )
                else:
                    logger.warning(
                        f"SCAN DEBUG: No script_title field found in DynamoDB item",
                        extra={
                            "job_id": job_data["job_id"],
                            "available_keys": list(item.keys()),
                        }
                    )
                jobs.append(job_data)
            jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            logger.info(
                "Retrieved user jobs via fallback scan",
                extra={
                    "user_id": user_id, 
                    "job_count": len(jobs),
                    "sample_job": jobs[0] if jobs else None,
                    "script_title_fields": [j.get("script_title") for j in jobs[:3]],
                    "final_jobs_with_titles": [(j["job_id"][:8], j.get("script_title", "MISSING")) for j in jobs[:3]]
                },
            )
            return jobs
        except Exception as fallback_error:
            logger.error(
                "Both GSI query and fallback scan failed",
                extra={
                    "user_id": user_id,
                    "gsi_error": str(e),
                    "scan_error": str(fallback_error),
                },
            )
            return []

def _get_all_jobs() -> List[Dict[str, Any]]:
    """Get all jobs from DynamoDB for admin users."""
    try:
        logger.info("Getting all jobs for admin user")
        
        # Scan all jobs without user filter
        response = dynamodb_client.scan(
            TableName=JOBS_TABLE,
            FilterExpression="attribute_not_exists(assignment_id)",  # Exclude assignments, only get jobs
        )
        
        jobs = []
        for idx, item in enumerate(response.get("Items", [])):
            logger.info(f"DEBUG _get_all_jobs item {idx}", extra={
                "job_id": item.get("job_id", {}).get("S", "unknown"),
                "has_script_title": "script_title" in item,
                "script_title_value": item.get("script_title", {}).get("S", "NOT_FOUND"),
                "all_keys": list(item.keys())
            })
            
            job_data = {
                "job_id": item["job_id"]["S"],
                "status": item["status"]["S"], 
                "updated_at": item["updated_at"]["S"],
            }
            if "created_at" in item:
                job_data["created_at"] = item["created_at"]["S"]
            if "user_id" in item:
                job_data["user_id"] = item["user_id"]["S"]
            if "request_data" in item:
                job_data["request_data"] = json.loads(item["request_data"]["S"])
            if "result" in item:
                job_data["result"] = json.loads(item["result"]["S"])
            if "error" in item:
                job_data["error"] = item["error"]["S"]
            if "script_title" in item:
                job_data["script_title"] = item["script_title"]["S"]
                logger.info(f"DEBUG _get_all_jobs added script_title", extra={
                    "job_id": job_data["job_id"],
                    "script_title": job_data["script_title"]
                })
            else:
                logger.warning(f"DEBUG _get_all_jobs missing script_title", extra={
                    "job_id": job_data["job_id"],
                    "available_keys": list(item.keys())
                })
                
            jobs.append(job_data)
            
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        logger.info(
            "Retrieved all jobs for admin",
            extra={"job_count": len(jobs), "sample_titles": [j.get("script_title", "NO_TITLE") for j in jobs[:3]]}
        )
        
        return jobs
    except Exception as e:
        logger.error("Failed to get all jobs", extra={"error": str(e)})
        return []

def _invoke_async_processing(job_id: str, original_request: Dict[str, Any]) -> None:
    """Invoke async processing by calling Lambda function asynchronously."""
    try:
        lambda_client = boto3.client("lambda")
        async_payload = {
            "httpMethod": "POST",
            "path": "/api/generate/ground-truth",
            "body": json.dumps(
                {
                    **original_request,
                    "_internal_async_processing": True,
                    "_job_id": job_id,
                }
            ),
        }
        function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        if function_name:
            lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="Event",  
                Payload=json.dumps(async_payload),
            )
            logger.info("Async processing invoked", extra={"job_id": job_id})
        else:
            logger.warning(
                "Cannot invoke async processing - function name not available"
            )
    except Exception as e:
        logger.error(
            "Failed to invoke async processing",
            extra={"job_id": job_id, "error": str(e)},
        )
        _store_job_status(
            job_id, "failed", error=f"Failed to start processing: {str(e)}"
        )
def get_job_status(job_id: str, event: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get job status endpoint with user validation."""
    try:
        if not job_id or job_id == "undefined":
            return create_response(400, {"error": "Invalid job ID"})
        user_id = _extract_user_id(event) if event else "anonymous_user"
        job_status = _get_job_status(job_id)
        if job_status.get("status") == "not_found":
            logger.warning(
                "Job not found in DynamoDB",
                extra={"job_id": job_id, "requesting_user": user_id},
            )
            return create_response(404, {"error": "Job not found"})
        job_data = _get_job_details(job_id)
        if job_data:
            job_owner = job_data.get("user_id")
            logger.info(
                "Job access attempt",
                extra={
                    "job_id": job_id,
                    "requesting_user": user_id,
                    "job_owner": job_owner,
                    "job_status": job_data.get("status"),
                    "user_match": job_owner == user_id,
                },
            )
            if job_owner != user_id:
                logger.warning(
                    "Unauthorized job access attempt - user mismatch",
                    extra={
                        "requesting_user": user_id,
                        "job_owner": job_owner,
                        "job_id": job_id,
                        "note": "Jobs created before authentication are not accessible",
                    },
                )
                return create_response(
                    404, {"error": "Job not found"}
                )  
        return create_response(200, job_status)
    except Exception as e:
        logger.error(
            "Error getting job status", extra={"job_id": job_id, "error": str(e)}
        )
        return create_response(500, {"error": "Failed to get job status"})
def _get_job_details(job_id: str) -> Dict[str, Any]:
    """Get job details including user_id for validation."""
    try:
        response = dynamodb_client.get_item(
            TableName=JOBS_TABLE, Key={"job_id": {"S": job_id}}
        )
        if "Item" not in response:
            return {}
        item = response["Item"]
        return {
            "job_id": job_id,
            "user_id": item.get("user_id", {}).get("S"),
            "status": item["status"]["S"],
        }
    except Exception as e:
        logger.error(
            "Failed to get job details", extra={"job_id": job_id, "error": str(e)}
        )
        return {}
def get_user_jobs(event: Dict[str, Any]) -> Dict[str, Any]:
    """Get all jobs for the current user."""
    try:
        user_id = _extract_user_id(event)
        
        # Check if user has admin groups to bypass user filtering
        headers = event.get("headers", {})
        auth_header = headers.get("Authorization") or headers.get("authorization")
        user_groups = []
        
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.replace("Bearer ", "")
                parts = token.split(".")
                if len(parts) == 3:
                    payload = parts[1]
                    padding = 4 - (len(payload) % 4)
                    if padding != 4:
                        payload += "=" * padding
                    decoded_payload = base64.urlsafe_b64decode(payload)
                    token_data = json.loads(decoded_payload)
                    user_groups = token_data.get("cognito:groups", [])
            except Exception:
                pass
        
        # TEMP DEBUG: Force admin path to test _get_all_jobs function
        logger.info("TEMP DEBUG: Forcing admin path", extra={"user_id": user_id, "groups": user_groups})
        jobs = _get_all_jobs()  # Get all jobs for admin
        logger.info("TEMP DEBUG: Admin jobs retrieved", extra={
            "job_count": len(jobs), 
            "sample_job_titles": [j.get("script_title", "NO_TITLE") for j in jobs[:3]],
            "sample_job_ids": [j.get("job_id", "NO_ID") for j in jobs[:3]]
        })
        
        # Original logic commented for debugging
        # Admin users see all jobs, regular users see only their own
        # if "admin" in user_groups:
        #     logger.info("Admin user detected - returning all jobs", extra={"user_id": user_id, "groups": user_groups})
        #     jobs = _get_all_jobs()  # Get all jobs for admin
        #     logger.info("Admin jobs retrieved", extra={
        #         "job_count": len(jobs), 
        #         "sample_job_titles": [j.get("script_title", "NO_TITLE") for j in jobs[:3]],
        #         "sample_job_ids": [j.get("job_id", "NO_ID") for j in jobs[:3]]
        #     })
        # else:
        #     logger.info("Regular user - filtering by user_id", extra={"user_id": user_id, "groups": user_groups})
        #     jobs = _get_user_jobs(user_id)
            
        return create_response(
            200, {"user_id": user_id, "jobs": jobs, "total_count": len(jobs)}
        )
    except Exception as e:
        logger.error("Error getting user jobs", extra={"error": str(e)})
        return create_response(500, {"error": "Failed to get user jobs"})
def process_ground_truth_async(body: Dict[str, Any]) -> Dict[str, Any]:
    """Process ground truth generation asynchronously."""
    job_id = body.get("_job_id")
    if not job_id:
        logger.error("No job ID provided for async processing")
        return create_response(400, {"error": "No job ID provided"})
    try:
        logger.info("Starting async ground truth processing", extra={"job_id": job_id})
        clean_body = {k: v for k, v in body.items() if not k.startswith("_")}
        result = generate_ground_truth_sync(clean_body)
        if result.get("statusCode") == 200:
            result_data = json.loads(result["body"])
            script_title = result_data.get("script_title", "")
            _store_job_status(job_id, "completed", result=result_data, script_title=script_title)
            logger.info(
                "Async processing completed successfully", extra={"job_id": job_id}
            )
        else:
            error_data = json.loads(result.get("body", "{}"))
            error_message = error_data.get("error", "Unknown error")
            _store_job_status(job_id, "failed", error=error_message)
            logger.error(
                "Async processing failed",
                extra={"job_id": job_id, "error": error_message},
            )
        return create_response(200, {"message": "Async processing completed"})
    except Exception as e:
        logger.error(
            "Error in async processing", extra={"job_id": job_id, "error": str(e)}
        )
        _store_job_status(job_id, "failed", error=str(e))
        return create_response(500, {"error": "Async processing failed"})
def _queue_large_job(job_id: str, request_data: Dict[str, Any]) -> bool:
    """Queue a large job to SQS for background processing."""
    try:
        if not LARGE_JOBS_QUEUE_URL:
            logger.error("Large jobs queue URL not configured")
            return False
        message_body = {
            "job_id": job_id,
            "request_data": request_data,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }
        response = sqs_client.send_message(
            QueueUrl=LARGE_JOBS_QUEUE_URL,
            MessageBody=json.dumps(message_body),
            MessageAttributes={
                "job_id": {"StringValue": job_id, "DataType": "String"},
                "word_count": {
                    "StringValue": str(request_data.get("target_word_count", 0)),
                    "DataType": "Number",
                },
            },
        )
        logger.info(
            "Large job queued successfully",
            extra={
                "job_id": job_id,
                "queue_url": LARGE_JOBS_QUEUE_URL,
                "message_id": response.get("MessageId"),
                "word_count": request_data.get("target_word_count"),
            },
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to queue large job",
            extra={"job_id": job_id, "error": str(e)},
            exc_info=True,
        )
        return False
def generate_ground_truth(
    body: Dict[str, Any], event: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Generate ground truth script - returns immediately with job ID for async processing."""
    try:
        user_id = _extract_user_id(event) if event else "anonymous_user"
        job_id = (
            f"gt_{uuid.uuid4().hex[:12]}_{int(datetime.now(timezone.utc).timestamp())}"
        )
        word_count_raw = body.get("target_word_count", body.get("word_count", 600))
        word_count = (
            int(word_count_raw)
            if isinstance(word_count_raw, (str, int, float))
            else 600
        )
        logger.info(
            "Creating new ground truth generation job",
            extra={
                "job_id": job_id,
                "user_id": user_id,
                "word_count": word_count,
                "large_job_threshold": LARGE_JOB_THRESHOLD_WORDS,
            },
        )
        is_large_job = word_count >= LARGE_JOB_THRESHOLD_WORDS
        if is_large_job and LARGE_JOBS_QUEUE_URL:
            _store_job_status(job_id, "queued", user_id=user_id, request_data=body)
            queue_success = _queue_large_job(job_id, body)
            if queue_success:
                return create_response(
                    202,
                    {
                        "job_id": job_id,
                        "status": "queued",
                        "message": f"Large job ({word_count:,} words) queued for background processing. Check status using /api/jobs/{job_id}",
                        "poll_url": f"/api/jobs/{job_id}",
                        "processing_method": "background_queue",
                        "estimated_time": "2-10 minutes depending on request size",
                        "word_count": word_count,
                    },
                )
            else:
                logger.warning(
                    f"Failed to queue large job {job_id}, falling back to direct processing"
                )
                _store_job_status(
                    job_id, "processing", user_id=user_id, request_data=body
                )
        else:
            _store_job_status(job_id, "processing", user_id=user_id, request_data=body)
        _invoke_async_processing(job_id, body)
        return create_response(
            202,
            {
                "job_id": job_id,
                "status": "queued" if is_large_job else "processing",
                "message": f"Ground truth generation started ({word_count:,} words). Use /api/jobs/{job_id} to check status.",
                "poll_url": f"/api/jobs/{job_id}",
                "processing_method": "background_queue"
                if is_large_job
                else "lambda_async",
                "word_count": word_count,
            },
        )
    except Exception as e:
        logger.error(
            "Error creating ground truth generation job", extra={"error": str(e)}
        )
        return create_response(500, {"error": f"Failed to start generation: {str(e)}"})
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def get_readers(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get available readers from Cognito User Pool."""
    logger.info("DEBUG: get_readers function called")
    try:
        user_id = _extract_user_id(event)
        user_groups = []
        authorizer_context = event.get("requestContext", {}).get("authorizer", {})
        if authorizer_context and "claims" in authorizer_context:
            claims = authorizer_context["claims"]
            groups = claims.get("cognito:groups", "")
            user_groups = groups.split(",") if groups else []
            logger.info("Using API Gateway authorizer claims", extra={
                "groups_raw": groups,
                "user_groups": user_groups,
                "claims_keys": list(claims.keys())
            })
        else:
            logger.info("Using manual JWT parsing (direct Lambda invocation)")
            auth_header = event.get("headers", {}).get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return create_response(401, {"error": "Invalid authorization header"})
            token = auth_header[7:]  
            try:
                parts = token.split('.')
                if len(parts) != 3:
                    return create_response(401, {"error": "Invalid JWT token format"})
                payload = parts[1]
                padding = 4 - (len(payload) % 4)
                if padding != 4:
                    payload += "=" * padding
                import base64
                decoded_payload = base64.urlsafe_b64decode(payload)
                token_data = json.loads(decoded_payload)
                groups = token_data.get("cognito:groups", [])
                user_groups = groups if isinstance(groups, list) else []
            except Exception as e:
                logger.error("Failed to parse JWT token", extra={"error": str(e)})
                return create_response(401, {"error": "Invalid JWT token"})
        allowed_groups = ["admin", "evaluator"]
        has_permission = any(group in user_groups for group in allowed_groups)
        logger.info("DEBUG: Checking reader access permission", extra={
            "user_groups": user_groups,
            "allowed_groups": allowed_groups,
            "has_permission": has_permission,
            "requesting_user": user_id
        })
        if not has_permission:
            logger.warning("Unauthorized user attempted to access readers", extra={
                "user_groups": user_groups,
                "requesting_user": user_id,
                "required_groups": allowed_groups
            })
            return create_response(403, {"error": "Only admins and evaluators can view available readers"})
        cognito_client = boto3.client("cognito-idp")
        user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
        if not user_pool_id:
            logger.error("COGNITO_USER_POOL_ID not configured")
            return create_response(500, {"error": "Cognito configuration missing"})
        logger.info("Fetching users from Cognito", extra={"user_pool_id": user_pool_id})
        try:
            response = cognito_client.list_users(
                UserPoolId=user_pool_id,
                Limit=60,  
                AttributesToGet=[
                    'email',
                    'email_verified',
                    'given_name',
                    'family_name',
                    'sub'
                ]
            )
            logger.info("Successfully fetched users from Cognito", extra={"user_count": len(response.get("Users", []))})
        except Exception as e:
            logger.error("Failed to list users from Cognito", extra={"error": str(e)})
            return create_response(500, {"error": "Failed to retrieve users"})
        readers = []
        for user in response.get("Users", []):
            try:
                attributes = {}
                for attr in user.get("Attributes", []):
                    attributes[attr["Name"]] = attr["Value"]
                username = user.get("Username", "")
                email = attributes.get("email", "")
                given_name = attributes.get("given_name", "")
                family_name = attributes.get("family_name", "")
                logger.info(
                    "Processing user for readers list",
                    extra={
                        "username": username,
                        "email": email,
                        "given_name": given_name,
                        "family_name": family_name,
                        "all_attributes": list(attributes.keys())
                    }
                )
                if given_name and family_name:
                    name = f"{given_name} {family_name}"
                elif given_name:
                    name = given_name
                elif family_name:
                    name = family_name
                else:
                    name = email.split('@')[0] if email else "Unknown"
                is_active = user.get("UserStatus") == "CONFIRMED"
                try:
                    groups_response = cognito_client.admin_list_groups_for_user(
                        UserPoolId=user_pool_id,
                        Username=username
                    )
                    user_groups = [group["GroupName"] for group in groups_response.get("Groups", [])]
                except Exception as e:
                    logger.warning("Failed to get groups for user", extra={"username": username, "error": str(e)})
                    user_groups = []
                is_reader = "reader" in user_groups
                logger.info("Checking user eligibility", extra={
                    "username": username,
                    "user_groups": user_groups,
                    "is_active": is_active,
                    "user_name": name,
                    "is_reader": is_reader,
                    "meets_criteria": is_reader and is_active
                })
                if is_reader and is_active:
                    reader_data = {
                        "cognito_id": username,
                        "email": email,
                        "name": name,
                        "is_active": is_active
                    }
                    readers.append(reader_data)
                    logger.info("SUCCESSFULLY added user to readers list", extra={
                        "reader_cognito_id": reader_data["cognito_id"],
                        "reader_email": reader_data["email"],
                        "reader_name": reader_data["name"],
                        "reader_is_active": reader_data["is_active"],
                        "total_readers_now": len(readers)
                    })
                else:
                    logger.warning("User NOT added to readers list", extra={
                        "username": username,
                        "email": email,
                        "is_reader": is_reader,
                        "is_active": is_active,
                        "user_status": user.get("UserStatus"),
                        "reason": "not_reader" if not is_reader else ("not_active" if not is_active else "unknown")
                    })
            except Exception as e:
                logger.warning("Failed to process user", extra={"user": str(user), "error": str(e)})
                continue
        logger.info(
            f"Retrieved {len(readers)} available readers",
            extra={"requesting_user": user_id, "reader_count": len(readers)}
        )
        logger.info("DEBUG: get_readers function completing", extra={
            "final_readers_count": len(readers),
            "final_readers_data": readers,
            "requesting_user": user_id,
            "user_pool_id": user_pool_id,
            "total_users_processed": len(response.get("Users", []))
        })
        return create_response(200, readers)
    except Exception as e:
        logger.error("Failed to get readers", extra={"error": str(e)})
        return create_response(500, {"error": "Failed to retrieve readers"})
def get_my_assignments(event: Dict[str, Any]) -> Dict[str, Any]:
    """Get assignments for the current user (reader)."""
    try:
        user_id = _extract_user_id(event)
        logger.info("Getting assignments for user", extra={"user_id": user_id})
        assignment_table = JOBS_TABLE or "assignments"  
        response = dynamodb_client.scan(
            TableName=assignment_table,
            FilterExpression="assigned_to_cognito_id = :user_id",
            ExpressionAttributeValues={":user_id": {"S": user_id}},
        )
        assignments = []
        for item in response.get("Items", []):
            if "assignment_id" in item:
                assignment_id = item.get("assignment_id", {}).get("S", "")
                script_job_id = item.get("script_job_id", {}).get("S", "")
                if not assignment_id:
                    logger.warning("Assignment missing assignment_id", extra={"item": str(item)})
                    continue
                assignment_data = {
                    "assignment_id": assignment_id,
                    "job_id": script_job_id,
                    "script_id": script_job_id,
                    "script_title": f"Script {script_job_id[:8] if script_job_id else 'unknown'}",
                    "assigned_by_cognito_id": item.get("assigned_by_cognito_id", {}).get("S", ""),
                    "assigned_to_cognito_id": item["assigned_to_cognito_id"]["S"],
                    "assignment_type": item["assignment_type"]["S"],
                    "priority": int(item.get("priority", {}).get("N", "2")),
                    "notes": item.get("notes", {}).get("S", ""),
                    "status": item["status"]["S"],
                    "created_at": item.get("created_at", {}).get("S", ""),
                    "updated_at": item.get("updated_at", {}).get("S", ""),
                }
                assignments.append(assignment_data)
        for assignment in assignments:
            script_job_id = assignment.get("job_id", "")  
            if script_job_id:
                try:
                    job_response = dynamodb_client.get_item(
                        TableName=JOBS_TABLE,  
                        Key={"job_id": {"S": script_job_id}}  
                    )
                    if "Item" in job_response:
                        job_item = job_response["Item"]
                        word_count = 1000  
                        if "result" in job_item:
                            try:
                                result_json = json.loads(job_item["result"]["S"])
                                word_count = result_json.get("word_count", 1000)
                            except (json.JSONDecodeError, KeyError):
                                pass
                        if word_count == 1000 and "word_count" in job_item:
                            word_count = int(job_item.get("word_count", {}).get("N", "1000"))
                        assignment["word_count"] = word_count
                        if "script_title" in job_item:
                            assignment["script_title"] = job_item["script_title"]["S"]
                    else:
                        assignment["word_count"] = 1000  
                except Exception as e:
                    logger.warning(f"Failed to get job details for script job {script_job_id}: {str(e)}")
                    assignment["word_count"] = 1000  
            else:
                assignment["word_count"] = 1000  
        assignments.sort(key=lambda x: (
            -x.get("priority", 2),  
            -x.get("word_count", 1000),  
            x.get("created_at", "")  
        ))
        incomplete_statuses = ["assigned", "in_progress"]
        incomplete_assignments = [a for a in assignments if a.get("status") in incomplete_statuses]
        if incomplete_assignments:
            highest_priority = max(a.get("priority", 2) for a in incomplete_assignments)
            for assignment in assignments:
                assignment_priority = assignment.get("priority", 2)
                assignment_status = assignment.get("status", "assigned")
                if (assignment_priority < highest_priority and 
                    assignment_status in incomplete_statuses):
                    assignment["blocked"] = True
                    priority_text = "High" if highest_priority == 3 else "Medium" if highest_priority == 2 else "Low"
                    assignment["blocked_reason"] = f"{priority_text} priority assignments must be completed first"
                else:
                    assignment["blocked"] = False
                    assignment["blocked_reason"] = None
        else:
            for assignment in assignments:
                assignment["blocked"] = False
                assignment["blocked_reason"] = None
        logger.info(
            "Retrieved assignments for user with priority ordering and blocking logic",
            extra={
                "user_id": user_id,
                "assignment_count": len(assignments)
            }
        )
        return create_response(200, assignments)
    except Exception as e:
        logger.error(
            "Failed to get user assignments",
            extra={"error": str(e), "user_id": _extract_user_id(event)}
        )
        return create_response(500, {"error": "Failed to retrieve assignments"})
def get_all_assignments(event):
    """Get all assignments for admin users with full details including reader names and script titles."""
    try:
        logger.info("Getting all assignments for admin user")
        user_id = _extract_user_id(event)
        if not user_id:
            return create_response(401, {"error": "User ID not found"})
        query_params = event.get("queryStringParameters") or {}
        limit = int(query_params.get("limit", "100"))
        assignment_table = JOBS_TABLE or "assignments"
        scan_params = {
            "TableName": assignment_table,
            "FilterExpression": "attribute_exists(assignment_id)",  
            "Limit": limit
        }
        logger.debug("Scanning for all assignments", extra={"params": scan_params})
        response = dynamodb_client.scan(**scan_params)
        assignments = []
        if "Items" in response and response["Items"]:
            for item in response["Items"]:
                assignment_id = item.get("assignment_id", {}).get("S", "")
                script_job_id = item.get("script_job_id", {}).get("S", "")  
                if not assignment_id:
                    logger.warning("Assignment missing assignment_id", extra={"item": str(item)})
                    continue
                assignment_data = {
                    "assignment_id": assignment_id,
                    "job_id": script_job_id,  
                    "script_id": script_job_id,  
                    "script_title": f"Script {script_job_id[:8] if script_job_id else 'unknown'}",  
                    "assigned_by_cognito_id": item.get("assigned_by_cognito_id", {}).get("S", ""),
                    "assigned_to_cognito_id": item["assigned_to_cognito_id"]["S"],
                    "assigned_to_name": None,  
                    "assignment_type": item["assignment_type"]["S"],
                    "priority": int(item.get("priority", {}).get("N", "2")),
                    "notes": item.get("notes", {}).get("S", ""),
                    "status": item["status"]["S"],
                    "created_at": item.get("created_at", {}).get("S", ""),
                    "updated_at": item.get("updated_at", {}).get("S", ""),
                    "completed_at": item.get("completed_at", {}).get("S", "") if item.get("completed_at") else None,
                    "due_date": item.get("due_date", {}).get("S", "") if item.get("due_date") else None,
                    "word_count": None,  
                    "blocked": False,
                    "blocked_reason": None
                }
                assignments.append(assignment_data)
        for assignment in assignments:
            script_job_id = assignment.get("job_id", "")  
            if script_job_id:
                try:
                    job_response = dynamodb_client.get_item(
                        TableName=JOBS_TABLE,  
                        Key={"job_id": {"S": script_job_id}}  
                    )
                    if "Item" in job_response:
                        job_item = job_response["Item"]
                        word_count = 1000  
                        if "result" in job_item:
                            try:
                                result_json = json.loads(job_item["result"]["S"])
                                word_count = result_json.get("word_count", 1000)
                            except (json.JSONDecodeError, KeyError):
                                pass
                        if word_count == 1000 and "word_count" in job_item:
                            word_count = int(job_item.get("word_count", {}).get("N", "1000"))
                        assignment["word_count"] = word_count
                        if "script_title" in job_item:
                            assignment["script_title"] = job_item["script_title"]["S"]
                    else:
                        assignment["word_count"] = 1000  
                except Exception as e:
                    logger.warning(f"Failed to get job details for script job {script_job_id}: {str(e)}")
                    assignment["word_count"] = 1000  
            else:
                assignment["word_count"] = 1000  
        cognito_client = boto3.client("cognito-idp")
        user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
        if not user_pool_id:
            logger.error("COGNITO_USER_POOL_ID not configured")
            for assignment in assignments:
                assignment["assigned_to_name"] = "Unknown Reader"
            return create_response(200, assignments)
        for assignment in assignments:
            assigned_to_id = assignment.get("assigned_to_cognito_id", "")
            if assigned_to_id:
                try:
                    user_response = cognito_client.admin_get_user(
                        UserPoolId=user_pool_id,
                        Username=assigned_to_id
                    )
                    attributes = user_response.get("UserAttributes", [])
                    given_name = None
                    family_name = None
                    for attr in attributes:
                        if attr["Name"] == "given_name":
                            given_name = attr["Value"]
                        elif attr["Name"] == "family_name":
                            family_name = attr["Value"]
                    if given_name and family_name:
                        assignment["assigned_to_name"] = f"{given_name} {family_name}"
                    elif given_name:
                        assignment["assigned_to_name"] = given_name
                    else:
                        assignment["assigned_to_name"] = "Unknown Reader"
                except Exception as e:
                    logger.warning(f"Failed to get reader name for {assigned_to_id}: {str(e)}")
                    assignment["assigned_to_name"] = "Unknown Reader"
            else:
                assignment["assigned_to_name"] = "Unknown Reader"
        assignments.sort(key=lambda x: (
            -x.get("priority", 2),  
            -int(datetime.fromisoformat(x.get("created_at", "1970-01-01T00:00:00")).timestamp()) if x.get("created_at") else 0
        ))
        logger.info(
            "Retrieved all assignments for admin user",
            extra={
                "user_id": user_id,
                "assignment_count": len(assignments)
            }
        )
        return create_response(200, assignments)
    except Exception as e:
        logger.error(
            "Failed to get all assignments",
            extra={"error": str(e), "user_id": _extract_user_id(event)}
        )
        return create_response(500, {"error": "Failed to retrieve all assignments"})
def update_assignment_status(assignment_id: str, body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Update the status of an assignment with proper validation and authorization."""
    try:
        user_id = _extract_user_id(event)
        status = body.get("status")
        notes = body.get("notes", "")
        if not status:
            return create_response(400, {"error": "Status is required"})
        valid_statuses = ["assigned", "in_progress", "audio_submitted", "completed", "skipped"]
        if status not in valid_statuses:
            return create_response(400, {
                "error": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            })
        logger.info(
            "Updating assignment status",
            extra={
                "assignment_id": assignment_id,
                "new_status": status,
                "user_id": user_id,
                "notes": notes
            }
        )
        assignment_table = JOBS_TABLE or "assignments"
        logger.info(
            "Attempting to find assignment for status update",
            extra={
                "assignment_id": assignment_id,
                "user_id": user_id,
                "table": assignment_table
            }
        )
        get_response = dynamodb_client.get_item(
            TableName=assignment_table,
            Key={"job_id": {"S": assignment_id}}
        )
        current_assignment = None
        if "Item" in get_response:
            current_assignment = get_response["Item"]
            logger.info("Found assignment with new structure", extra={"assignment_id": assignment_id})
        else:
            logger.warning("Assignment not found with new structure, trying old structure scan", extra={"assignment_id": assignment_id})
            try:
                scan_response = dynamodb_client.scan(
                    TableName=assignment_table,
                    FilterExpression="assignment_id = :assignment_id",
                    ExpressionAttributeValues={":assignment_id": {"S": assignment_id}},
                    Limit=1
                )
                if scan_response.get("Items"):
                    current_assignment = scan_response["Items"][0]
                    logger.info("Found assignment with old structure", extra={"assignment_id": assignment_id})
            except Exception as scan_error:
                logger.error("Error scanning for assignment", extra={"error": str(scan_error)})
        if not current_assignment:
            logger.error("Assignment not found with either structure", extra={"assignment_id": assignment_id})
            return create_response(404, {"error": "Assignment not found"})
        assigned_to_cognito_id = current_assignment.get("assigned_to_cognito_id", {}).get("S", "")
        if assigned_to_cognito_id != user_id:
            logger.warning(
                "User attempted to update assignment they are not assigned to",
                extra={
                    "assignment_id": assignment_id,
                    "user_id": user_id,
                    "assigned_to": assigned_to_cognito_id
                }
            )
            return create_response(403, {"error": "You can only update assignments assigned to you"})
        current_timestamp = datetime.now(timezone.utc).isoformat()
        update_expression = "SET #status = :status, updated_at = :updated_at"
        expression_attribute_names = {"#status": "status"}
        expression_attribute_values = {
            ":status": {"S": status},
            ":updated_at": {"S": current_timestamp}
        }
        if notes:
            update_expression += ", notes = :notes"
            expression_attribute_values[":notes"] = {"S": notes}
        assignment_job_id = current_assignment.get("job_id", {}).get("S", "")
        if assignment_job_id == assignment_id:
            update_key = {"job_id": {"S": assignment_id}}
            logger.info("Using new structure for update", extra={"assignment_id": assignment_id})
        else:
            update_key = {"job_id": {"S": assignment_job_id}}
            logger.info("Using old structure for update", extra={
                "assignment_id": assignment_id,
                "actual_job_id": assignment_job_id
            })
        update_response = dynamodb_client.update_item(
            TableName=assignment_table,
            Key=update_key,
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues="ALL_NEW"
        )
        logger.info(
            "Assignment status updated successfully",
            extra={
                "assignment_id": assignment_id,
                "old_status": current_assignment.get("status", {}).get("S", "unknown"),
                "new_status": status,
                "user_id": user_id
            }
        )
        return create_response(200, {
            "success": True,
            "message": f"Assignment status updated to {status}",
            "assignment_id": assignment_id,
            "status": status,
            "updated_at": current_timestamp
        })
    except Exception as e:
        logger.error(
            "Failed to update assignment status",
            extra={
                "assignment_id": assignment_id,
                "error": str(e),
                "user_id": _extract_user_id(event)
            },
            exc_info=True
        )
        return create_response(500, {"error": "Failed to update assignment status"})
def submit_recording(assignment_id: str, body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Submit an audio recording for an assignment with S3 pre-signed URL support."""
    try:
        user_id = _extract_user_id(event)
        request_type = body.get("request_type", "upload")  
        logger.info(
            "Processing recording submission",
            extra={
                "assignment_id": assignment_id,
                "user_id": user_id,
                "request_type": request_type
            }
        )
        assignment_table = JOBS_TABLE or "assignments"
        get_response = dynamodb_client.get_item(
            TableName=assignment_table,
            Key={"job_id": {"S": assignment_id}}  
        )
        if "Item" not in get_response:
            return create_response(404, {"error": "Assignment not found"})
        current_assignment = get_response["Item"]
        assigned_to_cognito_id = current_assignment.get("assigned_to_cognito_id", {}).get("S", "")
        if assigned_to_cognito_id != user_id:
            logger.warning(
                "User attempted to submit recording for assignment they are not assigned to",
                extra={
                    "assignment_id": assignment_id,
                    "user_id": user_id,
                    "assigned_to": assigned_to_cognito_id
                }
            )
            return create_response(403, {"error": "You can only submit recordings for assignments assigned to you"})
        current_status = current_assignment.get("status", {}).get("S", "")
        if current_status not in ["assigned", "in_progress"]:
            return create_response(400, {
                "error": f"Cannot submit recording for assignment with status: {current_status}. Must be 'assigned' or 'in_progress'."
            })
        if request_type == "presigned_url":
            file_extension = body.get("file_extension", "wav")
            content_type = body.get("content_type", "audio/wav")
            allowed_extensions = ["wav", "mp3", "m4a", "ogg"]
            allowed_content_types = ["audio/wav", "audio/mpeg", "audio/mp4", "audio/ogg"]
            if file_extension not in allowed_extensions:
                return create_response(400, {
                    "error": f"Invalid file extension. Allowed: {', '.join(allowed_extensions)}"
                })
            if content_type not in allowed_content_types:
                return create_response(400, {
                    "error": f"Invalid content type. Allowed: {', '.join(allowed_content_types)}"
                })
            current_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            s3_key = f"recordings/{user_id}/{assignment_id}_{current_timestamp}.{file_extension}"
            presigned_url = s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": RECORDINGS_BUCKET,
                    "Key": s3_key,
                    "ContentType": content_type
                },
                ExpiresIn=3600  
            )
            logger.info(
                "Generated pre-signed URL for recording upload",
                extra={
                    "assignment_id": assignment_id,
                    "user_id": user_id,
                    "s3_key": s3_key,
                    "content_type": content_type
                }
            )
            return create_response(200, {
                "upload_url": presigned_url,
                "s3_key": s3_key,
                "bucket": RECORDINGS_BUCKET,
                "expires_in": 3600,
                "content_type": content_type
            })
        elif request_type == "upload_complete":
            s3_key = body.get("s3_key")
            if not s3_key:
                return create_response(400, {"error": "s3_key is required for upload_complete"})
            try:
                s3_client.head_object(Bucket=RECORDINGS_BUCKET, Key=s3_key)
            except Exception as e:
                logger.error(
                    "Failed to verify uploaded file in S3",
                    extra={
                        "assignment_id": assignment_id,
                        "s3_key": s3_key,
                        "error": str(e)
                    }
                )
                return create_response(400, {"error": "Uploaded file not found or inaccessible"})
            current_timestamp = datetime.now(timezone.utc).isoformat()
            update_expression = "SET #status = :status, updated_at = :updated_at, s3_key = :s3_key"
            expression_attribute_names = {"#status": "status"}
            expression_attribute_values = {
                ":status": {"S": "audio_submitted"},
                ":updated_at": {"S": current_timestamp},
                ":s3_key": {"S": s3_key}
            }
            notes = body.get("notes", f"Audio recording submitted at {current_timestamp}")
            if notes:
                update_expression += ", notes = :notes"
                expression_attribute_values[":notes"] = {"S": notes}
            dynamodb_client.update_item(
                TableName=assignment_table,
                Key={"job_id": {"S": assignment_id}},  
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
            logger.info(
                "Recording submission completed successfully",
                extra={
                    "assignment_id": assignment_id,
                    "user_id": user_id,
                    "s3_key": s3_key,
                    "new_status": "audio_submitted"
                }
            )
            return create_response(200, {
                "success": True,
                "message": "Recording submitted successfully",
                "assignment_id": assignment_id,
                "status": "audio_submitted",
                "s3_key": s3_key,
                "updated_at": current_timestamp
            })
        else:
            return create_response(400, {
                "error": "Invalid request_type. Must be 'presigned_url' or 'upload_complete'"
            })
    except Exception as e:
        logger.error(
            "Failed to process recording submission",
            extra={
                "assignment_id": assignment_id,
                "error": str(e),
                "user_id": _extract_user_id(event)
            },
            exc_info=True
        )
        return create_response(500, {"error": "Failed to process recording submission"})
def create_assignment(body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new script assignment for a reader."""
    try:
        user_id = _extract_user_id(event)
        if "script_id" in body and "job_id" not in body:
            body["job_id"] = body["script_id"]
        required_fields = ["job_id", "assigned_to_cognito_id", "assignment_type"]
        missing_fields = [field for field in required_fields if not body.get(field)]
        if missing_fields:
            return create_response(400, {
                "error": f"Missing required fields: {', '.join(missing_fields)}"
            })
        assignment_id = f"assign_{uuid.uuid4().hex[:12]}_{int(datetime.now(timezone.utc).timestamp())}"
        assignment_data = {
            "job_id": {"S": assignment_id},  
            "assignment_id": {"S": assignment_id},  
            "script_job_id": {"S": body["job_id"]},  
            "assigned_by_cognito_id": {"S": user_id},
            "assigned_to_cognito_id": {"S": body["assigned_to_cognito_id"]},
            "assignment_type": {"S": body["assignment_type"]},
            "priority": {"N": str(body.get("priority", 2))},  
            "notes": {"S": body.get("notes", "")},
            "status": {"S": "assigned"},
            "created_at": {"S": datetime.now(timezone.utc).isoformat()},
            "updated_at": {"S": datetime.now(timezone.utc).isoformat()},
            "ttl": {"N": str(int(datetime.now(timezone.utc).timestamp()) + (30 * 86400))}  
        }
        assignment_table = JOBS_TABLE or "assignments"  
        dynamodb_client.put_item(
            TableName=assignment_table,
            Item=assignment_data
        )
        logger.info(
            "Assignment created successfully",
            extra={
                "assignment_id": assignment_id,
                "job_id": body["job_id"],
                "assigned_by": user_id,
                "assigned_to": body["assigned_to_cognito_id"],
                "assignment_type": body["assignment_type"]
            }
        )
        return create_response(201, {
            "success": True,
            "assignment_id": assignment_id,
            "message": "Assignment created successfully",
            "assignment": {
                "assignment_id": assignment_id,
                "job_id": body["job_id"],
                "assigned_to_cognito_id": body["assigned_to_cognito_id"],
                "assignment_type": body["assignment_type"],
                "priority": body.get("priority", 2),
                "notes": body.get("notes", ""),
                "status": "assigned",
                "created_at": assignment_data["created_at"]["S"]
            }
        })
    except Exception as e:
        logger.error(
            "Failed to create assignment",
            extra={"error": str(e), "request_body": body}
        )
        return create_response(500, {"error": "Failed to create assignment"})
def update_assignment_priority(assignment_id: str, body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Update assignment priority."""
    try:
        logger.info("Updating assignment priority", extra={"assignment_id": assignment_id})
        user_id = _extract_user_id(event)
        if not user_id:
            return create_response(401, {"error": "User ID not found"})
        priority = body.get("priority")
        if priority is None or not isinstance(priority, int) or priority < 1 or priority > 3:
            return create_response(400, {"error": "Priority must be an integer between 1 and 3"})
        assignment_table = JOBS_TABLE or "assignments"
        try:
            dynamodb_client.update_item(
                TableName=assignment_table,
                Key={"job_id": {"S": assignment_id}},
                UpdateExpression="SET priority = :priority, updated_at = :updated_at",
                ExpressionAttributeValues={
                    ":priority": {"N": str(priority)},
                    ":updated_at": {"S": datetime.now(timezone.utc).isoformat()}
                }
            )
            logger.info("Assignment priority updated successfully", extra={"assignment_id": assignment_id, "priority": priority})
            return create_response(200, {
                "success": True,
                "message": "Assignment priority updated successfully"
            })
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return create_response(404, {"error": "Assignment not found"})
            raise
    except Exception as e:
        logger.error("Failed to update assignment priority", extra={"error": str(e), "assignment_id": assignment_id})
        return create_response(500, {"error": "Failed to update assignment priority"})
def update_assignment_reader(assignment_id: str, body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Update assignment reader."""
    try:
        logger.info("Updating assignment reader", extra={"assignment_id": assignment_id})
        user_id = _extract_user_id(event)
        if not user_id:
            return create_response(401, {"error": "User ID not found"})
        new_reader_id = body.get("assigned_to_cognito_id")
        if not new_reader_id:
            return create_response(400, {"error": "assigned_to_cognito_id is required"})
        assignment_table = JOBS_TABLE or "assignments"
        try:
            dynamodb_client.update_item(
                TableName=assignment_table,
                Key={"job_id": {"S": assignment_id}},
                UpdateExpression="SET assigned_to_cognito_id = :reader_id, updated_at = :updated_at",
                ExpressionAttributeValues={
                    ":reader_id": {"S": new_reader_id},
                    ":updated_at": {"S": datetime.now(timezone.utc).isoformat()}
                }
            )
            logger.info("Assignment reader updated successfully", extra={"assignment_id": assignment_id, "new_reader": new_reader_id})
            return create_response(200, {
                "success": True,
                "message": "Assignment reader updated successfully"
            })
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return create_response(404, {"error": "Assignment not found"})
            raise
    except Exception as e:
        logger.error("Failed to update assignment reader", extra={"error": str(e), "assignment_id": assignment_id})
        return create_response(500, {"error": "Failed to update assignment reader"})
def delete_assignment(assignment_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Delete assignment."""
    try:
        logger.info("Deleting assignment", extra={"assignment_id": assignment_id})
        user_id = _extract_user_id(event)
        if not user_id:
            return create_response(401, {"error": "User ID not found"})
        assignment_table = JOBS_TABLE or "assignments"
        try:
            dynamodb_client.delete_item(
                TableName=assignment_table,
                Key={"job_id": {"S": assignment_id}},
                ConditionExpression="attribute_exists(assignment_id)"  
            )
            logger.info("Assignment deleted successfully", extra={"assignment_id": assignment_id})
            return create_response(200, {
                "success": True,
                "message": "Assignment deleted successfully"
            })
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return create_response(404, {"error": "Assignment not found"})
            raise
    except Exception as e:
        logger.error("Failed to delete assignment", extra={"error": str(e), "assignment_id": assignment_id})
        return create_response(500, {"error": "Failed to delete assignment"})
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler for API requests."""
    try:
        http_method = event.get("httpMethod", "")
        path = event.get("path", "")
        headers = event.get("headers", {})
        body = event.get("body")
        logger.info(
            "Received request",
            extra={"http_method": http_method, "path": path, "headers": headers},
        )
        request_body = {}
        if body:
            try:
                request_body = json.loads(body)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON body", extra={"body": body})
        if http_method == "OPTIONS":
            return create_response(200, {"message": "CORS preflight"})
        logger.info("DEBUG: Starting route matching", extra={
            "path": path, 
            "http_method": http_method,
            "all_paths_to_check": ["/health", "/assignments/readers"]
        })
        if path == "/health":
            return handle_health_check()
        elif path == "/generate/ground-truth" or path == "/api/generate/ground-truth":
            if http_method == "POST":
                if request_body.get("_internal_async_processing"):
                    return process_ground_truth_async(request_body)
                else:
                    return generate_ground_truth(request_body, event)
        elif path.startswith("/api/jobs/") and path.endswith("/script"):
            if http_method == "PUT":
                job_id = path.split("/")[3]  
                return update_job_script(job_id, request_body, event)
        elif path == "/jobs" or path == "/api/jobs":
            if http_method == "GET":
                return get_user_jobs(event)
        elif (path.startswith("/jobs/") or path.startswith("/api/jobs/")) and not path.endswith("/script"):
            job_id = path.split("/")[-1]
            if http_method == "GET":
                return get_job_detail(job_id, event)
            elif http_method == "DELETE":
                return delete_job(job_id, event)
        elif path == "/generate/verticals":
            if http_method == "GET":
                return get_available_verticals()
        elif path == "/analyze/single":
            if http_method == "POST":
                return analyze_single(request_body)
        elif path == "/assignments/readers":
            logger.info("DEBUG: MATCHED /assignments/readers path", extra={"method": http_method, "path": path})
            if http_method == "GET":
                logger.info("DEBUG: Method is GET, calling get_readers", extra={"method": http_method, "path": path})
                return get_readers(event, context)
            else:
                logger.warning("DEBUG: Method not GET for /assignments/readers", extra={"method": http_method, "path": path})
                return create_response(405, {"error": "Method not allowed"})
        elif path == "/assignments" or path == "/assignments/":
            if http_method == "POST":
                return create_assignment(request_body, event)
        elif path == "/assignments/my":
            if http_method == "GET":
                return get_my_assignments(event)
        elif path == "/assignments/all":
            if http_method == "GET":
                return get_all_assignments(event)
        elif path.startswith("/assignments/") and path.endswith("/status"):
            if http_method == "PUT":
                assignment_id = path.split("/")[2]  
                return update_assignment_status(assignment_id, request_body, event)
        elif path.startswith("/assignments/") and path.endswith("/recording"):
            if http_method == "POST":
                assignment_id = path.split("/")[2]  
                return submit_recording(assignment_id, request_body, event)
        elif path.startswith("/assignments/") and path.endswith("/priority"):
            if http_method == "PUT":
                assignment_id = path.split("/")[2]  
                return update_assignment_priority(assignment_id, request_body, event)
        elif path.startswith("/assignments/") and path.endswith("/reader"):
            if http_method == "PUT":
                assignment_id = path.split("/")[2]  
                return update_assignment_reader(assignment_id, request_body, event)
        elif path.startswith("/assignments/") and "/" not in path.split("/assignments/")[1]:
            if http_method == "DELETE":
                assignment_id = path.split("/")[2]  
                return delete_assignment(assignment_id, event)
        elif path == "/assignments/readers/debug":
            if http_method == "GET":
                return create_response(200, {"message": "Readers debug endpoint working", "timestamp": datetime.now(timezone.utc).isoformat()})
        elif path == "/debug/test":
            if http_method == "GET":
                return create_response(200, {"message": "Lambda is working", "timestamp": datetime.now(timezone.utc).isoformat()})
        elif path == "/brands" or path == "/api/brands":
            if http_method == "GET":
                query_params = event.get("queryStringParameters") or {}
                return get_brands(query_params)
            elif http_method == "POST":
                return add_brand(request_body)
            elif http_method == "DELETE":
                return delete_brand(request_body)
        elif path == "/terms" or path == "/api/terms":
            if http_method == "GET":
                query_params = event.get("queryStringParameters") or {}
                return get_terms(query_params)
            elif http_method == "POST":
                return add_term(request_body)
            elif http_method == "DELETE":
                return delete_term(request_body)
        elif path.startswith("/api/brands/"):
            if http_method == "DELETE":
                brand_name = path.split("/")[-1]
                return delete_brand({"name": brand_name})
        elif path.startswith("/api/terms/"):
            if http_method == "DELETE":
                term_name = path.split("/")[-1]
                return delete_term({"name": term_name})
        elif path == "/auth/me":
            if http_method == "GET":
                return get_current_user_info(event)
        elif path == "/auth/validate":
            if http_method == "GET":
                return validate_token(event)
        else:
            logger.warning("DEBUG: No route matched - returning 404", extra={
                "path": path, 
                "method": http_method,
                "available_paths": ["/health", "/assignments/readers", "/debug/test"]
            })
            return create_response(404, {"error": "Endpoint not found"})
    except Exception as e:
        logger.error(
            "Unhandled error in handler", extra={"error": str(e)}, exc_info=True
        )
        return create_response(500, {"error": "Internal server error"})
def handle_health_check() -> Dict[str, Any]:
    """Handle health check requests."""
    health_status = {
        "status": "healthy",
        "service": "voice-actor-platform",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment_vars": {
            "DB_SECRET_ARN": "configured" if DB_SECRET_ARN else "missing",
            "DB_CLUSTER_ARN": "configured" if DB_CLUSTER_ARN else "missing",
            "RECORDINGS_BUCKET": "configured" if RECORDINGS_BUCKET else "missing",
        },
    }
    return create_response(200, health_status)
def generate_ground_truth_sync(body: Dict[str, Any]) -> Dict[str, Any]:
    """Generate ground truth script with proper Doctor/Patient dialogue using Bedrock (synchronous version)."""
    try:
        vertical = body.get(
            "medical_vertical", body.get("vertical", "aesthetic_medicine")
        )
        word_count_raw = body.get("target_word_count", body.get("word_count", 600))
        word_count = (
            int(word_count_raw)
            if isinstance(word_count_raw, (str, int, float))
            else 600
        )
        language = body.get("language", "english")
        encounter_type = body.get("encounter_type", "initial_consultation")
        include_product_names_raw = body.get("include_product_names", True)
        if isinstance(include_product_names_raw, str):
            include_product_names = include_product_names_raw.lower() in (
                "true",
                "1",
                "yes",
            )
        else:
            include_product_names = bool(include_product_names_raw)
        seed_term_density_raw = body.get("seed_term_density", 0.15)
        if isinstance(seed_term_density_raw, str):
            try:
                seed_term_density = float(seed_term_density_raw)
            except ValueError:
                seed_term_density = 0.15
        else:
            seed_term_density = (
                float(seed_term_density_raw)
                if seed_term_density_raw is not None
                else 0.15
            )
        logger.info(
            "Generating ground truth",
            extra={
                "vertical": vertical,
                "word_count": word_count,
                "request_body": body,
            },
        )
        brands = []
        terms = []
        if BRANDS_TERMS_TABLE:
            try:
                if include_product_names:
                    brands_response = dynamodb_client.get_item(
                        TableName=BRANDS_TERMS_TABLE,
                        Key={"cache_key": {"S": "brands_list"}}
                    )
                    if "Item" in brands_response and "brands" in brands_response["Item"]:
                        brands_json = brands_response["Item"]["brands"]["S"]
                        brands = json.loads(brands_json)
                    else:
                        brands = []
                terms_response = dynamodb_client.get_item(
                    TableName=BRANDS_TERMS_TABLE,
                    Key={"cache_key": {"S": "terms_list"}}
                )
                if "Item" in terms_response and "terms" in terms_response["Item"]:
                    terms_json = terms_response["Item"]["terms"]["S"]
                    terms = json.loads(terms_json)
                else:
                    terms = []
                logger.info(
                    "Retrieved data from DynamoDB cache",
                    extra={"brands_count": len(brands), "terms_count": len(terms)},
                )
            except Exception as e:
                logger.warning(
                    "Error retrieving brands/terms from DynamoDB",
                    extra={"error": str(e)},
                )
                brands = []
                terms = []
        # No hardcoded fallbacks - use only DynamoDB data and user selections
        logger.info(
            "Using exclusively DynamoDB data and user selections",
            extra={"vertical": vertical, "brands_count": len(brands), "terms_count": len(terms)},
        )
        import random
        random_seed = hash(f"{vertical}_{encounter_type}_{word_count}_{int(datetime.now(timezone.utc).timestamp())}")
        random.seed(random_seed)
        
        # Use exclusively user selections - no hardcoded fallbacks
        user_selected_terms = body.get("selected_terms", [])
        user_selected_brands = body.get("selected_brands", [])
        
        selected_terms = user_selected_terms or []
        selected_brands = user_selected_brands or []
        
        logger.info(f"Using user-selected terms: {len(selected_terms)} terms")
        logger.info(f"Using user-selected brands: {len(selected_brands)} brands")
        doctor_names = [
            "Dr. Chen", "Dr. Rodriguez", "Dr. Johnson", "Dr. Patel", "Dr. Williams", 
            "Dr. Kim", "Dr. Thompson", "Dr. Anderson", "Dr. Lee", "Dr. Garcia",
            "Dr. Taylor", "Dr. Brown", "Dr. Davis", "Dr. Wilson", "Dr. Miller",
            "Dr. Moore", "Dr. Jackson", "Dr. White", "Dr. Harris", "Dr. Martin"
        ]
        patient_characteristics = [
            "first-time patient who is nervous about the procedure",
            "returning patient who had previous treatments",
            "well-informed patient who has researched extensively", 
            "patient with specific concerns about side effects",
            "patient seeking a second opinion",
            "patient with budget considerations",
            "patient with time constraints for recovery",
            "patient referred by another specialist",
            "patient with multiple areas of concern",
            "patient who is very detail-oriented"
        ]
        conversation_styles = [
            "thorough and educational approach",
            "conversational and reassuring style", 
            "direct and efficient discussion",
            "collaborative decision-making approach",
            "empathetic and patient-centered style"
        ]
        selected_doctor = random.choice(doctor_names)
        selected_patient_type = random.choice(patient_characteristics)
        selected_style = random.choice(conversation_styles)
        all_terminology = selected_terms + selected_brands
        terminology_text = (
            ", ".join(all_terminology)
            if all_terminology
            else "standard medical terminology"
        )
        logger.info(
            "Final terminology and randomization selection",
            extra={
                "terminology_text": terminology_text,
                "selected_terms_count": len(selected_terms),
                "selected_brands_count": len(selected_brands),
                "selected_doctor": selected_doctor,
                "selected_patient_type": selected_patient_type,
                "selected_style": selected_style,
                "random_seed": random_seed,
            },
        )
        concern_words_min = max(20, int(word_count * 0.15))
        concern_words_max = max(30, int(word_count * 0.25))
        exam_words_min = max(30, int(word_count * 0.25))
        exam_words_max = max(40, int(word_count * 0.35))
        treatment_words_min = max(30, int(word_count * 0.25))
        treatment_words_max = max(40, int(word_count * 0.35))
        closing_words_min = max(15, int(word_count * 0.1))
        closing_words_max = max(20, int(word_count * 0.15))
        approx_exchanges = word_count // 50
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
        variety_instruction = f"""
VARIETY REQUIREMENTS (to ensure unique content each time):
- Doctor name: Use '{selected_doctor}' as the doctor
- Patient profile: Create a {selected_patient_type}
- Conversation style: Adopt a {selected_style}
- Vary conversation topics within {vertical} scope
- Use diverse examples and scenarios, not repetitive patterns
- Include different medical concerns, questions, and explanations each time
- Avoid repetitive phrases like "How are you feeling today?" - be creative with openings"""
        prompt = f"""You are an expert medical writer creating realistic {vertical} consultation scripts for speech-to-text transcription training.
Generate a natural consultation dialogue between {selected_doctor} and a Patient for {vertical}.
{language_instruction}
{encounter_instruction}
{variety_instruction}
TARGET WORD COUNT: {word_count} words EXACTLY
This is absolutely critical - you must generate exactly {word_count} words, no more, no less.
STRICT REQUIREMENTS:
1. WORD COUNT: Generate exactly {word_count} words total
2. FORMAT: Only "Doctor: " and "Patient: " lines, alternating naturally
3. CONTENT: Include these terms naturally: {terminology_text}
4. STYLE: Professional medical terminology
5. FLOW: Natural medical consultation conversation
6. VARIETY: Each script must be significantly different from previous ones
CREATIVE ELEMENTS TO VARY:
- Opening conversation and greeting style
- Patient's specific concerns and background
- Medical history questions asked
- Treatment options discussed
- Patient's questions and responses
- Doctor's explanation approach
- Closing recommendations and follow-up plans
WORD COUNT STRATEGY:
- Count as you write to reach exactly {word_count} words
- {word_count} words requires approximately {approx_exchanges} exchanges between doctor and patient
- Adjust sentence length and detail to hit the exact target
CONVERSATION STRUCTURE for {word_count} words:
- Opening/greeting (10-15 words) - make this unique and varied
- Patient presents concern ({concern_words_min}-{concern_words_max} words)  
- Doctor questions/examination ({exam_words_min}-{exam_words_max} words)
- Treatment discussion ({treatment_words_min}-{treatment_words_max} words)
- Closing/next steps ({closing_words_min}-{closing_words_max} words)
FORMAT RULES:
- Each line starts with "Doctor: " or "Patient: " only
- No stage directions, asterisks, or extra formatting
- Natural conversation flow for {vertical} consultation
- Use {selected_doctor} name consistently
- Reflect the {selected_style} throughout
REMEMBER: The total word count must be exactly {word_count} words. Count carefully as you write. Make this script unique and different from other {vertical} consultations."""
        logger.info(
            "Generated enhanced Bedrock prompt with randomization",
            extra={
                "prompt_length": len(prompt),
                "word_count": word_count,
                "vertical": vertical,
                "approx_exchanges": approx_exchanges,
                "doctor_name": selected_doctor,
                "patient_type": selected_patient_type,
                "conversation_style": selected_style,
                "temperature": 1.0,  
            },
        )
        logger.info(
            "Environment check",
            extra={
                "aws_region": bedrock_client.meta.region_name,
                "db_secret_arn_set": bool(DB_SECRET_ARN),
                "brands_terms_table_set": bool(BRANDS_TERMS_TABLE),
            },
        )
        logger.info("Attempting Bedrock generation")
        if word_count > 8000:
            logger.warning(
                "Large word count request detected - using conservative generation",
                extra={
                    "word_count": word_count,
                    "recommendation": "Consider splitting into multiple smaller requests for better reliability",
                },
            )
        content = _generate_with_bedrock(prompt, word_count)
        logger.info(
            "Bedrock generation result",
            extra={
                "content_length": len(content) if content else 0,
                "content_preview": content[:100] if content else None,
            },
        )
        word_count_check = len(content.split()) if content else 0
        has_both_speakers = content and "Doctor:" in content and "Patient:" in content
        if not content or word_count_check < 50 or not has_both_speakers:
            if not content or word_count_check == 0:
                error_msg = f"Bedrock returned empty content. Requested {word_count} words but got 0."
            elif word_count_check < 50:
                error_msg = f"Bedrock generation incomplete - only {word_count_check} words generated out of {word_count} requested."
            else:
                error_msg = f"Bedrock generation failed - insufficient content (words: {word_count_check}, has both speakers: {has_both_speakers})"
            logger.error(
                "Bedrock generation failed",
                extra={
                    "failed_content": content[:200] if content else "EMPTY",
                    "word_count_requested": word_count,
                    "word_count_received": word_count_check,
                    "has_both_speakers": has_both_speakers,
                    "error_message": error_msg,
                },
            )
            raise Exception(error_msg)
        else:
            logger.info(
                "Bedrock generation successful",
                extra={
                    "content_word_count": word_count_check,
                    "content_preview": content[:200],
                },
            )
        actual_word_count = len(content.split())
        logger.info(
            "Initial generation complete",
            extra={
                "actual_word_count": actual_word_count,
                "target_word_count": word_count,
            },
        )
        word_diff_percentage = abs(actual_word_count - word_count) / word_count
        logger.info(
            "Word count analysis",
            extra={
                "word_diff_percentage": f"{word_diff_percentage:.1%}",
                "threshold": "20%",
            },
        )
        if (
            word_diff_percentage > 0.20
        ):  
            logger.warning(
                "Word count mismatch detected",
                extra={
                    "actual_word_count": actual_word_count,
                    "target_word_count": word_count,
                    "difference_percentage": f"{word_diff_percentage:.1%}",
                },
            )
            if actual_word_count < word_count:
                words_needed = word_count - actual_word_count
                logger.info(
                    "Content too short, generating longer version",
                    extra={"words_needed": words_needed},
                )
                adjustment_prompt = f"""The previous dialogue was too short ({actual_word_count} words vs {word_count} target).
You need to add exactly {words_needed} more words to reach {word_count} total words.
Please expand the dialogue by:
- Adding {words_needed // 10} more doctor-patient exchanges
- Including more detailed medical explanations 
- Expanding treatment option discussions
- Adding thorough risk/benefit discussions
- Including comprehensive follow-up planning
CRITICAL: The final dialogue must be exactly {word_count} words total. Count carefully to ensure you add exactly {words_needed} words."""
            else:
                words_to_remove = actual_word_count - word_count
                logger.info(
                    "Content too long, generating shorter version",
                    extra={"words_to_remove": words_to_remove},
                )
                adjustment_prompt = f"""The previous dialogue was too long ({actual_word_count} words vs {word_count} target).
You need to remove exactly {words_to_remove} words to reach {word_count} total words.
Please shorten the dialogue by:
- Making responses more concise ({words_to_remove // 5} fewer words per response)
- Focusing only on essential medical points
- Removing repetitive explanations
- Streamlining the conversation flow
CRITICAL: The final dialogue must be exactly {word_count} words total. Count carefully to ensure you remove exactly {words_to_remove} words."""
            logger.info("Attempting word count adjustment")
            full_adjustment_prompt = (
                prompt
                + "\n\nPREVIOUS ATTEMPT:\n"
                + content
                + "\n\nADJUSTMENT NEEDED:\n"
                + adjustment_prompt
            )
            adjusted_content = _generate_with_bedrock(
                full_adjustment_prompt, word_count
            )
            adjusted_word_count = len(adjusted_content.split())
            logger.info(
                "Word count adjustment complete",
                extra={
                    "adjusted_word_count": adjusted_word_count,
                    "target_word_count": word_count,
                },
            )
            if abs(adjusted_word_count - word_count) < abs(
                actual_word_count - word_count
            ):
                logger.info("Using adjusted version (better word count)")
                content = adjusted_content
                actual_word_count = adjusted_word_count
            else:
                logger.info(
                    "Keeping original version (adjustment didn't improve word count)"
                )
        else:
            logger.info("Word count within acceptable range - no adjustment needed")
        script_id = f"{vertical}_initial_{word_count}w_{random.randint(1000, 9999)}"
        # Base difficulty now determined by user-selected terminology complexity
        base_difficulty = min(0.3 + (len(selected_terms) * 0.05), 0.9)
        transcription_score = base_difficulty * (0.8 if include_product_names else 0.5)
        reader_score = base_difficulty * min(seed_term_density * 2, 1.0)
        script_title = _generate_script_title(
            vertical, encounter_type, word_count, selected_terms, selected_brands
        )
        logger.info(
            "Generated script summary",
            extra={
                "actual_word_count": actual_word_count,
                "selected_terms_count": len(selected_terms),
                "selected_brands_count": len(selected_brands),
                "script_id": script_id,
                "script_title": script_title,
            },
        )
        return create_response(
            200,
            {
                "success": True,
                "script_id": script_id,
                "script_title": script_title,
                "content": content,
                "word_count": actual_word_count,
                "storage_path": f"s3://voice-actor-scripts/{script_id}.txt",
                "metadata": {
                    "script_url": f"https://s3.amazonaws.com/voice-actor-scripts/{script_id}.txt",
                    "metadata_url": f"https://s3.amazonaws.com/voice-actor-scripts/{script_id}_metadata.json",
                    "generation_id": str(uuid.uuid4()),
                    "seed_terms_used": selected_terms,
                    "brand_names_used": selected_brands,
                    "difficulty_score": base_difficulty,
                    "transcription_challenge_score": min(transcription_score, 1.0),
                    "reader_challenge_score": min(reader_score, 1.0),
                    "parameters_used": {
                        "medical_vertical": vertical,
                        "language": language,
                                "include_product_names": include_product_names,
                        "seed_term_density": seed_term_density,
                        "target_word_count": word_count,
                        "actual_word_count": actual_word_count,
                    },
                },
                "message": f"Generated {actual_word_count} word medical consultation script",
            },
        )
    except Exception as e:
        logger.error(
            "Error generating ground truth", extra={"error": str(e)}, exc_info=True
        )
        return create_response(
            500, {"error": f"Failed to generate ground truth: {str(e)}"}
        )
def get_available_verticals() -> Dict[str, Any]:
    """Get list of available medical verticals."""
    verticals = [
        {
            "id": "aesthetic_medicine",
            "name": "Aesthetic Medicine",
            "description": "Cosmetic treatments and aesthetic procedures",
        },
        {
            "id": "dermatology",
            "name": "Dermatology",
            "description": "Skin care and dermatological treatments",
        },
        {
            "id": "plastic_surgery",
            "name": "Plastic Surgery",
            "description": "Surgical aesthetic procedures",
        },
        {
            "id": "venous_care",
            "name": "Venous Care",
            "description": "Vein treatments and vascular care",
        },
    ]
    return create_response(200, {"verticals": verticals})
def analyze_single(body: Dict[str, Any]) -> Dict[str, Any]:
    """Placeholder for single transcript analysis."""
    return create_response(
        200,
        {
            "analysis_id": str(uuid.uuid4()),
            "status": "completed",
            "message": "Analysis functionality will be implemented when connected to evaluation system",
        },
    )
def get_brands(query_params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get brand names from medical brands DynamoDB table, optionally filtered by vertical."""
    try:
        if not MEDICAL_BRANDS_TABLE:
            return create_response(500, {"error": "Medical brands table not configured"})
        
        scan_params = {"TableName": MEDICAL_BRANDS_TABLE}
        
        if query_params and query_params.get("vertical"):
            vertical = query_params["vertical"]
            scan_params["FilterExpression"] = "#v = :vertical"
            scan_params["ExpressionAttributeNames"] = {"#v": "vertical"}
            scan_params["ExpressionAttributeValues"] = {":vertical": {"S": vertical}}
        
        response = dynamodb_client.scan(**scan_params)
        
        brands = []
        for item in response.get("Items", []):
            brand_data = {
                "brand_id": item["brand_id"]["S"],
                "name": item["name"]["S"],
                "pronunciation": item.get("pronunciation", {}).get("S", ""),
                "difficulty": item.get("difficulty", {}).get("S", "average"),
                "category": item.get("category", {}).get("S", "general"),
                "is_active": item.get("is_active", {}).get("BOOL", True)
            }
            if brand_data["is_active"]:
                brands.append(brand_data)
        
        return create_response(200, {"brands": brands, "total_count": len(brands)})
    except Exception as e:
        logger.error("Error retrieving brands", extra={"error": str(e)})
        return create_response(500, {"error": "Failed to retrieve brands"})
def add_brand(body: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new brand to medical brands DynamoDB table."""
    try:
        if not MEDICAL_BRANDS_TABLE:
            return create_response(500, {"error": "Medical brands table not configured"})
        
        brand_name = body.get("name", "").strip()
        pronunciation = body.get("pronunciation", "").strip() or brand_name
        difficulty = body.get("difficulty", "average")
        category = body.get("category", "general")
        
        if not brand_name:
            return create_response(400, {"error": "Brand name is required"})
        
        brand_id = str(uuid.uuid4())
        
        dynamodb_client.put_item(
            TableName=MEDICAL_BRANDS_TABLE,
            Item={
                "brand_id": {"S": brand_id},
                "name": {"S": brand_name},
                "pronunciation": {"S": pronunciation},
                "difficulty": {"S": difficulty},
                "category": {"S": category},
                "is_active": {"BOOL": True},
                "created_at": {"S": datetime.now(timezone.utc).isoformat()},
            }
        )
        
        return create_response(
            201, {"success": True, "message": f'Brand "{brand_name}" added successfully', "brand_id": brand_id}
        )
    except Exception as e:
        logger.error("Error adding brand", extra={"error": str(e)})
        return create_response(500, {"error": "Failed to add brand"})
def delete_brand(body: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a brand from medical brands DynamoDB table."""
    try:
        if not MEDICAL_BRANDS_TABLE:
            return create_response(500, {"error": "Medical brands table not configured"})
        
        brand_id = body.get("brand_id", "").strip()
        brand_name = body.get("name", "").strip()
        
        if not brand_id and not brand_name:
            return create_response(400, {"error": "Either brand_id or name is required"})
        
        if brand_id:
            # Delete by brand_id
            dynamodb_client.delete_item(
                TableName=MEDICAL_BRANDS_TABLE,
                Key={"brand_id": {"S": brand_id}}
            )
            return create_response(
                200, {"success": True, "message": f"Brand deleted successfully"}
            )
        else:
            # Delete by name (scan to find brand_id first)
            response = dynamodb_client.scan(
                TableName=MEDICAL_BRANDS_TABLE,
                FilterExpression="attribute_exists(#name) AND #name = :name",
                ExpressionAttributeNames={"#name": "name"},
                ExpressionAttributeValues={":name": {"S": brand_name}}
            )
            
            if response.get("Items"):
                item = response["Items"][0]
                brand_id = item["brand_id"]["S"]
                
                dynamodb_client.delete_item(
                    TableName=MEDICAL_BRANDS_TABLE,
                    Key={"brand_id": {"S": brand_id}}
                )
                
                return create_response(
                    200, {"success": True, "message": f'Brand "{brand_name}" deleted successfully'}
                )
            else:
                return create_response(404, {"error": f'Brand "{brand_name}" not found'})
                
    except Exception as e:
        logger.error("Error deleting brand", extra={"error": str(e)})
        return create_response(500, {"error": "Failed to delete brand"})
def get_terms(query_params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get terms from medical terms DynamoDB table, optionally filtered by vertical."""
    try:
        if not MEDICAL_TERMS_TABLE:
            return create_response(500, {"error": "Medical terms table not configured"})
        
        scan_params = {"TableName": MEDICAL_TERMS_TABLE}
        
        if query_params and query_params.get("vertical"):
            vertical = query_params["vertical"]
            scan_params["FilterExpression"] = "#v = :vertical"
            scan_params["ExpressionAttributeNames"] = {"#v": "vertical"}
            scan_params["ExpressionAttributeValues"] = {":vertical": {"S": vertical}}
        
        response = dynamodb_client.scan(**scan_params)
        
        terms = []
        for item in response.get("Items", []):
            term_data = {
                "term_id": item["term_id"]["S"],
                "name": item["name"]["S"],
                "pronunciation": item.get("pronunciation", {}).get("S", ""),
                "difficulty": item.get("difficulty", {}).get("S", "average"),
                "category": item.get("category", {}).get("S", "general"),
                "definition": item.get("definition", {}).get("S", ""),
                "is_active": item.get("is_active", {}).get("BOOL", True)
            }
            if term_data["is_active"]:
                terms.append(term_data)
        
        return create_response(200, {"terms": terms, "total_count": len(terms)})
    except Exception as e:
        logger.error("Error retrieving terms", extra={"error": str(e)})
        return create_response(500, {"error": "Failed to retrieve terms"})
def add_term(body: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new term to medical terms DynamoDB table."""
    try:
        if not MEDICAL_TERMS_TABLE:
            return create_response(500, {"error": "Medical terms table not configured"})
        
        term_name = body.get("name", "").strip()
        pronunciation = body.get("pronunciation", "").strip() or term_name
        difficulty = body.get("difficulty", "average")
        category = body.get("category", "general")
        definition = body.get("definition", "").strip()
        
        if not term_name:
            return create_response(400, {"error": "Term name is required"})
        
        term_id = str(uuid.uuid4())
        
        item = {
            "term_id": {"S": term_id},
            "name": {"S": term_name},
            "pronunciation": {"S": pronunciation},
            "difficulty": {"S": difficulty},
            "category": {"S": category},
            "is_active": {"BOOL": True},
            "created_at": {"S": datetime.now(timezone.utc).isoformat()},
        }
        
        if definition:
            item["definition"] = {"S": definition}
        
        dynamodb_client.put_item(
            TableName=MEDICAL_TERMS_TABLE,
            Item=item
        )
        
        return create_response(
            201, {"success": True, "message": f'Term "{term_name}" added successfully', "term_id": term_id}
        )
    except Exception as e:
        logger.error("Error adding term", extra={"error": str(e)})
        return create_response(500, {"error": "Failed to add term"})
def delete_term(body: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a term from medical terms DynamoDB table."""
    try:
        if not MEDICAL_TERMS_TABLE:
            return create_response(500, {"error": "Medical terms table not configured"})
        
        term_id = body.get("term_id", "").strip()
        term_name = body.get("name", "").strip()
        
        if not term_id and not term_name:
            return create_response(400, {"error": "Either term_id or name is required"})
        
        if term_id:
            # Delete by term_id
            dynamodb_client.delete_item(
                TableName=MEDICAL_TERMS_TABLE,
                Key={"term_id": {"S": term_id}}
            )
            return create_response(
                200, {"success": True, "message": f"Term deleted successfully"}
            )
        else:
            # Delete by name (scan to find term_id first)
            response = dynamodb_client.scan(
                TableName=MEDICAL_TERMS_TABLE,
                FilterExpression="attribute_exists(#name) AND #name = :name",
                ExpressionAttributeNames={"#name": "name"},
                ExpressionAttributeValues={":name": {"S": term_name}}
            )
            
            if response.get("Items"):
                item = response["Items"][0]
                term_id = item["term_id"]["S"]
                
                dynamodb_client.delete_item(
                    TableName=MEDICAL_TERMS_TABLE,
                    Key={"term_id": {"S": term_id}}
                )
                
                return create_response(
                    200, {"success": True, "message": f'Term "{term_name}" deleted successfully'}
                )
            else:
                return create_response(404, {"error": f'Term "{term_name}" not found'})
                
    except Exception as e:
        logger.error("Error deleting term", extra={"error": str(e)})
        return create_response(500, {"error": "Failed to delete term"})
def get_current_user_info(event: Dict[str, Any]) -> Dict[str, Any]:
    """Get current user information including username and groups from JWT token."""
    try:
        headers = event.get("headers", {})
        auth_header = headers.get("Authorization") or headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return create_response(401, {"error": "Missing or invalid Authorization header"})
        try:
            token = auth_header.replace("Bearer ", "")
            parts = token.split(".")
            if len(parts) != 3:
                return create_response(401, {"error": "Invalid JWT token format"})
            payload = parts[1]
            padding = 4 - (len(payload) % 4)
            if padding != 4:
                payload += "=" * padding
            decoded_payload = base64.urlsafe_b64decode(payload)
            token_data = json.loads(decoded_payload)
            username = token_data.get("cognito:username") or token_data.get("name") or token_data.get("email", "").split('@')[0]
            email = token_data.get("email")
            groups = token_data.get("cognito:groups", [])
            cognito_user_id = token_data.get("sub")
            logger.info(
                "Successfully extracted user info from JWT",
                extra={
                    "username": username,
                    "email": email,
                    "groups": groups,
                    "cognito_user_id": cognito_user_id
                }
            )
            return create_response(200, {
                "username": username,
                "groups": groups,
                "email": email,
                "cognito_user_id": cognito_user_id
            })
        except json.JSONDecodeError as e:
            logger.error("Failed to decode JWT payload", extra={"error": str(e)})
            return create_response(401, {"error": "Invalid JWT token"})
        except Exception as e:
            logger.error("Error processing JWT token", extra={"error": str(e)})
            return create_response(401, {"error": "Token processing failed"})
    except Exception as e:
        logger.error("Error in get_current_user_info", extra={"error": str(e)})
        return create_response(500, {"error": "Internal server error"})
def validate_token(event: Dict[str, Any]) -> Dict[str, Any]:
    """Validate JWT token and return detailed user information."""
    try:
        headers = event.get("headers", {})
        auth_header = headers.get("Authorization") or headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return create_response(401, {"error": "Missing or invalid Authorization header"})
        try:
            token = auth_header.replace("Bearer ", "")
            parts = token.split(".")
            if len(parts) != 3:
                return create_response(401, {"error": "Invalid JWT token format"})
            payload = parts[1]
            padding = 4 - (len(payload) % 4)
            if padding != 4:
                payload += "=" * padding
            decoded_payload = base64.urlsafe_b64decode(payload)
            token_data = json.loads(decoded_payload)
            return create_response(200, {
                "valid": True,
                "user": {
                    "cognito_user_id": token_data.get("sub"),
                    "email": token_data.get("email"),
                    "name": token_data.get("name") or token_data.get("cognito:username"),
                    "groups": token_data.get("cognito:groups", []),
                    "email_verified": token_data.get("email_verified"),
                    "token_use": token_data.get("token_use")
                },
                "expires_at": token_data.get("exp")
            })
        except Exception as e:
            logger.error("Error validating token", extra={"error": str(e)})
            return create_response(401, {"error": "Invalid token"})
    except Exception as e:
        logger.error("Error in validate_token", extra={"error": str(e)})
        return create_response(500, {"error": "Internal server error"})
def _get_terms_used_in_script(script_content: str) -> List[Dict[str, str]]:
    """Find difficult medical terms from DynamoDB that are used in the script content."""
    if not MEDICAL_TERMS_TABLE or not script_content:
        return []
    
    try:
        # Get terms from medical terms table
        response = dynamodb_client.scan(TableName=MEDICAL_TERMS_TABLE)
        
        all_terms = []
        if "Items" in response:
            # Convert DynamoDB items to term objects
            for item in response["Items"]:
                all_terms.append({
                    "term": item["name"]["S"],
                    "difficulty": item.get("difficulty", {}).get("S", "average"),
                    "phonetic": item.get("pronunciation", {}).get("S", ""),
                })
        
        # Find terms that are actually used in the script (case-insensitive)
        # Only include terms marked as "difficult" for pronunciation guide
        script_lower = script_content.lower()
        used_terms = []
        
        for term_obj in all_terms:
            term_name = term_obj.get("term", "")
            difficulty = term_obj.get("difficulty", "average")
            phonetic = term_obj.get("phonetic", "")
            
            # Only include difficult terms and check if they appear in script
            if difficulty == "hard" and term_name.lower() in script_lower:
                # Use simplified phonetic format (just plain English pronunciation)
                pronunciation_guide = phonetic if phonetic else term_name
                used_terms.append({
                    'term': term_name,
                    'pronunciation': pronunciation_guide,
                    'phonetic': phonetic,
                    'difficulty': difficulty
                })
        
        logger.info("Found difficult terms in script", extra={
            "total_terms_checked": len(all_terms),
            "difficult_terms_found": len(used_terms),
            "used_terms": [t['term'] for t in used_terms]
        })
        
        return used_terms
        
    except Exception as e:
        logger.error("Failed to get terms from DynamoDB", extra={"error": str(e)})
        return []

def _highlight_difficult_terms_in_script(script_content: str) -> str:
    """Highlight difficult medical terms in script content with HTML spans."""
    if not MEDICAL_TERMS_TABLE or not script_content:
        return script_content
    
    try:
        # Get terms from medical terms table
        response = dynamodb_client.scan(TableName=MEDICAL_TERMS_TABLE)
        
        all_terms = []
        if "Items" in response:
            # Convert DynamoDB items to term objects
            for item in response["Items"]:
                all_terms.append({
                    "term": item["name"]["S"],
                    "difficulty": item.get("difficulty", {}).get("S", "average"),
                    "phonetic": item.get("pronunciation", {}).get("S", ""),
                })
        
        # Find difficult terms that appear in the script
        difficult_terms = []
        script_lower = script_content.lower()
        
        for term_obj in all_terms:
            term_name = term_obj.get("term", "")
            difficulty = term_obj.get("difficulty", "average")
            
            # Only highlight difficult terms that appear in script
            if difficulty == "hard" and term_name.lower() in script_lower:
                difficult_terms.append(term_name)
        
        # Sort terms by length (longest first) to avoid partial replacements
        difficult_terms.sort(key=len, reverse=True)
        
        # Highlight each difficult term with HTML span
        highlighted_script = script_content
        for term in difficult_terms:
            # Use case-insensitive replacement but preserve original case
            import re
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            highlighted_script = pattern.sub(
                f'<span class="difficult-term">{term}</span>', 
                highlighted_script
            )
        
        logger.info("Highlighted difficult terms in script", extra={
            "terms_highlighted": len(difficult_terms),
            "highlighted_terms": difficult_terms
        })
        
        return highlighted_script
        
    except Exception as e:
        logger.error("Failed to highlight terms in script", extra={"error": str(e)})
        return script_content

def get_job_detail(job_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Get detailed job information including script content and terms.
    Args:
        job_id (str): The job ID to retrieve
        event (Dict[str, Any]): Lambda event containing user context
    Returns:
        Dict[str, Any]: Job details with script content, terms, and pronunciation guide
    """
    try:
        user_id = _extract_user_id(event)
        if not user_id:
            return create_response(401, {"error": "Unauthorized"})
        logger.info("Retrieving job details", extra={"job_id": job_id, "user_id": user_id})
        job_table = JOBS_TABLE or "jobs"
        try:
            response = dynamodb_client.get_item(
                TableName=job_table,
                Key={"job_id": {"S": job_id}}
            )
            if "Item" not in response:
                return create_response(404, {"error": "Job not found"})
            
            job_item = response["Item"]
            
            # Extract job details from DynamoDB item
            script_title = job_item.get("script_title", {}).get("S", f"Medical Consultation Script {job_id[:8]}")
            status = job_item.get("status", {}).get("S", "unknown")
            created_at = job_item.get("created_at", {}).get("S", "")
            
            # Extract script content from job result
            script_content = ""
            word_count = 0
            vertical = "medical"
            
            if "result" in job_item:
                try:
                    result_json = json.loads(job_item["result"]["S"])
                    script_content = result_json.get("content", "")
                    word_count = result_json.get("word_count", 0)
                    
                    # Extract metadata from result
                    metadata = result_json.get("metadata", {})
                    parameters = metadata.get("parameters_used", {})
                    vertical = parameters.get("medical_vertical", "medical")
                    
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse job result JSON: {str(e)}")
                    script_content = "Script content could not be loaded from job data."
            
            if not script_content:
                script_content = "No script content available for this job."
            
            # Highlight difficult terms in script content
            highlighted_script_content = _highlight_difficult_terms_in_script(script_content)
            
            # Build job data response
            job_data = {
                "job_id": job_id,
                "title": script_title,
                "script_content": script_content,
                "highlighted_script_content": highlighted_script_content,
                "word_count": word_count,
                "vertical": vertical.replace("_", " ").title(),
                "status": status,
                "created_at": created_at,
                "metadata": {
                    "estimated_reading_time": f"{max(1, word_count // 200)}-{max(2, word_count // 150)} minutes",
                    "terminology_complexity": "based_on_selected_terms"
                }
            }
            
            # Add terms used in actual script content for pronunciation guide
            job_data["terms_used"] = _get_terms_used_in_script(script_content)
            
            # Add pronunciation guide instructions
            job_data["pronunciation_guide"] = {
                "instructions": "Please practice pronouncing these medical terms before recording. Pay special attention to the stress patterns and syllable emphasis.",
                "practice_tips": [
                    "Break complex terms into syllables",
                    "Practice medical terminology slowly first, then at normal speed",
                    "Pay attention to where the stress falls in each word",
                    "Medical terms often have Latin or Greek roots - pronunciation may differ from English patterns"
                ]
            }
            
            logger.info("Successfully retrieved actual job details", extra={
                "job_id": job_id,
                "script_length": len(script_content),
                "word_count": word_count,
                "terms_found": len(job_data["terms_used"])
            })
            return create_response(200, job_data)
            
        except Exception as e:
            logger.error("Failed to retrieve job from DynamoDB", extra={"job_id": job_id, "error": str(e)})
            return create_response(404, {"error": "Job not found"})
    except Exception as e:
        logger.error("Failed to get job details", extra={"job_id": job_id, "error": str(e)})
        return create_response(500, {"error": "Failed to retrieve job details"})
def delete_job(job_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a job and all its associated assignments (admin only)."""
    try:
        user_id = _extract_user_id(event)
        auth_header = event.get("headers", {}).get("Authorization", "")
        if not auth_header:
            return create_response(401, {"error": "Authentication required"})
        token = auth_header.replace("Bearer ", "")
        parts = token.split(".")
        if len(parts) != 3:
            return create_response(401, {"error": "Invalid token format"})
        import base64
        import json
        payload = parts[1]
        padding = 4 - (len(payload) % 4)
        if padding != 4:
            payload += "=" * padding
        decoded_payload = base64.urlsafe_b64decode(payload)
        token_data = json.loads(decoded_payload)
        user_groups = token_data.get("cognito:groups", [])
        if "admin" not in user_groups:
            return create_response(403, {"error": "Admin access required to delete jobs"})
        logger.info(
            "Admin attempting to delete job",
            extra={
                "job_id": job_id,
                "admin_user_id": user_id,
                "user_groups": user_groups
            }
        )
        jobs_table = JOBS_TABLE or "jobs"
        get_response = dynamodb_client.get_item(
            TableName=jobs_table,
            Key={"job_id": {"S": job_id}}
        )
        if "Item" not in get_response:
            return create_response(404, {"error": "Job not found"})
        job_item = get_response["Item"]
        job_created_by = job_item.get("user_id", {}).get("S", "")
        scan_response = dynamodb_client.scan(
            TableName=jobs_table,
            FilterExpression="job_id = :job_id AND attribute_exists(assignment_id)",
            ExpressionAttributeValues={":job_id": {"S": job_id}},
        )
        assignments = scan_response.get("Items", [])
        active_statuses = ["assigned", "in_progress"]
        active_assignments = [
            a for a in assignments 
            if a.get("status", {}).get("S", "") in active_statuses
        ]
        if active_assignments:
            return create_response(400, {
                "error": f"Cannot delete job with {len(active_assignments)} active assignments. Complete or reassign them first.",
                "active_assignments": len(active_assignments),
                "total_assignments": len(assignments)
            })
        deleted_assignments = 0
        for assignment in assignments:
            assignment_id = assignment.get("assignment_id", {}).get("S", "")
            if assignment_id:
                try:
                    dynamodb_client.delete_item(
                        TableName=jobs_table,
                        Key={"assignment_id": {"S": assignment_id}}
                    )
                    deleted_assignments += 1
                except Exception as e:
                    logger.warning(
                        "Failed to delete assignment during job deletion",
                        extra={
                            "assignment_id": assignment_id,
                            "job_id": job_id,
                            "error": str(e)
                        }
                    )
        dynamodb_client.delete_item(
            TableName=jobs_table,
            Key={"job_id": {"S": job_id}}
        )
        try:
            if job_item.get("result_path"):
                s3_key = job_item["result_path"]["S"]
                s3_client.delete_object(Bucket=SCRIPTS_BUCKET, Key=s3_key)
            if RECORDINGS_BUCKET:
                for assignment in assignments:
                    audio_key = assignment.get("audio_file_s3_key", {}).get("S", "")
                    if audio_key:
                        try:
                            s3_client.delete_object(Bucket=RECORDINGS_BUCKET, Key=audio_key)
                        except Exception as e:
                            logger.warning(f"Failed to delete recording {audio_key}: {str(e)}")
        except Exception as e:
            logger.warning(
                "Failed to clean up S3 files during job deletion",
                extra={"job_id": job_id, "error": str(e)}
            )
        logger.info(
            "Job deleted successfully by admin",
            extra={
                "job_id": job_id,
                "deleted_by": user_id,
                "deleted_assignments": deleted_assignments,
                "original_creator": job_created_by
            }
        )
        return create_response(200, {
            "success": True,
            "message": f"Job {job_id} deleted successfully",
            "deleted_assignments": deleted_assignments,
            "job_id": job_id
        })
    except Exception as e:
        logger.error(
            "Failed to delete job",
            extra={
                "job_id": job_id,
                "error": str(e),
                "admin_user_id": _extract_user_id(event)
            },
            exc_info=True
        )
        return create_response(500, {"error": "Failed to delete job"})
def update_job_script(job_id: str, request_body: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """Update script content for a job."""
    try:
        if not all(k in request_body for k in ["script_title", "content", "word_count"]):
            return create_response(400, {"error": "Missing required fields"})
        script_title = request_body["script_title"]
        content = request_body["content"]
        word_count = request_body["word_count"]
        user_id = _extract_user_id(event)
        if not user_id:
            return create_response(401, {"error": "Unauthorized"})
        jobs_table = os.getenv("JOBS_TABLE_NAME")
        if not jobs_table:
            logger.error("JOBS_TABLE_NAME environment variable not set")
            return create_response(500, {"error": "Configuration error"})
        response = dynamodb_client.get_item(
            TableName=jobs_table,
            Key={"job_id": {"S": job_id}}
        )
        if "Item" not in response:
            return create_response(404, {"error": "Job not found"})
        job_item = response["Item"]
        if job_item.get("user_id", {}).get("S") != user_id:
            return create_response(403, {"error": "Access denied"})
        current_result = {}
        if "result" in job_item:
            try:
                current_result = json.loads(job_item["result"]["S"])
            except (json.JSONDecodeError, KeyError):
                current_result = {}
        updated_result = {
            **current_result,
            "content": content,
            "word_count": word_count
        }
        update_response = dynamodb_client.update_item(
            TableName=jobs_table,
            Key={"job_id": {"S": job_id}},
            UpdateExpression="SET script_title = :title, #result = :result, updated_at = :updated_at",
            ExpressionAttributeNames={"#result": "result"},
            ExpressionAttributeValues={
                ":title": {"S": script_title},
                ":result": {"S": json.dumps(updated_result)},
                ":updated_at": {"S": datetime.now(timezone.utc).isoformat()}
            },
            ReturnValues="ALL_NEW"
        )
        logger.info(
            "Job script updated successfully",
            extra={
                "job_id": job_id,
                "user_id": user_id,
                "script_title": script_title,
                "word_count": word_count
            }
        )
        return create_response(200, {
            "success": True,
            "message": "Script updated successfully",
            "job_id": job_id
        })
    except Exception as e:
        logger.error(
            "Failed to update job script",
            extra={
                "job_id": job_id,
                "error": str(e),
                "user_id": _extract_user_id(event)
            },
            exc_info=True
        )
        return create_response(500, {"error": "Failed to update script"})
def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Create a standardized API response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Amz-Date, X-Api-Key",
        },
        "body": json.dumps(body),
    }
