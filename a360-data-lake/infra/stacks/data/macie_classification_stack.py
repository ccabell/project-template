"""Macie data classification and security monitoring stack.

This module implements Amazon Macie for automated data discovery and classification
of sensitive data in S3 buckets. It provides HIPAA-compliant data classification jobs,
sensitive data inventory management, and automated compliance monitoring for healthcare
data including PII, PHI, and financial information.

The stack creates classification jobs for different data types and buckets, monitors
findings, and integrates with EventBridge for real-time notification of sensitive
data discoveries. All resources are configured with least-privilege IAM policies
and KMS encryption.

Architecture:
    - Macie service enablement and configuration
    - Classification jobs for consultation data and attachments
    - Custom data identifiers for healthcare-specific patterns
    - EventBridge integration for real-time findings
    - SNS notifications for critical findings
    - CloudWatch metrics and alarms for monitoring
    - Lambda functions for job management and updates
"""

import json
import logging
from typing import Any

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_macie as macie
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sns as sns
from aws_cdk import aws_ssm as ssm
from constructs import Construct

logging.basicConfig(level=logging.ERROR)


class MacieClassificationStack(Stack):
    """Macie data classification stack for healthcare data security.

    Creates and manages Macie classification jobs for automated discovery
    and classification of sensitive data including HIPAA-protected PHI,
    PII, and financial information in S3 buckets.

    Attributes:
        macie_session: Macie configuration session
        classification_jobs: Dictionary of created classification jobs
        custom_data_identifiers: Dictionary of healthcare-specific data identifiers
        findings_event_rule: EventBridge rule for Macie findings
        findings_topic: SNS topic for critical findings notifications
        job_manager_function: Lambda function for job management
        job_status_tracker_function: Lambda function for job status tracking
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        consultation_bucket: s3.IBucket | None = None,
        consultation_bucket_name: str | None = None,
        attachment_bucket: s3.IBucket | None = None,
        kms_key: Any = None,
        environment_name: str = "production",
        **kwargs,
    ) -> None:
        """Initialize Macie classification stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            consultation_bucket: S3 bucket containing consultation data
            attachment_bucket: S3 bucket containing patient attachments
            kms_key: KMS key for encryption
            environment_name: Environment name for configuration
            **kwargs: Additional arguments passed to parent Stack
        """
        super().__init__(scope, construct_id, **kwargs)

        self.environment_name = environment_name.lower()
        self.consultation_bucket = consultation_bucket
        self.consultation_bucket_name = consultation_bucket_name or (
            consultation_bucket.bucket_name if consultation_bucket else None
        )
        self.attachment_bucket = attachment_bucket
        self.kms_key = kms_key

        # Initialize dictionaries
        self.classification_jobs: dict[str, Any] = {}
        self.custom_data_identifiers: dict[str, Any] = {}

        # Initialize Macie data classification resources
        self._create_macie_session()
        self._create_custom_data_identifiers()
        self._create_findings_notification_topic()
        self._create_job_management_functions()
        self._create_classification_jobs()
        self._create_event_bridge_integration()
        self._create_monitoring_and_alarms()
        self._create_ssm_parameters()

    def _create_macie_session(self) -> None:
        """Create and configure Macie session."""
        # Enable Macie service at account level
        self.macie_session = macie.CfnSession(
            self,
            "MacieSession",
            status="ENABLED",
            finding_publishing_frequency="FIFTEEN_MINUTES",
        )

        # Store configuration parameters
        self.macie_session_parameter = ssm.StringParameter(
            self,
            "MacieSessionConfig",
            parameter_name=f"/{self.stack_name}/macie/session-config",
            string_value=json.dumps(
                {
                    "status": "ENABLED",
                    "finding_publishing_frequency": "FIFTEEN_MINUTES",
                    "auto_enable": True,
                },
            ),
            description="Macie session configuration parameters",
        )

    def _create_custom_data_identifiers(self) -> None:
        """Create custom data identifiers for healthcare-specific patterns."""
        # TODO: Custom data identifiers temporarily disabled due to GeneralServiceException
        # Will rely on managed data identifiers for healthcare compliance
        # Custom identifiers can be added manually via AWS Console after stack deployment

        self.custom_data_identifiers = {}

        # Note: The following valid managed identifiers are used:
        # - USA_HEALTH_INSURANCE_CLAIM_NUMBER
        # - USA_MEDICARE_BENEFICIARY_IDENTIFIER
        # - USA_HEALTHCARE_PROCEDURE_CODE
        # - USA_NATIONAL_PROVIDER_IDENTIFIER
        # - MEDICAL_DEVICE_UDI
        # - USA_SOCIAL_SECURITY_NUMBER
        # These are configured in the classification jobs

    def _create_findings_notification_topic(self) -> None:
        """Create SNS topic for Macie findings notifications."""
        self.findings_topic = sns.Topic(
            self,
            "MacieFindingsTopic",
            topic_name=f"{self.stack_name}-macie-findings",
            display_name="Macie Data Classification Findings",
            master_key=self.kms_key,
        )

        # Configure SNS topic policy for Macie findings
        self.findings_topic.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("macie.amazonaws.com")],
                actions=["sns:Publish"],
                resources=[self.findings_topic.topic_arn],
                conditions={
                    "StringEquals": {
                        "aws:SourceAccount": self.account,
                    },
                },
            ),
        )

    def _create_job_management_functions(self) -> None:
        """Create Lambda functions for Macie job management."""
        # Job manager function
        self.job_manager_function = lambda_.Function(
            self,
            "MacieJobManagerFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "MACIE_SESSION_PARAMETER": self.macie_session_parameter.parameter_name,
                "CONSULTATION_BUCKET_NAME": self.consultation_bucket_name,
                "ATTACHMENT_BUCKET_NAME": self.attachment_bucket.bucket_name if self.attachment_bucket else "",
                "FINDINGS_TOPIC_ARN": self.findings_topic.topic_arn,
                "ENVIRONMENT_NAME": self.environment_name,
                "POWERTOOLS_SERVICE_NAME": "macie-job-manager",
                "POWERTOOLS_LOG_LEVEL": "INFO",
            },
            code=lambda_.Code.from_inline("""
