"""Entry point for MDA data foundation infrastructure deployment.

This module orchestrates the deployment of AWS CDK stacks for a secure data lake
infrastructure, supporting both environment-based and profile-based configuration
for flexible deployment scenarios.

Environment Configuration Options:
    1. AWS Named Profile:
       AWS_PROFILE: Named profile from AWS credentials file

    2. Direct Environment Variables:
       AWS_DEFAULT_REGION: Target AWS region for deployment
       CDK_DEFAULT_ACCOUNT: Target AWS account for deployment
"""

import os
from dataclasses import dataclass, replace

import boto3
from aws_cdk import App, Environment, Fn
from podcast_transcription_pipeline.podcast_transcription_medalion_stack import (
    PodcastPipelineMedallionStack,
)

from consultation_pipeline.consultation_medallion_stack import (
    ConsultationMedallionStack,
)
from consultation_pipeline.object_lambda_stack import (
    ConsultationObjectLambdaStack,
)
from dagster.consultation_pipeline_stack import ConsultationPipelineDagsterStack
from lakefs.lakefs_stack import LakeFSStack, LakeFSStackProps
from stacks.cicd.github_oidc_role_stack import GitHubOIDCRoleStack  # type: ignore
from stacks.component import DataFoundation  # type: ignore
from stacks.dagster import AgentConfiguration
from stacks.dagster import EcsStack as DagsterEcsStack
from stacks.dagster import MonitoringStack as DagsterMonitoringStack
from stacks.dagster import SecurityStack as DagsterSecurityStack
from stacks.dagster import ServiceDiscoveryStack as DagsterServiceDiscoveryStack
from stacks.dagster import AutoScalingStack as DagsterAutoScalingStack
from stacks.data.macie_classification_stack import MacieClassificationStack


@dataclass(frozen=True)
class StackConfiguration:
    """Configuration settings for stack deployment.

    Provides strongly typed configuration options for stack initialization,
    enforcing consistent naming and environment settings across deployments.

    Attributes:
        app_name: Base name for stack resources and identifiers.
            Used as prefix for stack naming and resource tagging.
        environment: Optional deployment environment name.
            Used to differentiate between deployment stages.
        aws_profile: Optional AWS credentials profile name.
            Used for authentication and environment configuration.
    """

    app_name: str = "MDADataFoundation"
    environment: str | None = None
    aws_profile: str | None = None

    @property
    def stack_name(self) -> str:
        """Generate stack name with environment suffix when applicable."""
        if self.environment:
            return f"{self.app_name}Stack-{self.environment}"
        return f"{self.app_name}Stack"

    def with_app_name(self, app_name: str) -> "StackConfiguration":
        """Create new configuration with updated app name."""
        return replace(self, app_name=app_name)


