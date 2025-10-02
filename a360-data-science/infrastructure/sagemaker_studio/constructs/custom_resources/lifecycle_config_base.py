"""
Base construct for SageMaker Studio lifecycle configurations.

Provides a standardized implementation for creating and managing SageMaker Studio
lifecycle configurations via custom resources.
"""

from aws_cdk import aws_iam as iam
from constructs import Construct

from .custom_resource_base import CustomResourceBase


class LifecycleConfigBase(CustomResourceBase):
    """
    Base construct for SageMaker Studio lifecycle configurations.

    This construct provides a standardized approach for creating lifecycle
    configurations that are attached to SageMaker Studio domains. It handles
    the creation, update, and deletion of lifecycle configurations through
    a custom resource implementation.

    Attributes:
        lifecycle_config_name: Name of the created lifecycle configuration.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        domain_id: str,
        config_name: str,
        lambda_file_path: str,
        **kwargs,
    ) -> None:
        """
        Initialize the lifecycle configuration construct.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            domain_id: SageMaker Studio domain ID
            config_name: Name for the lifecycle configuration
            lambda_file_path: Path to Lambda function code relative to lambda directory
            **kwargs: Additional arguments to pass to the parent construct
        """
        self.lifecycle_config_name = f"{domain_id}-{config_name}"

        iam_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "sagemaker:CreateStudioLifecycleConfig",
                "sagemaker:DeleteStudioLifecycleConfig",
                "sagemaker:DescribeStudioLifecycleConfig",
                "sagemaker:Describe*",
                "sagemaker:List*",
                "sagemaker:UpdateDomain",
            ],
            resources=["*"],
        )

        super().__init__(
            scope,
            construct_id,
            properties={
                "domain_id": domain_id,
                "lifecycle_config_name": self.lifecycle_config_name,
            },
            lambda_file_path=lambda_file_path,
            iam_statements=[iam_policy],
            **kwargs,
        )
