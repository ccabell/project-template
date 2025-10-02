"""Lambda that purges all DynamoDB items for a completed consultation.

Instrumentation
---------------
* **aws_lambda_powertools.Logger**  – structured JSON logging.
* **aws_lambda_powertools.Tracer**  – X‑Ray tracing for each handler and
  sub‑method.
* **aws_lambda_powertools.Metrics** – emits custom metrics to CloudWatch.
"""

from __future__ import annotations

import os
from typing import Any

import boto3
from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="ConsultationService")

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


@tracer.capture_lambda_handler
@metrics.log_metrics
def handler(event: dict[str, Any], context: LambdaContext) -> dict[str, int]:
    """Lambda entry‑point.

    Detects ``status#completed`` markers in DynamoDB stream events and removes
    all temporary session items for the associated consultation.

    Parameters
    ----------
    event :
        DynamoDB stream event payload.
    context :
        Runtime context supplied by AWS Lambda.

    Returns:
    -------
    dict[str, int]
        Counts of successfully purged consultations and failed purges.

    Raises:
    ------
    botocore.exceptions.BotoCoreError
        Propagated if a DynamoDB operation fails unexpectedly.
    """
    completed: list[str] = []
    failed: list[str] = []

    for record in event.get("Records", []):
        if record["eventName"] != "INSERT":
            continue
        new_img = record["dynamodb"]["NewImage"]
        metadata = new_img["metadata"]["S"]
        if not metadata.startswith("status#completed"):
            continue
        consultation_id = new_img["consultation_id"]["S"]
        try:
            _purge_items(consultation_id)
            completed.append(consultation_id)
            metrics.add_metric(
                name="ConsultationsPurged",
                unit=MetricUnit.Count,
                value=1,
            )
        except (BotoCoreError, ClientError) as exc:
            logger.exception("Purge failed for %s", consultation_id, exc_info=exc)
            failed.append(consultation_id)
            metrics.add_metric(name="PurgeFailures", unit=MetricUnit.Count, value=1)

    logger.info(
        "Cleanup summary",
        extra={"deleted": len(completed), "failed": len(failed)},
    )
    return {"deleted": len(completed), "failed": len(failed)}


@tracer.capture_method
def _purge_items(consultation_id: str) -> None:
    """Delete every DynamoDB item whose partition key matches *consultation_id*.

    Parameters
    ----------
    consultation_id :
        Unique consultation session identifier.

    Raises:
    ------
    botocore.exceptions.BotoCoreError
        If query or batch‑write operations fail.
    """
    paginator = table.meta.client.get_paginator("query")
    for page in paginator.paginate(
        TableName=table.name,
        KeyConditionExpression=Key("consultation_id").eq(consultation_id),
        ProjectionExpression="consultation_id, metadata",
    ):
        with table.batch_writer() as batch:
            for item in page["Items"]:
                batch.delete_item(
                    Key={
                        "consultation_id": item["consultation_id"],
                        "metadata": item["metadata"],
                    },
                )