def create_deployment_environment(config: StackConfiguration) -> Environment:
    """Creates CDK Environment from configuration.

    Handles both AWS profile and direct environment variable configurations
    for maximum deployment flexibility across different environments.

    Args:
        config: Stack configuration containing environment details.

    Returns:
        CDK Environment with account and region resolved.
    """
    if config.aws_profile:
        session = boto3.Session(profile_name=config.aws_profile)
        sts = session.client("sts")
        account = sts.get_caller_identity()["Account"]
        return Environment(
            account=account,
            region=session.region_name or "us-east-1",
        )

    return Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def initialize_app(
    environment: str | None = None,
    aws_profile: str | None = None,
) -> App:
    """Initializes and configures the CDK application.

    Creates and configures all required stacks with proper dependencies
    and environment settings based on provided configuration.

    Args:
        environment: Optional deployment environment name.
        aws_profile: Optional AWS credentials profile to use.

    Returns:
        Configured CDK App instance ready for synthesis.
    """
    config = StackConfiguration(environment=environment, aws_profile=aws_profile)
    env = create_deployment_environment(config)
    app = App()

    _foundation = DataFoundation(
        app,
        config.stack_name,
        env=env,
        description=(
            "MDA Data Foundation infrastructure for secure data lake deployment"
        ),
        tags={
            "Environment": environment or "dev",
            "Application": config.app_name,
            "ManagedBy": "AWS-CDK",
        },
    )

    _dagster_security = DagsterSecurityStack(
        app,
        config.with_app_name("DagsterSecurity").stack_name,
        vpc=_foundation.network.vpc,
        env=env,
        description="IAM roles and security groups for Dagster+ hybrid deployment.",
        tags={
            "Environment": environment or "staging",
            "Application": config.app_name,
            "ManagedBy": "AWS-CDK",
        },
    )

    _dagster_service_discovery = DagsterServiceDiscoveryStack(
        app,
        config.with_app_name("DagsterServiceDiscovery").stack_name,
        vpc=_foundation.network.vpc,
        env=env,
        description="Service discovery infrastructure for Dagster+ hybrid deployment.",
        tags={
            "Environment": environment or "staging",
            "Application": config.app_name,
            "ManagedBy": "AWS-CDK",
        },
    )

    _dagster_ecs = DagsterEcsStack(
        app,
        config.with_app_name("DagsterEcs").stack_name,
        vpc=_foundation.network.vpc,
        agent_security_group=_dagster_security.agent_security_group,
        user_code_security_group=_dagster_security.user_code_security_group,
        namespace=_dagster_service_discovery.namespace,
        agent_config=AgentConfiguration(),
        env=env,
        description="ECS cluster and tasks for Dagster+ hybrid deployment.",
        tags={
            "Environment": environment or "staging",
            "Application": config.app_name,
            "ManagedBy": "AWS-CDK",
        },
    )

    _dagster_ecs.node.add_dependency(_dagster_security)
    _dagster_ecs.node.add_dependency(_dagster_service_discovery)

    _dagster_monitoring = DagsterMonitoringStack(
        app,
        config.with_app_name("DagsterMonitoring").stack_name,
        cluster_arn=_dagster_ecs.get_cluster_arn(),
        service_arn=_dagster_ecs.get_service_arn(),
        log_group_name=_dagster_ecs.get_log_group_name(),
        env=env,
        description="Monitoring and observability for Dagster+ ECS agent/user code.",
        tags={
            "Environment": environment or "staging",
            "Application": config.app_name,
            "ManagedBy": "AWS-CDK",
        },
    )

    _dagster_autoscaling = DagsterAutoScalingStack(
        app,
        config.with_app_name("DagsterAutoScaling").stack_name,
        cluster=_dagster_ecs.cluster,
        agent_service=_dagster_ecs.agent_service,
        env=env,
    )

    _dagster_ecs.node.add_dependency(_dagster_security)
    _dagster_ecs.node.add_dependency(_dagster_service_discovery)

    _dagster_monitoring.node.add_dependency(_dagster_ecs)
    _dagster_autoscaling.node.add_dependency(_dagster_ecs)

    _podcast_medalion = PodcastPipelineMedallionStack(
        app,
        config.with_app_name("PodcastPipelineMedallion").stack_name,
        env_name=config.environment or "dev",
    )

    _github_oidc = GitHubOIDCRoleStack(
        app,
        "GitHubOIDCRoleStack",
        env=env,
        description="GitHub OIDC integration for secure CI/CD authentication",
        tags={
            "Environment": environment or "dev",
            "Application": config.app_name,
            "ManagedBy": "AWS-CDK",
        },
    )

    env_name = environment or "dev"
    _consultation_medallion = ConsultationMedallionStack(
        app,
        config.with_app_name("ConsultationMedallion").stack_name,
        env_name=env_name,
        env=env,
        description=(
            "Medallion architecture for consultation data processing with PII/PHI redaction"
        ),
        tags={
            "Environment": env_name,
            "Application": config.app_name,
            "Pipeline": "ConsultationAnalysis",
            "ManagedBy": "AWS-CDK",
        },
    )

    _consultation_object_lambda = ConsultationObjectLambdaStack(
        app,
        config.with_app_name("ConsultationObjectLambda").stack_name,
        env_name=env_name,
        medallion_stack_name=_consultation_medallion.stack_name,
        env=env,
        description="S3 Object Lambda Access Points for consultation data redaction",
        tags={
            "Environment": env_name,
            "Application": config.app_name,
            "Pipeline": "ConsultationAnalysis",
            "ManagedBy": "AWS-CDK",
        },
    )
    _consultation_object_lambda.add_dependency(_consultation_medallion)

    # LakeFS deployment for data version control - independent stack
    _lakefs = LakeFSStack(
        app,
        config.with_app_name("LakeFS").stack_name,
        props=LakeFSStackProps(
            vpc_id=Fn.import_value("MDADataFoundation-VPC-ID"),
            private_subnet_ids=Fn.split(
                ",",
                Fn.import_value("MDADataFoundation-Private-Subnet-IDs"),
            ),
            existing_kms_key_arn=Fn.import_value("MDADataFoundation-KMS-Key-ARN"),
            consultation_bucket_names={
                "landing": Fn.import_value(
                    f"ConsultationMedallion-{env_name}-LandingBucketName",
                ),
                "bronze": Fn.import_value(
                    f"ConsultationMedallion-{env_name}-BronzeBucketName",
                ),
                "silver": Fn.import_value(
                    f"ConsultationMedallion-{env_name}-SilverBucketName",
                ),
                "gold": Fn.import_value(
                    f"ConsultationMedallion-{env_name}-GoldBucketName",
                ),
            },
            consultation_bucket_arns={
                "landing": Fn.import_value(
                    f"ConsultationMedallion-{env_name}-LandingBucketArn",
                ),
                "bronze": Fn.import_value(
                    f"ConsultationMedallion-{env_name}-BronzeBucketArn",
                ),
                "silver": Fn.import_value(
                    f"ConsultationMedallion-{env_name}-SilverBucketArn",
                ),
                "gold": Fn.import_value(
                    f"ConsultationMedallion-{env_name}-GoldBucketArn",
                ),
            },
            environment_name=env_name,
        ),
        env=env,
        description="LakeFS deployment for data version control and git-like operations",
        tags={
            "Environment": env_name,
            "Application": config.app_name,
            "Component": "DataVersioning",
            "ManagedBy": "AWS-CDK",
        },
    )

    # Add explicit dependencies for LakeFS stack to ensure CloudFormation exports exist
    _lakefs.add_dependency(_foundation)
    _lakefs.add_dependency(_consultation_medallion)

    # Macie for automated PII/PHI detection
    _macie_classification = MacieClassificationStack(
        app,
        config.with_app_name("MacieClassification").stack_name,
        consultation_bucket=_consultation_medallion.landing_bucket,
        consultation_bucket_name=_consultation_medallion.landing_bucket.bucket_name,
        environment_name=env_name,
        env=env,
        description="Amazon Macie configuration for automated PII/PHI detection",
        tags={
            "Environment": env_name,
            "Application": config.app_name,
            "Component": "DataClassification",
            "ManagedBy": "AWS-CDK",
        },
    )

    # Dagster orchestration for consultation pipeline
    _consultation_dagster = ConsultationPipelineDagsterStack(
        app,
        config.with_app_name("ConsultationDagster").stack_name,
        environment_name=env_name,
        env=env,
        description="Dagster orchestration for consultation data processing pipeline",
        tags={
            "Environment": env_name,
            "Application": config.app_name,
            "Pipeline": "ConsultationAnalysis",
            "Component": "Orchestration",
            "ManagedBy": "AWS-CDK",
        },
    )

    return app


def main() -> None:
    """Main execution entry point."""
    environment = os.environ.get("ENVIRONMENT")
    aws_profile = None

    app = initialize_app(environment=environment, aws_profile=aws_profile)
    app.synth()


if __name__ == "__main__":
    main()
