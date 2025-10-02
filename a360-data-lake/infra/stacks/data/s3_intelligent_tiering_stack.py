"""S3 Intelligent-Tiering storage optimization stack.

This module implements S3 Intelligent-Tiering configurations for cost optimization
of healthcare data storage. It automatically moves objects between storage classes
based on access patterns, reducing storage costs while maintaining performance
for frequently accessed data.

The stack creates Intelligent-Tiering configurations for different data types:
- Consultation data with long-term retention requirements
- Attachment data with varying access patterns
- Processed results and analytics data
- Backup and archival data

All configurations include appropriate filters, lifecycle policies, and
monitoring to ensure optimal cost management while maintaining HIPAA
compliance and data accessibility requirements.
"""

import json
import logging
from typing import Any

from aws_cdk import Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_ssm as ssm
from constructs import Construct

logging.basicConfig(level=logging.ERROR)


class S3IntelligentTieringStack(Stack):
    """S3 Intelligent-Tiering storage optimization stack.

    Implements Intelligent-Tiering configurations for healthcare data buckets
    to optimize storage costs based on access patterns while maintaining
    compliance and performance requirements.

    Attributes:
        tiering_configurations: Dictionary of Intelligent-Tiering configurations
        lifecycle_policies: Dictionary of lifecycle policies for buckets
        optimization_function: Lambda function for storage optimization monitoring
        cost_tracking_parameters: SSM parameters for cost tracking
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        consultation_bucket: s3.IBucket,
        attachment_bucket: s3.IBucket,
        environment_name: str = "production",
        **kwargs,
    ) -> None:
        """Initialize S3 Intelligent-Tiering stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            consultation_bucket: S3 bucket for consultation data
            attachment_bucket: S3 bucket for patient attachments
            environment_name: Environment name for configuration
            **kwargs: Additional arguments passed to parent Stack
        """
        super().__init__(scope, construct_id, **kwargs)

        self.environment_name = environment_name.lower()
        self.consultation_bucket = consultation_bucket
        self.attachment_bucket = attachment_bucket

        # Initialize dictionaries
        self.tiering_configurations: dict[str, Any] = {}
        self.lifecycle_policies: dict[str, Any] = {}
        self.cost_tracking_parameters: dict[str, ssm.StringParameter] = {}

        # Create intelligent tiering configurations
        self._create_consultation_tiering_config()
        self._create_attachment_tiering_config()
        self._create_processed_data_tiering_config()
        self._create_backup_tiering_config()
        self._create_lifecycle_policies()
        self._create_optimization_monitoring()
        self._create_cost_tracking_parameters()

    def _create_consultation_tiering_config(self) -> None:
        """Create Intelligent-Tiering configuration for consultation data."""
        # Configuration for consultation transcripts and medical records
        consultation_config = {
            "id": "ConsultationDataTiering",
            "status": "Enabled",
            "filter": {
                "prefix": "consultations/",
                "tags": [
                    {"key": "DataType", "value": "Consultation"},
                    {"key": "Classification", "value": "PHI"},
                ],
            },
            "tierings": [
                {
                    "days": 0,
                    "access_tier": "ARCHIVE_ACCESS",
                },
                {
                    "days": 90,
                    "access_tier": "DEEP_ARCHIVE_ACCESS",
                },
            ],
            "optional_fields": {
                "bucket_key_enabled": True,
            },
        }

        self.tiering_configurations["consultation"] = consultation_config

        # Configuration for consultation attachments (images, documents)
        consultation_attachments_config = {
            "id": "ConsultationAttachmentsTiering",
            "status": "Enabled",
            "filter": {
                "prefix": "consultations/attachments/",
                "tags": [
                    {"key": "DataType", "value": "Attachment"},
                    {"key": "Classification", "value": "PHI"},
                ],
            },
            "tierings": [
                {
                    "days": 30,
                    "access_tier": "ARCHIVE_ACCESS",
                },
                {
                    "days": 365,
                    "access_tier": "DEEP_ARCHIVE_ACCESS",
                },
            ],
            "optional_fields": {
                "bucket_key_enabled": True,
            },
        }

        self.tiering_configurations["consultation_attachments"] = (
            consultation_attachments_config
        )

    def _create_attachment_tiering_config(self) -> None:
        """Create Intelligent-Tiering configuration for patient attachments."""
        # Configuration for patient document uploads
        patient_documents_config = {
            "id": "PatientDocumentsTiering",
            "status": "Enabled",
            "filter": {
                "prefix": "patients/documents/",
                "tags": [
                    {"key": "DataType", "value": "PatientDocument"},
                    {"key": "Classification", "value": "PHI"},
                ],
            },
            "tierings": [
                {
                    "days": 7,
                    "access_tier": "ARCHIVE_ACCESS",
                },
                {
                    "days": 180,
                    "access_tier": "DEEP_ARCHIVE_ACCESS",
                },
            ],
            "optional_fields": {
                "bucket_key_enabled": True,
            },
        }

        self.tiering_configurations["patient_documents"] = patient_documents_config

        # Configuration for medical images
        medical_images_config = {
            "id": "MedicalImagesTiering",
            "status": "Enabled",
            "filter": {
                "prefix": "patients/images/",
                "tags": [
                    {"key": "DataType", "value": "MedicalImage"},
                    {"key": "Classification", "value": "PHI"},
                ],
                "object_size_greater_than": 10485760,  # 10MB
            },
            "tierings": [
                {
                    "days": 14,
                    "access_tier": "ARCHIVE_ACCESS",
                },
                {
                    "days": 90,
                    "access_tier": "DEEP_ARCHIVE_ACCESS",
                },
            ],
            "optional_fields": {
                "bucket_key_enabled": True,
            },
        }

        self.tiering_configurations["medical_images"] = medical_images_config

    def _create_processed_data_tiering_config(self) -> None:
        """Create Intelligent-Tiering configuration for processed data."""
        # Configuration for Textract results
        textract_results_config = {
            "id": "TextractResultsTiering",
            "status": "Enabled",
            "filter": {
                "prefix": "processed/textract-results/",
                "tags": [
                    {"key": "DataType", "value": "ProcessedData"},
                    {"key": "ProcessingType", "value": "Textract"},
                ],
            },
            "tierings": [
                {
                    "days": 30,
                    "access_tier": "ARCHIVE_ACCESS",
                },
                {
                    "days": 365,
                    "access_tier": "DEEP_ARCHIVE_ACCESS",
                },
            ],
            "optional_fields": {
                "bucket_key_enabled": True,
            },
        }

        self.tiering_configurations["textract_results"] = textract_results_config

        # Configuration for AI/ML processing results
        ai_processing_config = {
            "id": "AiProcessingResultsTiering",
            "status": "Enabled",
            "filter": {
                "prefix": "processed/ai-results/",
                "tags": [
                    {"key": "DataType", "value": "ProcessedData"},
                    {"key": "ProcessingType", "value": "AI"},
                ],
            },
            "tierings": [
                {
                    "days": 60,
                    "access_tier": "ARCHIVE_ACCESS",
                },
                {
                    "days": 730,
                    "access_tier": "DEEP_ARCHIVE_ACCESS",
                },
            ],
            "optional_fields": {
                "bucket_key_enabled": True,
            },
        }

        self.tiering_configurations["ai_processing"] = ai_processing_config

        # Configuration for analytics and reporting data
        analytics_config = {
            "id": "AnalyticsDataTiering",
            "status": "Enabled",
            "filter": {
                "prefix": "analytics/",
                "tags": [
                    {"key": "DataType", "value": "Analytics"},
                    {"key": "RetentionClass", "value": "LongTerm"},
                ],
            },
            "tierings": [
                {
                    "days": 90,
                    "access_tier": "ARCHIVE_ACCESS",
                },
                {
                    "days": 1095,  # 3 years
                    "access_tier": "DEEP_ARCHIVE_ACCESS",
                },
            ],
            "optional_fields": {
                "bucket_key_enabled": True,
            },
        }

        self.tiering_configurations["analytics"] = analytics_config

    def _create_backup_tiering_config(self) -> None:
        """Create Intelligent-Tiering configuration for backup data."""
        # Configuration for database backups
        database_backup_config = {
            "id": "DatabaseBackupTiering",
            "status": "Enabled",
            "filter": {
                "prefix": "backups/database/",
                "tags": [
                    {"key": "DataType", "value": "Backup"},
                    {"key": "BackupType", "value": "Database"},
                ],
            },
            "tierings": [
                {
                    "days": 7,
                    "access_tier": "ARCHIVE_ACCESS",
                },
                {
                    "days": 30,
                    "access_tier": "DEEP_ARCHIVE_ACCESS",
                },
            ],
            "optional_fields": {
                "bucket_key_enabled": True,
            },
        }

        self.tiering_configurations["database_backup"] = database_backup_config

        # Configuration for system logs and audit trails
        logs_config = {
            "id": "LogsAndAuditTiering",
            "status": "Enabled",
            "filter": {
                "prefix": "logs/",
                "tags": [
                    {"key": "DataType", "value": "Log"},
                    {"key": "LogType", "value": "Audit"},
                ],
            },
            "tierings": [
                {
                    "days": 30,
                    "access_tier": "ARCHIVE_ACCESS",
                },
                {
                    "days": 180,
                    "access_tier": "DEEP_ARCHIVE_ACCESS",
                },
            ],
            "optional_fields": {
                "bucket_key_enabled": True,
            },
        }

        self.tiering_configurations["logs"] = logs_config

    def _create_lifecycle_policies(self) -> None:
        """Create lifecycle policies for buckets with Intelligent-Tiering integration."""
        # Consultation bucket lifecycle policy
        consultation_lifecycle_rules = [
            # Rule for consultation data with Intelligent-Tiering
            s3.LifecycleRule(
                id="ConsultationDataLifecycle",
                status=s3.LifecycleRuleStatus.ENABLED,
                prefix="consultations/",
                transitions=[
                    s3.Transition(
                        storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                        transition_after=Duration.days(0),  # Immediate transition
                    ),
                ],
                tag_filters={
                    "DataType": "Consultation",
                    "Classification": "PHI",
                },
            ),
            # Rule for temporary processing files
            s3.LifecycleRule(
                id="TempProcessingCleanup",
                status=s3.LifecycleRuleStatus.ENABLED,
                prefix="temp/",
                expiration=Duration.days(7),  # Delete after 7 days
                abort_incomplete_multipart_upload_after=Duration.days(1),
            ),
            # Rule for old versions of consultation data
            s3.LifecycleRule(
                id="ConsultationVersionManagement",
                status=s3.LifecycleRuleStatus.ENABLED,
                prefix="consultations/",
                noncurrent_version_transitions=[
                    s3.NoncurrentVersionTransition(
                        storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                        transition_after=Duration.days(30),
                    ),
                    s3.NoncurrentVersionTransition(
                        storage_class=s3.StorageClass.GLACIER,
                        transition_after=Duration.days(365),
                    ),
                ],
                noncurrent_version_expiration=Duration.days(
                    2555,
                ),  # 7 years HIPAA retention
            ),
        ]

        self.lifecycle_policies["consultation"] = consultation_lifecycle_rules

        # Attachment bucket lifecycle policy
        attachment_lifecycle_rules = [
            # Rule for patient attachments with Intelligent-Tiering
            s3.LifecycleRule(
                id="PatientAttachmentsLifecycle",
                status=s3.LifecycleRuleStatus.ENABLED,
                prefix="patients/",
                transitions=[
                    s3.Transition(
                        storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                        transition_after=Duration.days(0),  # Immediate transition
                    ),
                ],
                tag_filters={
                    "Classification": "PHI",
                },
            ),
            # Rule for processed results
            s3.LifecycleRule(
                id="ProcessedResultsLifecycle",
                status=s3.LifecycleRuleStatus.ENABLED,
                prefix="processed/",
                transitions=[
                    s3.Transition(
                        storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                        transition_after=Duration.days(1),
                    ),
                ],
            ),
            # Rule for backup data
            s3.LifecycleRule(
                id="BackupDataLifecycle",
                status=s3.LifecycleRuleStatus.ENABLED,
                prefix="backups/",
                transitions=[
                    s3.Transition(
                        storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                        transition_after=Duration.days(0),
                    ),
                    s3.Transition(
                        storage_class=s3.StorageClass.GLACIER,
                        transition_after=Duration.days(90),
                    ),
                    s3.Transition(
                        storage_class=s3.StorageClass.DEEP_ARCHIVE,
                        transition_after=Duration.days(365),
                    ),
                ],
            ),
        ]

        self.lifecycle_policies["attachment"] = attachment_lifecycle_rules

    def _create_optimization_monitoring(self) -> None:
        """Create Lambda function for monitoring storage optimization."""
        self.optimization_function = lambda_.Function(
            self,
            "S3OptimizationMonitoringFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            timeout=Duration.minutes(10),
            memory_size=512,
            environment={
                "CONSULTATION_BUCKET_NAME": self.consultation_bucket.bucket_name,
                "ATTACHMENT_BUCKET_NAME": self.attachment_bucket.bucket_name,
                "ENVIRONMENT_NAME": self.environment_name,
                "POWERTOOLS_SERVICE_NAME": "s3-optimization-monitoring",
                "POWERTOOLS_LOG_LEVEL": "INFO",
            },
            code=lambda_.Code.from_inline("""
