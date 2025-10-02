"""Stack for triggering SageMaker Pipeline execution based on S3 events.

This module provides a CDK stack that creates the AWS infrastructure
required to automatically trigger SageMaker Pipeline executions when
new data is uploaded to an S3 bucket. The stack sets up S3 buckets and
Lambda functions to enable this automated workflow.
"""

import json
from typing import Any, cast

from aws_cdk import Duration, Fn, RemovalPolicy, Stack, aws_s3_notifications
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from cdk_nag import NagSuppressions
from constructs import Construct


class StartSagemakerPipelineStack(Stack):
    """Creates infrastructure to trigger SageMaker Pipeline executions.

    This stack sets up S3 buckets and Lambda functions to automatically
    trigger pipeline executions when new training data arrives.
    """

    @staticmethod
    def from_lookup(
        scope: Construct, id: str, stack_name: str
    ) -> "StartSagemakerPipelineStack":
        """
        References an existing StartSagemakerPipelineStack by name without recreating it.

        Args:
            scope: Parent construct
            id: Unique identifier for the reference
            stack_name: Name of the existing stack to reference

        Returns:
            Reference to the existing StartSagemakerPipelineStack
        """
        existing_stack_ref = Stack.of(scope).stack_name
        return cast(StartSagemakerPipelineStack, existing_stack_ref)

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs: Any,
    ) -> None:
        """Initializes the pipeline execution trigger stack.

        Args:
            scope: CDK app construct scope
            construct_id: Unique identifier for the stack
            **kwargs: Additional arguments passed to parent Stack
        """
        super().__init__(scope, construct_id, **kwargs)

        stack_name = Stack.of(self).stack_name.lower()
        file = open("./examples/model_train_deploy_pipeline/project_config.json")
        variables = json.load(file)
        sm_pipeline_name = variables["SageMakerPipelineName"]

        current_region = Stack.of(self).region

        access_log_bucket_arn = Fn.import_value("accesslogbucketarn")
        pipeline_project_role_arn = Fn.import_value("pipelineprojectrolearn")

        access_logs_bucket = s3.Bucket.from_bucket_arn(
            self, "AccessLogsBucket", access_log_bucket_arn
        )
        pipeline_project_role = iam.Role.from_role_arn(
            self, "Project Role", pipeline_project_role_arn
        )

        training_bucket_s3 = s3.Bucket(
            self,
            "TrainingBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            enforce_ssl=True,
            auto_delete_objects=True,
        )
        training_bucket_s3.grant_read_write(pipeline_project_role)

        start_sm_pipeline_lambda = _lambda.Function(
            self,
            "start-sm-pipeline-lambda",
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset(
                "infrastructure/sagemaker_pipeline/lambda/start_sm_pipeline/"
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
                "sm_pipeline_name": sm_pipeline_name,
                "POWERTOOLS_SERVICE_NAME": f"sagemaker-pipeline-{construct_id.lower()}",
                "LOG_LEVEL": "INFO",
            },
        )

        start_sm_pipeline_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess")
        )
        training_bucket_s3.grant_read_write(start_sm_pipeline_lambda)

        notification = training_bucket_s3.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            aws_s3_notifications.LambdaDestination(start_sm_pipeline_lambda),
            s3.NotificationKeyFilter(
                prefix="training-dataset",
                suffix=".csv",
            ),
        )

        NagSuppressions.add_resource_suppressions(
            [start_sm_pipeline_lambda.role],
            suppressions=[
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Allowing AmazonSageMakerFullAccess as it is sample code, for production usecase scope down the permission",
                }
            ],
            apply_to_children=True,
        )

        NagSuppressions.add_resource_suppressions(
            [start_sm_pipeline_lambda.role, pipeline_project_role],
            suppressions=[
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "This code is for demo purposes. So granted access to all indices of S3 bucket.",
                }
            ],
            apply_to_children=True,
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Lambda execution policy for custom resources created by higher level CDK constructs",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                    ],
                }
            ],
        )

        NagSuppressions.add_resource_suppressions(
            self,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CDK BucketNotificationsHandler L1 Construct",
                }
            ],
            apply_to_children=True,
        )
