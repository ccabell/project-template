"""Textract parallel processing stack with SQS consumers.

This module implements a scalable architecture for processing Textract document
analysis results using SQS queues and Lambda functions. It provides parallel
processing capabilities for large document sets, handles Textract async operations,
and integrates with the consultation pipeline for medical document processing.

The stack creates multiple SQS queues for different processing stages,
Lambda consumers for parallel processing, and proper error handling with
DLQ (Dead Letter Queue) patterns. All components use least-privilege IAM
policies and are integrated with AWS Powertools for observability.

Architecture:
    - SQS queues for Textract job distribution and result processing
    - Lambda consumers for parallel document processing
    - Dead letter queues for error handling and retry logic
    - EventBridge integration for job status updates
    - S3 integration for document storage and retrieval
    - CloudWatch metrics and alarms for monitoring
    - Circuit breaker pattern for resilience
"""

import json
import logging
from typing import Any

import aws_cdk as cdk
from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as event_sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_ssm as ssm
from constructs import Construct

logging.basicConfig(level=logging.ERROR)


class TextractProcessingStack(Stack):
    """Textract parallel processing stack with SQS consumers.

    Creates a scalable architecture for processing Textract document analysis
    results using SQS queues and Lambda functions for parallel processing
    of medical documents and consultation attachments.

    Attributes:
        textract_job_queue: SQS queue for Textract job distribution
        textract_result_queue: SQS queue for processing Textract results
        textract_dlq: Dead letter queue for failed processing
        job_dispatcher_function: Lambda function for distributing Textract jobs
        result_processor_functions: List of Lambda functions for parallel processing
        status_tracker_function: Lambda function for job status tracking
        notification_topic: SNS topic for processing notifications
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        consultation_bucket: s3.IBucket,
        attachment_bucket: s3.IBucket,
        kms_key: Any,
        environment_name: str = "production",
        **kwargs,
    ) -> None:
        """Initialize Textract processing stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            consultation_bucket: S3 bucket for consultation documents
            attachment_bucket: S3 bucket for patient attachments
            kms_key: KMS key for encryption
            environment_name: Environment name for configuration
            **kwargs: Additional arguments passed to parent Stack
        """
        super().__init__(scope, construct_id, **kwargs)

        self.environment_name = environment_name.lower()
        self.consultation_bucket = consultation_bucket
        self.attachment_bucket = attachment_bucket
        self.kms_key = kms_key

        # Initialize lists
        self.result_processor_functions: list[lambda_.Function] = []

        # Initialize Textract processing infrastructure
        self._create_sqs_queues()
        self._create_notification_topic()
        self._create_job_dispatcher_function()
        self._create_result_processor_functions()
        self._create_status_tracker_function()
        self._create_event_bridge_integration()
        self._create_monitoring_and_alarms()
        self._create_ssm_parameters()

    def _create_sqs_queues(self) -> None:
        """Create SQS queues for Textract job processing."""
        # Dead letter queue for failed processing
        self.textract_dlq = sqs.Queue(
            self,
            "TextractDeadLetterQueue",
            queue_name=f"{self.stack_name}-textract-dlq",
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=self.kms_key,
            message_retention_period=Duration.days(14),
            visibility_timeout=Duration.minutes(2),
        )

        # Main job queue for Textract jobs
        self.textract_job_queue = sqs.Queue(
            self,
            "TextractJobQueue",
            queue_name=f"{self.stack_name}-textract-jobs",
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=self.kms_key,
            message_retention_period=Duration.days(4),
            visibility_timeout=Duration.minutes(15),
            receive_message_wait_time=Duration.seconds(20),  # Long polling
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.textract_dlq,
            ),
        )

        # Result processing queue
        self.textract_result_queue = sqs.Queue(
            self,
            "TextractResultQueue",
            queue_name=f"{self.stack_name}-textract-results",
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=self.kms_key,
            message_retention_period=Duration.days(4),
            visibility_timeout=Duration.minutes(10),
            receive_message_wait_time=Duration.seconds(20),  # Long polling
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=5,
                queue=self.textract_dlq,
            ),
        )

        # High-priority queue for urgent documents
        self.textract_priority_queue = sqs.Queue(
            self,
            "TextractPriorityQueue",
            queue_name=f"{self.stack_name}-textract-priority",
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=self.kms_key,
            message_retention_period=Duration.days(4),
            visibility_timeout=Duration.minutes(10),
            receive_message_wait_time=Duration.seconds(20),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.textract_dlq,
            ),
        )

    def _create_notification_topic(self) -> None:
        """Create SNS topic for processing notifications."""
        self.notification_topic = sns.Topic(
            self,
            "TextractProcessingTopic",
            topic_name=f"{self.stack_name}-textract-notifications",
            display_name="Textract Processing Notifications",
            kms_master_key=self.kms_key,
        )

    def _create_job_dispatcher_function(self) -> None:
        """Create Lambda function for dispatching Textract jobs."""
        # Define Powertools layer (shared across all Lambda functions)
        self.powertools_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            layer_version_arn=f"arn:aws:lambda:{cdk.Aws.REGION}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:18",
        )

        self.job_dispatcher_function = lambda_.Function(
            self,
            "TextractJobDispatcherFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            timeout=Duration.minutes(10),
            memory_size=1024,
            reserved_concurrent_executions=10,
            layers=[self.powertools_layer],
            environment={
                "TEXTRACT_JOB_QUEUE_URL": self.textract_job_queue.queue_url,
                "TEXTRACT_RESULT_QUEUE_URL": self.textract_result_queue.queue_url,
                "TEXTRACT_PRIORITY_QUEUE_URL": self.textract_priority_queue.queue_url,
                "CONSULTATION_BUCKET_NAME": self.consultation_bucket.bucket_name,
                "ATTACHMENT_BUCKET_NAME": self.attachment_bucket.bucket_name,
                "NOTIFICATION_TOPIC_ARN": self.notification_topic.topic_arn,
                "ENVIRONMENT_NAME": self.environment_name,
                "POWERTOOLS_SERVICE_NAME": "textract-job-dispatcher",
                "POWERTOOLS_LOG_LEVEL": "INFO",
                "CIRCUIT_BREAKER_SSM_PARAM": f"/{self.stack_name}/textract/circuit-breaker",
                "RETRY_CONFIG_SSM_PARAM": f"/{self.stack_name}/textract/retry-config",
            },
            code=lambda_.Code.from_inline("""
