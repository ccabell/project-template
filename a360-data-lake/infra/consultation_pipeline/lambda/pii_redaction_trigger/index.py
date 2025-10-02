"""Landing zone PII redaction trigger using Amazon Macie and Textract.

This Lambda is triggered by S3 object creation events in the landing bucket
and initiates PII detection using Macie and text extraction using Textract.
Outputs are written to the silver bucket, with job tracking in DynamoDB and
notifications via SNS.
"""

import json
import os
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import ClientError

# Optional PowerTools import for testing compatibility
try:
    from aws_lambda_powertools import Logger, Metrics, Tracer
    from aws_lambda_powertools.metrics import MetricUnit

    tracer = Tracer(service="consultation-pii-redaction")
    logger = Logger(service="consultation-pii-redaction")
    metrics = Metrics(
        namespace="ConsultationPipeline",
        service="consultation-pii-redaction",
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

        def inject_lambda_context(
            self,
            func=None,
            log_event=False,
            correlation_id_path=None,
            clear_state=False,
        ):
            if func is None:
                # Called with parentheses like @logger.inject_lambda_context()
                def decorator(f):
                    def wrapper(*func_args, **func_kwargs):
                        return f(*func_args, **func_kwargs)

                    return wrapper

                return decorator

            # Called without parentheses like @logger.inject_lambda_context
            def wrapper(*func_args, **func_kwargs):
                return func(*func_args, **func_kwargs)

            return wrapper

    class MockTracer:
        def capture_lambda_handler(self, func=None, *args, **kwargs):
            if func is None:
                # Called with parentheses like @tracer.capture_lambda_handler()
                def decorator(f):
                    def wrapper(*func_args, **func_kwargs):
                        return f(*func_args, **func_kwargs)

                    return wrapper

                return decorator

            # Called without parentheses like @tracer.capture_lambda_handler
            def wrapper(*func_args, **func_kwargs):
                return func(*func_args, **func_kwargs)

            return wrapper

        def capture_method(self, func=None, *args, **kwargs):
            if func is None:
                # Called with parentheses like @tracer.capture_method()
                def decorator(f):
                    def wrapper(*func_args, **func_kwargs):
                        return f(*func_args, **func_kwargs)

                    return wrapper

                return decorator

            # Called without parentheses like @tracer.capture_method
            def wrapper(*func_args, **func_kwargs):
                return func(*func_args, **func_kwargs)

            return wrapper

    class MockMetrics:
        def add_metric(self, *args, **kwargs):
            pass

        def add_metadata(self, *args, **kwargs):
            pass

        def log_metrics(
            self,
            func=None,
            capture_cold_start_metric=False,
            raise_on_empty_metrics=False,
        ):
            if func is None:
                # Called with parentheses like @metrics.log_metrics()
                def decorator(f):
                    def wrapper(*func_args, **func_kwargs):
                        return f(*func_args, **func_kwargs)

                    return wrapper

                return decorator

            # Called without parentheses like @metrics.log_metrics
            def wrapper(*func_args, **func_kwargs):
                return func(*func_args, **func_kwargs)

            return wrapper

    class MetricUnit:
        Count = "Count"
        Seconds = "Seconds"
        Bytes = "Bytes"

    tracer = MockTracer()
    logger = MockLogger()
    metrics = MockMetrics()

s3_client = boto3.client("s3")
macie_client = boto3.client("macie2")
textract_client = boto3.client("textract")
dynamodb_client = boto3.client("dynamodb")
sns_client = boto3.client("sns")

LANDING_BUCKET = os.environ["LANDING_BUCKET"]
SILVER_BUCKET = os.environ["SILVER_BUCKET"]
JOB_STATUS_TABLE = os.environ["JOB_STATUS_TABLE"]
PII_DETECTION_TOPIC_ARN = os.environ["PII_DETECTION_TOPIC_ARN"]
TEXTRACT_SNS_ROLE_ARN = os.environ["TEXTRACT_SNS_ROLE_ARN"]


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        records = event.get("Records", [])
        if not records:
            logger.warning("No S3 records found in event")
            return {"statusCode": 200, "body": "No records to process"}

        processed_objects: list[dict[str, Any]] = []
        for record in records:
            s3_info = record.get("s3", {})
            bucket_name = s3_info.get("bucket", {}).get("name")
            object_key_raw = s3_info.get("object", {}).get("key")
            if not bucket_name or not object_key_raw:
                logger.warning("Invalid S3 record structure")
                continue

            # S3 event keys are URL-encoded, decode them for proper path handling
            object_key = unquote_plus(object_key_raw)

            logger.info(f"Processing object: s3://{bucket_name}/{object_key}")
            result = process_document(bucket_name, object_key)
            processed_objects.append(result)

            metrics.add_metric(
                name="DocumentsProcessed",
                unit=MetricUnit.Count,
                value=1,
            )
            if result.get("status") == "success":
                metrics.add_metric(
                    name="DocumentsSuccessful",
                    unit=MetricUnit.Count,
                    value=1,
                )
            else:
                metrics.add_metric(
                    name="DocumentsFailed",
                    unit=MetricUnit.Count,
                    value=1,
                )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Documents processed",
                    "processed_count": len(processed_objects),
                    "results": processed_objects,
                },
            ),
        }
    except Exception:
        logger.exception("Error processing S3 event")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }


