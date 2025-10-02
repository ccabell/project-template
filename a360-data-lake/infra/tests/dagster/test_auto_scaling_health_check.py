"""Tests for Dagster+ auto-scaling health check Lambda function."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def lambda_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.aws_request_id = "test-request-id"
    return context


@pytest.fixture
def environment_variables():
    """Set up test environment variables."""
    env_vars = {
        "CLUSTER_NAME": "test-cluster",
        "SERVICE_NAME": "test-service",
        "ALERT_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "POWERTOOLS_SERVICE_NAME": "dagster-health-check",
        "POWERTOOLS_METRICS_NAMESPACE": "DagsterPlatform/HealthCheck",
    }

    with patch.dict(os.environ, env_vars):
        yield env_vars


@pytest.fixture
def mock_boto3_clients():
    """Mock boto3 clients."""
    with patch("boto3.client") as mock_client:
        mock_ecs = MagicMock()
        mock_sns = MagicMock()

        def client_factory(service_name):
            if service_name == "ecs":
                return mock_ecs
            elif service_name == "sns":
                return mock_sns
            return MagicMock()

        mock_client.side_effect = client_factory
        yield {"ecs": mock_ecs, "sns": mock_sns}


def test_health_check_success(
    environment_variables, lambda_context, mock_boto3_clients
):
    from infra.stacks.dagster.lambda_functions.dagster_health_check.index import handler

    """Test successful health check execution."""

    mock_boto3_clients["ecs"].describe_services.return_value = {
        "services": [{"runningCount": 2, "desiredCount": 2, "status": "ACTIVE"}]
    }

    event = {}
    result = handler(event, lambda_context)

    assert result["statusCode"] == 200
    response_body = json.loads(result["body"])
    assert response_body["healthy"] is True
    assert response_body["running_count"] == 2
    assert response_body["desired_count"] == 2


def test_health_check_failure_no_running_tasks(
    environment_variables, lambda_context, mock_boto3_clients
):
    """Test health check failure when no tasks are running."""
    import infra.stacks.dagster.lambda_functions.dagster_health_check.index as health_check

    health_check.ecs_client.describe_services.return_value = {
        "services": [{"runningCount": 0, "desiredCount": 2, "status": "ACTIVE"}],
    }
    health_check.sns_client.publish = MagicMock()
    event = {}
    result = health_check.handler(event, lambda_context)
    assert result["statusCode"] == 200
    response_body = json.loads(result["body"])
    assert response_body["healthy"] is False
    health_check.sns_client.publish.assert_called_once()


def test_health_check_service_not_found(
    environment_variables, lambda_context, mock_boto3_clients
):
    """Test health check when service is not found."""
    import infra.stacks.dagster.lambda_functions.dagster_health_check.index as health_check

    health_check.ecs_client.describe_services.return_value = {"services": []}
    event = {}
    result = health_check.handler(event, lambda_context)
    assert result["statusCode"] == 200
    response_body = json.loads(result["body"])
    assert response_body["healthy"] is False
    assert response_body["reason"] == "Service not found"
