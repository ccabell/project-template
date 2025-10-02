"""Monitoring and observability infrastructure for Dagster+ services.

This module provides comprehensive monitoring including CloudWatch dashboards,
custom metrics, log aggregation, and alerting for Dagster+ hybrid deployment
with healthcare data processing compliance requirements.
"""

from typing import Any

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from aws_cdk import aws_kms as kms
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from constructs import Construct

from .constants import DAGSTER_STACK_PREFIX, LOG_RETENTION_DAYS
from .outputs import OutputManager


class MonitoringStack(Stack):
    """Monitoring and observability infrastructure for Dagster+ services.

    Creates and manages CloudWatch dashboards, custom metrics, log insights,
    and alerting infrastructure for comprehensive Dagster+ monitoring with
    healthcare data processing compliance and cost optimization.

    Attributes:
        dashboard: CloudWatch dashboard for Dagster+ monitoring.
        agent_health_alarm: CloudWatch alarm for agent health monitoring.
        pipeline_failure_alarm: CloudWatch alarm for pipeline failure detection.
        cost_alarm: CloudWatch alarm for cost threshold monitoring.
        alert_topic: SNS topic for alert notifications.
        log_insights_queries: Pre-built log insights queries for troubleshooting.
        output_manager: Manager for consistent output creation.
    """

    dashboard: cloudwatch.Dashboard
    agent_health_alarm: cloudwatch.Alarm
    pipeline_failure_alarm: cloudwatch.Alarm
    cost_alarm: cloudwatch.Alarm
    alert_topic: sns.Topic
    log_insights_queries: dict[str, logs.QueryDefinition]
    output_manager: OutputManager

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cluster_arn: str,
        service_arn: str,
        log_group_name: str,
        **kwargs: Any,
    ) -> None:
        """Initialize monitoring stack with dashboard and alerting.

        Args:
            scope: CDK construct scope for resource creation.
            construct_id: Unique identifier for this stack.
            cluster_arn: ECS cluster ARN for monitoring integration.
            service_arn: ECS service ARN for monitoring integration.
            log_group_name: CloudWatch log group name for log analysis.
            **kwargs: Additional arguments passed to parent Stack.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.output_manager = OutputManager(self, self.stack_name)
        self.cluster_arn = cluster_arn
        self.service_arn = service_arn
        self.log_group_name = log_group_name

        self.cluster_name = self._parse_name_from_arn(cluster_arn)
        self.service_name = self._parse_name_from_arn(service_arn)

        self._create_alert_topic()
        self._enforce_log_retention()
        self._create_dashboard()
        self._create_agent_health_alarm()
        self._create_pipeline_failure_alarm()
        self._create_cost_monitoring_alarm()
        self._create_log_insights_queries()
        self._create_outputs()

    @staticmethod
    def _parse_name_from_arn(arn: str) -> str:
        # ARN format: arn:aws:ecs:region:account-id:cluster/cluster-name or service/service-name
        return arn.split(":")[-1].split("/")[-1]

    def _create_alert_topic(self) -> None:
        """Create SNS topic for alert notifications.

        Configures SNS topic for delivering monitoring alerts with
        proper integration to existing notification infrastructure.
        """
        alert_key = kms.Key(
            self,
            "DagsterAlertKmsKey",
            enable_key_rotation=True,
            alias=f"alias/{DAGSTER_STACK_PREFIX}-alerts-key",
            description="KMS key for Dagster+ alert SNS topic encryption",
        )
        # Ensure compliance-safe deletion behavior
        alert_key.apply_removal_policy(RemovalPolicy.RETAIN)
        self.alert_topic = sns.Topic(
            self,
            "DagsterAlertTopic",
            topic_name=f"{DAGSTER_STACK_PREFIX}-alerts",
            display_name="Dagster+ Infrastructure Alerts",
            master_key=alert_key,
        )

    def _enforce_log_retention(self) -> None:
        """Ensure log group retention per policy."""
        logs.LogRetention(
            self,
            "DagsterLogsRetention",
            log_group_name=self.log_group_name,
            retention=LOG_RETENTION_DAYS,
        )

    def _create_dashboard(self) -> None:
        """Create CloudWatch dashboard for Dagster+ monitoring.

        Configures comprehensive dashboard with agent health, resource
        utilization, pipeline performance, and cost monitoring widgets.
        """
        self.dashboard = cloudwatch.Dashboard(
            self,
            "DagsterDashboard",
            dashboard_name=f"{DAGSTER_STACK_PREFIX}-monitoring",
            widgets=[
                [
                    cloudwatch.GraphWidget(
                        title="Agent Health and Connectivity",
                        left=[
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
                        width=12,
                        height=6,
                    ),
                ],
                [
                    cloudwatch.GraphWidget(
                        title="Resource Utilization",
                        left=[
                            cloudwatch.Metric(
                                namespace="AWS/ECS",
                                metric_name="CPUUtilization",
                                dimensions_map={
                                    "ServiceName": self.service_name,
                                    "ClusterName": self.cluster_name,
                                },
                                statistic="Average",
                                color=cloudwatch.Color.BLUE,
                            ),
                        ],
                        right=[
                            cloudwatch.Metric(
                                namespace="AWS/ECS",
                                metric_name="MemoryUtilization",
                                dimensions_map={
                                    "ServiceName": self.service_name,
                                    "ClusterName": self.cluster_name,
                                },
                                statistic="Average",
                                color=cloudwatch.Color.GREEN,
                            ),
                        ],
                        width=12,
                        height=6,
                    ),
                ],
                [
                    cloudwatch.LogQueryWidget(
                        title="Recent Error Logs",
                        log_group_names=[self.log_group_name],
                        query_lines=[
                            "fields @timestamp, @message",
                            "filter @message like /ERROR/",
                            "sort @timestamp desc",
                            "limit 20",
                        ],
                        width=24,
                        height=6,
                    ),
                ],
            ],
        )

    def _create_agent_health_alarm(self) -> None:
        """Create CloudWatch alarm for agent health monitoring.

        Configures alarm to detect when Dagster+ agent is unhealthy
        or not running with automatic notification delivery.
        """
        agent_running_metric = cloudwatch.Metric(
            namespace="AWS/ECS",
            metric_name="RunningTaskCount",
            dimensions_map={
                "ServiceName": self.service_name,
                "ClusterName": self.cluster_name,
            },
            statistic="Average",
        )

        self.agent_health_alarm = cloudwatch.Alarm(
            self,
            "AgentHealthAlarm",
            alarm_name=f"{DAGSTER_STACK_PREFIX}-agent-health",
            alarm_description="Dagster+ agent is not running or unhealthy",
            metric=agent_running_metric,
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
        )

        self.agent_health_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alert_topic),
        )

    def _create_pipeline_failure_alarm(self) -> None:
        """Create CloudWatch alarm for pipeline failure detection.

        Configures alarm to detect pipeline failures through log analysis
        with automatic notification and escalation procedures.
        """
        _pipeline_failure_filter = logs.MetricFilter(
            self,
            "PipelineFailureFilter",
            log_group=logs.LogGroup.from_log_group_name(
                self,
                "PipelineLogGroup",
                self.log_group_name,
            ),
            metric_namespace="Dagster/Pipeline",
            metric_name="Failures",
            filter_pattern=logs.FilterPattern.any_term("FAILED", "ERROR", "EXCEPTION"),
            metric_value="1",
        )

        pipeline_failure_metric = cloudwatch.Metric(
            namespace="Dagster/Pipeline",
            metric_name="Failures",
            statistic="Sum",
            period=Duration.minutes(5),
        )

        self.pipeline_failure_alarm = cloudwatch.Alarm(
            self,
            "PipelineFailureAlarm",
            alarm_name=f"{DAGSTER_STACK_PREFIX}-pipeline-failures",
            alarm_description="High rate of pipeline failures detected",
            metric=pipeline_failure_metric,
            threshold=5,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            evaluation_periods=1,
        )

        self.pipeline_failure_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alert_topic),
        )

    def _create_cost_monitoring_alarm(self) -> None:
        """Create CloudWatch alarm for cost threshold monitoring.

        Configures alarm to monitor ECS costs and alert when spending
        exceeds expected thresholds for budget management.
        """
        self.cost_alarm = cloudwatch.Alarm(
            self,
            "CostMonitoringAlarm",
            alarm_name=f"{DAGSTER_STACK_PREFIX}-estimated-charges-ecs",
            alarm_description="Estimated ECS charges exceed threshold (USD)",
            metric=cloudwatch.Metric(
                namespace="AWS/Billing",
                metric_name="EstimatedCharges",
                dimensions_map={
                    "Currency": "USD",
                    "ServiceName": "Amazon Elastic Container Service",
                },
                statistic="Maximum",
                period=Duration.hours(6),
                region="us-east-1",
                stack_region=self.region,
            ),
            threshold=100.0,  # TODO: set an environment-specific budget threshold
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=1,
        )

        self.cost_alarm.add_alarm_action(cloudwatch_actions.SnsAction(self.alert_topic))

    def _create_log_insights_queries(self) -> None:
        """Create pre-built CloudWatch Log Insights queries.

        Configures commonly used queries for troubleshooting and
        analysis of Dagster+ operations and healthcare data processing.
        """
        self.log_insights_queries = {}

        error_analysis_query = logs.QueryDefinition(
            self,
            "ErrorAnalysisQuery",
            query_definition_name=f"{DAGSTER_STACK_PREFIX}-error-analysis",
            query_string=logs.QueryString(
                fields=["@timestamp", "@message", "@logStream"],
                filter_statements=["@message like /ERROR/"],
                stats="count() by bin(5m)",
                sort="@timestamp desc",
            ),
            log_groups=[
                logs.LogGroup.from_log_group_name(
                    self,
                    "ErrorLogGroup",
                    self.log_group_name,
                ),
            ],
        )

        self.log_insights_queries["error_analysis"] = error_analysis_query

        performance_query = logs.QueryDefinition(
            self,
            "PerformanceQuery",
            query_definition_name=f"{DAGSTER_STACK_PREFIX}-performance-analysis",
            query_string=logs.QueryString(
                fields=["@timestamp", "@message"],
                filter_statements=["@message like /execution_time/"],
                parse_statements=[r"@message /execution_time: (?<duration>\d+)/"],
                stats="avg(duration), max(duration), min(duration) by bin(5m)",
                sort="@timestamp desc",
            ),
            log_groups=[
                logs.LogGroup.from_log_group_name(
                    self,
                    "PerformanceLogGroup",
                    self.log_group_name,
                ),
            ],
        )

        self.log_insights_queries["performance"] = performance_query

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for cross-stack references."""
        self.output_manager.add_output_with_ssm(
            "DashboardUrl",
            f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={self.dashboard.dashboard_name}",
            "CloudWatch dashboard URL",
            f"{self.stack_name}-Dashboard-URL",
        )

        self.output_manager.add_output_with_ssm(
            "AlertTopicArn",
            self.alert_topic.topic_arn,
            "SNS topic ARN for alerts",
            f"{self.stack_name}-Alert-Topic-ARN",
        )

    def get_dashboard_name(self) -> str:
        """Get CloudWatch dashboard name for external references.

        Returns:
            CloudWatch dashboard name.
        """
        return self.dashboard.dashboard_name

    def get_alert_topic_arn(self) -> str:
        """Get SNS alert topic ARN for notification integration.

        Returns:
            SNS topic ARN for alert delivery.
        """
        return self.alert_topic.topic_arn