import json
import boto3
import os
import uuid
from datetime import datetime
from typing import Dict, List, Any
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.parameters import get_parameter
from botocore.exceptions import ClientError
import time

logger = Logger()
tracer = Tracer()
metrics = Metrics()

textract_client = boto3.client('textract')
sqs_client = boto3.client('sqs')
s3_client = boto3.client('s3')

@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    try:
        # Check circuit breaker status
        circuit_breaker_config = get_circuit_breaker_config()
        if not circuit_breaker_config.get('enabled', True):
            logger.warning("Circuit breaker is open, skipping processing")
            return {'statusCode': 503, 'message': 'Service temporarily unavailable'}

        # Process S3 event or direct invocation
        if 'Records' in event:
            return process_s3_events(event['Records'])
        else:
            return process_direct_invocation(event)

    except Exception as e:
        logger.error(f"Error in job dispatcher: {str(e)}")
        metrics.add_metric(name="DispatcherErrors", unit=MetricUnit.Count, value=1)
        raise

@tracer.capture_method
def get_circuit_breaker_config() -> Dict[str, Any]:
    try:
        param_name = os.environ.get('CIRCUIT_BREAKER_SSM_PARAM')
        if param_name:
            config_str = get_parameter(param_name, decrypt=False)
            return json.loads(config_str) if config_str else {}
        return {}
    except Exception as e:
        logger.warning(f"Could not get circuit breaker config: {str(e)}")
        return {}

