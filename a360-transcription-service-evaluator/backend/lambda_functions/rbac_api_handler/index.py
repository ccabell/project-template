"""AWS Lambda handler for RBAC-enabled API endpoints.

This Lambda function handles API Gateway requests with AWS Cognito authentication
and Amazon Verified Permissions authorization. It integrates with the transcription
evaluator service using AWS managed services.
"""

import json
import os
import traceback
from typing import Any, Dict, Optional
from uuid import uuid4

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.metrics import MetricUnit

# Initialize PowerTools
tracer = Tracer(service="rbac-api-handler")
logger = Logger(service="rbac-api-handler")
metrics = Metrics(namespace="TranscriptionEvaluator", service="rbac-api-handler")

# Initialize AWS clients
cognito_client = boto3.client("cognito-idp")
avp_client = boto3.client("verifiedpermissions")
rds_client = boto3.client("rds-data")
s3_client = boto3.client("s3")

# Environment variables
COGNITO_USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
VERIFIED_PERMISSIONS_POLICY_STORE_ID = os.environ[
    "VERIFIED_PERMISSIONS_POLICY_STORE_ID"
]
DATABASE_CLUSTER_ARN = os.environ["DATABASE_CLUSTER_ARN"]
DATABASE_SECRET_ARN = os.environ["DATABASE_SECRET_ARN"]
S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]


@tracer.capture_lambda_handler
@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@metrics.log_metrics
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle API Gateway requests with RBAC.

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        logger.info("Processing API request", extra={"event": event})

        # Extract request details
        http_method = event.get("httpMethod", "").upper()
        resource_path = event.get("resource", "")
        path_parameters = event.get("pathParameters") or {}
        query_parameters = event.get("queryStringParameters") or {}
        body = event.get("body")

        # Parse JSON body if present
        request_data = {}
        if body:
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in request body")
                return create_response(400, {"error": "Invalid JSON in request body"})

        # Health check endpoint (no auth required)
        if resource_path == "/api/health" and http_method == "GET":
            return handle_health_check()

        # Extract user info from Cognito authorizer
        user_info = extract_user_from_event(event)
        if not user_info:
            return create_response(401, {"error": "Unauthorized"})

        logger.info(
            "User authenticated",
            extra={
                "user_id": user_info.get("sub"),
                "email": user_info.get("email"),
                "groups": user_info.get("cognito:groups", []),
            },
        )

        # Route request to appropriate handler
        if resource_path.startswith("/api/users"):
            return handle_users_api(
                http_method, path_parameters, query_parameters, request_data, user_info
            )
        elif resource_path.startswith("/api/scripts"):
            return handle_scripts_api(
                http_method, path_parameters, query_parameters, request_data, user_info
            )
        elif resource_path.startswith("/api/evaluations"):
            return handle_evaluations_api(
                http_method, path_parameters, query_parameters, request_data, user_info
            )
        elif resource_path.startswith("/api/assignments"):
            return handle_assignments_api(
                http_method, path_parameters, query_parameters, request_data, user_info
            )
        else:
            return create_response(404, {"error": "Endpoint not found"})

    except Exception as e:
        logger.error(
            "Unhandled error in Lambda handler",
            extra={"error": str(e), "traceback": traceback.format_exc()},
        )
        metrics.add_metric(name="LambdaErrors", unit=MetricUnit.Count, value=1)
        return create_response(500, {"error": "Internal server error"})


