"""Consultation medallion architecture CDK stack.

This module implements the medallion architecture (bronze/silver/gold) for
clinical consultation data processing with comprehensive PII/PHI redaction
capabilities using Amazon Macie, Textract, and Comprehend Medical.

The stack creates S3 buckets for each layer, Lambda functions for processing,
and proper IAM permissions following least-privilege principles.
"""

import aws_cdk as cdk
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications as s3n
from aws_cdk import aws_sns as sns
from aws_cdk import aws_ssm as ssm
from constructs import Construct

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
        environment: str = "prod",
        existing_bronze_bucket: str | None = None,
        **kwargs,
    ) -> None:
        """Initialize the consultation medallion stack.

        Args:
            scope: CDK scope for this stack.
            construct_id: Unique identifier for this stack.
            environment: Deployment environment (prod, staging, dev).
            existing_bronze_bucket: Optional existing bronze bucket name. If not provided,
                                   a new bronze bucket will be created.
            **kwargs: Additional CDK stack arguments.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.environment = environment
        self.existing_bronze_bucket = existing_bronze_bucket

        # Create S3 buckets for medallion architecture
        self._create_s3_buckets()

        # Create DynamoDB tables for job tracking
        self._create_dynamodb_tables()

        # Create SNS topics for notifications
        self._create_sns_topics()

        # Create Lambda functions for processing
        self._create_lambda_functions()

        # Configure S3 event notifications
        self._configure_s3_notifications()

        # Create EventBridge rules for orchestration
        self._create_eventbridge_rules()

        # Store configuration in SSM Parameter Store
        self._create_ssm_parameters()

    def _create_s3_buckets(self) -> None:
        """Create S3 buckets for each medallion layer."""
        # Landing zone bucket for PII redaction
        self.landing_bucket = s3.Bucket(
            self,
            "LandingBucket",
            bucket_name=f"a360-{self.environment}-consultation-landing",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioning=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=cdk.Duration.days(30),
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=cdk.Duration.days(90),
                        ),
                    ],
                ),
            ],
        )

        # Silver layer bucket for PHI-redacted content
        self.silver_bucket = s3.Bucket(
            self,
            "SilverBucket",
            bucket_name=f"a360-{self.environment}-consultation-silver",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioning=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=cdk.Duration.days(90),
                        ),
                    ],
                ),
            ],
        )

        # Gold layer bucket for enriched analytics
        self.gold_bucket = s3.Bucket(
            self,
            "GoldBucket",
            bucket_name=f"a360-{self.environment}-consultation-gold",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioning=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=cdk.Duration.days(180),
                        ),
                    ],
                ),
            ],
        )

        # Create or reference bronze bucket
        if self.existing_bronze_bucket:
            # Reference existing bronze bucket
            self.bronze_bucket = s3.Bucket.from_bucket_name(
                self,
                "BronzeBucket",
                bucket_name=self.existing_bronze_bucket,
            )
        else:
            # Create new bronze bucket for this environment
            self.bronze_bucket = s3.Bucket(
                self,
                "BronzeBucket",
                bucket_name=f"a360-{self.environment}-consultation-bronze",
                encryption=s3.BucketEncryption.S3_MANAGED,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                versioning=True,
                lifecycle_rules=[
                    s3.LifecycleRule(
                        id="TransitionToIA",
                        enabled=True,
                        transitions=[
                            s3.Transition(
                                storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                                transition_after=cdk.Duration.days(30),
                            ),
                            s3.Transition(
                                storage_class=s3.StorageClass.GLACIER,
                                transition_after=cdk.Duration.days(90),
                            ),
                        ],
                    ),
                ],
            )

        # Create customer-managed KMS key for encryption
        self.data_kms_key = kms.Key(
            self,
            "DataKMSKey",
            description=f"KMS key for consultation data encryption in {self.environment}",
            enable_key_rotation=True,
            alias=f"alias/consultation-data-{self.environment}",
        )

        # Note: KMS permissions are handled through bucket encryption settings and IAM roles

    def _create_dynamodb_tables(self) -> None:
        """Create DynamoDB tables for job tracking and metadata."""
        # Job status tracking table (similar to enhancing-macie-textract pattern)
        self.job_status_table = dynamodb.Table(
            self,
            "JobStatusTable",
            table_name=f"consultation-job-status-{self.environment}",
            partition_key=dynamodb.Attribute(
                name="JobType",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="JobId",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=cdk.RemovalPolicy.RETAIN,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        # Consultation metadata table
        self.consultation_metadata_table = dynamodb.Table(
            self,
            "ConsultationMetadataTable",
            table_name=f"consultation-metadata-{self.environment}",
            partition_key=dynamodb.Attribute(
                name="ConsultationId",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # Add GSI for querying by tenant
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
        # PII detection completion notifications
        self.pii_detection_topic = sns.Topic(
            self,
            "PIIDetectionTopic",
            topic_name=f"consultation-pii-detection-{self.environment}",
            display_name="Consultation PII Detection Notifications",
        )

        # PHI detection completion notifications
        self.phi_detection_topic = sns.Topic(
            self,
            "PHIDetectionTopic",
            topic_name=f"consultation-phi-detection-{self.environment}",
            display_name="Consultation PHI Detection Notifications",
        )

        # Pipeline completion notifications
        self.pipeline_completion_topic = sns.Topic(
            self,
            "PipelineCompletionTopic",
            topic_name=f"consultation-transcripts-pipeline-completion-{self.environment}",
            display_name="Consultation Pipeline Completion Notifications",
        )

    def _create_lambda_functions(self) -> None:
        """Create Lambda functions for each processing stage."""
        # Note: Lambda code paths will need to be created in the lambda directory

        # PII redaction trigger for landing zone
        self.pii_redaction_function = PowertoolsLambdaConstruct(
            self,
            "PIIRedactionFunction",
            code_path="infra/stacks/consultation_pipeline/lambda/pii_redaction_trigger",
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

        # PHI detection processor for clinical text
        self.phi_detection_function = PowertoolsLambdaConstruct(
            self,
            "PHIDetectionFunction",
            code_path="infra/stacks/consultation_pipeline/lambda/phi_detection_processor",
            service_name="consultation-phi-detection",
            namespace="ConsultationPipeline",
            memory_size=1024,
            timeout=cdk.Duration.minutes(15),
            s3_buckets=[
                self.bronze_bucket.bucket_name,
                self.silver_bucket.bucket_name,
            ],
            enable_comprehend_medical=True,
            environment={
                "BRONZE_BUCKET": self.bronze_bucket.bucket_name,
                "SILVER_BUCKET": self.silver_bucket.bucket_name,
                "CONSULTATION_METADATA_TABLE": self.consultation_metadata_table.table_name,
                "PHI_DETECTION_TOPIC_ARN": self.phi_detection_topic.topic_arn,
            },
        )

        # Embedding processor using Cohere Embed English v3
        self.embedding_function = PowertoolsLambdaConstruct(
            self,
            "EmbeddingFunction",
            code_path="infra/stacks/consultation_pipeline/lambda/embedding_processor",
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
            },
        )

        # Consultation enrichment and analytics
        self.enrichment_function = PowertoolsLambdaConstruct(
            self,
            "EnrichmentFunction",
            code_path="infra/stacks/consultation_pipeline/lambda/consultation_enrichment",
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

        # Grant DynamoDB permissions
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

        # Grant SNS publish permissions
        self.pii_detection_topic.grant_publish(self.pii_redaction_function.function)
        self.phi_detection_topic.grant_publish(self.phi_detection_function.function)
        self.pipeline_completion_topic.grant_publish(self.enrichment_function.function)

        # KMS permissions for encrypted S3 access
        for fn in [
            self.pii_redaction_function.function,
            self.phi_detection_function.function,
            self.embedding_function.function,
            self.enrichment_function.function,
        ]:
            self.data_kms_key.grant_encrypt_decrypt(fn)

        # Fix Macie IAM policy - separate Create and Get permissions
        # Create new Macie jobs (requires "*" resource)
        self.pii_redaction_function.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["macie2:CreateClassificationJob"],
                resources=["*"],
            ),
        )
        # Read Macie job details (can be scoped)
        self.pii_redaction_function.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["macie2:GetClassificationJob"],
                resources=[
                    f"arn:aws:macie2:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:classification-job/*",
                ],
            ),
        )

    def _configure_s3_notifications(self) -> None:
        """Configure S3 event notifications to trigger processing."""
        # Landing bucket triggers PII redaction
        # Landing bucket is always created, not imported
        self.landing_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.pii_redaction_function.function),
            s3.NotificationKeyFilter(suffix=".json"),
        )

        # Bronze bucket triggers PHI detection
        # Check if bronze bucket is imported or created
        if self.existing_bronze_bucket:
            # Create EventBridge rule for imported bucket
            bronze_trigger_rule = events.Rule(
                self,
                "BronzeTriggerRule",
                rule_name=f"consultation-bronze-trigger-{self.environment}",
                event_pattern=events.EventPattern(
                    source=["aws.s3"],
                    detail_type=["Object Created"],
                    detail={
                        "bucket": {"name": [self.existing_bronze_bucket]},
                        "object": {"key": [{"suffix": ".json"}]},
                    },
                ),
            )
            bronze_trigger_rule.add_target(targets.LambdaFunction(self.phi_detection_function.function))

            # Add Lambda permission for EventBridge
            self.phi_detection_function.function.add_permission(
                "AllowEventBridgeInvoke",
                principal=iam.ServicePrincipal("events.amazonaws.com"),
                source_arn=bronze_trigger_rule.rule_arn,
            )
        else:
            # Use direct S3 notification for created bucket
            self.bronze_bucket.add_event_notification(
                s3.EventType.OBJECT_CREATED,
                s3n.LambdaDestination(self.phi_detection_function.function),
                s3.NotificationKeyFilter(suffix=".json"),
            )

    def _create_eventbridge_rules(self) -> None:
        """Create EventBridge rules for pipeline orchestration."""
        # Rule for PHI detection completion -> embedding processing
        phi_completion_rule = events.Rule(
            self,
            "PHICompletionRule",
            rule_name=f"consultation-phi-completion-{self.environment}",
            event_pattern=events.EventPattern(
                source=["consultation.pipeline"],
                detail_type=["PHI Detection Completed"],
            ),
        )
        phi_completion_rule.add_target(
            targets.LambdaFunction(self.embedding_function.function),
        )

        # Rule for embedding completion -> enrichment processing
        embedding_completion_rule = events.Rule(
            self,
            "EmbeddingCompletionRule",
            rule_name=f"consultation-embedding-completion-{self.environment}",
            event_pattern=events.EventPattern(
                source=["consultation.pipeline"],
                detail_type=["Embedding Processing Completed"],
            ),
        )
        embedding_completion_rule.add_target(
            targets.LambdaFunction(self.enrichment_function.function),
        )

    def _create_ssm_parameters(self) -> None:
        """Create SSM parameters for configuration management."""
        # Bucket names
        ssm.StringParameter(
            self,
            "LandingBucketParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.environment}/landing-bucket",
            string_value=self.landing_bucket.bucket_name,
        )

        ssm.StringParameter(
            self,
            "SilverBucketParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.environment}/silver-bucket",
            string_value=self.silver_bucket.bucket_name,
        )

        ssm.StringParameter(
            self,
            "GoldBucketParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.environment}/gold-bucket",
            string_value=self.gold_bucket.bucket_name,
        )

        # Table names
        ssm.StringParameter(
            self,
            "JobStatusTableParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.environment}/job-status-table",
            string_value=self.job_status_table.table_name,
        )

        ssm.StringParameter(
            self,
            "MetadataTableParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.environment}/metadata-table",
            string_value=self.consultation_metadata_table.table_name,
        )

        # SNS topic ARNs
        ssm.StringParameter(
            self,
            "PIITopicParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.environment}/pii-topic-arn",
            string_value=self.pii_detection_topic.topic_arn,
        )

        ssm.StringParameter(
            self,
            "PHITopicParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.environment}/phi-topic-arn",
            string_value=self.phi_detection_topic.topic_arn,
        )

        ssm.StringParameter(
            self,
            "CompletionTopicParam",
            parameter_name=f"/consultation-transcripts-pipeline/{self.environment}/completion-topic-arn",
            string_value=self.pipeline_completion_topic.topic_arn,
        )