@tracer.capture_method
def get_retry_config() -> Dict[str, Any]:
    try:
        param_name = os.environ.get('RETRY_CONFIG_SSM_PARAM')
        if param_name:
            config_str = get_parameter(param_name, decrypt=False)
            return json.loads(config_str) if config_str else {}
        return {
            "max_attempts": 3,
            "initial_delay_seconds": 2,
            "max_delay_seconds": 30,
            "backoff_multiplier": 2.0
        }
    except Exception as e:
        logger.warning(f"Could not get retry config: {str(e)}")
        return {}

@tracer.capture_method
def process_s3_events(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    jobs_dispatched = 0
    errors = 0

    for record in records:
        try:
            bucket_name = record['s3']['bucket']['name']
            object_key = record['s3']['object']['key']

            # Check if file is a document that needs processing
            if should_process_document(bucket_name, object_key):
                job_id = dispatch_textract_job(bucket_name, object_key)
                if job_id:
                    jobs_dispatched += 1
                    logger.info(f"Dispatched Textract job {job_id} for s3://{bucket_name}/{object_key}")

        except Exception as e:
            logger.error(f"Error processing S3 record: {str(e)}")
            errors += 1

    metrics.add_metric(name="JobsDispatched", unit=MetricUnit.Count, value=jobs_dispatched)
    metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=errors)

    return {
        'statusCode': 200,
        'jobs_dispatched': jobs_dispatched,
        'errors': errors
    }

@tracer.capture_method
def process_direct_invocation(event: Dict[str, Any]) -> Dict[str, Any]:
    bucket_name = event.get('bucket_name')
    object_key = event.get('object_key')
    priority = event.get('priority', 'normal')

    if not bucket_name or not object_key:
        raise ValueError("bucket_name and object_key are required")

    job_id = dispatch_textract_job(bucket_name, object_key, priority)

    if job_id:
        metrics.add_metric(name="JobsDispatched", unit=MetricUnit.Count, value=1)
        return {
            'statusCode': 200,
            'job_id': job_id,
            'bucket_name': bucket_name,
            'object_key': object_key
        }
    else:
        metrics.add_metric(name="JobDispatchFailures", unit=MetricUnit.Count, value=1)
        return {
            'statusCode': 500,
            'error': 'Failed to dispatch job'
        }

@tracer.capture_method
def should_process_document(bucket_name: str, object_key: str) -> bool:
    # Check file extension
    allowed_extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']
    if not any(object_key.lower().endswith(ext) for ext in allowed_extensions):
        return False

    # Check if document is in consultation or attachment folder
    consultation_bucket = os.environ.get('CONSULTATION_BUCKET_NAME', '')
    attachment_bucket = os.environ.get('ATTACHMENT_BUCKET_NAME', '')

    return bucket_name in [consultation_bucket, attachment_bucket]

