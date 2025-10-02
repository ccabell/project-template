"""Orchestrator Lambda for consultation pipeline (Dagster integration point).

This Lambda can be triggered by EventBridge or API to kick off Dagster jobs or
emit orchestration events for the medallion pipeline.
"""

import json
from typing import Any

# Optional PowerTools import for testing compatibility
try:
    from aws_lambda_powertools import Logger, Metrics, Tracer

    tracer = Tracer(service="consultation-orchestrator")
    logger = Logger(service="consultation-orchestrator")
    metrics = Metrics(
        namespace="ConsultationPipeline",
        service="consultation-orchestrator",
    )
except ImportError:
    # Mock objects for testing environments
    class MockLogger:
        def info(self, msg, **kwargs):
            pass

        def error(self, msg, **kwargs):
            pass

        def warning(self, msg, **kwargs):
            pass

        def exception(self, msg, **kwargs):
            pass

        def inject_lambda_context(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    class MockTracer:
        def capture_lambda_handler(self, *args, **kwargs):
            def decorator(func):
                def wrapper(*wrapper_args, **wrapper_kwargs):
                    return func(*wrapper_args, **wrapper_kwargs)

                return wrapper

            if len(args) == 1 and callable(args[0]) and not kwargs:
                # Called without parentheses: @decorator
                return decorator(args[0])
            # Called with parentheses: @decorator() or @decorator(params)
            return decorator

    class MockMetrics:
        def add_metric(self, *args, **kwargs):
            pass

        def add_metadata(self, *args, **kwargs):
            pass

        def log_metrics(self, *args, **kwargs):
            def decorator(func):
                def wrapper(*wrapper_args, **wrapper_kwargs):
                    return func(*wrapper_args, **wrapper_kwargs)

                return wrapper

            if len(args) == 1 and callable(args[0]) and not kwargs:
                # Called without parentheses: @decorator
                return decorator(args[0])
            # Called with parentheses: @decorator() or @decorator(params)
            return decorator

    tracer = MockTracer()
    logger = MockLogger()
    metrics = MockMetrics()


@logger.inject_lambda_context(log_event=False)
@tracer.capture_lambda_handler
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Orchestrator that validates input and processes different event types.

    Handles EventBridge events from S3 and API Gateway requests to trigger Dagster pipelines.
    """
    _ = context

    # Validate event payload
    if not event:
        logger.error("No event payload received")
        return {"statusCode": 400, "body": json.dumps({"error": "No event payload"})}

    try:
        # Check for EventBridge S3 event
        if (
            event.get("source") == "aws.s3"
            and event.get("detail-type") == "Object Created"
        ):
            return _process_s3_event(event)

        # Check for API Gateway event
        if event.get("httpMethod"):
            return _process_api_gateway_event(event)

        # Check for direct invocation with consultation details
        if event.get("source") == "consultation.pipeline":
            return _process_pipeline_event(event)

        # Unknown event type - log and accept
        logger.warning(f"Unknown event type: {event.get('source', 'no-source')}")
        return {
            "statusCode": 202,
            "body": json.dumps({"message": "orchestration accepted"}),
        }

    except Exception as e:
        logger.exception(f"Error processing orchestration event: {e!s}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


def _process_s3_event(event: dict[str, Any]) -> dict[str, Any]:
    """Process S3 EventBridge event for consultation data."""
    detail = event.get("detail", {})
    bucket = detail.get("bucket", {}).get("name")
    key = detail.get("object", {}).get("key")

    if not bucket or not key:
        logger.error("Missing bucket or key in S3 event")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid S3 event structure"}),
        }

    logger.info(f"Processing S3 event for {bucket}/{key}")

    # TODO: Extract consultation metadata from S3 key
    # TODO: Trigger Dagster pipeline via GraphQL API

    return {
        "statusCode": 202,
        "body": json.dumps(
            {
                "message": "S3 orchestration accepted",
                "bucket": bucket,
                "key": key,
            },
        ),
    }


def _process_api_gateway_event(event: dict[str, Any]) -> dict[str, Any]:
    """Process API Gateway request for consultation orchestration."""
    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        logger.exception("Invalid JSON in API Gateway request body")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON payload"}),
        }

    consultation_id = body.get("consultation_id")
    tenant_id = body.get("tenant_id")

    if not consultation_id:
        logger.error("Missing consultation_id in API request")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing consultation_id"}),
        }

    logger.info(f"Processing API request for consultation {consultation_id}")

    # TODO: Validate consultation exists
    # TODO: Trigger Dagster pipeline via GraphQL API

    return {
        "statusCode": 202,
        "body": json.dumps(
            {
                "message": "API orchestration accepted",
                "consultation_id": consultation_id,
                "tenant_id": tenant_id,
            },
        ),
    }


def _process_pipeline_event(event: dict[str, Any]) -> dict[str, Any]:
    """Process direct pipeline event for consultation orchestration."""
    consultation_id = event.get("consultation_id")
    tenant_id = event.get("tenant_id")

    if not consultation_id:
        logger.error("Missing consultation_id in pipeline event")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing consultation_id"}),
        }

    logger.info(f"Processing pipeline event for consultation {consultation_id}")

    # TODO: Trigger Dagster pipeline via GraphQL API

    return {
        "statusCode": 202,
        "body": json.dumps(
            {
                "message": "Pipeline orchestration accepted",
                "consultation_id": consultation_id,
                "tenant_id": tenant_id,
            },
        ),
    }
