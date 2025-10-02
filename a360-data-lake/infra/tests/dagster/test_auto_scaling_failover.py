"""Tests for Dagster+ auto-scaling failover Lambda function."""

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
        "SCALABLE_TARGET_ID": "service/test-cluster/test-service",
        "ALERT_TOPIC_ARN": "arn:aws:sns:us-east-1:123456789012:test-topic",
        "POWERTOOLS_SERVICE_NAME": "dagster-failover",
        "POWERTOOLS_METRICS_NAMESPACE": "DagsterPlatform/Failover",
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


def test_failover_success(environment_variables, lambda_context, mock_boto3_clients):
    """Test successful failover execution."""
    from infra.stacks.dagster.lambda_functions.dagster_failover.index import handler

    mock_boto3_clients["ecs"].update_service.return_value = {
        "service": {
            "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service",
            "deployments": [{"id": "ecs-svc-123456789"}],
        }
    }

    event = {}
    result = handler(event, lambda_context)

    assert result["statusCode"] == 200
    response_body = json.loads(result["body"])
    assert response_body["success"] is True
    assert response_body["action"] == "force_new_deployment"
    assert "deployment_id" in response_body

    mock_boto3_clients["ecs"].update_service.assert_called_once_with(
        cluster="test-cluster", service="test-service", forceNewDeployment=True
    )

    mock_boto3_clients["sns"].publish.assert_called_once()


def test_failover_ecs_error(environment_variables, lambda_context, mocker):
    """Test failover handling ECS service update error."""
    import infra.stacks.dagster.lambda_functions.dagster_failover.index as failover

    # Patch the already-imported ecs_client in your module
    failover.ecs_client.update_service.side_effect = Exception(
        "ECS service update failed"
    )
    failover.sns_client.publish = mocker.MagicMock()

    event = {}

    with pytest.raises(Exception, match="ECS service update failed"):
        failover.handler(event, lambda_context)

    failover.sns_client.publish.assert_called_once()
    call_args = failover.sns_client.publish.call_args
    message_body = json.loads(call_args[1]["Message"])
    assert message_body["result"]["success"] is False
