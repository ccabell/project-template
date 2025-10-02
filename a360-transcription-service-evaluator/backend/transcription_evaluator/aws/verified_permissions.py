"""Amazon Verified Permissions integration client.

This module provides an Amazon Verified Permissions client for fine-grained
authorization using Cedar policy language in the A360 Transcription Service
Evaluator.

The module includes:
    • Authorization decision requests using Cedar policies
    • Policy management and evaluation
    • Principal, action, and resource context handling
    • Integration with Cognito user groups
    • Performance-optimized authorization checks

Example:
    Basic Verified Permissions usage:

    >>> from transcription_evaluator.aws.verified_permissions import VerifiedPermissionsClient
    >>> avp = VerifiedPermissionsClient()
    >>> decision = await avp.is_authorized(
    ...     principal_id="user123",
    ...     action="CreateScript",
    ...     resource_id="script456"
    ... )
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger

logger = Logger(service="verified-permissions-client")
stdlib_logger = logging.getLogger(__name__)


class AuthorizationDecision(str, Enum):
    """Authorization decision values from Verified Permissions."""

    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass
class AuthorizationRequest:
    """Represents an authorization request to Verified Permissions."""

    principal_type: str
    principal_id: str
    action_type: str
    action_id: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class AuthorizationResponse:
    """Represents an authorization response from Verified Permissions."""

    decision: AuthorizationDecision
    determining_policies: List[str]
    errors: Optional[List[str]] = None


class VerifiedPermissionsClient:
    """Amazon Verified Permissions client for Cedar-based authorization.

    Provides fine-grained authorization using Cedar policy language,
    integrated with Cognito user groups for role-based access control.
    """

    def __init__(
        self, policy_store_id: Optional[str] = None, region: Optional[str] = None
    ):
        """Initialize Verified Permissions client.

        Args:
            policy_store_id: Verified Permissions policy store ID
            region: AWS region (from environment if not provided)

        Raises:
            ValueError: If required configuration is missing
        """
        self.policy_store_id = policy_store_id or os.getenv(
            "VERIFIED_PERMISSIONS_POLICY_STORE_ID"
        )
        self.region = region or os.getenv("AWS_REGION", "us-east-1")

        if not self.policy_store_id:
            raise ValueError(
                "Verified Permissions Policy Store ID must be provided via parameter "
                "or environment variable (VERIFIED_PERMISSIONS_POLICY_STORE_ID)"
            )

        # Initialize boto3 client
        self.avp_client = boto3.client("verifiedpermissions", region_name=self.region)

        logger.info(
            "Verified Permissions client initialized",
            extra={"policy_store_id": self.policy_store_id, "region": self.region},
        )

    async def is_authorized(
        self,
        principal_id: str,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        principal_groups: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AuthorizationResponse:
        """Check if principal is authorized to perform action on resource.

        Args:
            principal_id: Cognito user ID (sub)
            action: Action to be performed (e.g., "CreateScript")
            resource_type: Type of resource (e.g., "Script")
            resource_id: Specific resource identifier
            principal_groups: Cognito groups the principal belongs to
            context: Additional context for authorization decision

        Returns:
            AuthorizationResponse: Authorization decision with details

        Example:
            >>> avp = VerifiedPermissionsClient()
            >>> response = await avp.is_authorized(
            ...     principal_id="user123",
            ...     action="CreateScript",
            ...     resource_type="Script",
            ...     principal_groups=["evaluator"]
            ... )
            >>> print(f"Decision: {response.decision}")
        """
        try:
            # Build authorization request
            request_data = {
                "policyStoreId": self.policy_store_id,
                "principal": {"entityType": "User", "entityId": principal_id},
                "action": {"actionType": "Action", "actionId": action},
            }

            # Add resource if specified
            if resource_type and resource_id:
                request_data["resource"] = {
                    "entityType": resource_type,
                    "entityId": resource_id,
                }
            elif resource_type:
                request_data["resource"] = {
                    "entityType": resource_type,
                    "entityId": "any",
                }

            # Add context including group memberships
            auth_context = context or {}
            if principal_groups:
                auth_context["groups"] = principal_groups

            if auth_context:
                request_data["context"] = {"contextMap": auth_context}

            # Make authorization request
            response = self.avp_client.is_authorized(**request_data)

            decision = AuthorizationDecision(response["decision"])
            determining_policies = response.get("determiningPolicies", [])
            errors = response.get("errors", [])

            logger.info(
                "Authorization decision made",
                extra={
                    "principal_id": principal_id,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "decision": decision.value,
                    "determining_policies": len(determining_policies),
                },
            )

            return AuthorizationResponse(
                decision=decision,
                determining_policies=[
                    p.get("policyId", "") for p in determining_policies
                ],
                errors=[e.get("errorDescription", "") for e in errors]
                if errors
                else None,
            )

        except Exception as e:
            logger.error(
                "Authorization request failed",
                extra={
                    "principal_id": principal_id,
                    "action": action,
                    "resource_type": resource_type,
                    "error": str(e),
                },
            )

            # Return DENY on error for security
            return AuthorizationResponse(
                decision=AuthorizationDecision.DENY,
                determining_policies=[],
                errors=[f"Authorization error: {str(e)}"],
            )

    async def batch_is_authorized(
        self, requests: List[AuthorizationRequest]
    ) -> List[AuthorizationResponse]:
        """Check authorization for multiple requests in batch.

        Args:
            requests: List of authorization requests

        Returns:
            List[AuthorizationResponse]: List of authorization decisions
        """
        try:
            # Build batch request
            batch_requests = []
            for req in requests:
                request_data = {
                    "principal": {"entityType": "User", "entityId": req.principal_id},
                    "action": {
                        "actionType": req.action_type,
                        "actionId": req.action_id,
                    },
                }

                if req.resource_type and req.resource_id:
                    request_data["resource"] = {
                        "entityType": req.resource_type,
                        "entityId": req.resource_id,
                    }

                if req.context:
                    request_data["context"] = {"contextMap": req.context}

                batch_requests.append(request_data)

            # Make batch authorization request
            response = self.avp_client.batch_is_authorized(
                policyStoreId=self.policy_store_id, requests=batch_requests
            )

            # Process results
            results = []
            for result in response.get("results", []):
                decision = AuthorizationDecision(result["decision"])
                determining_policies = result.get("determiningPolicies", [])
                errors = result.get("errors", [])

                results.append(
                    AuthorizationResponse(
                        decision=decision,
                        determining_policies=[
                            p.get("policyId", "") for p in determining_policies
                        ],
                        errors=[e.get("errorDescription", "") for e in errors]
                        if errors
                        else None,
                    )
                )

            logger.info(
                "Batch authorization completed",
                extra={"request_count": len(requests), "results_count": len(results)},
            )

            return results

        except Exception as e:
            logger.error(
                "Batch authorization failed",
                extra={"request_count": len(requests), "error": str(e)},
            )

            # Return DENY for all requests on error
            return [
                AuthorizationResponse(
                    decision=AuthorizationDecision.DENY,
                    determining_policies=[],
                    errors=[f"Batch authorization error: {str(e)}"],
                )
                for _ in requests
            ]

    async def create_policy(
        self, policy_id: str, cedar_policy: str, description: Optional[str] = None
    ) -> bool:
        """Create a new Cedar policy in the policy store.

        Args:
            policy_id: Unique identifier for the policy
            cedar_policy: Cedar policy definition
            description: Optional policy description

        Returns:
            bool: True if policy created successfully
        """
        try:
            policy_data = {
                "policyStoreId": self.policy_store_id,
                "policyId": policy_id,
                "definition": {"static": {"statement": cedar_policy}},
            }

            if description:
                policy_data["definition"]["static"]["description"] = description

            self.avp_client.create_policy(**policy_data)

            logger.info(
                "Policy created successfully",
                extra={"policy_id": policy_id, "description": description},
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to create policy",
                extra={"policy_id": policy_id, "error": str(e)},
            )
            raise

    async def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy from the policy store.

        Args:
            policy_id: ID of the policy to delete

        Returns:
            bool: True if policy deleted successfully
        """
        try:
            self.avp_client.delete_policy(
                policyStoreId=self.policy_store_id, policyId=policy_id
            )

            logger.info("Policy deleted successfully", extra={"policy_id": policy_id})

            return True

        except Exception as e:
            logger.error(
                "Failed to delete policy",
                extra={"policy_id": policy_id, "error": str(e)},
            )
            raise

    async def list_policies(self) -> List[Dict[str, Any]]:
        """List all policies in the policy store.

        Returns:
            List[Dict]: List of policy information
        """
        try:
            response = self.avp_client.list_policies(policyStoreId=self.policy_store_id)

            policies = response.get("policies", [])

            logger.info("Listed policies", extra={"policy_count": len(policies)})

            return policies

        except Exception as e:
            logger.error("Failed to list policies", extra={"error": str(e)})
            raise


# Global Verified Permissions client instance
_verified_permissions_client: Optional[VerifiedPermissionsClient] = None


def get_verified_permissions_client() -> VerifiedPermissionsClient:
    """Get or create the global Verified Permissions client instance.

    Returns:
        VerifiedPermissionsClient: Singleton Verified Permissions client instance
    """
    global _verified_permissions_client

    if _verified_permissions_client is None:
        _verified_permissions_client = VerifiedPermissionsClient()

    return _verified_permissions_client
