"""Module for creating an EventBridge rule for S3 events with input transformation.

This construct sets up an EventBridge rule for S3 Object Created events that
filters based on bucket name, prefix, and suffix, and forwards transformed input
to a supported target such as an SQS queue (default), Lambda, or Step Function.
"""

from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk.aws_events import EventField
from constructs import Construct


class EventBridgeS3RuleWithTransformer(Construct):
    """A construct for creating an EventBridge rule for S3 events with input transformation.

    Attributes:
        rule: The created EventBridge Rule.
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        description: str,
        bucket_name: str,
        prefix: str,
        suffix: str,
        input_path: dict[str, str] | None = None,
        input_template: str | None = None,
        target: sqs.Queue | lambda_.IFunction | sfn.IStateMachine | None = None,
    ) -> None:
        """Initialize the EventBridgeS3RuleWithTransformer construct.

        Args:
            scope: Parent construct.
            id: Logical ID of the construct.
            description: Description of the rule's purpose.
            bucket_name: Name of the S3 bucket to filter events on.
            prefix: Prefix of the object key to match.
            suffix: Suffix of the object key to match.
            input_path: Optional input paths map for the input transformer. Defaults to None.
            input_template: Optional input template string for the input transformer. Defaults to None.
            target: Optional target resource. Defaults to SQS if not provided.
        """
        super().__init__(scope, id)

        event_pattern = events.EventPattern(
            source=["aws.s3"],
            detail_type=["Object Created"],
            detail={
                "bucket": {"name": [bucket_name]},
                "object": {"key": [{"wildcard": f"{prefix}*{suffix}"}]},
            },
        )

        self.rule = events.Rule(
            self,
            "S3ObjectCreatedRule",
            description=description,
            event_pattern=event_pattern,
        )

        transformed_input = self._create_transformed_input(input_path, input_template)
        resolved_target = self._resolve_target(target, transformed_input)
        self.rule.add_target(resolved_target)

    def _create_transformed_input(
        self,
        input_path: dict[str, str] | None,
        input_template: str | None,
    ) -> events.RuleTargetInput | None:
        """Create a transformed input for the rule target if input path or template is provided.

        Args:
            input_path: Optional input paths map for the input transformer.
            input_template: Optional input template string for the input transformer.

        Returns:
            A RuleTargetInput instance if transformation is needed, None otherwise.
        """
        if input_path and input_template:
            msg = "Provide either input_path or input_template, not both."
            raise ValueError(msg)
        if input_path:
            return events.RuleTargetInput.from_object(
                {key: EventField.from_path(path) for key, path in input_path.items()},
            )
        if input_template:
            return events.RuleTargetInput.from_text(input_template)
        return None

    def _resolve_target(
        self,
        target: sqs.Queue | lambda_.IFunction | sfn.IStateMachine | None,
        transformed_input: events.RuleTargetInput | None,
    ) -> events.IRuleTarget:
        """Resolve and return the appropriate EventBridge rule target.

        Args:
            target: Optional target to resolve.
            transformed_input: Optional input transformer to apply.

        Returns:
            An EventBridge IRuleTarget instance.
        """
        if hasattr(target, "function_arn"):
            return targets.LambdaFunction(target, event=transformed_input)
        if hasattr(target, "state_machine_arn"):
            return targets.SfnStateMachine(target, input=transformed_input)
        # SQS (duck-type to allow imported/IQueue targets)
        if target is None or hasattr(target, "queue_arn"):
            queue = target or sqs.Queue(
                self,
                "DefaultTargetQueue",
                encryption=sqs.QueueEncryption.SQS_MANAGED,
            )
            return targets.SqsQueue(queue, message=transformed_input)
        msg = "Unsupported target type. Must be SQS, Lambda, or Step Function."
        raise ValueError(msg)