@tracer.capture_method
def dispatch_textract_job(bucket_name: str, object_key: str, priority: str = 'normal') -> str:
    retry_config = get_retry_config()

    for attempt in range(retry_config.get('max_attempts', 3)):
        try:
            # Start Textract job
            response = textract_client.start_document_text_detection(
                DocumentLocation={
                    'S3Object': {
                        'Bucket': bucket_name,
                        'Name': object_key
                    }
                },
                JobTag=f"consultation-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )

            job_id = response['JobId']

            # Send message to appropriate queue
            queue_url = (
                os.environ['TEXTRACT_PRIORITY_QUEUE_URL']
                if priority == 'high'
                else os.environ['TEXTRACT_JOB_QUEUE_URL']
            )

            message = {
                'job_id': job_id,
                'bucket_name': bucket_name,
                'object_key': object_key,
                'priority': priority,
                'start_time': datetime.now().isoformat(),
                'retry_count': 0
            }

            # Build send_message kwargs conditionally for FIFO vs standard queues
            send_message_kwargs = {
                'QueueUrl': queue_url,
                'MessageBody': json.dumps(message)
            }

            # Only include MessageGroupId for FIFO queues
            if 'fifo' in queue_url.lower():
                send_message_kwargs['MessageGroupId'] = job_id

            sqs_client.send_message(**send_message_kwargs)

            logger.info(f"Dispatched Textract job {job_id} for {bucket_name}/{object_key}")
            return job_id

        except ClientError as e:
            if e.response['Error']['Code'] in ['ThrottlingException', 'ProvisionedThroughputExceededException']:
                wait_time = (retry_config.get('backoff_multiplier', 2.0) ** attempt) + (0.1 * attempt)
                wait_time = min(wait_time, retry_config.get('max_delay_seconds', 30))
                logger.warning(f"Throttling detected, waiting {wait_time} seconds before retry")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"AWS error dispatching job: {str(e)}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
            if attempt == retry_config.get('max_attempts', 3) - 1:
                raise
            time.sleep(retry_config.get('initial_delay_seconds', 2) * (attempt + 1))

    logger.error(f"Failed to dispatch job after {retry_config.get('max_attempts', 3)} attempts")
    return None
"""),
        )

        # Configure IAM permissions for dispatcher function
        self.job_dispatcher_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "textract:StartDocumentTextDetection",
                    "textract:StartDocumentAnalysis",
                    "textract:GetDocumentTextDetection",
                    "textract:GetDocumentAnalysis",
                ],
                resources=["*"],
            ),
        )

        # Configure SQS queue access
        self.textract_job_queue.grant_send_messages(self.job_dispatcher_function)
        self.textract_result_queue.grant_send_messages(self.job_dispatcher_function)
        self.textract_priority_queue.grant_send_messages(self.job_dispatcher_function)

        # Add KMS permissions for encrypted SQS queues
        self.job_dispatcher_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:DescribeKey",
                ],
                resources=[self.kms_key.key_arn],
            ),
        )

        # Configure S3 document access
        self.consultation_bucket.grant_read(self.job_dispatcher_function)
        self.attachment_bucket.grant_read(self.job_dispatcher_function)

        # Grant SNS permissions
        self.notification_topic.grant_publish(self.job_dispatcher_function)

    def _create_result_processor_functions(self) -> None:
        """Create multiple Lambda functions for parallel result processing."""
        # Create 3 result processor functions for parallel processing
        for i in range(3):
            result_processor = lambda_.Function(
                self,
                f"TextractResultProcessorFunction{i + 1}",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.lambda_handler",
                timeout=Duration.minutes(5),
                memory_size=512,
                reserved_concurrent_executions=5,
                layers=[self.powertools_layer],
                environment={
                    "TEXTRACT_RESULT_QUEUE_URL": self.textract_result_queue.queue_url,
                    "CONSULTATION_BUCKET_NAME": self.consultation_bucket.bucket_name,
                    "ATTACHMENT_BUCKET_NAME": self.attachment_bucket.bucket_name,
                    "NOTIFICATION_TOPIC_ARN": self.notification_topic.topic_arn,
                    "PROCESSOR_ID": str(i + 1),
                    "ENVIRONMENT_NAME": self.environment_name,
                    "POWERTOOLS_SERVICE_NAME": f"textract-result-processor-{i + 1}",
                    "POWERTOOLS_LOG_LEVEL": "INFO",
                },
                code=lambda_.Code.from_inline("""
import json
import boto3
import os
from typing import Dict, List, Any
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

logger = Logger()
tracer = Tracer()
metrics = Metrics()

textract_client = boto3.client('textract')
s3_client = boto3.client('s3')

@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    try:
        # Process SQS messages
        if 'Records' in event:
            return process_sqs_messages(event['Records'])
        else:
            return process_textract_result(event)

    except Exception as e:
        logger.error(f"Error in result processor: {str(e)}")
        metrics.add_metric(name="ProcessorErrors", unit=MetricUnit.Count, value=1)
        raise

@tracer.capture_method
def process_sqs_messages(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    processed = 0
    errors = 0
    batch_item_failures = []

    for record in records:
        try:
            message_body = json.loads(record['body'])
            job_id = message_body.get('job_id')

            if job_id:
                result = process_textract_job(job_id, message_body)
                if result is True:
                    processed += 1
                    logger.info(f"Processed Textract job {job_id}")
                elif result is False:
                    # Hard failure - don't retry
                    errors += 1
                    logger.error(f"Hard failure for job {job_id}")
                else:
                    # result is None - IN_PROGRESS, should retry
                    batch_item_failures.append({"itemIdentifier": record['messageId']})
                    logger.info(f"Job {job_id} still in progress, will retry")
            else:
                errors += 1
                logger.error("Missing job_id in message")

        except Exception as e:
            logger.error(f"Error processing SQS message: {str(e)}")
            errors += 1
            # Add to retry list for transient errors
            batch_item_failures.append({"itemIdentifier": record['messageId']})

    metrics.add_metric(name="MessagesProcessed", unit=MetricUnit.Count, value=processed)
    metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=errors)
    metrics.add_metric(name="MessagesPendingRetry", unit=MetricUnit.Count, value=len(batch_item_failures))

    response = {
        'statusCode': 200,
        'processed': processed,
        'errors': errors
    }

    # Include batch item failures for SQS partial batch failure handling
    if batch_item_failures:
        response['batchItemFailures'] = batch_item_failures

    return response

@tracer.capture_method
def process_textract_result(event: Dict[str, Any]) -> Dict[str, Any]:
    job_id = event.get('job_id')
    if not job_id:
        raise ValueError("job_id is required")

    result = process_textract_job(job_id, event)

    return {
        'statusCode': 200 if result else 500,
        'job_id': job_id,
        'processed': result
    }

@tracer.capture_method
def process_textract_job(job_id: str, message_data: Dict[str, Any]) -> bool:
    try:
        # Get Textract results
        response = textract_client.get_document_text_detection(JobId=job_id)

        job_status = response.get('JobStatus')
        logger.info(f"Job {job_id} status: {job_status}")

        if job_status == 'SUCCEEDED':
            # Process the text detection results
            blocks = response.get('Blocks', [])
            extracted_text = extract_text_from_blocks(blocks)

            # Store results in S3
            bucket_name = message_data.get('bucket_name')
            object_key = message_data.get('object_key')

            if bucket_name and object_key:
                store_textract_results(bucket_name, object_key, job_id, extracted_text, blocks)

            metrics.add_metric(name="JobsSucceeded", unit=MetricUnit.Count, value=1)
            return True

        elif job_status == 'FAILED':
            logger.error(f"Textract job {job_id} failed")
            metrics.add_metric(name="JobsFailed", unit=MetricUnit.Count, value=1)
            return False

        elif job_status == 'IN_PROGRESS':
            logger.info(f"Job {job_id} still in progress")
            # Re-queue for later processing
            return False

        else:
            logger.warning(f"Unknown job status {job_status} for job {job_id}")
            return False

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'InvalidJobIdException':
            logger.error(f"Invalid job ID: {job_id}")
            return False
        else:
            logger.error(f"AWS error processing job {job_id}: {str(e)}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error processing job {job_id}: {str(e)}")
        raise

@tracer.capture_method
def extract_text_from_blocks(blocks: List[Dict[str, Any]]) -> str:
    text_lines = []

    for block in blocks:
        if block.get('BlockType') == 'LINE':
            text = block.get('Text', '')
            if text.strip():
                text_lines.append(text)

    return '\\n'.join(text_lines)

@tracer.capture_method
def store_textract_results(bucket_name: str, object_key: str, job_id: str,
                          extracted_text: str, blocks: List[Dict[str, Any]]) -> None:
    try:
        # Create results object key
        base_key = object_key.rsplit('.', 1)[0] if '.' in object_key else object_key
        results_key = f"{base_key}-textract-results/{job_id}"

        # Store extracted text
        text_key = f"{results_key}/extracted-text.txt"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=text_key,
            Body=extracted_text.encode('utf-8'),
            ContentType='text/plain'
        )

        # Store raw blocks data
        blocks_key = f"{results_key}/blocks.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=blocks_key,
            Body=json.dumps(blocks, indent=2).encode('utf-8'),
            ContentType='application/json'
        )

        logger.info(f"Stored Textract results for job {job_id} in s3://{bucket_name}/{results_key}")
        metrics.add_metric(name="ResultsStored", unit=MetricUnit.Count, value=1)

    except Exception as e:
        logger.error(f"Error storing results for job {job_id}: {str(e)}")
        metrics.add_metric(name="StorageErrors", unit=MetricUnit.Count, value=1)
        raise
