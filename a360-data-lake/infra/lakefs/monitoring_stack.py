"""LakeFS monitoring and alerting infrastructure.

This module provides comprehensive monitoring, alerting, and observability
for LakeFS operations with healthcare compliance requirements.
"""

from dataclasses import dataclass
from typing import Any

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cw_actions
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from constructs import Construct


@dataclass(frozen=True)
class LakeFSMonitoringProps:
    """Configuration properties for LakeFS monitoring stack.

    Attributes:
        cluster_name: ECS cluster name for LakeFS service.
        service_name: ECS service name for LakeFS.
        database_identifier: RDS database identifier.
        load_balancer_arn: Application Load Balancer ARN.
        notification_emails: List of email addresses for alerts.
    """

    cluster_name: str
    service_name: str
    database_identifier: str
    load_balancer_arn: str
    notification_emails: list[str]


class LakeFSMonitoringStack(Construct):
    """LakeFS monitoring and alerting infrastructure.

    Provides comprehensive monitoring dashboard, alerting for critical
    metrics, and notification system for operational incidents.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: LakeFSMonitoringProps,
        **kwargs: dict[str, Any],
    ) -> None:
        """Initialize LakeFS monitoring stack.

        Args:
            scope: CDK construct scope for resource creation.
            construct_id: Unique identifier for this construct.
            props: Configuration properties for monitoring.
            **kwargs: Additional arguments passed to parent Construct.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.cluster_name = props.cluster_name
        self.service_name = props.service_name
        self.database_identifier = props.database_identifier
        self.load_balancer_arn = props.load_balancer_arn
        self.notification_emails = props.notification_emails

        # Create SNS topic for alerts
        self._create_notification_infrastructure()

        # Create CloudWatch dashboard
        self._create_monitoring_dashboard()

        # Set up alerting rules
        self._create_alerting_rules()

        # Create custom metrics for LakeFS operations
        self._create_custom_metrics()

    def _create_notification_infrastructure(self) -> None:
        """Create SNS topic and subscriptions for monitoring alerts."""
        self.alert_topic = sns.Topic(
            self,
            "LakeFSAlertTopic",
            topic_name="lakefs-operational-alerts",
            display_name="LakeFS Operational Alerts",
        )

        # Subscribe email addresses to alerts
        for email in self.notification_emails:
            self.alert_topic.add_subscription(
                subscriptions.EmailSubscription(email),
            )

        # Create separate topic for audit events
        self.audit_topic = sns.Topic(
            self,
            "LakeFSAuditTopic",
            topic_name="lakefs-audit-events",
            display_name="LakeFS Audit Events",
        )

    def _create_monitoring_dashboard(self) -> None:
        """Create comprehensive CloudWatch dashboard for LakeFS monitoring."""
        self.dashboard = cloudwatch.Dashboard(
            self,
            "LakeFSDashboard",
            dashboard_name="LakeFS-Operations-Dashboard",
            period_override=cloudwatch.PeriodOverride.AUTO,
        )

        # ECS Service Health Metrics
        ecs_widget = cloudwatch.GraphWidget(
            title="ECS Service Health",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ECS",
                    metric_name="CPUUtilization",
                    dimensions_map={
                        "ServiceName": self.service_name,
                        "ClusterName": self.cluster_name,
                    },
                    statistic="Average",
                ),
                cloudwatch.Metric(
                    namespace="AWS/ECS",
                    metric_name="MemoryUtilization",
                    dimensions_map={
                        "ServiceName": self.service_name,
                        "ClusterName": self.cluster_name,
                    },
                    statistic="Average",
                ),
            ],
            right=[
                cloudwatch.Metric(
                    namespace="AWS/ECS",
                    metric_name="RunningTaskCount",
                    dimensions_map={
                        "ServiceName": self.service_name,
                        "ClusterName": self.cluster_name,
                    },
                    statistic="Average",
                ),
            ],
        )

        # RDS Database Metrics
        rds_widget = cloudwatch.GraphWidget(
            title="RDS Database Performance",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/RDS",
                    metric_name="CPUUtilization",
                    dimensions_map={"DBInstanceIdentifier": self.database_identifier},
                    statistic="Average",
                ),
                cloudwatch.Metric(
                    namespace="AWS/RDS",
                    metric_name="DatabaseConnections",
                    dimensions_map={"DBInstanceIdentifier": self.database_identifier},
                    statistic="Average",
                ),
            ],
            right=[
                cloudwatch.Metric(
                    namespace="AWS/RDS",
                    metric_name="FreeStorageSpace",
                    dimensions_map={"DBInstanceIdentifier": self.database_identifier},
                    statistic="Average",
                ),
            ],
        )

        # Application Load Balancer Metrics
        alb_widget = cloudwatch.GraphWidget(
            title="Load Balancer Performance",
            left=[
                cloudwatch.Metric(
                    namespace="AWS/ApplicationELB",
                    metric_name="RequestCount",
                    dimensions_map={"LoadBalancer": self._get_load_balancer_name()},
                    statistic="Sum",
                ),
                cloudwatch.Metric(
                    namespace="AWS/ApplicationELB",
                    metric_name="TargetResponseTime",
                    dimensions_map={"LoadBalancer": self._get_load_balancer_name()},
                    statistic="Average",
                ),
            ],
            right=[
                cloudwatch.Metric(
                    namespace="AWS/ApplicationELB",
                    metric_name="HTTPCode_Target_4XX_Count",
                    dimensions_map={"LoadBalancer": self._get_load_balancer_name()},
                    statistic="Sum",
                ),
                cloudwatch.Metric(
                    namespace="AWS/ApplicationELB",
                    metric_name="HTTPCode_Target_5XX_Count",
                    dimensions_map={"LoadBalancer": self._get_load_balancer_name()},
                    statistic="Sum",
                ),
            ],
        )

        # Custom LakeFS Operations Metrics
        operations_widget = cloudwatch.GraphWidget(
            title="LakeFS Operations",
            left=[
                cloudwatch.Metric(
                    namespace="LakeFS/Operations",
                    metric_name="RepositoryOperations",
                    dimensions_map={"Operation": "commit"},
                    statistic="Sum",
                ),
                cloudwatch.Metric(
                    namespace="LakeFS/Operations",
                    metric_name="RepositoryOperations",
                    dimensions_map={"Operation": "merge"},
                    statistic="Sum",
                ),
            ],
            right=[
                cloudwatch.Metric(
                    namespace="LakeFS/Operations",
                    metric_name="BranchOperations",
                    dimensions_map={"Operation": "create"},
                    statistic="Sum",
                ),
                cloudwatch.Metric(
                    namespace="LakeFS/Operations",
                    metric_name="BranchOperations",
                    dimensions_map={"Operation": "delete"},
                    statistic="Sum",
                ),
            ],
        )

        # Add all widgets to dashboard
        self.dashboard.add_widgets(ecs_widget, rds_widget)
        self.dashboard.add_widgets(alb_widget, operations_widget)

    def _create_alerting_rules(self) -> None:
        """Create CloudWatch alarms for critical LakeFS metrics."""
        # ECS Service Health Alarms
        self.cpu_alarm = cloudwatch.Alarm(
            self,
            "LakeFSHighCPUAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/ECS",
                metric_name="CPUUtilization",
                dimensions_map={
                    "ServiceName": self.service_name,
                    "ClusterName": self.cluster_name,
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=80,
            evaluation_periods=3,
            alarm_description="LakeFS ECS service CPU utilization is high",
            actions_enabled=True,
        )
        self.cpu_alarm.add_alarm_action(cw_actions.SnsAction(self.alert_topic))

        self.memory_alarm = cloudwatch.Alarm(
            self,
            "LakeFSHighMemoryAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/ECS",
                metric_name="MemoryUtilization",
                dimensions_map={
                    "ServiceName": self.service_name,
                    "ClusterName": self.cluster_name,
                },
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=85,
            evaluation_periods=3,
            alarm_description="LakeFS ECS service memory utilization is high",
            actions_enabled=True,
        )
        self.memory_alarm.add_alarm_action(cw_actions.SnsAction(self.alert_topic))

        # RDS Database Alarms
        self.db_cpu_alarm = cloudwatch.Alarm(
            self,
            "LakeFSDBHighCPUAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="CPUUtilization",
                dimensions_map={"DBInstanceIdentifier": self.database_identifier},
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=75,
            evaluation_periods=3,
            alarm_description="LakeFS RDS database CPU utilization is high",
            actions_enabled=True,
        )
        self.db_cpu_alarm.add_alarm_action(cw_actions.SnsAction(self.alert_topic))

        self.db_storage_alarm = cloudwatch.Alarm(
            self,
            "LakeFSDBLowStorageAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="FreeStorageSpace",
                dimensions_map={"DBInstanceIdentifier": self.database_identifier},
                statistic="Average",
                period=Duration.minutes(5),
            ),
            threshold=2_000_000_000,  # 2GB in bytes
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=2,
            alarm_description="LakeFS RDS database storage space is low",
            actions_enabled=True,
        )
        self.db_storage_alarm.add_alarm_action(cw_actions.SnsAction(self.alert_topic))

        # Load Balancer Health Alarms
        self.alb_5xx_alarm = cloudwatch.Alarm(
            self,
            "LakeFS5XXErrorsAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/ApplicationELB",
                metric_name="HTTPCode_Target_5XX_Count",
                dimensions_map={"LoadBalancer": self._get_load_balancer_name()},
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=10,
            evaluation_periods=2,
            alarm_description="LakeFS is experiencing high server error rates",
            actions_enabled=True,
        )
        self.alb_5xx_alarm.add_alarm_action(cw_actions.SnsAction(self.alert_topic))

    def _create_custom_metrics(self) -> None:
        """Create custom CloudWatch log groups and metrics for LakeFS operations."""
        # Log group for LakeFS application logs
        self.lakefs_log_group = logs.LogGroup(
            self,
            "LakeFSApplicationLogs",
            log_group_name="/aws/lakefs/application",
            retention=logs.RetentionDays.THREE_MONTHS,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Log group for audit trail
        self.audit_log_group = logs.LogGroup(
            self,
            "LakeFSAuditLogs",
            log_group_name="/aws/lakefs/audit",
            retention=logs.RetentionDays.ONE_YEAR,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Metric filters for operational metrics
        self.commit_metric_filter = logs.MetricFilter(
            self,
            "LakeFSCommitMetricFilter",
            log_group=self.lakefs_log_group,
            metric_namespace="LakeFS/Operations",
            metric_name="RepositoryOperations",
            filter_pattern=logs.FilterPattern.literal(
                "[timestamp, request_id, level=INFO, event=commit, ...]",
            ),
            metric_value="1",
        )

        self.merge_metric_filter = logs.MetricFilter(
            self,
            "LakeFSMergeMetricFilter",
            log_group=self.lakefs_log_group,
            metric_namespace="LakeFS/Operations",
            metric_name="RepositoryOperations",
            filter_pattern=logs.FilterPattern.literal(
                "[timestamp, request_id, level=INFO, event=merge, ...]",
            ),
            metric_value="1",
        )

        # Error tracking metric filter
        self.error_metric_filter = logs.MetricFilter(
            self,
            "LakeFSErrorMetricFilter",
            log_group=self.lakefs_log_group,
            metric_namespace="LakeFS/Errors",
            metric_name="ApplicationErrors",
            filter_pattern=logs.FilterPattern.literal(
                "[timestamp, request_id, level=ERROR, ...]",
            ),
            metric_value="1",
        )

        # Create alarm for application errors
        self.error_alarm = cloudwatch.Alarm(
            self,
            "LakeFSErrorRateAlarm",
            metric=cloudwatch.Metric(
                namespace="LakeFS/Errors",
                metric_name="ApplicationErrors",
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=5,
            evaluation_periods=2,
            alarm_description="LakeFS is experiencing high error rates",
            actions_enabled=True,
        )
        self.error_alarm.add_alarm_action(cw_actions.SnsAction(self.alert_topic))

    def _get_load_balancer_name(self) -> str:
        """Extract load balancer name from ARN for CloudWatch metrics."""
        # ALB ARN format: arn:aws:elasticloadbalancing:region:account:loadbalancer/app/name/id
        return "/".join(self.load_balancer_arn.split("/")[-3:])

    @property
    def alert_topic_arn(self) -> str:
        """ARN of the SNS topic for operational alerts."""
        return self.alert_topic.topic_arn

    @property
    def audit_topic_arn(self) -> str:
        """ARN of the SNS topic for audit events."""
        return self.audit_topic.topic_arn
