"""API Gateway authorizer utilities for Cognito integration.

This module provides utilities for handling API Gateway authorization with
AWS Cognito, including JWT token validation, claims extraction, and
integration with Amazon Verified Permissions for fine-grained access control.

The module includes:
    • JWT token validation and decoding
    • Cognito claims extraction and processing
    • API Gateway Lambda authorizer implementation
    • Integration with Verified Permissions for authorization
    • Structured error handling and logging

Example:
    Basic API Gateway authorizer usage:

    >>> from transcription_evaluator.aws.authorizers import APIGatewayAuthorizer
    >>> authorizer = APIGatewayAuthorizer()
    >>> context = await authorizer.authorize(event, context)
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import jwt
import requests
from aws_lambda_powertools import Logger
from jwt.algorithms import RSAAlgorithm
from fastapi import Depends, HTTPException, Request, status

from .verified_permissions import AuthorizationDecision, get_verified_permissions_client

logger = Logger(service="api-gateway-authorizer")
stdlib_logger = logging.getLogger(__name__)


@dataclass
class CognitoClaims:
    """Represents claims extracted from Cognito JWT token."""

    sub: str
    email: str
    name: str
    groups: List[str]
    token_use: str
    aud: str
    iss: str
    exp: int
    iat: int
    username: str
    email_verified: bool


@dataclass
class AuthorizationContext:
    """Context information for API Gateway authorization."""

    user_id: str
    username: str
    email: str
    groups: List[str]
    is_authorized: bool
    authorization_decision: AuthorizationDecision
    claims: CognitoClaims
    requested_resource: Optional[str] = None
    requested_action: Optional[str] = None


class APIGatewayAuthorizer:
    """API Gateway Lambda authorizer for Cognito and Verified Permissions.

    Provides comprehensive authorization using Cognito JWT tokens and
    Amazon Verified Permissions for fine-grained access control.
    """

    def __init__(
        self, user_pool_id: Optional[str] = None, region: Optional[str] = None
    ):
        """Initialize API Gateway authorizer.

        Args:
            user_pool_id: Cognito User Pool ID (from environment if not provided)
            region: AWS region (from environment if not provided)
        """
        self.user_pool_id = user_pool_id or os.getenv("COGNITO_USER_POOL_ID")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")

        if not self.user_pool_id:
            raise ValueError(
                "Cognito User Pool ID must be provided via parameter "
                "or environment variable (COGNITO_USER_POOL_ID)"
            )

        # Build Cognito JWKS URL
        self.jwks_url = (
            f"https://cognito-idp.{self.region}.amazonaws.com/"
            f"{self.user_pool_id}/.well-known/jwks.json"
        )

        # Cache for JWKS keys
        self._jwks_keys: Optional[Dict[str, Any]] = None

        logger.info(
            "API Gateway authorizer initialized",
            extra={
                "user_pool_id": self.user_pool_id,
                "region": self.region,
                "jwks_url": self.jwks_url,
            },
        )

    async def authorize(
        self,
        event: Dict[str, Any],
        context: Dict[str, Any],
        required_action: Optional[str] = None,
        required_resource: Optional[str] = None,
    ) -> AuthorizationContext:
        """Authorize API Gateway request using Cognito and Verified Permissions.

        Args:
            event: API Gateway Lambda authorizer event
            context: Lambda context object
            required_action: Required action for Verified Permissions check
            required_resource: Required resource for Verified Permissions check

        Returns:
            AuthorizationContext: Authorization result with user information

        Raises:
            Exception: If authorization fails

        Example:
            >>> authorizer = APIGatewayAuthorizer()
            >>> auth_context = await authorizer.authorize(
            ...     event,
            ...     context,
            ...     required_action="CreateScript",
            ...     required_resource="Script"
            ... )
        """
        try:
            # Extract JWT token from event
            token = self._extract_token_from_event(event)
            if not token:
                raise ValueError("No authorization token found in request")

            # Validate and decode JWT token
            claims = await self._validate_cognito_token(token)

            # Check authorization with Verified Permissions if required
            authorization_decision = AuthorizationDecision.ALLOW
            if required_action:
                avp_client = get_verified_permissions_client()
                avp_response = await avp_client.is_authorized(
                    principal_id=claims.sub,
                    action=required_action,
                    resource_type=required_resource,
                    principal_groups=claims.groups,
                )
                authorization_decision = avp_response.decision

            is_authorized = authorization_decision == AuthorizationDecision.ALLOW

            auth_context = AuthorizationContext(
                user_id=claims.sub,
                username=claims.username,
                email=claims.email,
                groups=claims.groups,
                is_authorized=is_authorized,
                authorization_decision=authorization_decision,
                claims=claims,
                requested_resource=required_resource,
                requested_action=required_action,
            )

            logger.info(
                "Authorization completed",
                extra={
                    "user_id": claims.sub,
                    "email": claims.email,
                    "groups": claims.groups,
                    "is_authorized": is_authorized,
                    "required_action": required_action,
                    "required_resource": required_resource,
                },
            )

            return auth_context

        except Exception as e:
            logger.error(
                "Authorization failed",
                extra={
                    "error": str(e),
                    "required_action": required_action,
                    "required_resource": required_resource,
                },
            )
            raise

    def _extract_token_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract JWT token from API Gateway event.

        Args:
            event: API Gateway event

        Returns:
            Optional[str]: JWT token if found
        """
        # Check Authorization header
        headers = event.get("headers", {})
        auth_header = headers.get("Authorization") or headers.get("authorization")

        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]

        # Check query string parameters
        query_params = event.get("queryStringParameters") or {}
        if "token" in query_params:
            return query_params["token"]

        # Check path parameters for WebSocket connections
        path_params = event.get("pathParameters") or {}
        if "token" in path_params:
            return path_params["token"]

        return None

    def _validate_cognito_token(self, token: str) -> CognitoClaims:
        """Validate Cognito JWT token and extract claims.

        Args:
            token: JWT token string

        Returns:
            CognitoClaims: Validated token claims

        Raises:
            Exception: If token validation fails
        """
        try:
            # Get JWKS keys
            jwks_keys = self._get_jwks_keys()

            # Decode token header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            key_id = unverified_header.get("kid")

            if not key_id:
                raise ValueError("Token missing key ID")

            # Find matching key
            signing_key = None
            for key_data in jwks_keys.get("keys", []):
                if key_data.get("kid") == key_id:
                    signing_key = RSAAlgorithm.from_jwk(key_data)
                    break

            if not signing_key:
                raise ValueError(f"Signing key not found for key ID: {key_id}")

            # Verify and decode token
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=os.getenv("COGNITO_CLIENT_ID"),
                issuer=f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}",
            )

            # Extract groups from token (from Cognito groups claim)
            groups = payload.get("cognito:groups", [])
            
            # Enhanced logging for debugging group claims
            logger.info(
                "JWT token payload analysis",
                extra={
                    "sub": payload.get("sub"),
                    "email": payload.get("email"),
                    "cognito_groups": groups,
                    "cognito_username": payload.get("cognito:username"),
                    "token_use": payload.get("token_use"),
                    "payload_keys": list(payload.keys())
                }
            )

            # Create claims object
            claims = CognitoClaims(
                sub=payload["sub"],
                email=payload.get("email", ""),
                name=payload.get("name", ""),
                groups=groups,
                token_use=payload.get("token_use", ""),
                aud=payload.get("aud", ""),
                iss=payload.get("iss", ""),
                exp=payload.get("exp", 0),
                iat=payload.get("iat", 0),
                username=payload.get("cognito:username", payload.get("username", "")),
                email_verified=payload.get("email_verified", False),
            )

            logger.debug(
                "Token validated successfully",
                extra={
                    "sub": claims.sub,
                    "email": claims.email,
                    "groups": claims.groups,
                    "token_use": claims.token_use,
                },
            )

            return claims

        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            raise ValueError(f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            raise

    def _get_jwks_keys(self) -> Dict[str, Any]:
        """Get JWKS keys from Cognito, with caching.

        Returns:
            Dict[str, Any]: JWKS keys data
        """
        if self._jwks_keys is None:
            try:
                response = requests.get(self.jwks_url, timeout=10)
                response.raise_for_status()
                self._jwks_keys = response.json()

                logger.debug(
                    "JWKS keys retrieved",
                    extra={"key_count": len(self._jwks_keys.get("keys", []))},
                )

            except Exception as e:
                logger.error(
                    "Failed to retrieve JWKS keys",
                    extra={"jwks_url": self.jwks_url, "error": str(e)},
                )
                raise

        return self._jwks_keys

    def generate_policy(
        self,
        principal_id: str,
        effect: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate API Gateway policy document.

        Args:
            principal_id: Principal identifier (user ID)
            effect: Policy effect ("Allow" or "Deny")
            resource: Resource ARN
            context: Additional context to pass to API Gateway

        Returns:
            Dict[str, Any]: API Gateway policy document
        """
        policy = {
            "principalId": principal_id,
            "policyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "execute-api:Invoke",
                        "Effect": effect,
                        "Resource": resource,
                    }
                ],
            },
        }

        if context:
            policy["context"] = context

        return policy


def extract_cognito_claims(event: Dict[str, Any]) -> Optional[CognitoClaims]:
    """Extract Cognito claims from API Gateway event context.

    Args:
        event: API Gateway event with authorizer context

    Returns:
        Optional[CognitoClaims]: Cognito claims if available
    """
    try:
        # Extract from authorizer context
        authorizer_context = event.get("requestContext", {}).get("authorizer", {})

        if not authorizer_context:
            return None

        # Build claims from context
        claims = CognitoClaims(
            sub=authorizer_context.get("sub", ""),
            email=authorizer_context.get("email", ""),
            name=authorizer_context.get("name", ""),
            groups=authorizer_context.get("groups", "").split(",")
            if authorizer_context.get("groups")
            else [],
            token_use=authorizer_context.get("token_use", ""),
            aud=authorizer_context.get("aud", ""),
            iss=authorizer_context.get("iss", ""),
            exp=int(authorizer_context.get("exp", 0)),
            iat=int(authorizer_context.get("iat", 0)),
            username=authorizer_context.get("username", ""),
            email_verified=authorizer_context.get("email_verified", "").lower()
            == "true",
        )

        return claims

    except Exception as e:
        logger.error("Failed to extract Cognito claims", extra={"error": str(e)})
        return None


def validate_cognito_token(token: str) -> Optional[CognitoClaims]:
    """Validate Cognito JWT token and return claims.

    Args:
        token: JWT token string

    Returns:
        Optional[CognitoClaims]: Token claims if valid
    """
    try:
        authorizer = APIGatewayAuthorizer()
        return authorizer._validate_cognito_token(token)
    except Exception as e:
        logger.error("Token validation failed", extra={"error": str(e)})
        return None


# Global API Gateway authorizer instance
_api_gateway_authorizer: Optional[APIGatewayAuthorizer] = None


def get_api_gateway_authorizer() -> APIGatewayAuthorizer:
    """Get or create the global API Gateway authorizer instance.

    Returns:
        APIGatewayAuthorizer: Singleton API Gateway authorizer instance
    """
    global _api_gateway_authorizer

    if _api_gateway_authorizer is None:
        _api_gateway_authorizer = APIGatewayAuthorizer()

    return _api_gateway_authorizer


# FastAPI dependency functions for Cognito authentication

@dataclass
class CognitoUser:
    """Represents an authenticated Cognito user for FastAPI dependencies."""
    
    user_id: str
    email: str
    username: str
    groups: List[str]
    claims: CognitoClaims


async def get_current_user(request: Request) -> CognitoUser:
    """Extract current user from Cognito token in request headers.
    
    Args:
        request: FastAPI request object
        
    Returns:
        CognitoUser: Authenticated user information
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Extract token from Authorization header
        authorization = request.headers.get("authorization") or request.headers.get("Authorization")
        
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = authorization[7:]  # Remove "Bearer " prefix
        
        # Validate token using the authorizer
        authorizer = get_api_gateway_authorizer()
        claims = authorizer._validate_cognito_token(token)
        
        return CognitoUser(
            user_id=claims.sub,
            email=claims.email,
            username=claims.username,
            groups=claims.groups,
            claims=claims
        )
        
    except HTTPException:
        raise
    except Exception as e:
        stdlib_logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def require_cognito_auth(current_user: CognitoUser = Depends(get_current_user)) -> CognitoUser:
    """Dependency that requires Cognito authentication.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        CognitoUser: Authenticated user information
        
    Raises:
        HTTPException: If user is not authenticated
    """
    return current_user


async def require_admin_access(current_user: CognitoUser = Depends(require_cognito_auth)) -> bool:
    """Dependency that requires admin access.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        bool: True if user has admin access
        
    Raises:
        HTTPException: If user lacks admin access
    """
    if "admin" not in current_user.groups:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return True


async def require_evaluator_access(current_user: CognitoUser = Depends(require_cognito_auth)) -> bool:
    """Dependency that requires evaluator access.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        bool: True if user has evaluator access
        
    Raises:
        HTTPException: If user lacks evaluator access
    """
    if not ("admin" in current_user.groups or "evaluator" in current_user.groups):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluator access required"
        )
    return True


async def require_reviewer_access(current_user: CognitoUser = Depends(require_cognito_auth)) -> bool:
    """Dependency that requires reviewer access.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        bool: True if user has reviewer access
        
    Raises:
        HTTPException: If user lacks reviewer access
    """
    if not ("admin" in current_user.groups or "reviewer" in current_user.groups):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer access required"
        )
    return True


async def require_evaluation_access(current_user: CognitoUser = Depends(require_cognito_auth)) -> bool:
    """Dependency that requires evaluation-related access (admin, evaluator, or reviewer).
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        bool: True if user has evaluation access
        
    Raises:
        HTTPException: If user lacks evaluation access
    """
    # Enhanced logging for debugging access control
    stdlib_logger.info(
        f"Checking evaluation access for user {current_user.user_id} ({current_user.email}). "
        f"User groups: {current_user.groups}. "
        f"Required groups: admin, evaluator, or reviewer"
    )
    
    has_access = "admin" in current_user.groups or "evaluator" in current_user.groups or "reviewer" in current_user.groups
    
    if not has_access:
        stdlib_logger.warning(
            f"Access denied for user {current_user.user_id} ({current_user.email}). "
            f"User groups: {current_user.groups} do not include admin, evaluator, or reviewer"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation access required (admin, evaluator, or reviewer)"
        )
    
    stdlib_logger.info(f"Access granted for user {current_user.user_id} ({current_user.email}) with groups: {current_user.groups}")
    return True