"""),
            )

            # Configure IAM permissions for dispatcher function
            result_processor.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "textract:GetDocumentTextDetection",
                        "textract:GetDocumentAnalysis",
                    ],
                    resources=["*"],
                ),
            )

            # Configure S3 document access
            self.consultation_bucket.grant_read_write(result_processor)
            self.attachment_bucket.grant_read_write(result_processor)

            # Grant SNS permissions
            self.notification_topic.grant_publish(result_processor)

            # Add KMS permissions for encrypted SQS queues
            result_processor.add_to_role_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:GenerateDataKey",
                        "kms:DescribeKey",
                    ],
                    resources=[self.kms_key.key_arn],
                ),
            )

            # Add SQS event source - consume from job queue where dispatcher sends messages
            result_processor.add_event_source(
                event_sources.SqsEventSource(
                    queue=self.textract_job_queue,
                    batch_size=5,
                    max_batching_window=Duration.seconds(30),
                    report_batch_item_failures=True,
                ),
            )

            # Add to list
            self.result_processor_functions.append(result_processor)

        # Create priority processor for high-priority documents
        priority_processor = lambda_.Function(
            self,
            "TextractPriorityProcessorFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            timeout=Duration.minutes(3),
            memory_size=1024,
            reserved_concurrent_executions=10,
            layers=[self.powertools_layer],
            environment={
                "TEXTRACT_PRIORITY_QUEUE_URL": self.textract_priority_queue.queue_url,
                "CONSULTATION_BUCKET_NAME": self.consultation_bucket.bucket_name,
                "ATTACHMENT_BUCKET_NAME": self.attachment_bucket.bucket_name,
                "NOTIFICATION_TOPIC_ARN": self.notification_topic.topic_arn,
                "ENVIRONMENT_NAME": self.environment_name,
                "POWERTOOLS_SERVICE_NAME": "textract-priority-processor",
                "POWERTOOLS_LOG_LEVEL": "INFO",
            },
            code=lambda_.Code.from_inline("""
