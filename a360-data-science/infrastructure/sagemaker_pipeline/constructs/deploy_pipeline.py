"""
Deploy Pipeline Construct for SageMaker ML Operations workflow.

This module defines the DeployPipelineConstruct class which establishes the infrastructure
for the model deployment components, including Lambda functions for model deployment
and an S3 bucket for access logging.
"""

from typing import Any

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from cdk_nag import NagSuppressions
from constructs import Construct


class DeployPipelineConstruct(Construct):
    """
    Construct for SageMaker model deployment infrastructure.

    This construct creates the necessary AWS resources for the model deployment
    pipeline, including:
    - S3 bucket for access logging
    - Lambda function for model deployment

    Attributes:
        access_logs_bucket: S3 bucket for storing access logs
        model_deploy_lambda: Lambda function for model deployment
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs: Any) -> None:
        """
        Initialize DeployPipelineConstruct.

        Args:
            scope: Parent construct
            construct_id: Unique identifier for this construct
            **kwargs: Additional arguments to pass to the parent construct
        """
        super().__init__(scope, construct_id, **kwargs)

        self.access_logs_bucket = self._create_access_logs_bucket()
        self.model_deploy_lambda = self._create_model_deploy_lambda(construct_id)

        self._apply_nag_suppressions()

    def _create_access_logs_bucket(self) -> s3.Bucket:
        """
        Create S3 bucket for access logs.

        Returns:
            S3 bucket for access logs
        """
        bucket = s3.Bucket(
            self,
            "AccessLogsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            auto_delete_objects=True,
        )
        return bucket

    def _create_model_deploy_lambda(self, construct_id: str) -> _lambda.Function:
        """
        Create Lambda function for model deployment.

        Args:
            construct_id: Unique identifier for the construct, used for naming resources

        Returns:
            Lambda function for model deployment
        """
        current_region = Stack.of(self).region

        lambda_function = _lambda.Function(
            self,
            "SagemakerModelDeploy",
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset(
                "./infrastructure/sagemaker_pipeline/lambda/model_deploy/"
            ),
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            timeout=Duration.seconds(90),
            layers=[
                _lambda.LayerVersion.from_layer_version_arn(
                    self,
                    "PowertoolsLayer",
                    f"arn:aws:lambda:{current_region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-arm64:7",
                )
            ],
            environment={
                "POWERTOOLS_SERVICE_NAME": f"sagemaker-model-deploy-{construct_id.lower()}",
                "LOG_LEVEL": "INFO",
            },
        )

        lambda_function.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess")
        )

        return lambda_function

    def _apply_nag_suppressions(self) -> None:
        """
        Apply CDK Nag suppressions to resources.
        """
        NagSuppressions.add_resource_suppressions(
            self.model_deploy_lambda.role,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Allowing AmazonSageMakerFullAccess as it is sample code, for production usecase scope down the permission",
                }
            ],
            apply_to_children=True,
        )
