"""Main CDK application entry point for SageMaker Pipeline deployment.

This module orchestrates the deployment of multiple stacks for setting up
SageMaker Studio, creating and executing SageMaker Pipelines, and managing
inference results.

Environment Configuration Options:
    1. AWS Named Profile:
       AWS_PROFILE: Named profile from AWS credentials file
    2. Direct Environment Variables:
       AWS_DEFAULT_REGION: Target AWS region for deployment
       CDK_DEFAULT_ACCOUNT: Target AWS account for deployment
"""

import json
import os
from typing import Any, Dict, Optional

import aws_cdk as cdk
from aws_cdk import Environment, Tags

from infrastructure.sagemaker_studio.sagemaker_studio_stack import SagemakerStudioStack


class StackConfiguration:
    """Configuration settings for stack deployment.

    Attributes:
        app_name: Base name for stack resources and identifiers.
        environment: Optional deployment environment name.
        aws_profile: Optional AWS credentials profile name.
        stack_prefix: Prefix for all stack names.
    """

    app_name: str = "A360-Data-Science-Environment"
    environment: Optional[str] = None
    aws_profile: Optional[str] = None
    stack_prefix: str = "A360-"

    def __init__(
        self, environment: Optional[str] = None, aws_profile: Optional[str] = None
    ) -> None:
        """Initialize configuration with optional environment settings.

        Args:
            environment: Optional deployment environment name
            aws_profile: Optional AWS credentials profile name
        """
        if environment:
            self.environment = environment
        if aws_profile:
            self.aws_profile = aws_profile


def apply_stack_configuration(stack: cdk.Stack, description: str) -> None:
    """Applies common configuration to a stack.

    Args:
        stack: The CDK stack to configure
        description: Stack description text
    """
    stack.termination_protection = True

    stack.template_options.description = description

    Tags.of(stack).add("ManagedBy", "CDK")
    Tags.of(stack).add("Service", "SageMaker Studio")
    Tags.of(stack).add("Domain", "Data Science")
    Tags.of(stack).add("Environment", os.getenv("ENVIRONMENT", "Development"))
    Tags.of(stack).add("Project", "MLOps Platform")


def create_deployment_environment(config: StackConfiguration) -> Environment:
    """Creates CDK environment configuration using AWS configuration.

    Args:
        config: Stack configuration containing deployment preferences.

    Returns:
        Configured CDK Environment instance.
    """
    if config.aws_profile:
        os.environ["AWS_PROFILE"] = config.aws_profile

    return Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION"),
    )


def load_project_config() -> Dict[str, Any]:
    """Loads project configuration from JSON file.

    Returns:
        Dictionary containing project configuration variables.

    Raises:
        FileNotFoundError: If project_config.json doesn't exist.
        JSONDecodeError: If JSON parsing fails.
    """
    with open("project_config.json") as file:
        return json.load(file)


def create_application(
    environment: Optional[str] = None, aws_profile: Optional[str] = None
) -> cdk.App:
    """Creates and configures the CDK application with all required stacks.

    Args:
        environment: Optional deployment environment name.
        aws_profile: Optional AWS credentials profile to use.

    Returns:
        Configured CDK App instance with all stacks and dependencies.
    """
    config = StackConfiguration(environment=environment, aws_profile=aws_profile)
    env = create_deployment_environment(config)
    app = cdk.App()

    studio_stack = SagemakerStudioStack(
        app,
        "DevAe360DataScience-SageMakerStudioStack",
        domain_name=f"{config.stack_prefix}SageMaker-Studio-Domain",
        vpc_id="vpc-09f9592be2f3a5ac2",
        workspace_id=f"{config.stack_prefix}SageMaker-Studio-Domain",
        env=env,
    )
    apply_stack_configuration(
        studio_stack,
        "SageMaker Studio setup stack with VPC configuration and user profiles",
    )

    return app


def main() -> None:
    """Application entry point for stack deployment."""
    environment = os.getenv("ENVIRONMENT")
    aws_profile = os.getenv("AWS_PROFILE")

    variables = load_project_config()
    app = create_application(environment=environment, aws_profile=aws_profile)
    app.synth()


if __name__ == "__main__":
    main()
