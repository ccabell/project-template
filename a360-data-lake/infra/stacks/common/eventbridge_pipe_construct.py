"""Module for EventBridge Pipe construct to connect event sources to targets.

This module provides a reusable construct for creating EventBridge Pipes that
connect sources like SQS queues to targets like Lambda functions or Step Functions
state machines, with proper input transformation and permissions.
"""

from typing import Any

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_pipes as pipes
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class EventBridgePipeConstruct(Construct):
    """Reusable EventBridge Pipe construct for connecting event sources to targets.

    This construct creates an EventBridge Pipe with common configurations for
    connecting sources (e.g., SQS) to targets (e.g., Lambda, Step Functions).

    Attributes:
        pipe_role: IAM role for the pipe execution
        pipe: The EventBridge Pipe instance
        pipe_arn: ARN of the EventBridge Pipe
    """

    def __init__(
        self,
        scope: Construct,
        id_: str,
        source: Any | str,
        target: Any | str,
        target_type: str,
        input_template: str | None = None,
        additional_role_policy_statements: list[iam.PolicyStatement] | None = None,
        batch_size: int = 10,
        maximum_batching_window_in_seconds: int = 120,
        pipe_name: str | None = None,
        removal_policy: RemovalPolicy = RemovalPolicy.DESTROY,
        enable_logging: bool = False,
        log_level: str | None = None,
        log_include_execution_data: list[str] | None = None,
        enrichment: lambda_.Function | str | None = None,
    ) -> None:
        """Initialize EventBridge Pipe with standard configurations.

        Args:
            scope: The parent CDK construct.
            id_: The construct ID.
            source: Source for the pipe (e.g., SQS queue).
            target: Target for the pipe (e.g., Lambda function).
            target_type: Type of the target ('lambda' or 'step_function').
            input_template: Template for transforming the source event.
            additional_role_policy_statements: Additional IAM policy statements.
            batch_size: Number of events to batch.
            maximum_batching_window_in_seconds: Maximum batching window.
            pipe_name: Name for the pipe.
            removal_policy: Policy for removing the pipe.
            enable_logging: Whether to enable CloudWatch logging.
            log_level: Log level for the pipe ('INFO', 'TRACE', 'ERROR', etc.).
            log_include_execution_data: List of execution data to include in logs ('ALL', etc.).
            enrichment: Optional Lambda function for enrichment.
        """
        super().__init__(scope, id_)

        self.pipe_role = iam.Role(
            self,
            "PipeRole",
            assumed_by=iam.ServicePrincipal("pipes.amazonaws.com"),
        )

        source_arn = self._configure_source_permissions(source)
        target_arn = self._configure_target_permissions(target, target_type)

        enrichment_arn = None
        if enrichment:
            enrichment_arn = self._configure_enrichment_permissions(enrichment)

        if additional_role_policy_statements:
            for statement in additional_role_policy_statements:
                self.pipe_role.add_to_policy(statement)

        source_parameters = pipes.CfnPipe.PipeSourceParametersProperty(
            sqs_queue_parameters=pipes.CfnPipe.PipeSourceSqsQueueParametersProperty(
                batch_size=batch_size,
                maximum_batching_window_in_seconds=maximum_batching_window_in_seconds,
            ),
        )

        target_parameters = self._create_target_parameters(target_type, input_template)

        pipe_props = {
            "role_arn": self.pipe_role.role_arn,
            "source": source_arn,
            "target": target_arn,
            "source_parameters": source_parameters,
            "target_parameters": target_parameters,
        }

        if enrichment_arn:
            pipe_props["enrichment"] = enrichment_arn

        if pipe_name:
            pipe_props["name"] = pipe_name

        if enable_logging and log_level:
            log_group = logs.LogGroup(
                self,
                "LogGroup",
                log_group_name=f"/aws/vendedlogs/pipes/{id_}",
                retention=logs.RetentionDays.TWO_WEEKS,
                removal_policy=removal_policy,
            )

            # CreateLogGroup does not support resource-level permissions
            self.pipe_role.add_to_policy(
                iam.PolicyStatement(
                    actions=["logs:CreateLogGroup"],
                    resources=["*"],
                ),
            )

            # Other log actions can be scoped to specific log group
            self.pipe_role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    resources=[log_group.log_group_arn, f"{log_group.log_group_arn}:*"],
                ),
            )

            pipe_props["log_configuration"] = (
                pipes.CfnPipe.PipeLogConfigurationProperty(
                    level=log_level,
                    cloudwatch_logs_log_destination=pipes.CfnPipe.CloudwatchLogsLogDestinationProperty(
                        log_group_arn=log_group.log_group_arn,
                    ),
                    include_execution_data=log_include_execution_data or [],
                )
            )

        self.pipe = pipes.CfnPipe(self, "Pipe", **pipe_props)

        self.pipe.apply_removal_policy(removal_policy)
        self.pipe_role.apply_removal_policy(removal_policy)

        self.pipe_arn = self.pipe.attr_arn

    def _configure_source_permissions(self, source: Any | str) -> str:
        """Configure permissions for the pipe to read from the source.

        Args:
            source: The source for the pipe.

        Returns:
            ARN of the source.
        """
        if hasattr(source, "queue_arn") and callable(
            getattr(source, "grant_consume_messages", None),
        ):
            source.grant_consume_messages(self.pipe_role)
            return source.queue_arn
        source_arn = source
        if source_arn.startswith("arn:aws:sqs:"):
            self.pipe_role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes",
                    ],
                    resources=[source_arn],
                ),
            )
        return source_arn

    def _configure_target_permissions(
        self,
        target: Any | str,
        target_type: str,
    ) -> str:
        """Configure permissions for the pipe to invoke the target.

        Args:
            target: The target for the pipe.
            target_type: Type of the target.

        Returns:
            ARN of the target.
        """
        if target_type.lower() == "lambda":
            if hasattr(target, "function_arn"):
                target_arn = target.function_arn
            else:
                target_arn = target

            self.pipe_role.add_to_policy(
                iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=[target_arn],
                ),
            )
            return target_arn

        if target_type.lower() == "step_function":
            if hasattr(target, "state_machine_arn"):
                target_arn = target.state_machine_arn
            else:
                target_arn = target

            self.pipe_role.add_to_policy(
                iam.PolicyStatement(
                    actions=["states:StartExecution"],
                    resources=[target_arn],
                ),
            )
            return target_arn

        msg = f"Unsupported target type: {target_type}"
        raise ValueError(msg)

    def _configure_enrichment_permissions(
        self,
        enrichment: lambda_.Function | str,
    ) -> str:
        """Configure permissions for the pipe to invoke the enrichment Lambda function.

        Args:
            enrichment: The enrichment Lambda function.

        Returns:
            ARN of the enrichment function.
        """
        if hasattr(enrichment, "function_arn"):
            enrichment_arn = enrichment.function_arn
        else:
            enrichment_arn = enrichment

        self.pipe_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[enrichment_arn],
            ),
        )
        return enrichment_arn

    def _create_target_parameters(
        self,
        target_type: str,
        input_template: str | None,
    ) -> pipes.CfnPipe.PipeTargetParametersProperty:
        """Create target parameters for the pipe.

        Args:
            target_type: Type of the target.
            input_template: Template for transforming the input.

        Returns:
            Target parameters for the pipe.
        """
        target_parameters_props = {}

        if target_type.lower() == "step_function":
            target_parameters_props["step_function_state_machine_parameters"] = (
                pipes.CfnPipe.PipeTargetStateMachineParametersProperty(
                    invocation_type="FIRE_AND_FORGET",
                )
            )

        if input_template:
            target_parameters_props["input_template"] = input_template
            # Only add SQS parameters for SQS targets to avoid synthesis errors
            if (
                target_type.lower() == "sqs"
                and "$.body" in input_template
                and "Records" in input_template
            ):
                target_parameters_props["sqs_queue_parameters"] = (
                    pipes.CfnPipe.PipeTargetSqsQueueParametersProperty(
                        message_deduplication_id="$.messageId",
                        message_group_id="$.messageId",
                    )
                )

        return pipes.CfnPipe.PipeTargetParametersProperty(**target_parameters_props)