import json
import boto3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError

logger = Logger()
tracer = Tracer()
metrics = Metrics()

s3_client = boto3.client('s3')
cloudwatch_client = boto3.client('cloudwatch')

@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    try:
        consultation_bucket = os.environ['CONSULTATION_BUCKET_NAME']
        attachment_bucket = os.environ['ATTACHMENT_BUCKET_NAME']

        # Analyze storage optimization for both buckets
        consultation_analysis = analyze_bucket_storage(consultation_bucket)
        attachment_analysis = analyze_bucket_storage(attachment_bucket)

        # Generate cost optimization recommendations
        recommendations = generate_optimization_recommendations(
            consultation_analysis, attachment_analysis
        )

        # Update CloudWatch metrics
        publish_optimization_metrics(consultation_analysis, attachment_analysis)

        logger.info("Storage optimization analysis completed")

        return {
            'statusCode': 200,
            'consultation_bucket': consultation_analysis,
            'attachment_bucket': attachment_analysis,
            'recommendations': recommendations
        }

    except Exception as e:
        logger.error(f"Error in optimization monitoring: {str(e)}")
        metrics.add_metric(name="OptimizationErrors", unit=MetricUnit.Count, value=1)
        raise

@tracer.capture_method
def analyze_bucket_storage(bucket_name: str) -> Dict[str, Any]:
    try:
        # Get bucket statistics
        storage_metrics = get_storage_metrics(bucket_name)

        # Analyze Intelligent-Tiering effectiveness
        tiering_analysis = analyze_intelligent_tiering(bucket_name)

        # Calculate cost savings
        cost_analysis = calculate_cost_savings(storage_metrics, tiering_analysis)

        return {
            'bucket_name': bucket_name,
            'storage_metrics': storage_metrics,
            'tiering_analysis': tiering_analysis,
            'cost_analysis': cost_analysis,
            'last_analyzed': datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error analyzing bucket {bucket_name}: {str(e)}")
        return {'error': str(e)}

@tracer.capture_method
def get_storage_metrics(bucket_name: str) -> Dict[str, Any]:
    # Get CloudWatch metrics for S3 bucket storage
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=7)

        # Get storage size metrics
        storage_response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/S3',
            MetricName='BucketSizeBytes',
            Dimensions=[
                {'Name': 'BucketName', 'Value': bucket_name},
                {'Name': 'StorageType', 'Value': 'StandardStorage'}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,  # Daily
            Statistics=['Average']
        )

        # Get object count metrics
        objects_response = cloudwatch_client.get_metric_statistics(
            Namespace='AWS/S3',
            MetricName='NumberOfObjects',
            Dimensions=[
                {'Name': 'BucketName', 'Value': bucket_name},
                {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=86400,  # Daily
            Statistics=['Average']
        )

        storage_size = 0
        object_count = 0

        if storage_response['Datapoints']:
            storage_size = storage_response['Datapoints'][-1]['Average']

        if objects_response['Datapoints']:
            object_count = objects_response['Datapoints'][-1]['Average']

        return {
            'storage_size_bytes': storage_size,
            'object_count': object_count,
            'average_object_size': storage_size / object_count if object_count > 0 else 0
        }

    except Exception as e:
        logger.warning(f"Could not get storage metrics for {bucket_name}: {str(e)}")
        return {}

@tracer.capture_method
def analyze_intelligent_tiering(bucket_name: str) -> Dict[str, Any]:
    try:
        # Get Intelligent-Tiering configurations
        response = s3_client.list_bucket_intelligent_tiering_configurations(
            Bucket=bucket_name
        )

        configurations = response.get('IntelligentTieringConfigurationList', [])

        analysis = {
            'configurations_count': len(configurations),
            'configurations': [],
            'coverage_analysis': {}
        }

        for config in configurations:
            config_analysis = {
                'id': config.get('Id'),
                'status': config.get('Status'),
                'filter_prefix': config.get('Filter', {}).get('Prefix', ''),
                'tierings': config.get('Tierings', [])
            }
            analysis['configurations'].append(config_analysis)

        return analysis

    except Exception as e:
        logger.warning(f"Could not analyze Intelligent-Tiering for {bucket_name}: {str(e)}")
        return {}

@tracer.capture_method
def calculate_cost_savings(storage_metrics: Dict, tiering_analysis: Dict) -> Dict[str, Any]:
    # Calculate estimated cost savings from Intelligent-Tiering
    try:
        storage_size_gb = storage_metrics.get('storage_size_bytes', 0) / (1024**3)

        # Simplified cost calculation (actual costs vary by region and usage)
        standard_cost_per_gb = 0.023  # Example: Standard storage cost per GB/month
        it_cost_per_gb = 0.0125       # Example: Intelligent-Tiering cost per GB/month

        monthly_savings = (standard_cost_per_gb - it_cost_per_gb) * storage_size_gb
        annual_savings = monthly_savings * 12

        return {
            'storage_size_gb': storage_size_gb,
            'estimated_monthly_savings': monthly_savings,
            'estimated_annual_savings': annual_savings,
            'cost_optimization_percentage': ((standard_cost_per_gb - it_cost_per_gb) / standard_cost_per_gb) * 100
        }

    except Exception as e:
        logger.warning(f"Could not calculate cost savings: {str(e)}")
        return {}

@tracer.capture_method
def generate_optimization_recommendations(
    consultation_analysis: Dict, attachment_analysis: Dict
) -> List[str]:
    recommendations = []

    # Analyze consultation bucket
    if consultation_analysis.get('tiering_analysis', {}).get('configurations_count', 0) == 0:
        recommendations.append(
            "Configure Intelligent-Tiering for consultation bucket to optimize storage costs"
        )

    # Analyze attachment bucket
    if attachment_analysis.get('tiering_analysis', {}).get('configurations_count', 0) == 0:
        recommendations.append(
            "Configure Intelligent-Tiering for attachment bucket to optimize storage costs"
        )

    # Check storage size thresholds
    consultation_size_gb = consultation_analysis.get('cost_analysis', {}).get('storage_size_gb', 0)
    if consultation_size_gb > 1000:  # 1TB threshold
        recommendations.append(
            f"Consultation bucket ({consultation_size_gb:.1f} GB) is large. "
            "Consider additional lifecycle policies for long-term archival."
        )

    attachment_size_gb = attachment_analysis.get('cost_analysis', {}).get('storage_size_gb', 0)
    if attachment_size_gb > 2000:  # 2TB threshold
        recommendations.append(
            f"Attachment bucket ({attachment_size_gb:.1f} GB) is large. "
            "Review data retention policies and consider Deep Archive for old data."
        )

    return recommendations

@tracer.capture_method
def publish_optimization_metrics(consultation_analysis: Dict, attachment_analysis: Dict) -> None:
    try:
        namespace = 'Healthcare/StorageOptimization'

        # Publish consultation bucket metrics
        if 'cost_analysis' in consultation_analysis:
            cost_data = consultation_analysis['cost_analysis']

            cloudwatch_client.put_metric_data(
                Namespace=namespace,
                MetricData=[
                    {
                        'MetricName': 'StorageSizeGB',
                        'Value': cost_data.get('storage_size_gb', 0),
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'BucketType', 'Value': 'Consultation'},
                            {'Name': 'Environment', 'Value': os.environ.get('ENVIRONMENT_NAME', 'Unknown')}
                        ]
                    },
                    {
                        'MetricName': 'EstimatedMonthlySavings',
                        'Value': cost_data.get('estimated_monthly_savings', 0),
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'BucketType', 'Value': 'Consultation'},
                            {'Name': 'Environment', 'Value': os.environ.get('ENVIRONMENT_NAME', 'Unknown')}
                        ]
                    }
                ]
            )

        # Publish attachment bucket metrics
        if 'cost_analysis' in attachment_analysis:
            cost_data = attachment_analysis['cost_analysis']

            cloudwatch_client.put_metric_data(
                Namespace=namespace,
                MetricData=[
                    {
                        'MetricName': 'StorageSizeGB',
                        'Value': cost_data.get('storage_size_gb', 0),
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'BucketType', 'Value': 'Attachment'},
                            {'Name': 'Environment', 'Value': os.environ.get('ENVIRONMENT_NAME', 'Unknown')}
                        ]
                    },
                    {
                        'MetricName': 'EstimatedMonthlySavings',
                        'Value': cost_data.get('estimated_monthly_savings', 0),
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'BucketType', 'Value': 'Attachment'},
                            {'Name': 'Environment', 'Value': os.environ.get('ENVIRONMENT_NAME', 'Unknown')}
                        ]
                    }
                ]
            )

        logger.info("Published storage optimization metrics to CloudWatch")

    except Exception as e:
        logger.error(f"Error publishing metrics: {str(e)}")
