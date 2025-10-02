"""Configuration management for Dagster+ hybrid agents.

This module provides configuration classes and utilities for setting up
Dagster+ hybrid agents with proper integration to existing data lake
infrastructure and healthcare data processing requirements.
"""

from dataclasses import dataclass

from aws_cdk import Duration
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from .constants import AGENT_CPU, AGENT_MEMORY


@dataclass(frozen=True)
class EnvironmentVariable:
    """Environment variable configuration for containers.

    Attributes:
        name: Environment variable name.
        value: Environment variable value.
    """

    name: str
    value: str


@dataclass
class AgentConfiguration:
    """Configuration for Dagster+ hybrid agent deployment.

    Manages agent settings, environment variables, and deployment
    configuration for healthcare data processing workloads.

    Attributes:
        organization: Dagster+ organization name.
        deployment: Dagster+ deployment name.
        enable_branch_deployments: Whether to enable branch deployments.
        enable_zero_downtime: Whether to enable zero-downtime deployments.
        image_tag: Docker image tag for agent container.
        metrics_enabled: Whether to enable agent metrics collection.
    """

    organization: str = "aesthetics360"
    deployment: str = "prod"
    enable_branch_deployments: bool = True
    enable_zero_downtime: bool = True
    image_tag: str = "latest"
    metrics_enabled: bool = True
    user_code_metrics_enabled: bool = True

    def get_agent_secret(self, scope: Construct) -> secretsmanager.ISecret:
        """Retrieves the Secrets Manager secret for Dagster+ agent token.

        Args:
            scope: CDK construct scope for secret creation.

        Returns:
            Secrets Manager secret for agent authentication.
        """
        return secretsmanager.Secret.from_secret_name_v2(
            scope,
            "DagsterAgentToken",
            secret_name="dagster/agent-token",  # noqa: S106
        )

    def get_agent_environment_variables(
        self,
    ) -> list[EnvironmentVariable]:
        """Generate environment variables for Dagster+ agent container.

        Args:
            None
        Returns:
            List of environment variables for agent configuration.
        """
        return [
            EnvironmentVariable("DAGSTER_HOME", "/opt/dagster/dagster_home"),
            EnvironmentVariable("DAGSTER_CLOUD_AGENT_MEMORY_LIMIT", AGENT_MEMORY),
            EnvironmentVariable("DAGSTER_CLOUD_AGENT_CPU_LIMIT", AGENT_CPU),
        ]

    def get_health_check_config(self) -> ecs.HealthCheck | None:
        """Get health check configuration for agent container.

        Returns:
            ECS health check configuration or None if disabled.
        """
        if not self.enable_zero_downtime:
            return None

        return ecs.HealthCheck(
            command=[
                "CMD-SHELL",
                "test -f /opt/finished_initial_reconciliation_sentinel.txt",
            ],
            interval=Duration.seconds(60),
            retries=10,
            start_period=Duration.seconds(300),
        )
