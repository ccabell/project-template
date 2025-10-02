"""PII redaction trigger Lambda for consultation documents.

This function is triggered when documents are uploaded to the landing zone S3 bucket.
It uses Amazon Macie to detect PII in intake forms and other documents, then
redacts sensitive information before moving to the silver layer.
"""

import json
import os
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote_plus

import boto3

# Optional PowerTools import for testing compatibility
try:
    from aws_lambda_powertools import Logger, Metrics, Tracer
    from aws_lambda_powertools.metrics import MetricUnit

    POWERTOOLS_AVAILABLE = True
except ImportError:
    POWERTOOLS_AVAILABLE = False

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

        def debug(self, msg, **kwargs):
            pass

        def inject_lambda_context(
            self,
            log_event=False,
            correlation_id_path=None,
            clear_state=False,
        ):
            def decorator(func):
                return func

            return decorator

    class MockTracer:
        def capture_lambda_handler(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def capture_method(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    class MockMetrics:
        def add_metric(self, *args, **kwargs):
            pass

        def add_metadata(self, *args, **kwargs):
            pass

        def log_metrics(
            self,
            capture_cold_start_metric=False,
            raise_on_empty_metrics=False,
        ):
            def decorator(func):
                return func

            return decorator

    class MetricUnit:
        Count = "Count"
        Seconds = "Seconds"
        Bytes = "Bytes"
        Milliseconds = "Milliseconds"

    Logger = MockLogger
    Metrics = MockMetrics
    Tracer = MockTracer

# Initialize PowerTools instances
if POWERTOOLS_AVAILABLE:
    tracer = Tracer(service="consultation-pii-redaction")
    logger = Logger(service="consultation-pii-redaction")
    metrics = Metrics(
        namespace="ConsultationPipeline",
        service="consultation-pii-redaction",
    )
else:
    tracer = MockTracer()
    logger = MockLogger()
    metrics = MockMetrics()

# Initialize AWS clients
s3_client = boto3.client("s3")
macie_client = boto3.client("macie2")
dynamodb_client = boto3.client("dynamodb")
sns_client = boto3.client("sns")

# Environment variables - safe getters
LANDING_BUCKET = os.environ.get("LANDING_BUCKET", "")
SILVER_BUCKET = os.environ.get("SILVER_BUCKET", "")
JOB_STATUS_TABLE = os.environ.get("JOB_STATUS_TABLE", "")
PII_DETECTION_TOPIC_ARN = os.environ.get("PII_DETECTION_TOPIC_ARN", "")


def _is_safe_bucket_name(bucket_name: str) -> bool:
    """Validate S3 bucket name for security.

    Args:
        bucket_name: The bucket name to validate

    Returns:
        True if the bucket name is safe, False otherwise
    """
    if not bucket_name:
        return False

    # Check for expected bucket pattern: a360-{env}-consultation-{layer}
    pattern = r'^a360-(dev|staging|prod|test)-consultation-(landing|bronze|silver|gold)$'
    return bool(re.match(pattern, bucket_name))


def _is_safe_object_key(object_key: str) -> bool:
    """Validate S3 object key for security.

    Args:
        object_key: The object key to validate

    Returns:
        True if the object key is safe, False otherwise
    """
    if not object_key:
        return False

    # Prevent directory traversal attacks
    if '..' in object_key or object_key.startswith('/') or object_key.endswith('/'):
        return False

    # Check for null bytes or other dangerous characters
    if '\x00' in object_key or any(ord(c) < 32 for c in object_key if c not in '\t\n\r'):
        return False

    # Limit key length for DoS prevention
    if len(object_key) > 1024:
        return False

    # Only allow expected file extensions
    allowed_extensions = {'.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.json'}
    if not any(object_key.lower().endswith(ext) for ext in allowed_extensions):
        return False

    return True


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle PII redaction for uploaded documents.

    Args:
        event: S3 event data containing file upload information.
        context: Lambda context object.

    Returns:
        Response dictionary with processing status.
    """
    # Validate required environment variables
    required = ["LANDING_BUCKET", "SILVER_BUCKET", "JOB_STATUS_TABLE", "PII_DETECTION_TOPIC_ARN"]
    missing = [n for n in required if not globals()[n]]
    if missing:
        logger.error("Missing required environment variables: %s", missing)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Missing required environment variables: {missing}"}),
        }

    try:
        # Process S3 event records
        for record in event.get("Records", []):
            if record.get("eventSource") == "aws:s3":
                process_s3_object(record)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "PII redaction processing initiated"}),
        }

    except Exception as e:
        logger.exception("Error processing PII redaction trigger")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)

        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "error": "Internal server error",
                    "message": str(e),
                },
            ),
        }


@tracer.capture_method
def process_s3_object(record: dict[str, Any]) -> None:
    """Process an S3 object for PII detection and redaction.

    Args:
        record: S3 event record.
    """
    s3_info = record["s3"]
    bucket_name = s3_info["bucket"]["name"]
    object_key_raw = s3_info["object"]["key"]

    # URL-decode the object key (S3 event keys are URL-encoded)
    object_key = unquote_plus(object_key_raw)

    # Validate S3 bucket name and object key for security
    if not _is_safe_bucket_name(bucket_name):
        logger.error(f"Invalid bucket name: {bucket_name}")
        return

    if not _is_safe_object_key(object_key):
        logger.error(f"Invalid object key: {object_key}")
        return

    logger.info(f"Processing object: s3://{bucket_name}/{object_key}")

    # Extract metadata from object key
    # Expected format: documents/{tenant_id}/{consultation_id}/intake_forms.pdf
    path_parts = object_key.split("/")
    if len(path_parts) < 4 or path_parts[0] != "documents":
        logger.warning(f"Invalid object key format: {object_key}")
        return

    tenant_id = path_parts[1]
    consultation_id = path_parts[2]
    document_type = path_parts[3]

    # Start Macie classification job
    logger.info(f"Starting classification for document type: {document_type}")
    job_id = start_macie_classification(
        bucket_name,
        object_key,
        tenant_id,
        consultation_id,
    )

    if job_id:
        # Store job metadata
        store_job_metadata(job_id, tenant_id, consultation_id, object_key)

        # Update metrics
        metrics.add_metric(name="MacieJobsStarted", unit=MetricUnit.Count, value=1)
    else:
        metrics.add_metric(name="MacieJobsFailed", unit=MetricUnit.Count, value=1)


@tracer.capture_method
def start_macie_classification(
    bucket_name: str,
    object_key: str,
    tenant_id: str,
    consultation_id: str,
) -> str | None:
    """Start Macie classification job for PII detection.

    Args:
        bucket_name: S3 bucket name.
        object_key: S3 object key.
        tenant_id: Tenant identifier.
        consultation_id: Consultation identifier.

    Returns:
        Macie job ID if successful, None otherwise.
    """
    try:
        job_name = f"Consultation-PII-{consultation_id}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"

        response = macie_client.create_classification_job(
            jobType="ONE_TIME",
            name=job_name,
            description=f"PII detection for consultation {consultation_id}",
            managedDataIdentifierSelector="RECOMMENDED",
            s3JobDefinition={
                "bucketDefinitions": [
                    {
                        "accountId": boto3.client("sts").get_caller_identity()[
                            "Account"
                        ],
                        "buckets": [bucket_name],
                    },
                ],
                "scoping": {
                    "includes": {
                        "and": [
                            {
                                "simpleScopeTerm": {
                                    "comparator": "STARTS_WITH",
                                    "key": "OBJECT_KEY",
                                    "values": [object_key],
                                },
                            },
                        ],
                    },
                },
            },
        )

        job_id = response["jobId"]
        logger.info(f"Started Macie classification job: {job_id}")

        return job_id

    except Exception as e:
        logger.exception(f"Error starting Macie classification job: {e}")
        return None


@tracer.capture_method
def store_job_metadata(
    job_id: str,
    tenant_id: str,
    consultation_id: str,
    object_key: str,
) -> None:
    """Store job metadata in DynamoDB.

    Args:
        job_id: Macie job ID.
        tenant_id: Tenant identifier.
        consultation_id: Consultation identifier.
        object_key: S3 object key.
    """
    try:
        dynamodb_client.put_item(
            TableName=JOB_STATUS_TABLE,
            Item={
                "JobType": {"S": "PII_DETECTION"},
                "JobId": {"S": job_id},
                "TenantId": {"S": tenant_id},
                "ConsultationId": {"S": consultation_id},
                "ObjectKey": {"S": object_key},
                "Status": {"S": "RUNNING"},
                "StartedAt": {"S": datetime.now(UTC).isoformat()},
            },
        )

        logger.info(f"Stored job metadata for {job_id}")

    except Exception as e:
        logger.exception(f"Error storing job metadata: {e}")
        # Don't raise - this is not critical for the pipeline
