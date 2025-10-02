"""Consultation medallion architecture CDK stack.

This module implements the medallion architecture (bronze/silver/gold) for
clinical consultation data processing with comprehensive PII/PHI redaction
capabilities using Amazon Macie, Textract, and Comprehend Medical.

The stack creates S3 buckets for each layer, Lambda functions for processing,
and proper IAM permissions following least-privilege principles.
"""

import json
from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_cloudtrail as cloudtrail
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from infra.shared.s3_constructs import MedallionBucketSet
from infra.stacks.shared.lambda_constructs import PowertoolsLambdaConstruct


class ConsultationMedallionStack(cdk.Stack):
    """CDK stack implementing medallion architecture for consultation analysis.

    This stack creates the infrastructure for processing clinical consultation
    data through bronze (raw), silver (cleaned/redacted), and gold (enriched)
    layers with comprehensive PII/PHI detection and redaction capabilities.

    Key Components:
    - Landing zone S3 bucket with Macie + Textract PII detection
    - Bronze layer for raw consultation transcripts
    - Silver layer for PHI-redacted clinical text
    - Gold layer for embeddings and enriched analytics
    - Lambda processors for each transformation stage
    - SNS notifications for pipeline coordination
    - DynamoDB for job tracking and metadata
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str = "prod",
        existing_bronze_bucket: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the consultation medallion stack.

        Args:
            scope: CDK scope for this stack.
            construct_id: Unique identifier for this stack.
            env_name: Deployment environment (prod, staging, dev).
            existing_bronze_bucket: Existing bronze bucket name.
            **kwargs: Additional CDK stack arguments.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.existing_bronze_bucket = existing_bronze_bucket
        self._create_s3_buckets()
        self._create_dynamodb_tables()
        self._create_sns_topics()
        self._create_lambda_functions()
        self._configure_textract_notifications()
        self._configure_parallel_processing()
        self._configure_eventbridge_routing()
        self._create_ssm_parameters()
        self._export_resources()

    def _create_s3_buckets(self) -> None:
        """Create S3 buckets for each medallion layer."""
        # Customer-managed KMS key
        self.data_kms_key = kms.Key(
            self,
            "DataKmsKey",
            alias=f"alias/consultation-transcripts-pipeline-{self.env_name}",
            enable_key_rotation=True,
        )

        medallion_buckets = MedallionBucketSet(
            self,
            "MedallionBuckets",
            env_name=self.env_name,
            data_type="consultation",
            kms_key=self.data_kms_key,
            create_landing=True,
            existing_bronze_bucket=self.existing_bronze_bucket,
        )

        self.landing_bucket = medallion_buckets.landing_bucket

        if not self.existing_bronze_bucket:
            self.bronze_bucket = medallion_buckets.bronze_bucket
        self.bronze_bucket_name = medallion_buckets.bronze_bucket_name
        self.silver_bucket = medallion_buckets.silver_bucket
        self.gold_bucket = medallion_buckets.gold_bucket

    def _create_dynamodb_tables(self) -> None:
        """Create DynamoDB tables for job tracking and metadata."""
        self.job_status_table = dynamodb.Table(
            self,
            "JobStatusTable",
            table_name=f"consultation-job-status-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="JobType",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="JobId",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.data_kms_key,
            removal_policy=cdk.RemovalPolicy.RETAIN,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            point_in_time_recovery=True,
        )

        self.consultation_metadata_table = dynamodb.Table(
            self,
            "ConsultationMetadataTable",
            table_name=f"consultation-metadata-{self.env_name}",
            partition_key=dynamodb.Attribute(
                name="ConsultationId",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.data_kms_key,
            removal_policy=cdk.RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
        )

        self.consultation_metadata_table.add_global_secondary_index(
            index_name="TenantIdIndex",
            partition_key=dynamodb.Attribute(
                name="TenantId",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="ProcessedAt",
                type=dynamodb.AttributeType.STRING,
            ),
        )

    def _create_sns_topics(self) -> None:
        """Create SNS topics for pipeline notifications."""
        self.pii_detection_topic = sns.Topic(
            self,
            "PIIDetectionTopic",
            topic_name=f"consultation-pii-detection-{self.env_name}",
            display_name="Consultation PII Detection Notifications",
            master_key=self.data_kms_key,
        )

        self.phi_detection_topic = sns.Topic(
            self,
            "PHIDetectionTopic",
            topic_name=f"consultation-phi-detection-{self.env_name}",
            display_name="Consultation PHI Detection Notifications",
            master_key=self.data_kms_key,
        )

        self.pipeline_completion_topic = sns.Topic(
            self,
            "PipelineCompletionTopic",
            topic_name=f"consultation-transcripts-pipeline-completion-{self.env_name}",
            display_name="Consultation Pipeline Completion Notifications",
            master_key=self.data_kms_key,
        )

        self.human_review_topic = sns.Topic(
            self,
            "HumanReviewTopic",
            topic_name=f"consultation-human-review-{self.env_name}",
            display_name="Consultation Human Review Notifications",
            master_key=self.data_kms_key,
        )

    def _create_lambda_functions(self) -> None:
        """Create Lambda functions for each processing stage."""
        self.pii_redaction_function = PowertoolsLambdaConstruct(
            self,
            "PIIRedactionFunction",
            code_path="consultation_pipeline/lambda/pii_redaction_trigger",
            service_name="consultation-pii-redaction",
            namespace="ConsultationPipeline",
            memory_size=1024,
            timeout=cdk.Duration.minutes(10),
            s3_buckets=[
                self.landing_bucket.bucket_name,
                self.silver_bucket.bucket_name,
            ],
            enable_macie=True,
            environment={
                "LANDING_BUCKET": self.landing_bucket.bucket_name,
                "SILVER_BUCKET": self.silver_bucket.bucket_name,
                "JOB_STATUS_TABLE": self.job_status_table.table_name,
                "PII_DETECTION_TOPIC_ARN": self.pii_detection_topic.topic_arn,
            },
        )

        self.phi_detection_function = PowertoolsLambdaConstruct(
            self,
            "PHIDetectionFunction",
            code_path="consultation_pipeline/lambda/phi_detection_processor",
            service_name="consultation-phi-detection",
            namespace="ConsultationPipeline",
            memory_size=1024,
            timeout=cdk.Duration.minutes(15),
            s3_buckets=[
                self.bronze_bucket_name,
                self.silver_bucket.bucket_name,
            ],
            enable_comprehend_medical=True,
            environment={
                "BRONZE_BUCKET": self.bronze_bucket_name,
                "SILVER_BUCKET": self.silver_bucket.bucket_name,
                "CONSULTATION_METADATA_TABLE": self.consultation_metadata_table.table_name,
                "PHI_DETECTION_TOPIC_ARN": self.phi_detection_topic.topic_arn,
            },
        )

        self.embedding_function = PowertoolsLambdaConstruct(
            self,
            "EmbeddingFunction",
            code_path="consultation_pipeline/lambda/embedding_processor",
            service_name="consultation-embedding",
            namespace="ConsultationPipeline",
            memory_size=2048,
            timeout=cdk.Duration.minutes(10),
            s3_buckets=[
                self.silver_bucket.bucket_name,
                self.gold_bucket.bucket_name,
            ],
            enable_bedrock=True,
            environment={
                "SILVER_BUCKET": self.silver_bucket.bucket_name,
                "GOLD_BUCKET": self.gold_bucket.bucket_name,
                "CONSULTATION_METADATA_TABLE": self.consultation_metadata_table.table_name,
                "BEDROCK_EMBEDDING_MODEL_ID": "cohere.embed-english-v3",
            },
        )

        self.enrichment_function = PowertoolsLambdaConstruct(
            self,
            "EnrichmentFunction",
            code_path="consultation_pipeline/lambda/consultation_enrichment",
            service_name="consultation-enrichment",
            namespace="ConsultationPipeline",
            memory_size=1024,
            timeout=cdk.Duration.minutes(15),
            s3_buckets=[
                self.silver_bucket.bucket_name,
                self.gold_bucket.bucket_name,
            ],
            enable_bedrock=True,
            environment={
                "SILVER_BUCKET": self.silver_bucket.bucket_name,
                "GOLD_BUCKET": self.gold_bucket.bucket_name,
                "CONSULTATION_METADATA_TABLE": self.consultation_metadata_table.table_name,
                "PIPELINE_COMPLETION_TOPIC_ARN": self.pipeline_completion_topic.topic_arn,
            },
        )

        self.job_status_table.grant_read_write_data(
            self.pii_redaction_function.function,
        )
        self.consultation_metadata_table.grant_read_write_data(
            self.phi_detection_function.function,
        )
        self.consultation_metadata_table.grant_read_write_data(
            self.embedding_function.function,
        )
        self.consultation_metadata_table.grant_read_write_data(
            self.enrichment_function.function,
        )

        self.pii_detection_topic.grant_publish(self.pii_redaction_function.function)
        self.phi_detection_topic.grant_publish(self.phi_detection_function.function)
        self.pipeline_completion_topic.grant_publish(self.enrichment_function.function)
        self.human_review_topic.grant_publish(self.phi_detection_function.function)

    def _configure_eventbridge_routing(self) -> None:
        """Configure all EventBridge routing for S3 events and pipeline orchestration."""
        # S3 EventBridge integration is enabled by default in CDK v2
        # No explicit bucket configuration needed for EventBridge notifications

        # S3 Event Rules: Landing bucket JSON files → PII Redaction
        events.Rule(
            self,
            "LandingJsonCreatedRule",
            rule_name=f"consultation-landing-json-created-{self.env_name}",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [self.landing_bucket.bucket_name]},
                    "object": {"key": [{"suffix": ".json"}]},
                },
            ),
            targets=[targets.LambdaFunction(self.pii_redaction_function.function)],
        )

        if not self.existing_bronze_bucket:
            events.Rule(
                self,
                "BronzeObjectCreatedJsonRule",
                rule_name=f"consultation-bronze-json-created-{self.env_name}",
                event_pattern=events.EventPattern(
                    source=["aws.s3"],
                    detail_type=["Object Created"],
                    detail={
                        "bucket": {"name": [self.bronze_bucket_name]},
                        "object": {"key": [{"suffix": ".json"}]},
                    },
                ),
                targets=[targets.LambdaFunction(self.phi_detection_function.function)],
            )
        else:
            # For external bronze bucket, alternative trigger mechanism needed
            # (e.g., direct S3 notification, SNS, or manual EventBridge setup)
            pass

        events.Rule(
            self,
            "SilverTextractOutputRule",
            rule_name=f"consultation-silver-textract-output-{self.env_name}",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [self.silver_bucket.bucket_name]},
                    "object": {"key": [{"prefix": "textract-output/"}]},
                },
            ),
            targets=[targets.SqsQueue(self.textract_queue)],
        )

        phi_completion_rule = events.Rule(
            self,
            "PHICompletionRule",
            rule_name=f"consultation-phi-completion-{self.env_name}",
            event_pattern=events.EventPattern(
                source=["consultation.pipeline"],
                detail_type=["PHI Detection Completed"],
            ),
        )
        phi_completion_rule.add_target(
            targets.LambdaFunction(self.embedding_function.function),
        )

        embedding_completion_rule = events.Rule(
            self,
            "EmbeddingCompletionRule",
            rule_name=f"consultation-embedding-completion-{self.env_name}",
            event_pattern=events.EventPattern(
                source=["consultation.pipeline"],
                detail_type=["Embedding Processing Completed"],
            ),
        )
        embedding_completion_rule.add_target(
            targets.LambdaFunction(self.enrichment_function.function),
        )

        macie_findings_rule = events.Rule(
            self,
            "MacieFindingsRule",
            rule_name=f"consultation-macie-findings-{self.env_name}",
            event_pattern=events.EventPattern(
                source=["aws.macie"],
                detail_type=["Macie Finding"],
            ),
        )
        macie_findings_rule.add_target(
            targets.LambdaFunction(self.pii_redaction_function.function),
        )

    def _configure_textract_notifications(self) -> None:
        """Create SNS topic for Textract async job completion and subscribe lambda."""
        self.textract_topic = sns.Topic(
            self,
            "TextractNotificationTopic",
            topic_name=f"consultation-textract-completion-{self.env_name}",
            display_name="Textract Job Completion",
            master_key=self.data_kms_key,
        )

        self.textract_completion_function = PowertoolsLambdaConstruct(
            self,
            "TextractCompletionFunction",
            code_path="consultation_pipeline/lambda/textract_completion_processor",
            service_name="consultation-textract-completion",
            namespace="ConsultationPipeline",
            memory_size=1024,
            timeout=cdk.Duration.minutes(5),
            s3_buckets=[self.silver_bucket.bucket_name],
            enable_macie=False,
            environment={
                "SILVER_BUCKET": self.silver_bucket.bucket_name,
                "JOB_STATUS_TABLE": self.job_status_table.table_name,
            },
        )

        self.job_status_table.grant_read_write_data(
            self.textract_completion_function.function,
        )
        self.textract_completion_function.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "macie2:CreateClassificationJob",
                    "macie2:GetClassificationJob",
                ],
                resources=[
                    f"arn:aws:macie2:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:classification-job/*",
                ],
            ),
        )

        # Allow reading Textract async job results
        self.textract_completion_function.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "textract:GetDocumentTextDetection",
                    "textract:GetDocumentAnalysis",
                    "textract:GetExpenseAnalysis",
                ],
                resources=[
                    "*",
                ],  # Textract Get* does not support resource-level permissions
            ),
        )

        self.textract_topic.add_subscription(
            subs.LambdaSubscription(self.textract_completion_function.function),
        )

        for name, fn in {
            "pii": self.pii_redaction_function.function,
            "phi": self.phi_detection_function.function,
            "embed": self.embedding_function.function,
            "enrich": self.enrichment_function.function,
            "textract": self.textract_completion_function.function,
        }.items():
            cw.Alarm(
                self,
                f"{name}ErrorsAlarm",
                metric=fn.metric_errors(period=cdk.Duration.minutes(5)),
                threshold=1,
                evaluation_periods=1,
                alarm_description=f"{name} lambda has errors",
            )

        trail = cloudtrail.Trail(self, "ConsultationTrail")
        trail.add_s3_event_selector(
            [cloudtrail.S3EventSelector(bucket=self.landing_bucket)],
        )
        trail.add_s3_event_selector(
            [cloudtrail.S3EventSelector(bucket=self.silver_bucket)],
        )

    def _create_ssm_parameters(self) -> None:
        """Create SSM parameters for configuration management."""
        ssm.StringParameter(
            self,
            "LandingBucketParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/landing-bucket",
            string_value=self.landing_bucket.bucket_name,
        )

        if not self.existing_bronze_bucket:
            ssm.StringParameter(
                self,
                "BronzeBucketParam",
                parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/bronze-bucket",
                string_value=self.bronze_bucket_name,
            )

        ssm.StringParameter(
            self,
            "SilverBucketParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/silver-bucket",
            string_value=self.silver_bucket.bucket_name,
        )

        ssm.StringParameter(
            self,
            "GoldBucketParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/gold-bucket",
            string_value=self.gold_bucket.bucket_name,
        )

        # Table names
        ssm.StringParameter(
            self,
            "JobStatusTableParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/job-status-table",
            string_value=self.job_status_table.table_name,
        )

        ssm.StringParameter(
            self,
            "MetadataTableParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/metadata-table",
            string_value=self.consultation_metadata_table.table_name,
        )

        ssm.StringParameter(
            self,
            "PIITopicParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/pii-topic-arn",
            string_value=self.pii_detection_topic.topic_arn,
        )

        ssm.StringParameter(
            self,
            "PHITopicParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/phi-topic-arn",
            string_value=self.phi_detection_topic.topic_arn,
        )

        ssm.StringParameter(
            self,
            "CompletionTopicParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/completion-topic-arn",
            string_value=self.pipeline_completion_topic.topic_arn,
        )

        ssm.StringParameter(
            self,
            "HumanReviewTopicParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/human-review-topic-arn",
            string_value=self.human_review_topic.topic_arn,
        )

        ssm.StringParameter(
            self,
            "PhiThresholdParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/phi-threshold",
            string_value="0.8",
        )
        ssm.StringParameter(
            self,
            "CircuitBreakerParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.env_name}/circuit-breaker",
            string_value=json.dumps(
                {
                    "enabled": True,
                    "failure_threshold": 5,
                    "recovery_timeout_seconds": 300,
                    "half_open_max_calls": 3,
                },
            ),
            description="Circuit breaker configuration for consultation pipeline",
        )

    def _export_resources(self) -> None:
        """Export resources needed by the LakeFS stack and other integrations."""
        # Landing bucket exports
        cdk.CfnOutput(
            self,
            "LandingBucketName",
            value=self.landing_bucket.bucket_name,
            export_name=f"ConsultationMedallion-{self.env_name}-LandingBucketName",
        )

        cdk.CfnOutput(
            self,
            "LandingBucketArn",
            value=self.landing_bucket.bucket_arn,
            export_name=f"ConsultationMedallion-{self.env_name}-LandingBucketArn",
        )

        # Bronze bucket exports
        cdk.CfnOutput(
            self,
            "BronzeBucketName",
            value=self.bronze_bucket_name,
            export_name=f"ConsultationMedallion-{self.env_name}-BronzeBucketName",
        )

        # Silver bucket exports
        cdk.CfnOutput(
            self,
            "SilverBucketName",
            value=self.silver_bucket.bucket_name,
            export_name=f"ConsultationMedallion-{self.env_name}-SilverBucketName",
        )

        cdk.CfnOutput(
            self,
            "SilverBucketArn",
            value=self.silver_bucket.bucket_arn,
            export_name=f"ConsultationMedallion-{self.env_name}-SilverBucketArn",
        )

        # Gold bucket exports
        cdk.CfnOutput(
            self,
            "GoldBucketName",
            value=self.gold_bucket.bucket_name,
            export_name=f"ConsultationMedallion-{self.env_name}-GoldBucketName",
        )

        cdk.CfnOutput(
            self,
            "GoldBucketArn",
            value=self.gold_bucket.bucket_arn,
            export_name=f"ConsultationMedallion-{self.env_name}-GoldBucketArn",
        )

    def _configure_parallel_processing(self) -> None:
        """Set up SQS-based parallel processing for textract outputs."""
        # DLQ for failed message processing
        self.textract_dlq = sqs.Queue(
            self,
            "TextractDLQ",
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=self.data_kms_key,
            retention_period=cdk.Duration.days(14),
        )
        self.textract_queue = sqs.Queue(
            self,
            "TextractOutputQueue",
            visibility_timeout=cdk.Duration.minutes(5),
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=self.data_kms_key,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=5,
                queue=self.textract_dlq,
            ),
        )

        self.textract_worker_function = PowertoolsLambdaConstruct(
            self,
            "TextractQueueWorker",
            code_path="consultation_pipeline/lambda/textract_queue_worker",
            service_name="consultation-textract-worker",
            namespace="ConsultationPipeline",
            memory_size=512,
            timeout=cdk.Duration.minutes(2),
            s3_buckets=[self.silver_bucket.bucket_name],
            environment={
                "SILVER_BUCKET": self.silver_bucket.bucket_name,
            },
        )
        self.textract_worker_function.function.add_event_source_mapping(
            "TextractQueueEvent",
            event_source_arn=self.textract_queue.queue_arn,
            batch_size=5,
            report_batch_item_failures=True,
        )
        self.textract_queue.grant_consume_messages(
            self.textract_worker_function.function,
        )