@tracer.capture_method
def process_document(bucket_name: str, object_key: str) -> dict[str, Any]:
    try:
        consultation_info = extract_consultation_info(object_key)
        if not consultation_info:
            return {
                "status": "error",
                "object_key": object_key,
                "error": "Invalid object key",
            }

        consultation_id = consultation_info["consultation_id"]
        tenant_id = consultation_info["tenant_id"]
        document_type = consultation_info["document_type"]

        if not is_supported_document_type(object_key):
            return {
                "status": "skipped",
                "object_key": object_key,
                "reason": "Unsupported document type",
            }

        textract_job_id = start_textract_job(bucket_name, object_key)
        if not textract_job_id:
            return {
                "status": "error",
                "object_key": object_key,
                "error": "Failed to start Textract job",
            }

        job_record = {
            "JobType": {"S": "TEXTRACT"},
            "JobId": {"S": textract_job_id},
            "ConsultationId": {"S": consultation_id},
            "TenantId": {"S": tenant_id},
            "DocumentType": {"S": document_type},
            "SourceBucket": {"S": bucket_name},
            "SourceKey": {"S": object_key},
            "Status": {"S": "IN_PROGRESS"},
            "StartTimestamp": {"S": datetime.now(UTC).isoformat()},
            "MacieProcessed": {"BOOL": False},
        }
        dynamodb_client.put_item(TableName=JOB_STATUS_TABLE, Item=job_record)

        return {
            "status": "success",
            "object_key": object_key,
            "textract_job_id": textract_job_id,
            "consultation_id": consultation_id,
            "tenant_id": tenant_id,
        }
    except Exception as e:
        logger.exception(f"Error processing document {object_key}")
        return {"status": "error", "object_key": object_key, "error": str(e)}


@tracer.capture_method
def extract_consultation_info(object_key: str) -> dict[str, str] | None:
    # Expected structure: documents/{tenant_id}/{consultation_id}/{filename}
    expected_min_parts = 4

    try:
        parts = object_key.split("/")
        if len(parts) >= expected_min_parts and parts[0] == "documents":
            tenant_id = parts[1]
            consultation_id = parts[2]
            filename = parts[3]

            # Validate that IDs are not empty
            if not tenant_id or not consultation_id or not filename:
                logger.warning(
                    f"Invalid object key structure: empty components in {object_key}",
                )
                return None

            document_type = filename.split(".")[0]
            if not document_type:
                logger.warning(f"Invalid filename structure in {object_key}")
                return None

            return {
                "tenant_id": tenant_id,
                "consultation_id": consultation_id,
                "document_type": document_type,
            }
    except Exception as e:
        logger.warning(f"Failed to parse object key {object_key}: {e}")
    return None


@tracer.capture_method
def is_supported_document_type(object_key: str) -> bool:
    supported_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
    lower = object_key.lower()
    return any(lower.endswith(ext) for ext in supported_extensions)


@tracer.capture_method
def start_textract_job(bucket_name: str, object_key: str) -> str | None:
    try:
        response = textract_client.start_document_analysis(
            DocumentLocation={"S3Object": {"Bucket": bucket_name, "Name": object_key}},
            FeatureTypes=["TABLES", "FORMS"],
            OutputConfig={
                "S3Bucket": SILVER_BUCKET,
                "S3Prefix": f"textract-output/{object_key}/",
            },
            NotificationChannel={
                "SNSTopicArn": PII_DETECTION_TOPIC_ARN,
                "RoleArn": TEXTRACT_SNS_ROLE_ARN,
            },
        )
        return response.get("JobId")
    except ClientError as e:
        logger.exception(f"Textract API error {e.response['Error']['Code']}: {e}")
        return None
    except Exception:
        logger.exception("Unexpected error starting Textract job")
        return None