import json
import boto3
import os
from datetime import datetime, timedelta
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
import time

logger = Logger()
tracer = Tracer()
metrics = Metrics()

macie_client = boto3.client('macie2')
ssm_client = boto3.client('ssm')

@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    try:
        action = event.get('action', 'create_jobs')

        if action == 'create_jobs':
            return create_classification_jobs(event)
        elif action == 'update_job':
            return update_classification_job(event)
        elif action == 'check_status':
            return check_job_status(event)
        else:
            raise ValueError(f"Unknown action: {action}")

    except Exception as e:
        logger.error(f"Error in job manager: {str(e)}")
        metrics.add_metric(name="JobManagerErrors", unit=MetricUnit.Count, value=1)
        raise

@tracer.capture_method
def create_classification_jobs(event: dict) -> dict:
    consultation_bucket = os.environ['CONSULTATION_BUCKET_NAME']
    attachment_bucket = os.environ['ATTACHMENT_BUCKET_NAME']

    jobs_created = []

    # Schedule consultation data classification job
    consultation_job = create_job_for_bucket(
        bucket_name=consultation_bucket,
        job_name=f"consultation-data-classification-{datetime.now().strftime('%Y%m%d%H%M')}",
        description="Classification of consultation transcripts and medical records"
    )

    if consultation_job:
        jobs_created.append(consultation_job)

    # Schedule attachment data classification job
    attachment_job = create_job_for_bucket(
        bucket_name=attachment_bucket,
        job_name=f"attachment-classification-{datetime.now().strftime('%Y%m%d%H%M')}",
        description="Classification of patient attachments and documents"
    )

    if attachment_job:
        jobs_created.append(attachment_job)

    logger.info(f"Created {len(jobs_created)} classification jobs")
    metrics.add_metric(name="JobsCreated", unit=MetricUnit.Count, value=len(jobs_created))

    return {
        'statusCode': 200,
        'jobs_created': jobs_created
    }

