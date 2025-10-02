"""Main CDK application entry point for SageMaker pipeline deployment.

This module orchestrates the deployment of SageMaker Pipeline stack with
references to existing SageMaker Studio infrastructure.

Environment Configuration Options:
    1. AWS Named Profile:
       AWS_PROFILE: Named profile from AWS credentials file
    2. Direct Environment Variables:
       AWS_DEFAULT_REGION: Target AWS region for deployment
       CDK_DEFAULT_ACCOUNT: Target AWS account for deployment
       DEPLOY_PIPELINE: Whether to deploy the Pipeline stack (true/false)
       DEPLOY_EXECUTION: Whether to deploy the Execution stack (true/false)
       DEPLOY_RESULTS: Whether to deploy the Results stack (true/false)
    3. CDK Context Variables:
       deploy_pipeline: Whether to deploy the Pipeline stack (true/false)
       deploy_execution: Whether to deploy the Execution stack (true/false)
       deploy_results: Whether to deploy the Results stack (true/false)
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from aws_cdk import App, Environment, Stack, Tags

from infrastructure.sagemaker_pipeline.inference_results_stack import (
    InferenceResultsStack,
)
from infrastructure.sagemaker_pipeline.sagemaker_pipeline_stack import (
    SagemakerPipelineStack,
)
from infrastructure.sagemaker_pipeline.start_sagemaker_pipeline_stack import (
    StartSagemakerPipelineStack,
)


@dataclass(frozen=True)
class StackConfiguration:
    """Configuration settings for stack deployment.

    Manages configuration parameters for CDK stack deployment including
    application naming, environment settings, and AWS credentials.

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


def apply_stack_configuration(stack: Stack, description: str) -> None:
    """Applies common configuration to a stack.

    Configures common stack properties including termination protection,
    description, and standardized tags for resource categorization.

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

    Sets up the AWS environment for deployment based on configuration
    preferences, including AWS profile and region settings.

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

    Reads and parses the project_config.json file containing deployment
    variables and configuration settings, used by SageMaker Pipeline stacks.

    Returns:
        Dictionary containing project configuration variables.

    Raises:
        FileNotFoundError: If project_config.json doesn't exist.
        json.JSONDecodeError: If JSON parsing fails.
    """
    try:
        with open("examples/model_train_deploy_pipeline/project_config.json") as file:
            return json.load(file)
    except FileNotFoundError:
        print("Warning: Could not find project_config.json")
        return {}


def reference_studio_resources(config: StackConfiguration) -> Dict[str, Any]:
    """Provides references to existing SageMaker Studio resource names.

    Prepares a dictionary of resource names from an existing
    SageMaker Studio stack without creating any CDK constructs.

    Args:
        config: Stack configuration settings

    Returns:
        Dictionary containing references to existing Studio resource names
    """
    domain_name = f"{config.stack_prefix}SageMaker-Studio-Domain"

    default_role_name = f"{domain_name}DefaultRole"
    data_scientist_role_name = f"{domain_name}DataScientistRole"

    return {
        "domain_name": domain_name,
        "default_role_name": default_role_name,
        "data_scientist_role_name": data_scientist_role_name,
    }


def create_pipeline_stack(
    app: App,
    config: StackConfiguration,
    env: Environment,
    studio_resources: Dict[str, Any],
) -> SagemakerPipelineStack:
    """Creates and configures the SageMaker Pipeline infrastructure stack.

    Initializes the SageMaker Pipeline infrastructure using the
    SagemakerPipelineStack implementation with build and deployment pipelines,
    and connects it to existing SageMaker Studio resources.

    Args:
        app: CDK application instance
        config: Stack configuration settings
        env: AWS environment for deployment
        studio_resources: Dictionary containing existing Studio resources

    Returns:
        Configured SageMaker Pipeline stack
    """
    pipeline_stack = SagemakerPipelineStack(
        app,
        f"{config.stack_prefix}SageMakerPipelineStack",
        env=env,
        studio_resources=studio_resources,
    )

    apply_stack_configuration(
        pipeline_stack,
        "SageMaker Pipeline stack for model training and deployment automation",
    )

    return pipeline_stack


