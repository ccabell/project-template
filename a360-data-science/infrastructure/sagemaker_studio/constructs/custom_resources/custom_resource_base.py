"""
Base construct for SageMaker Studio custom resources.

Provides a standardized foundation for implementing custom resources that require
event-driven Lambda functions for provisioning and managing SageMaker resources.
"""

import os
from typing import Dict, List

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk.custom_resources import Provider
from constructs import Construct


class CustomResourceBase(Construct):
    """
    Base construct for SageMaker custom resources with Lambda handlers.

    This construct provides a standardized approach for creating custom resources
    that use Lambda functions for handling lifecycle events (create, update, delete).
    It sets up the necessary infrastructure including IAM roles, Lambda functions,
    and CloudWatch logging.

    Attributes:
        service_token: Token that can be used to reference this custom resource.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        properties: Dict,
        lambda_file_path: str,
        iam_statements: List[iam.PolicyStatement],
        python_version: lambda_.Runtime = lambda_.Runtime.PYTHON_3_12,
        architecture: lambda_.Architecture = lambda_.Architecture.ARM_64,
        **kwargs,
    ) -> None:
        """
        Initialize the custom resource with event handler Lambdas.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            properties: Properties to pass to the custom resource
            lambda_file_path: Path to Lambda function code relative to lambda directory
            iam_statements: List of IAM policy statements for Lambda execution
            python_version: Python runtime version for Lambda functions
            architecture: CPU architecture for Lambda functions
            **kwargs: Additional arguments to pass to the parent construct
        """
        super().__init__(scope, construct_id, **kwargs)

        region = cdk.Stack.of(self).region
        account = cdk.Stack.of(self).account

        lambda_code_path = os.path.join(
            os.path.dirname(__file__), "../../lambda", lambda_file_path
        )

        on_event_lambda = lambda_.Function(
            self,
            "EventHandler",
            runtime=python_version,
            handler="index.on_event_handler",
            architecture=architecture,
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=cdk.Duration.minutes(3),
            initial_policy=iam_statements,
            layers=[
                lambda_.LayerVersion.from_layer_version_arn(
                    self,
                    "PowertoolsLayer",
                    f"arn:aws:lambda:{region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-arm64:7",
                )
            ],
            environment={
                "POWERTOOLS_SERVICE_NAME": f"custom-resource-{construct_id.lower()}",
                "LOG_LEVEL": "INFO",
            },
        )

        is_complete_lambda = lambda_.Function(
            self,
            "IsCompleteHandler",
            runtime=python_version,
            handler="index.is_complete_handler",
            architecture=architecture,
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=cdk.Duration.minutes(10),
            initial_policy=iam_statements,
            layers=[
                lambda_.LayerVersion.from_layer_version_arn(
                    self,
                    "PowertoolsLayerIsComplete",
                    f"arn:aws:lambda:{region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-arm64:7",
                )
            ],
            environment={
                "POWERTOOLS_SERVICE_NAME": f"custom-resource-{construct_id.lower()}-is-complete",
                "LOG_LEVEL": "INFO",
            },
        )

        provider = Provider(
            self,
            "Provider",
            on_event_handler=on_event_lambda,
            is_complete_handler=is_complete_lambda,
            total_timeout=cdk.Duration.minutes(10),
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        resource = cdk.CustomResource(
            self,
            "Resource",
            service_token=provider.service_token,
            properties={
                **properties,
                "resource_iteration": "1",  # Fixed value to avoid versioning issues
            },
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        self.service_token = provider.service_token