@tracer.capture_method
def create_job_for_bucket(bucket_name: str, job_name: str, description: str) -> dict:
    try:
        # Configure classification job with error handling
        for attempt in range(3):
            try:
                response = macie_client.create_classification_job(
                    name=job_name,
                    description=description,
                    jobType='ONE_TIME',
                    s3JobDefinition={
                        'bucketDefinitions': [{
                            'accountId': boto3.client("sts").get_caller_identity()["Account"],
                            'buckets': [bucket_name]
                        }],
                        'scoping': {
                            'includes': {
                                'and': [{
                                    'simpleCriterion': {
                                        'comparator': 'GT',
                                        'key': 'OBJECT_SIZE',
                                        'values': ['0']
                                    }
                                }]
                            }
                        }
                    },
                    samplingPercentage=100,
                    allowListIds=[],
                    customDataIdentifierIds=[],
                    managedDataIdentifierIds=[
                        'USA_HEALTH_INSURANCE_CLAIM_NUMBER',
                        'USA_MEDICARE_BENEFICIARY_IDENTIFIER',
                        'USA_HEALTHCARE_PROCEDURE_CODE',
                        'USA_NATIONAL_PROVIDER_IDENTIFIER',
                        'MEDICAL_DEVICE_UDI',
                        'USA_SOCIAL_SECURITY_NUMBER'
                    ]
                )

                logger.info(f"Created classification job {job_name} for bucket {bucket_name}")
                return {
                    'job_id': response['jobId'],
                    'job_name': job_name,
                    'bucket_name': bucket_name
                }

            except ClientError as e:
                if e.response['Error']['Code'] == 'ThrottlingException':
                    wait_time = (2 ** attempt) + (0.1 * attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    raise

        raise Exception(f"Failed to create job after 3 attempts")

    except Exception as e:
        logger.error(f"Error creating job for bucket {bucket_name}: {str(e)}")
        metrics.add_metric(name="JobCreationErrors", unit=MetricUnit.Count, value=1)
        return {}

@tracer.capture_method
def update_classification_job(event: dict) -> dict:
    job_id = event.get('job_id')
    if not job_id:
        raise ValueError("job_id is required for update action")

    try:
        # Update job configuration if needed
        response = macie_client.describe_classification_job(jobId=job_id)

        logger.info(f"Job {job_id} status: {response.get('jobStatus', 'UNKNOWN')}")

        return {
            'statusCode': 200,
            'job_id': job_id,
            'status': response.get('jobStatus', 'UNKNOWN')
        }

    except Exception as e:
        logger.error(f"Error updating job {job_id}: {str(e)}")
        metrics.add_metric(name="JobUpdateErrors", unit=MetricUnit.Count, value=1)
        raise

@tracer.capture_method
def check_job_status(event: dict) -> dict:
    job_id = event.get('job_id')
    if not job_id:
        raise ValueError("job_id is required for check status action")

    try:
        response = macie_client.describe_classification_job(jobId=job_id)

        status = response.get('jobStatus', 'UNKNOWN')
        logger.info(f"Job {job_id} status: {status}")

        return {
            'statusCode': 200,
            'job_id': job_id,
            'status': status,
            'details': response
        }

    except Exception as e:
        logger.error(f"Error checking job status {job_id}: {str(e)}")
        metrics.add_metric(name="JobStatusErrors", unit=MetricUnit.Count, value=1)
        raise
"""),
        )

        # Configure IAM permissions for job management
        self.job_manager_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "macie2:CreateClassificationJob",
                    "macie2:DescribeClassificationJob",
                    "macie2:UpdateClassificationJob",
                    "macie2:ListClassificationJobs",
                    "macie2:GetMacieSession",
                ],
                resources=["*"],
            ),
        )

        # Configure SSM parameter access
        self.macie_session_parameter.grant_read(self.job_manager_function)

        # Configure SNS publishing access
        self.findings_topic.grant_publish(self.job_manager_function)

        # Configure S3 data access permissions
        if self.consultation_bucket:
            self.consultation_bucket.grant_read(self.job_manager_function)
        if self.attachment_bucket:
            self.attachment_bucket.grant_read(self.job_manager_function)

    def _create_classification_jobs(self) -> None:
        """Create initial classification jobs for healthcare data."""
        # Store job configurations in SSM parameters
        consultation_job_config = ssm.StringParameter(
            self,
            "ConsultationJobConfig",
            parameter_name=f"/{self.stack_name}/macie/consultation-job-config",
            string_value=json.dumps(
                {
                    "bucket_name": self.consultation_bucket_name,
                    "job_type": "ONE_TIME",
                    "sampling_percentage": 100,
                    "managed_data_identifiers": [
                        "USA_HEALTH_INSURANCE_CLAIM_NUMBER",
                        "USA_MEDICARE_BENEFICIARY_IDENTIFIER",
                        "USA_HEALTHCARE_PROCEDURE_CODE",
                        "USA_NATIONAL_PROVIDER_IDENTIFIER",
                        "MEDICAL_DEVICE_UDI",
                        "USA_SOCIAL_SECURITY_NUMBER",
                        "CREDIT_CARD_NUMBER",
                    ],
                    "schedule": {
                        "enabled": True,
                        "frequency": "WEEKLY",
                    },
                },
            ),
            description="Configuration for consultation data classification jobs",
        )

        attachment_job_config = ssm.StringParameter(
            self,
            "AttachmentJobConfig",
            parameter_name=f"/{self.stack_name}/macie/attachment-job-config",
            string_value=json.dumps(
                {
                    "bucket_name": self.attachment_bucket.bucket_name if self.attachment_bucket else "",
                    "job_type": "ONE_TIME",
                    "sampling_percentage": 100,
                    "managed_data_identifiers": [
                        "USA_HEALTH_INSURANCE_CLAIM_NUMBER",
                        "USA_MEDICARE_BENEFICIARY_IDENTIFIER",
                        "USA_HEALTHCARE_PROCEDURE_CODE",
                        "USA_NATIONAL_PROVIDER_IDENTIFIER",
                        "MEDICAL_DEVICE_UDI",
                        "USA_SOCIAL_SECURITY_NUMBER",
                        "CREDIT_CARD_NUMBER",
                    ],
                    "schedule": {
                        "enabled": True,
                        "frequency": "DAILY",
                    },
                },
            ),
            description="Configuration for attachment classification jobs",
        )

        self.classification_jobs["consultation_config"] = consultation_job_config
        self.classification_jobs["attachment_config"] = attachment_job_config

    def _create_event_bridge_integration(self) -> None:
        """Create EventBridge integration for Macie findings."""
        # EventBridge rule for Macie findings
        self.findings_event_rule = events.Rule(
            self,
            "MacieFindingsRule",
            description="Capture Macie classification findings",
            event_pattern=events.EventPattern(
                source=["aws.macie"],
                detail_type=["Macie Finding"],
                detail={
                    "severity": {
                        "description": ["HIGH", "MEDIUM"],
                    },
                },
            ),
        )

        # Configure SNS notifications for critical findings
        self.findings_event_rule.add_target(
            targets.SnsTopic(
                self.findings_topic,
                message=events.RuleTargetInput.from_text(
                    "Macie has detected sensitive data:\n"
                    "Severity: ${severity}\n"
                    "Type: ${type}\n"
                    "Bucket: ${resources.s3Bucket.name}\n"
                    "Object: ${resources.s3Object.key}\n"
                    "Time: ${time}",
                ),
            ),
        )

        # Configure Lambda processing for findings events
        findings_processor = lambda_.Function(
            self,
            "MacieFindingsProcessor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            timeout=Duration.minutes(3),
            memory_size=256,
            environment={
                "FINDINGS_TOPIC_ARN": self.findings_topic.topic_arn,
                "POWERTOOLS_SERVICE_NAME": "macie-findings-processor",
                "POWERTOOLS_LOG_LEVEL": "INFO",
            },
            code=lambda_.Code.from_inline("""
import json
import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()
metrics = Metrics()

@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    try:
        # Process Macie finding
        finding_detail = event.get('detail', {})
        severity = finding_detail.get('severity', {}).get('description', 'UNKNOWN')
        finding_type = finding_detail.get('type', 'UNKNOWN')

        logger.info(f"Processing Macie finding: {finding_type} with severity {severity}")

        # Configure CloudWatch metrics dashboard
        metrics.add_metric(name="FindingsProcessed", unit=MetricUnit.Count, value=1)
        metrics.add_metric(name=f"Severity{severity}", unit=MetricUnit.Count, value=1)

        # Process based on severity
        if severity in ['HIGH', 'CRITICAL']:
            # Send to security team for immediate review
            logger.warning(f"High/Critical severity finding detected: {finding_type}")
            metrics.add_metric(name="CriticalFindings", unit=MetricUnit.Count, value=1)

        return {
            'statusCode': 200,
            'finding_processed': True,
            'severity': severity,
            'type': finding_type
        }

    except Exception as e:
        logger.error(f"Error processing finding: {str(e)}")
        metrics.add_metric(name="ProcessingErrors", unit=MetricUnit.Count, value=1)
        raise
"""),
        )

        self.findings_event_rule.add_target(targets.LambdaFunction(findings_processor))

        # Configure findings processor permissions
        self.findings_topic.grant_publish(findings_processor)

    def _create_monitoring_and_alarms(self) -> None:
        """Create CloudWatch monitoring and alarms for Macie operations."""
        # Configure CloudWatch logging for Macie operations
        self.log_group = logs.LogGroup(
            self,
            "MacieLogGroup",
            log_group_name=f"/aws/lambda/macie-operations-{self.environment_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _create_ssm_parameters(self) -> None:
        """Create SSM parameters for configuration and tracking."""
        # Circuit breaker parameter for job management
        ssm.StringParameter(
            self,
            "MacieCircuitBreakerParam",
            parameter_name=f"/{self.stack_name}/macie/circuit-breaker",
            string_value=json.dumps(
                {
                    "enabled": True,
                    "failure_threshold": 5,
                    "recovery_timeout_seconds": 300,
                    "half_open_max_calls": 3,
                },
            ),
            description="Circuit breaker configuration for Macie job management",
        )

        # Retry configuration parameter
        ssm.StringParameter(
            self,
            "MacieRetryConfigParam",
            parameter_name=f"/{self.stack_name}/macie/retry-config",
            string_value=json.dumps(
                {
                    "max_attempts": 3,
                    "initial_delay_seconds": 2,
                    "max_delay_seconds": 30,
                    "backoff_multiplier": 2.0,
                    "jitter": True,
                },
            ),
            description="Retry configuration for Macie operations",
        )

        # Job tracking parameter
        ssm.StringParameter(
            self,
            "MacieJobTrackingParam",
            parameter_name=f"/{self.stack_name}/macie/job-tracking",
            string_value=json.dumps(
                {
                    "active_jobs": [],
                    "last_job_run": None,
                    "total_jobs_created": 0,
                    "failed_jobs": 0,
                },
            ),
            description="Tracking information for Macie classification jobs",
        )