def create_execution_stack(
    app: App,
    config: StackConfiguration,
    env: Environment,
    pipeline_stack: SagemakerPipelineStack,
) -> StartSagemakerPipelineStack:
    """Creates and configures the SageMaker Pipeline execution stack.

    Initializes the stack for triggering SageMaker Pipeline execution
    based on S3 events or other triggers.

    Args:
        app: CDK application instance
        config: Stack configuration settings
        env: AWS environment for deployment
        pipeline_stack: SageMaker Pipeline stack for dependencies

    Returns:
        Configured SageMaker Pipeline execution stack
    """
    execution_stack = StartSagemakerPipelineStack(
        app,
        f"{config.stack_prefix}SageMakerPipelineExecutionStack",
        env=env,
    )
    apply_stack_configuration(
        execution_stack,
        "Stack for triggering SageMaker Pipeline execution based on S3 events",
    )

    execution_stack.add_dependency(pipeline_stack)

    return execution_stack


def create_results_stack(
    app: App,
    config: StackConfiguration,
    env: Environment,
    execution_stack: StartSagemakerPipelineStack,
) -> InferenceResultsStack:
    """Creates and configures the SageMaker Inference results stack.

    Initializes the stack for managing model inference results and data
    processing workflows.

    Args:
        app: CDK application instance
        config: Stack configuration settings
        env: AWS environment for deployment
        execution_stack: Pipeline Execution stack for dependencies

    Returns:
        Configured SageMaker Inference results stack
    """
    results_stack = InferenceResultsStack(
        app,
        f"{config.stack_prefix}SageMakerInferenceResultsStack",
        env=env,
    )
    apply_stack_configuration(
        results_stack,
        "Stack for managing model inference results and data processing",
    )

    results_stack.add_dependency(execution_stack)

    return results_stack


def parse_env_boolean(env_var: str, default: bool = True) -> bool:
    """Parses environment variable string to boolean value.

    Interprets common boolean string representations as boolean values.

    Args:
        env_var: Environment variable string value
        default: Default boolean value if env_var is not set

    Returns:
        Boolean interpretation of the environment variable
    """
    if env_var is None:
        return default

    return env_var.lower() in ("true", "yes", "y", "1", "t")


def create_application() -> App:
    """Creates and configures the CDK application with selected stacks.

    Initializes and configures the CDK application with the stacks specified
    by environment variables. References existing SageMaker Studio resources
    instead of redeploying them.

    Returns:
        Configured CDK App instance with selected stacks
    """
    environment = os.getenv("ENVIRONMENT")
    aws_profile = os.getenv("AWS_PROFILE")

    app = App()

    # Check environment variables first, then fall back to context values
    deploy_pipeline = parse_env_boolean(
        os.getenv("DEPLOY_PIPELINE"),
        app.node.try_get_context("deploy_pipeline") or True,
    )
    deploy_execution = parse_env_boolean(
        os.getenv("DEPLOY_EXECUTION"),
        app.node.try_get_context("deploy_execution") or True,
    )
    deploy_results = parse_env_boolean(
        os.getenv("DEPLOY_RESULTS"), app.node.try_get_context("deploy_results") or True
    )

    config = StackConfiguration(environment=environment, aws_profile=aws_profile)
    env = create_deployment_environment(config)

    studio_resources = reference_studio_resources(config)

    # Create all stacks if they're needed, we'll let the CDK CLI select which ones to deploy
    pipeline_stack = None
    execution_stack = None
    results_stack = None

    if deploy_pipeline:
        pipeline_stack = create_pipeline_stack(app, config, env, studio_resources)

    if deploy_execution and pipeline_stack:
        execution_stack = create_execution_stack(app, config, env, pipeline_stack)

    if deploy_results and execution_stack:
        results_stack = create_results_stack(app, config, env, execution_stack)

    return app


def main() -> None:
    """Application entry point for stack deployment.

    Initializes environment variables, creates the CDK application with
    selected stacks, and synthesizes CloudFormation templates.

    Environment variables control which stacks are deployed:
        DEPLOY_PIPELINE: Whether to deploy the SageMaker Pipeline stack
        DEPLOY_EXECUTION: Whether to deploy the Pipeline Execution stack
        DEPLOY_RESULTS: Whether to deploy the Inference Results stack

    CDK context values can also control deployment (via cdk.json):
        deploy_pipeline: Whether to deploy the Pipeline stack
        deploy_execution: Whether to deploy the Execution stack
        deploy_results: Whether to deploy the Results stack
    """
    load_project_config()
    app = create_application()
    app.synth()


if __name__ == "__main__":
    main()
