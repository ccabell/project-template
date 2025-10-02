"""This module defines a CDK stack for setting up GitHub OIDC integration.

The stack creates:
1. An OIDC provider for GitHub
2. An IAM role that can be assumed by GitHub Actions

Usage:
    cdk deploy --profile <profile_name> GitHubOIDCRoleStack
"""

import logging
from typing import Any

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from constructs import Construct

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class GitHubOIDCRoleStack(Stack):
    """A CDK stack that sets up GitHub OIDC integration."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        """Initialize the GitHubOIDCRoleStack.

        Args:
            scope (Construct): The scope in which to define this construct.
            construct_id (str): The scoped construct ID.
            **kwargs: Keyword arguments to pass to the parent Stack.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.github_org: str = "Aesthetics-360"
        self.github_repos: list[str] = [
            "a360-data-lake",
        ]

        self.template_options.description = (
            "GitHub OIDC Integration for AWS Access: Establishes an OIDC provider "
            "for GitHub and creates an IAM role that can be assumed by GitHub Actions, "
            "enabling secure, keyless authentication for CI/CD workflows."
        )

        self.tags.set_tag("Project", "A360 Data Lake")
        self.tags.set_tag("Domain", "GitHub OIDC Role")
        self.tags.set_tag("Team", "Data")
        self.tags.set_tag("ManagedBy", "CDK")

        self.create_oidc_provider()
        self.create_iam_role()

    def create_oidc_provider(self) -> None:
        """Create an OIDC provider for GitHub Actions."""
        logger.info("Creating GitHub OIDC provider")
        self.github_provider = iam.OpenIdConnectProvider(
            self,
            "GitHubProvider",
            url="https://token.actions.githubusercontent.com",
            client_ids=["sts.amazonaws.com"],
            thumbprints=[
                "6938fd4d98bab03faadb97b34396831e3780aea1",
                "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
            ],
        )

    def create_iam_role(self) -> None:
        """Create an IAM role that can be assumed by GitHub Actions.

        Creates an IAM role with administrator access and cross-account permissions
        for CDK deployments. The role is configured with:
            - OIDC-based trust relationship for GitHub Actions
            - Administrator access for base operations
            - Cross-account assume role permissions for CDK roles
            - CloudFormation outputs for role ARN reference

        The role allows assuming CDK roles across accounts while maintaining security
        through OIDC trust conditions and resource pattern restrictions.

        Raises:
            CfnException: If role creation fails due to permission or configuration issues.
        """
        logger.info("Creating IAM role for GitHub Actions")

        github_role = iam.Role(
            self,
            "GitHubOIDCRole",
            role_name="AWSGitHubOIDCAdministratorRole",
            assumed_by=iam.OpenIdConnectPrincipal(self.github_provider).with_conditions(
                self.get_oidc_conditions(),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess"),
            ],
            inline_policies={
                "CrossAccountAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sts:AssumeRole",
                            ],
                            resources=[
                                "arn:aws:iam::*:role/cdk-*",
                            ],
                        ),
                    ],
                ),
            },
        )

        CfnOutput(
            self,
            "RoleArn",
            value=github_role.role_arn,
            description="ARN of the IAM role for GitHub Actions",
        )

    def get_oidc_conditions(self) -> dict[str, Any]:
        """Generate the conditions for the OIDC trust relationship.

        Returns:
            Dict[str, Any]: A dictionary of conditions for the OIDC trust relationship.
        """
        return {
            "StringEquals": {
                "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
            },
            "StringLike": {
                "token.actions.githubusercontent.com:sub": [
                    f"repo:{self.github_org}/{repo}:*" for repo in self.github_repos
                ],
            },
        }