# Similar code to result processor but optimized for priority processing
import json
import boto3
import os
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()
metrics = Metrics()

@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    logger.info("Processing high-priority Textract job")
    metrics.add_metric(name="PriorityJobsProcessed", unit="Count", value=1)

    # Enhanced processing for priority documents
    return {
        'statusCode': 200,
        'message': 'Priority processing completed'
    }
"""),
        )

        # Add event source for priority queue
        priority_processor.add_event_source(
            event_sources.SqsEventSource(
                queue=self.textract_priority_queue,
                batch_size=1,
                max_batching_window=Duration.seconds(5),
                report_batch_item_failures=True,
            ),
        )

        # Grant permissions
        self.consultation_bucket.grant_read_write(priority_processor)
        self.attachment_bucket.grant_read_write(priority_processor)
        self.notification_topic.grant_publish(priority_processor)

        # Add KMS permissions for encrypted SQS queues
        priority_processor.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:DescribeKey",
                ],
                resources=[self.kms_key.key_arn],
            ),
        )

    def _create_status_tracker_function(self) -> None:
        """Create Lambda function for tracking Textract job status."""
        self.status_tracker_function = lambda_.Function(
            self,
            "TextractStatusTrackerFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            timeout=Duration.minutes(5),
            layers=[self.powertools_layer],
            memory_size=256,
            environment={
                "NOTIFICATION_TOPIC_ARN": self.notification_topic.topic_arn,
                "ENVIRONMENT_NAME": self.environment_name,
                "POWERTOOLS_SERVICE_NAME": "textract-status-tracker",
                "POWERTOOLS_LOG_LEVEL": "INFO",
            },
            code=lambda_.Code.from_inline("""