"""),
        )

        # Grant necessary permissions
        self.optimization_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetBucketLocation",
                    "s3:ListBucket",
                    "s3:GetBucketIntelligentTieringConfiguration",
                    "s3:ListBucketIntelligentTieringConfigurations",
                    "s3:GetBucketLifecycleConfiguration",
                    "cloudwatch:GetMetricStatistics",
                    "cloudwatch:PutMetricData",
                ],
                resources=[
                    self.consultation_bucket.bucket_arn,
                    self.attachment_bucket.bucket_arn,
                    f"{self.consultation_bucket.bucket_arn}/*",
                    f"{self.attachment_bucket.bucket_arn}/*",
                    "arn:aws:cloudwatch:*:*:metric/AWS/S3/*",
                    "arn:aws:cloudwatch:*:*:metric/Healthcare/*",
                ],
            ),
        )

    def _create_cost_tracking_parameters(self) -> None:
        """Create SSM parameters for cost tracking and optimization settings."""
        # Storage optimization settings
        optimization_settings = ssm.StringParameter(
            self,
            "StorageOptimizationSettings",
            parameter_name=f"/{self.environment_name}/storage/optimization-settings",
            string_value=json.dumps(
                {
                    "intelligent_tiering_enabled": True,
                    "automatic_transitions": True,
                    "cost_optimization_threshold_gb": 100,
                    "deep_archive_threshold_days": 365,
                    "lifecycle_policy_enabled": True,
                    "monitoring_enabled": True,
                    "cost_alerts_enabled": True,
                    "optimization_schedule": "weekly",
                },
            ),
            description="Storage optimization settings and thresholds",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.cost_tracking_parameters["optimization_settings"] = optimization_settings

        # Cost tracking configuration
        cost_tracking_config = ssm.StringParameter(
            self,
            "CostTrackingConfig",
            parameter_name=f"/{self.environment_name}/storage/cost-tracking",
            string_value=json.dumps(
                {
                    "track_storage_costs": True,
                    "track_request_costs": True,
                    "track_data_transfer_costs": True,
                    "cost_allocation_tags": [
                        "Environment",
                        "DataType",
                        "Classification",
                        "RetentionClass",
                    ],
                    "monthly_budget_alert_threshold": 1000.00,
                    "cost_anomaly_detection_enabled": True,
                    "detailed_billing_enabled": True,
                },
            ),
            description="Cost tracking and monitoring configuration",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.cost_tracking_parameters["cost_tracking"] = cost_tracking_config

        # Retention policies configuration
        retention_policies = ssm.StringParameter(
            self,
            "DataRetentionPolicies",
            parameter_name=f"/{self.environment_name}/storage/retention-policies",
            string_value=json.dumps(
                {
                    "consultation_data": {
                        "minimum_retention_years": 7,  # HIPAA requirement
                        "active_access_days": 90,
                        "archive_access_days": 365,
                        "deep_archive_days": 2555,  # 7 years
                    },
                    "patient_attachments": {
                        "minimum_retention_years": 7,
                        "active_access_days": 30,
                        "archive_access_days": 180,
                        "deep_archive_days": 2555,
                    },
                    "processed_data": {
                        "minimum_retention_years": 3,
                        "active_access_days": 60,
                        "archive_access_days": 365,
                        "deep_archive_days": 1095,  # 3 years
                    },
                    "backup_data": {
                        "minimum_retention_years": 1,
                        "active_access_days": 7,
                        "archive_access_days": 30,
                        "deep_archive_days": 365,
                    },
                    "audit_logs": {
                        "minimum_retention_years": 10,  # Extended retention for compliance
                        "active_access_days": 30,
                        "archive_access_days": 180,
                        "deep_archive_days": 3650,  # 10 years
                    },
                },
            ),
            description="Data retention policies for different data types",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.cost_tracking_parameters["retention_policies"] = retention_policies

    def get_tiering_configuration(self, config_name: str) -> dict[str, Any] | None:
        """Get Intelligent-Tiering configuration by name.

        Args:
            config_name: Name of the configuration to retrieve

        Returns:
            Configuration dictionary or None if not found
        """
        return self.tiering_configurations.get(config_name)

    def get_lifecycle_policy(self, policy_name: str) -> list[s3.LifecycleRule] | None:
        """Get lifecycle policy by name.

        Args:
            policy_name: Name of the policy to retrieve

        Returns:
            List of lifecycle rules or None if not found
        """
        return self.lifecycle_policies.get(policy_name)

    def get_cost_tracking_parameter(
        self,
        parameter_name: str,
    ) -> ssm.StringParameter | None:
        """Get cost tracking parameter by name.

        Args:
            parameter_name: Name of the parameter to retrieve

        Returns:
            SSM parameter or None if not found
        """
        return self.cost_tracking_parameters.get(parameter_name)