def create_eventbridge_pipe(
    scope: Construct,
    pipe_id: str,
    source_queue: sqs.Queue,
    target_lambda: lambda_.Function,
    kms_key: kms.IKey,
    input_template: str | None = None,
    enrichment_lambda: lambda_.Function | None = None,
    enable_logging: bool = True,
    log_level: str = "INFO",
    log_include_execution_data: list[str] | None = None,
) -> EventBridgePipeConstruct:
    """Create a generic EventBridge pipe with X-Ray tracing enabled.

    Args:
        scope: The parent construct scope.
        pipe_id: ID for the pipe construct.
        source_queue: SQS queue for source.
        target_lambda: Lambda function for target.
        kms_key: KMS key for encryption permissions.
        input_template: Optional JSON template for input transformation. Defaults to None.
        enrichment_lambda: Optional Lambda function for enrichment processing.
        enable_logging: Whether to enable CloudWatch Logs. Default is True.
        log_level: Log level for the pipe. Default is INFO.
        log_include_execution_data: List of execution data types to include in logs.

    Returns:
        The created EventBridge pipe construct with tracing enabled.
    """
    if log_include_execution_data is None:
        log_include_execution_data = ["ALL"]

    pipe_props = {
        "source": source_queue,
        "target": target_lambda,
        "target_type": "lambda",
        "additional_role_policy_statements": [
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:DescribeKey",
                ],
                resources=[kms_key.key_arn],
            ),
            iam.PolicyStatement(
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                    "xray:GetSamplingStatisticSummaries",
                ],
                resources=["*"],
            ),
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                resources=["*"],
            ),
        ],
        "enable_logging": enable_logging,
        "log_level": log_level,
        "log_include_execution_data": log_include_execution_data,
    }

    if input_template:
        pipe_props["input_template"] = input_template

    if enrichment_lambda:
        pipe_props["enrichment"] = enrichment_lambda

    return EventBridgePipeConstruct(scope, pipe_id, **pipe_props)