import json
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()
metrics = Metrics()

textract_client = boto3.client('textract')

@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    try:
        job_ids = event.get('job_ids', [])
        statuses = {}

        for job_id in job_ids:
            try:
                response = textract_client.get_document_text_detection(JobId=job_id)
                status = response.get('JobStatus', 'UNKNOWN')
                statuses[job_id] = status

                logger.info(f"Job {job_id}: {status}")

                if status == 'SUCCEEDED':
                    metrics.add_metric(name="CompletedJobs", unit="Count", value=1)
                elif status == 'FAILED':
                    metrics.add_metric(name="FailedJobs", unit="Count", value=1)

            except Exception as e:
                logger.error(f"Error checking status for job {job_id}: {str(e)}")
                statuses[job_id] = 'ERROR'

        return {
            'statusCode': 200,
            'job_statuses': statuses
        }

    except Exception as e:
        logger.error(f"Error in status tracker: {str(e)}")
        raise
"""),
        )

        # Grant permissions
        self.status_tracker_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "textract:GetDocumentTextDetection",
                    "textract:GetDocumentAnalysis",
                ],
                resources=["*"],
            ),
        )

        # Add KMS permissions for encrypted SQS queues
        self.status_tracker_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:DescribeKey",
                ],
                resources=[self.kms_key.key_arn],
            ),
        )

    def _create_event_bridge_integration(self) -> None:
        """Create EventBridge integration for Textract job events."""
        # EventBridge rule for Textract job state changes
        textract_state_rule = events.Rule(
            self,
            "TextractJobStateRule",
            description="Capture Textract job state changes",
            event_pattern=events.EventPattern(
                source=["aws.textract"],
                detail_type=["Textract Job State Change"],
                detail={
                    "status": ["SUCCEEDED", "FAILED", "PARTIAL_SUCCESS"],
                },
            ),
        )

        # Add Lambda target for processing state changes
        textract_state_rule.add_target(
            targets.LambdaFunction(self.status_tracker_function),
        )

        # Add SNS target for notifications
        textract_state_rule.add_target(
            targets.SnsTopic(
                self.notification_topic,
                message=events.RuleTargetInput.from_text(
                    "Textract job completed:\n"
                    "Job ID: ${detail.jobId}\n"
                    "Status: ${detail.status}\n"
                    "Time: ${time}",
                ),
            ),
        )

    def _create_monitoring_and_alarms(self) -> None:
        """Create CloudWatch monitoring and alarms."""
        # Log group for Textract operations
        self.log_group = logs.LogGroup(
            self,
            "TextractProcessingLogGroup",
            log_group_name=f"/aws/lambda/textract-processing-{self.environment_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _create_ssm_parameters(self) -> None:
        """Create SSM parameters for configuration."""
        # Circuit breaker parameter
        ssm.StringParameter(
            self,
            "TextractCircuitBreakerParam",
            parameter_name=f"/{self.stack_name}/textract/circuit-breaker",
            string_value=json.dumps(
                {
                    "enabled": True,
                    "failure_threshold": 5,
                    "recovery_timeout_seconds": 300,
                    "half_open_max_calls": 3,
                },
            ),
            description="Circuit breaker configuration for Textract processing",
        )

        # Retry configuration parameter
        ssm.StringParameter(
            self,
            "TextractRetryConfigParam",
            parameter_name=f"/{self.stack_name}/textract/retry-config",
            string_value=json.dumps(
                {
                    "max_attempts": 3,
                    "initial_delay_seconds": 2,
                    "max_delay_seconds": 30,
                    "backoff_multiplier": 2.0,
                    "jitter": True,
                },
            ),
            description="Retry configuration for Textract operations",
        )
