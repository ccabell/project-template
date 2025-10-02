"""AWS service integration for transcription evaluator service.

This module provides AWS service integrations for the A360 Transcription Service
Evaluator, replacing custom authentication and authorization with AWS managed services.

The module includes:
    • AWS Cognito User Pool integration for authentication
    • Amazon Verified Permissions for fine-grained authorization
    • API Gateway authorizer utilities
    • CloudWatch structured logging and X-Ray tracing
    • Boto3 service clients with proper error handling

Example:
    Basic AWS service usage:

    >>> from transcription_evaluator.aws import CognitoClient
    >>> cognito = CognitoClient()
    >>> user = await cognito.authenticate_user("user@example.com", "password")
"""

from .authorizers import (
    APIGatewayAuthorizer,
    CognitoClaims,
    extract_cognito_claims,
    validate_cognito_token,
)
from .cognito_client import CognitoClient, CognitoUserInfo, get_cognito_client
from .verified_permissions import (
    AuthorizationDecision,
    VerifiedPermissionsClient,
    get_verified_permissions_client,
)

__all__ = [
    "CognitoClient",
    "get_cognito_client",
    "CognitoUserInfo",
    "VerifiedPermissionsClient",
    "get_verified_permissions_client",
    "AuthorizationDecision",
    "APIGatewayAuthorizer",
    "extract_cognito_claims",
    "validate_cognito_token",
    "CognitoClaims",
]
