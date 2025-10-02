"""Stack for managing SageMaker inference results and data processing.

This module provides a CDK stack that creates the AWS infrastructure
required to process and store SageMaker model inference results. The stack
sets up S3 buckets, SQS queues, DynamoDB tables, and Lambda functions to
enable automated data processing workflows.
"""

import json
from typing import Any, cast

from aws_cdk import Duration, Fn, RemovalPolicy, Stack, aws_s3_notifications
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from cdk_nag import NagSuppressions
from constructs import Construct


class InferenceResultsStack(Stack):
    """Creates infrastructure for processing and storing model inference results.

    This stack sets up S3 buckets, SQS queues, DynamoDB tables, and Lambda
    functions to handle model inference data processing and storage.
    """

    @staticmethod
    def from_lookup(
        scope: Construct, id: str, stack_name: str
    ) -> "InferenceResultsStack":
        """
        References an existing InferenceResultsStack by name without recreating it.

        Args:
            scope: Parent construct
            id: Unique identifier for the reference
            stack_name: Name of the existing stack to reference

        Returns:
            Reference to the existing InferenceResultsStack
        """
        existing_stack_ref = Stack.of(scope).stack_name
        return cast(InferenceResultsStack, existing_stack_ref)

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs: Any,
    ) -> None:
        """Initializes the inference results processing stack.

        Args:
            scope: CDK app construct scope
            construct_id: Unique identifier for the stack
            **kwargs: Additional arguments passed to parent Stack
        """
        super().__init__(scope, construct_id, **kwargs)

        file = open("./examples/model_train_deploy_pipeline/project_config.json")
        variables = json.load(file)
        sm_pipeline_name = variables["SageMakerPipelineName"]
        USE_AMT = variables["USE_AMT"]

        current_region = Stack.of(self).region

        access_log_bucket_arn = Fn.import_value("accesslogbucketarn")
        access_logs_bucket = s3.Bucket.from_bucket_arn(
            self, "AccessLogsBucket", access_log_bucket_arn
        )

        inference_bucket_s3 = s3.Bucket(
            self,
            "InferenceBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            enforce_ssl=True,
            auto_delete_objects=True,
        )

        dlq = sqs.Queue(
            self,
            id="dead_letter_queue_id",
            retention_period=Duration.days(7),
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
        )
        dead_letter_queue = sqs.DeadLetterQueue(
            max_receive_count=2,
            queue=dlq,
        )

        record_queue = sqs.Queue(
            self,
            "RecordQueue",
            receive_message_wait_time=Duration.seconds(10),
            visibility_timeout=Duration.seconds(540),
            dead_letter_queue=dead_letter_queue,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        inference_ddb_table = dynamodb.Table(
            self,
            "inference_table",
            partition_key=dynamodb.Attribute(
                name="id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery_specification={
                "point_in_time_recovery_enabled": True,
                "recovery_period_in_days": 35,
            },
            removal_policy=RemovalPolicy.DESTROY,
        )
        aws_sdk_pandas_layer_arn = f"arn:aws:lambda:{current_region}:336392948345:layer:AWSSDKPandas-Python312-Arm64:16"
        aws_sdk_pandas_layer = _lambda.LayerVersion.from_layer_version_arn(
            self, "AWSSDKPandas-Layer", aws_sdk_pandas_layer_arn
        )

        powertools_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            f"arn:aws:lambda:{current_region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-arm64:7",
        )

        send_messages_to_sqs_lambda = _lambda.Function(
            self,
            "SendMessagesToSQS",
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset(
                "infrastructure/sagemaker_pipeline/lambda/send_messages_sqs/"
            ),
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            layers=[aws_sdk_pandas_layer, powertools_layer],
            environment={
                "queue_url": record_queue.queue_url,
                "POWERTOOLS_SERVICE_NAME": f"send-messages-sqs-{construct_id.lower()}",
                "LOG_LEVEL": "INFO",
            },
            timeout=Duration.seconds(90),
        )
        inference_bucket_s3.grant_read_write(send_messages_to_sqs_lambda)
        record_queue.grant_send_messages(send_messages_to_sqs_lambda)

        notification = inference_bucket_s3.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            aws_s3_notifications.LambdaDestination(send_messages_to_sqs_lambda),
            s3.NotificationKeyFilter(
                prefix="",
                suffix=".csv",
            ),
        )

        consume_messages_from_sqs_lambda = _lambda.Function(
            self,
            "ConsumeMessagesFromSQS",
            handler="index.lambda_handler",
            code=_lambda.Code.from_asset(
                "infrastructure/sagemaker_pipeline/lambda/consume_messages_sqs/"
            ),
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            layers=[aws_sdk_pandas_layer, powertools_layer],
            environment={
                "inference_ddb_table": inference_ddb_table.table_name,
                "partition_key": "id",
                "POWERTOOLS_SERVICE_NAME": f"consume-messages-sqs-{construct_id.lower()}",
                "LOG_LEVEL": "INFO",
            },
            timeout=Duration.seconds(90),
        )
        record_queue.grant_consume_messages(consume_messages_from_sqs_lambda)
        inference_ddb_table.grant_read_write_data(consume_messages_from_sqs_lambda)
        consume_messages_from_sqs_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSageMakerFullAccess")
        )

        invoke_event_source = lambda_event_sources.SqsEventSource(
            record_queue, batch_size=1
        )
        consume_messages_from_sqs_lambda.add_event_source(invoke_event_source)

        NagSuppressions.add_resource_suppressions(
            [send_messages_to_sqs_lambda.role],
            suppressions=[
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "This code is for demo purposes. So granted access to all indices of S3 bucket.",
                }
            ],
            apply_to_children=True,
        )

        NagSuppressions.add_resource_suppressions(
            [consume_messages_from_sqs_lambda.role],
            suppressions=[
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Allowing AmazonSageMakerFullAccess as it is sample code, for production usecase scope down the permission",
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