def create_sqs_to_lambda_pipe(
    scope: Construct,
    source_queue: sqs.Queue,
    target_lambda: lambda_.Function,
    pipe_id: str,
    input_template: str | None = None,
    kms_key: kms.IKey | None = None,
    enable_logging: bool = True,
    log_level: str = "INFO",
    batch_size: int = 1,
    max_batch_window: Duration | None = None,
    pipe_role_name: str | None = None,
) -> pipes.CfnPipe:
    """Create an EventBridge Pipe connecting an SQS queue to a Lambda function.

    Args:
        scope: CDK construct scope.
        source_queue: Source SQS queue for the pipe.
        target_lambda: Target Lambda function to invoke.
        pipe_id: Identifier for the pipe.
        input_template: Optional input template for transforming the event. Defaults to None.
        kms_key: Optional KMS key for encryption permissions. Defaults to None.
        enable_logging: Whether to enable CloudWatch logging.
        log_level: Log level for the pipe (ERROR, INFO, TRACE).
        batch_size: Maximum number of records to include in a batch.
        max_batch_window: Maximum amount of time to wait before processing a batch.
        pipe_role_name: Optional custom name for the pipe execution role.

    Returns:
        The created EventBridge Pipe.
    """
    role_name = pipe_role_name or f"{pipe_id}ExecutionRole"

    pipe_role = iam.Role(
        scope,
        f"{pipe_id}Role",
        role_name=role_name,
        assumed_by=iam.ServicePrincipal("pipes.amazonaws.com"),
    )

    source_queue.grant_consume_messages(pipe_role)
    target_lambda.grant_invoke(pipe_role)

    if kms_key:
        pipe_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:DescribeKey",
                ],
                resources=[kms_key.key_arn],
            ),
        )

    pipe_role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "xray:GetSamplingRules",
                "xray:GetSamplingTargets",
                "xray:GetSamplingStatisticSummaries",
            ],
            resources=["*"],
        ),
    )

    pipe_role.add_to_policy(
        iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams",
            ],
            resources=["*"],
        ),
    )

    log_group = None
    if enable_logging:
        log_group = logs.LogGroup(
            scope,
            f"{pipe_id}LogGroup",
            log_group_name=f"/aws/vendedlogs/pipes/{pipe_id}",
            removal_policy=RemovalPolicy.RETAIN,
            retention=logs.RetentionDays.ONE_MONTH,
        )

        log_group.grant_write(pipe_role)

    pipe_props = {
        "name": pipe_id,
        "role_arn": pipe_role.role_arn,
        "source": source_queue.queue_arn,
        "source_parameters": {
            "sqsQueueParameters": {
                "batchSize": batch_size,
            },
        },
        "target": target_lambda.function_arn,
        "target_parameters": {
            "lambdaFunctionParameters": {
                "invocationType": "REQUEST_RESPONSE",
            },
        },
    }

    if input_template:
        pipe_props["target_parameters"]["inputTemplate"] = input_template

    if max_batch_window:
        pipe_props["source_parameters"]["sqsQueueParameters"][
            "maximumBatchingWindowInSeconds"
        ] = max_batch_window.to_seconds()

    if enable_logging and log_group:
        pipe_props["log_configuration"] = {
            "level": log_level,
            "includeExecutionData": ["ALL"],
            "cloudwatchLogsLogDestination": {
                "logGroupArn": log_group.log_group_arn,
            },
        }

    return pipes.CfnPipe(
        scope,
        pipe_id,
        **pipe_props,
    )


def create_sqs_lambda_enriched_pipe(
    scope: Construct,
    source_queue: sqs.Queue,
    enrichment_lambda: lambda_.Function,
    target_lambda: lambda_.Function,
    kms_key: kms.IKey,
    input_template: str | None = None,
    pipe_id: str = "SqsLambdaEnrichedPipe",
    enable_logging: bool = True,
    log_level: str = "INFO",
    log_include_execution_data: list[str] | None = None,
) -> EventBridgePipeConstruct:
    """Create EventBridge pipe with SQS source, enrichment Lambda, and target Lambda.

    This pipe creates a flow from SQS → Enrichment Lambda → Target Lambda with tracing.

    Args:
        scope: The parent construct scope.
        source_queue: SQS queue for source.
        enrichment_lambda: Lambda function for enrichment.
        target_lambda: Lambda function for target.
        kms_key: KMS key for encryption permissions.
        input_template: Optional JSON template for input transformation. Defaults to None.
        pipe_id: ID for the pipe construct.
        enable_logging: Whether to enable CloudWatch Logs. Default is True.
        log_level: Log level for the pipe. Default is INFO.
        log_include_execution_data: List of execution data types to include in logs.

    Returns:
        The created EventBridge pipe construct with tracing enabled.
    """
    return create_eventbridge_pipe(
        scope=scope,
        pipe_id=pipe_id,
        source_queue=source_queue,
        target_lambda=target_lambda,
        enrichment_lambda=enrichment_lambda,
        kms_key=kms_key,
        input_template=input_template,
        enable_logging=enable_logging,
        log_level=log_level,
        log_include_execution_data=log_include_execution_data,
    )
