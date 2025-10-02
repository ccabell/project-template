"""Automated failover function for Dagster+ agents.

This function handles automated failover scenarios for Dagster+ agents
including service recovery, task management, and healthcare data processing
continuity with comprehensive logging and alerting.
"""

import json
import os
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit

tracer = Tracer(service="dagster-failover")
logger = Logger(service="dagster-failover")
metrics = Metrics(namespace="DagsterPlatform", service="dagster-failover")

ecs_client = boto3.client("ecs")
autoscaling_client = boto3.client("application-autoscaling")
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

        failover_result = execute_failover(cluster_name, service_name)

        metrics.add_metric(name="FailoverExecuted", unit=MetricUnit.Count, value=1)

        if failover_result["success"]:
            metrics.add_metric(name="FailoverSuccess", unit=MetricUnit.Count, value=1)
        else:
            metrics.add_metric(name="FailoverFailure", unit=MetricUnit.Count, value=1)

        send_notification(alert_topic_arn, failover_result)

        logger.info("Failover execution completed", extra={"result": failover_result})

        return {"statusCode": 200, "body": json.dumps(failover_result)}

    except Exception as e:
        logger.error("Failover execution failed", extra={"error": str(e)})
        metrics.add_metric(name="FailoverError", unit=MetricUnit.Count, value=1)
        if alert_topic_arn:
            send_notification(
                alert_topic_arn,
                {
                    "success": False,
                    "error": str(e),
                    "action": "failover_function_error",
                },
            )
        else:
            logger.warning(
                "ALERT_TOPIC_ARN missing; skipping failover alert",
                extra={"error": str(e)},
            )
        raise


@tracer.capture_method
def execute_failover(cluster_name: str, service_name: str) -> Dict[str, Any]:
    try:
        logger.info(
            "Executing failover",
            extra={"service": service_name, "cluster": cluster_name},
        )

        response = ecs_client.update_service(
            cluster=cluster_name, service=service_name, forceNewDeployment=True
        )

        result = {
            "success": True,
            "action": "force_new_deployment",
            "service_arn": response["service"]["serviceArn"],
            "deployment_id": response["service"]["deployments"][0]["id"]
            if response["service"]["deployments"]
            else None,
        }

        metrics.add_metric(name="ServiceRestarted", unit=MetricUnit.Count, value=1)

        return result

    except Exception as e:
        logger.error("Failover execution error", extra={"error": str(e)})
        raise


@tracer.capture_method
def send_notification(topic_arn: str, result: Dict[str, Any]) -> None:
    try:
        message = {"alert_type": "dagster_agent_failover", "result": result}

        sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message),
            Subject="Dagster+ Agent Failover Execution",
        )

        metrics.add_metric(name="NotificationsSent", unit=MetricUnit.Count, value=1)
        logger.info("Failover notification sent successfully")

    except Exception as e:
        logger.error("Failed to send notification", extra={"error": str(e)})
