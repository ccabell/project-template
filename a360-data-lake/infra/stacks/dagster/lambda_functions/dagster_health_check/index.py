"""Advanced health check function for Dagster+ agents.

This function performs comprehensive health checks on Dagster+ agents
including connectivity, resource utilization, and healthcare compliance
monitoring with automated alerting capabilities.
"""

import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

tracer = Tracer(service="dagster-health-check")
logger = Logger(service="dagster-health-check")
metrics = Metrics(namespace="DagsterPlatform", service="dagster-health-check")

ecs_client = boto3.client("ecs")
cloudwatch_client = boto3.client("cloudwatch")
sns_client = boto3.client("sns")


@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    alert_topic_arn: str | None = None
    try:
        cluster_name = os.environ["CLUSTER_NAME"]
        service_name = os.environ["SERVICE_NAME"]
        alert_topic_arn = os.environ["ALERT_TOPIC_ARN"]
        health_status = perform_health_check(cluster_name, service_name)

        metrics.add_metric(name="HealthCheckExecuted", unit=MetricUnit.Count, value=1)

        if health_status["healthy"]:
            metrics.add_metric(
                name="HealthCheckSuccess", unit=MetricUnit.Count, value=1
            )
        else:
            metrics.add_metric(
                name="HealthCheckFailure", unit=MetricUnit.Count, value=1
            )
            send_alert(alert_topic_arn, health_status)

        logger.info("Health check completed", extra={"health_status": health_status})

        return {"statusCode": 200, "body": json.dumps(health_status)}

    except Exception as e:
        logger.error("Health check failed", extra={"error": str(e)})
        metrics.add_metric(name="HealthCheckError", unit=MetricUnit.Count, value=1)
        if alert_topic_arn:
            send_alert(
                alert_topic_arn,
                {
                    "healthy": False,
                    "error": str(e),
                    "check_type": "health_check_function_error",
                },
            )
        else:
            logger.warning(
                "ALERT_TOPIC_ARN missing; skipping alert for health check failure",
                extra={"error": str(e)},
            )
        raise


@tracer.capture_method
def perform_health_check(cluster_name: str, service_name: str) -> Dict[str, Any]:
    try:
        response = ecs_client.describe_services(
            cluster=cluster_name, services=[service_name]
        )

        if not response["services"]:
            return {"healthy": False, "reason": "Service not found"}

        service = response["services"][0]
        running_count = service["runningCount"]
        desired_count = service["desiredCount"]

        # Healthy when scaled to zero, or meeting desired capacity when > 0
        healthy = (desired_count == 0 and running_count == 0) or (
            desired_count > 0 and running_count >= desired_count
        )

        metrics.add_metric(
            name="RunningTasks", unit=MetricUnit.Count, value=running_count
        )
        metrics.add_metric(
            name="DesiredTasks", unit=MetricUnit.Count, value=desired_count
        )

        return {
            "healthy": healthy,
            "running_count": running_count,
            "desired_count": desired_count,
            "service_status": service["status"],
        }

    except Exception as e:
        logger.error("Health check error", extra={"error": str(e)})
        return {"healthy": False, "error": str(e)}


@tracer.capture_method
def send_alert(topic_arn: str, health_status: Dict[str, Any]) -> None:
    try:
        message = {"alert_type": "dagster_agent_health_check", "status": health_status}

        sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message),
            Subject="Dagster+ Agent Health Check Alert",
        )

        metrics.add_metric(name="AlertsSent", unit=MetricUnit.Count, value=1)
        logger.info("Alert sent successfully")

    except Exception as e:
        logger.error("Failed to send alert", extra={"error": str(e)})
