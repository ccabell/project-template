from aws_cdk import Duration, RemovalPolicy, Tags
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class QueueFactory:
    """Factory class for creating production-grade SQS queues with best practices.

    This class provides methods to create SQS queues following AWS best practices
    including encryption, dead letter queues, proper visibility timeouts,
    and monitoring capabilities.
    """

    @staticmethod
    def create_queue(
        scope: Construct,
        id_prefix: str,
        queue_name: str,
        visibility_timeout: Duration | None = None,
        retention_period: Duration | None = None,
        receive_message_wait_time: Duration | None = None,
        max_receive_count: int = 3,
        encryption: sqs.QueueEncryption = sqs.QueueEncryption.KMS,
        data_key_reuse: Duration | None = None,
        removal_policy: RemovalPolicy = RemovalPolicy.RETAIN,
        tags: dict[str, str] | None = None,
    ) -> sqs.Queue:
        """Create a production-ready SQS queue with proper encryption and DLQ.

        Args:
            scope: Construct scope for resource creation.
            id_prefix: Prefix for the construct ID.
            queue_name: Name for the SQS queue.
            visibility_timeout: Time that a message is invisible after being received.
            retention_period: Time that messages will be kept in the queue.
            receive_message_wait_time: Long polling duration for message retrieval.
            max_receive_count: Maximum number of times a message can be received
                before being sent to the DLQ.
            encryption: Type of encryption to use for the queue.
            data_key_reuse: Time that Amazon SQS reuses a data key before calling KMS again.
            removal_policy: Policy to apply when the queue is removed from the stack.
                Defaults to RETAIN to prevent accidental data loss in prod/PHI environments.
                Explicitly pass RemovalPolicy.DESTROY for dev/ephemeral environments.
            tags: Tags to apply to the queue for organizational purposes.

        Returns:
            The created SQS queue with all configurations applied.

        Note:
            The default RemovalPolicy.RETAIN protects against accidental data loss.
            For development or ephemeral environments, explicitly pass
            removal_policy=RemovalPolicy.DESTROY to enable cleanup.
        """
        dlq = sqs.Queue(
            scope,
            f"{id_prefix}DLQ",
            queue_name=f"{queue_name}-dlq",
            encryption=encryption,
            data_key_reuse=data_key_reuse,
            visibility_timeout=visibility_timeout,
            retention_period=retention_period,
            receive_message_wait_time=receive_message_wait_time,
            removal_policy=removal_policy,
        )

        main_queue = sqs.Queue(
            scope,
            id_prefix,
            queue_name=queue_name,
            encryption=encryption,
            data_key_reuse=data_key_reuse,
            visibility_timeout=visibility_timeout,
            retention_period=retention_period,
            receive_message_wait_time=receive_message_wait_time,
            removal_policy=removal_policy,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=max_receive_count,
                queue=dlq,
            ),
        )

        if tags:
            for key, value in tags.items():
                Tags.of(main_queue).add(key, value)
                Tags.of(dlq).add(key, value)

        return main_queue

    @staticmethod
    def setup_queue_monitoring(
        scope: Construct,
        queue: sqs.Queue,
        alarm_topic: sns.Topic | None = None,
        create_dashboard: bool = True,
        message_age_threshold_seconds: int = 300,
        queue_depth_threshold: int = 100,
        evaluation_periods: int = 3,
    ) -> list[cloudwatch.Alarm]:
        """Set up CloudWatch monitoring for an SQS queue.

        Args:
            scope: Construct scope for resource creation.
            queue: SQS queue to monitor.
            alarm_topic: Optional SNS topic for alarm notifications.
            create_dashboard: Whether to create a CloudWatch dashboard.
            message_age_threshold_seconds: Threshold for oldest message age.
            queue_depth_threshold: Threshold for queue depth.
            evaluation_periods: Number of periods to evaluate for alarm.

        Returns:
            List of CloudWatch alarms created.
        """
        alarms = []

        oldest_message_alarm = cloudwatch.Alarm(
            scope,
            f"{queue.node.id}OldestMessageAlarm",
            alarm_name=f"{queue.queue_name}-oldest-message-alarm",
            alarm_description=f"Alarm if oldest message in {queue.queue_name} is older than {message_age_threshold_seconds} seconds",
            metric=queue.metric_approximate_age_of_oldest_message(
                statistic="Maximum",
                period=Duration.minutes(1),
                color="#FF9900",
            ),
            threshold=message_age_threshold_seconds,
            evaluation_periods=evaluation_periods,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        alarms.append(oldest_message_alarm)

        queue_depth_alarm = cloudwatch.Alarm(
            scope,
            f"{queue.node.id}DepthAlarm",
            alarm_name=f"{queue.queue_name}-depth-alarm",
            alarm_description=f"Alarm if {queue.queue_name} depth exceeds {queue_depth_threshold} messages",
            metric=queue.metric_approximate_number_of_messages_visible(
                statistic="Maximum",
                period=Duration.minutes(1),
                color="#FF0000",
            ),
            threshold=queue_depth_threshold,
            evaluation_periods=evaluation_periods,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        alarms.append(queue_depth_alarm)

        if alarm_topic:
            for alarm in alarms:
                alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

        if create_dashboard:
            dashboard = cloudwatch.Dashboard(
                scope,
                f"{queue.node.id}Dashboard",
                dashboard_name=f"{queue.queue_name}-dashboard",
            )

            dashboard.add_widgets(
                cloudwatch.GraphWidget(
                    title="Queue Metrics",
                    left=[
                        queue.metric_approximate_number_of_messages_visible(
                            label="Messages Visible",
                            color="#1E88E5",
                            statistic="Maximum",
                        ),
                        queue.metric_approximate_number_of_messages_not_visible(
                            label="Messages In Flight",
                            color="#43A047",
                            statistic="Maximum",
                        ),
                        queue.metric_approximate_number_of_messages_delayed(
                            label="Messages Delayed",
                            color="#FB8C00",
                            statistic="Maximum",
                        ),
                    ],
                ),
                cloudwatch.GraphWidget(
                    title="Message Processing",
                    left=[
                        queue.metric_number_of_messages_sent(
                            label="Messages Sent",
                            color="#7B1FA2",
                            statistic="Sum",
                        ),
                        queue.metric_number_of_messages_received(
                            label="Messages Received",
                            color="#0097A7",
                            statistic="Sum",
                        ),
                        queue.metric_number_of_messages_deleted(
                            label="Messages Deleted",
                            color="#689F38",
                            statistic="Sum",
                        ),
                    ],
                ),
                cloudwatch.GraphWidget(
                    title="Queue Health",
                    left=[
                        queue.metric_approximate_age_of_oldest_message(
                            label="Oldest Message Age (sec)",
                            color="#D32F2F",
                            statistic="Maximum",
                        ),
                        queue.metric_sent_message_size(
                            label="Message Size",
                            color="#303F9F",
                            statistic="Average",
                        ),
                        queue.metric_number_of_empty_receives(
                            label="Empty Receives",
                            color="#F57C00",
                            statistic="Sum",
                        ),
                    ],
                ),
            )

        return alarms
