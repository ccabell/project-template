"""LakeFS operations and branch management automation.

This module provides automated branch management, repository initialization,
and workflow integration for LakeFS data version control operations.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from aws_cdk import Aws, Duration
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import custom_resources as cr
from constructs import Construct


@dataclass(frozen=True)
class LakeFSOperationsProps:
    """Configuration properties for LakeFS operations stack.

    Attributes:
        lakefs_endpoint: LakeFS server endpoint URL.
        repository_configs: Dictionary of repository configurations from LakeFS stack.
        admin_secret_arn: ARN of Secrets Manager secret containing admin credentials.
        environment_name: Environment name for resource naming (prod, dev, etc.).
    """

    lakefs_endpoint: str
    repository_configs: dict[str, dict] | None
    admin_secret_arn: str
    environment_name: str | None = None


class LakeFSOperationsStack(Construct):
    """LakeFS operations and branch management automation.

    Provides automated repository initialization, branch management for
    data pipeline environments, and integration hooks for workflow systems.
    """

    BRANCH_ENVIRONMENTS: ClassVar[list[str]] = ["dev", "staging", "prod"]

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: LakeFSOperationsProps,
        **kwargs: dict[str, Any],
    ) -> None:
        """Initialize LakeFS operations stack.

        Args:
            scope: CDK construct scope for resource creation.
            construct_id: Unique identifier for this construct.
            props: Configuration properties for operations.
            **kwargs: Additional arguments passed to parent Construct.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.lakefs_endpoint = props.lakefs_endpoint
        self.repository_configs = props.repository_configs or {}
        self.admin_secret_arn = props.admin_secret_arn
        self.environment_name = props.environment_name or "prod"

        # Create IAM role for LakeFS operations
        self._create_operations_role()

        # Create Lambda functions for branch management
        self._create_repository_initializer()
        self._create_branch_manager()
        self._create_merge_automation()

        # Set up EventBridge rules for automation
        self._create_automation_rules()

        # Initialize repositories on deployment
        self._create_repository_initialization()

    def _get_lambda_asset_path(self, lambda_name: str) -> str:
        """Get Lambda asset path with absolute path resolution."""
        asset_path = Path(__file__).parent / "lambda" / lambda_name
        return str(asset_path)

    def _create_operations_role(self) -> None:
        """Create IAM role for LakeFS operations Lambda functions."""
        self.operations_role = iam.Role(
            self,
            "LakeFSOperationsRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole",
                ),
            ],
            inline_policies={
                "LakeFSOperationsPolicy": iam.PolicyDocument(
                    statements=[
                        # Secrets Manager permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "secretsmanager:GetSecretValue",
                                "secretsmanager:DescribeSecret",
                            ],
                            resources=[self.admin_secret_arn],
                        ),
                        # S3 permissions for repository storage
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                                "s3:ListBucket",
                            ],
                            resources=[
                                "arn:aws:s3:::a360-datalake-*/*",
                                "arn:aws:s3:::a360-datalake-*",
                                f"arn:aws:s3:::a360-{self.environment_name}-consultation-*/*",
                                f"arn:aws:s3:::a360-{self.environment_name}-consultation-*",
                            ],
                        ),
                        # EventBridge permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "events:PutEvents",
                            ],
                            resources=[
                                f"arn:aws:events:{Aws.REGION}:{Aws.ACCOUNT_ID}:event-bus/default",
                            ],
                        ),
                    ],
                ),
            },
        )

    def _create_repository_initializer(self) -> None:
        """Create Lambda function for repository initialization."""
        self.repo_initializer = lambda_.Function(
            self,
            "RepositoryInitializer",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            role=self.operations_role,
            timeout=Duration.minutes(5),
            environment={
                "LAKEFS_ENDPOINT": self.lakefs_endpoint,
                "ADMIN_SECRET_ARN": self.admin_secret_arn,
            },
            code=lambda_.Code.from_asset(
                self._get_lambda_asset_path("repository_initializer")
            ),
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

    def _create_branch_manager(self) -> None:
        """Create Lambda function for automated branch management."""
        self.branch_manager = lambda_.Function(
            self,
            "BranchManager",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            role=self.operations_role,
            timeout=Duration.minutes(3),
            environment={
                "LAKEFS_ENDPOINT": self.lakefs_endpoint,
                "ADMIN_SECRET_ARN": self.admin_secret_arn,
            },
            code=lambda_.Code.from_asset(
                self._get_lambda_asset_path("branch_manager")
            ),
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

    def _create_merge_automation(self) -> None:
        """Create Lambda function for automated merge operations."""
        self.merge_automation = lambda_.Function(
            self,
            "MergeAutomation",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            role=self.operations_role,
            timeout=Duration.minutes(3),
            environment={
                "LAKEFS_ENDPOINT": self.lakefs_endpoint,
                "ADMIN_SECRET_ARN": self.admin_secret_arn,
            },
            code=lambda_.Code.from_asset(
                self._get_lambda_asset_path("merge_automation")
            ),
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

    def _create_automation_rules(self) -> None:
        """Create EventBridge rules for pipeline automation."""
        # Rule for Dagster+ pipeline completion events
        self.pipeline_completion_rule = events.Rule(
            self,
            "PipelineCompletionRule",
            event_pattern=events.EventPattern(
                source=["consultation.pipeline"],
                detail_type=["Pipeline Execution Completed"],
                detail={
                    "status": ["SUCCESS"],
                    "environment": self.BRANCH_ENVIRONMENTS,
                },
            ),
        )

        # Add branch manager as target for pipeline completion
        self.pipeline_completion_rule.add_target(
            targets.LambdaFunction(self.branch_manager),
        )

    def _create_repository_initialization(self) -> None:
        """Create Custom Resource to initialize repositories on deployment."""
        if not self.repository_configs:
            return

        # Prepare repository list for initialization
        repositories = [
            {
                "name": config["name"],
                "storage_namespace": config["storage_namespace"],
            }
            for config in self.repository_configs.values()
        ]

        # Create Custom Resource to trigger initialization
        self.repo_initialization = cr.AwsCustomResource(
            self,
            "RepositoryInitialization",
            on_create=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": self.repo_initializer.function_name,
                    "Payload": json.dumps({"repositories": repositories}),
                },
                physical_resource_id=cr.PhysicalResourceId.of("lakefs-repo-init"),
            ),
            on_update=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": self.repo_initializer.function_name,
                    "Payload": json.dumps({"repositories": repositories}),
                },
                physical_resource_id=cr.PhysicalResourceId.of("lakefs-repo-init"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["lambda:InvokeFunction"],
                        resources=[self.repo_initializer.function_arn],
                    ),
                ],
            ),
            install_latest_aws_sdk=False,
        )