def extract_user_from_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract user information from Cognito authorizer context.

    Args:
        event: API Gateway event

    Returns:
        User information from Cognito claims
    """
    try:
        authorizer = event.get("requestContext", {}).get("authorizer", {})
        claims = authorizer.get("claims", {})

        if not claims:
            return None

        return {
            "sub": claims.get("sub"),
            "email": claims.get("email"),
            "name": claims.get("name"),
            "cognito:groups": claims.get("cognito:groups", "").split(",")
            if claims.get("cognito:groups")
            else [],
            "email_verified": claims.get("email_verified", "false").lower() == "true",
        }
    except Exception as e:
        logger.error("Failed to extract user from event", extra={"error": str(e)})
        return None


def handle_health_check() -> Dict[str, Any]:
    """Handle health check endpoint.

    Returns:
        Health check response
    """
    try:
        # Test database connectivity
        db_response = rds_client.execute_statement(
            resourceArn=DATABASE_CLUSTER_ARN,
            secretArn=DATABASE_SECRET_ARN,
            database="transcription_evaluator",
            sql="SELECT 1 as health_check",
        )

        db_healthy = len(db_response.get("records", [])) > 0

        health_status = {
            "status": "healthy" if db_healthy else "unhealthy",
            "database": "connected" if db_healthy else "disconnected",
            "timestamp": "2024-01-01T00:00:00Z",  # In real implementation, use datetime.utcnow()
            "version": "1.0.0",
        }

        status_code = 200 if db_healthy else 503
        return create_response(status_code, health_status)

    except Exception as e:
        logger.error("Health check failed", extra={"error": str(e)})
        return create_response(
            503,
            {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": "2024-01-01T00:00:00Z",
            },
        )


@tracer.capture_method
def check_authorization(
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    groups: Optional[list] = None,
) -> bool:
    """Check authorization using Amazon Verified Permissions.

    Args:
        user_id: Cognito user ID (sub)
        action: Action to authorize
        resource_type: Type of resource
        resource_id: Specific resource ID
        groups: User's Cognito groups

    Returns:
        True if authorized, False otherwise
    """
    try:
        request_data = {
            "policyStoreId": VERIFIED_PERMISSIONS_POLICY_STORE_ID,
            "principal": {"entityType": "User", "entityId": user_id},
            "action": {"actionType": "Action", "actionId": action},
        }

        if resource_type and resource_id:
            request_data["resource"] = {
                "entityType": resource_type,
                "entityId": resource_id,
            }
        elif resource_type:
            request_data["resource"] = {"entityType": resource_type, "entityId": "any"}

        # Add context including group memberships
        context = {}
        if groups:
            context["groups"] = groups

        if context:
            request_data["context"] = {"contextMap": context}

        response = avp_client.is_authorized(**request_data)
        is_authorized = response.get("decision") == "ALLOW"

        logger.info(
            "Authorization check completed",
            extra={
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "is_authorized": is_authorized,
            },
        )

        return is_authorized

    except Exception as e:
        logger.error(
            "Authorization check failed",
            extra={"user_id": user_id, "action": action, "error": str(e)},
        )
        # Default to deny on error
        return False


def handle_users_api(
    method: str, path_params: Dict, query_params: Dict, data: Dict, user_info: Dict
) -> Dict[str, Any]:
    """Handle users API endpoints.

    Args:
        method: HTTP method
        path_params: Path parameters
        query_params: Query parameters
        data: Request body data
        user_info: Authenticated user information

    Returns:
        API response
    """
    user_id = user_info.get("sub")
    groups = user_info.get("cognito:groups", [])

    if method == "GET" and not path_params.get("user_id"):
        # List users - admin only
        if not check_authorization(user_id, "ListUsers", "User", groups=groups):
            return create_response(403, {"error": "Insufficient permissions"})

        try:
            # Get users from Cognito
            response = cognito_client.list_users(
                UserPoolId=COGNITO_USER_POOL_ID,
                Limit=int(query_params.get("limit", 50)),
            )

            users = []
            for user in response.get("Users", []):
                user_data = {
                    "user_id": user.get("Username"),
                    "email": next(
                        (
                            attr["Value"]
                            for attr in user.get("UserAttributes", [])
                            if attr["Name"] == "email"
                        ),
                        "",
                    ),
                    "name": next(
                        (
                            attr["Value"]
                            for attr in user.get("UserAttributes", [])
                            if attr["Name"] == "name"
                        ),
                        "",
                    ),
                    "status": user.get("UserStatus"),
                    "created": user.get("UserCreateDate").isoformat()
                    if user.get("UserCreateDate")
                    else None,
                }
                users.append(user_data)

            return create_response(200, {"users": users})

        except Exception as e:
            logger.error("Failed to list users", extra={"error": str(e)})
            return create_response(500, {"error": "Failed to list users"})

    elif method == "POST":
        # Create user - admin only
        if not check_authorization(user_id, "CreateUser", "User", groups=groups):
            return create_response(403, {"error": "Insufficient permissions"})

        try:
            required_fields = ["email", "name", "temporary_password"]
            if not all(field in data for field in required_fields):
                return create_response(400, {"error": "Missing required fields"})

            # Create user in Cognito
            user_attributes = [
                {"Name": "email", "Value": data["email"]},
                {"Name": "name", "Value": data["name"]},
                {"Name": "email_verified", "Value": "true"},
            ]

            response = cognito_client.admin_create_user(
                UserPoolId=COGNITO_USER_POOL_ID,
                Username=data["email"],
                UserAttributes=user_attributes,
                TemporaryPassword=data["temporary_password"],
                MessageAction="SUPPRESS",
            )

            # Add user to groups if specified
            if "groups" in data:
                for group_name in data["groups"]:
                    try:
                        cognito_client.admin_add_user_to_group(
                            UserPoolId=COGNITO_USER_POOL_ID,
                            Username=data["email"],
                            GroupName=group_name,
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to add user to group {group_name}",
                            extra={"error": str(e)},
                        )

            return create_response(
                201,
                {
                    "message": "User created successfully",
                    "user_id": response["User"]["Username"],
                },
            )

        except Exception as e:
            logger.error("Failed to create user", extra={"error": str(e)})
            return create_response(500, {"error": "Failed to create user"})

    else:
        return create_response(405, {"error": "Method not allowed"})


def handle_scripts_api(
    method: str, path_params: Dict, query_params: Dict, data: Dict, user_info: Dict
) -> Dict[str, Any]:
    """Handle scripts API endpoints.

    Args:
        method: HTTP method
        path_params: Path parameters
        query_params: Query parameters
        data: Request body data
        user_info: Authenticated user information

    Returns:
        API response
    """
    user_id = user_info.get("sub")
    groups = user_info.get("cognito:groups", [])

    if method == "GET":
        # List or get scripts
        if not check_authorization(user_id, "ViewScript", "Script", groups=groups):
            return create_response(403, {"error": "Insufficient permissions"})

        # Placeholder implementation - replace with actual database queries
        scripts = [
            {
                "script_id": "script_1",
                "title": "Sample Script",
                "content": "This is a sample script for testing.",
                "status": "draft",
                "created_by": user_id,
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]

        return create_response(200, {"scripts": scripts})

    elif method == "POST":
        # Create script
        if not check_authorization(user_id, "CreateScript", "Script", groups=groups):
            return create_response(403, {"error": "Insufficient permissions"})

        if "title" not in data or "content" not in data:
            return create_response(
                400, {"error": "Missing required fields: title, content"}
            )

        # Placeholder implementation - replace with actual database insertion
        script_id = f"script_{hash(data['title']) % 10000}"

        return create_response(
            201, {"message": "Script created successfully", "script_id": script_id}
        )

    else:
        return create_response(405, {"error": "Method not allowed"})


def handle_evaluations_api(
    method: str, path_params: Dict, query_params: Dict, data: Dict, user_info: Dict
) -> Dict[str, Any]:
    """Handle evaluations API endpoints."""
    user_id = user_info.get("sub")
    groups = user_info.get("cognito:groups", [])

    if method == "GET":
        if not check_authorization(
            user_id, "ViewEvaluation", "Evaluation", groups=groups
        ):
            return create_response(403, {"error": "Insufficient permissions"})

        # Placeholder implementation
        evaluations = [
            {
                "evaluation_id": "eval_1",
                "script_id": "script_1",
                "evaluator_id": user_id,
                "status": "completed",
                "score": 85,
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]

        return create_response(200, {"evaluations": evaluations})

    elif method == "POST":
        if not check_authorization(
            user_id, "CreateEvaluation", "Evaluation", groups=groups
        ):
            return create_response(403, {"error": "Insufficient permissions"})

        if "script_id" not in data:
            return create_response(400, {"error": "Missing required field: script_id"})

        # Placeholder implementation
        evaluation_id = f"eval_{hash(data['script_id']) % 10000}"

        return create_response(
            201,
            {
                "message": "Evaluation created successfully",
                "evaluation_id": evaluation_id,
            },
        )

    else:
        return create_response(405, {"error": "Method not allowed"})


def handle_assignments_api(
    method: str, path_params: Dict, query_params: Dict, data: Dict, user_info: Dict
) -> Dict[str, Any]:
    """Handle script assignments API endpoints."""
    user_id = user_info.get("sub")
    groups = user_info.get("cognito:groups", [])

    if method == "POST":
        if not check_authorization(user_id, "AssignScript", "Script", groups=groups):
            return create_response(403, {"error": "Insufficient permissions"})

        required_fields = ["script_id", "assignee_id"]
        if not all(field in data for field in required_fields):
            return create_response(
                400, {"error": "Missing required fields: script_id, assignee_id"}
            )

        # Placeholder implementation
        assignment_id = f"assign_{uuid4()}"

        return create_response(
            201,
            {"message": "Script assigned successfully", "assignment_id": assignment_id},
        )

    else:
        return create_response(405, {"error": "Method not allowed"})


def create_response(
    status_code: int, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Create standardized API Gateway response.

    Args:
        status_code: HTTP status code
        body: Response body
        headers: Optional additional headers

    Returns:
        API Gateway response format
    """
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key",
    }

    if headers:
        default_headers.update(headers)

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body),
    }
