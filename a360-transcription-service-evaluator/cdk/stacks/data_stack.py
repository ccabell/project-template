"""Data stack for A360 Transcription Service Evaluator.

This stack creates data storage infrastructure including Aurora Serverless,
S3 buckets, and other data services following AWS best practices.
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_rds as rds,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_dynamodb as dynamodb,
    aws_secretsmanager as secretsmanager,
    aws_ec2 as ec2,
    aws_kms as kms,
    aws_lambda as lambda_,
    aws_iam,
    Duration,
    RemovalPolicy,
)
from constructs import Construct


class DataStack(cdk.NestedStack):
    """Data infrastructure stack."""
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_name: str,
        stage: str,
        vpc: ec2.Vpc,
        database_security_group: ec2.SecurityGroup,
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)
        
        self.app_name = app_name
        self.stage = stage
        self.vpc = vpc
        self.database_security_group = database_security_group
        
        # Create KMS keys for encryption
        self.kms_key = self._create_kms_key()
        
        # Create Aurora Serverless database
        self.database_cluster = self._create_database_cluster()
        
        # Create S3 buckets
        self.application_bucket = self._create_application_bucket()
        self.transcription_bucket = self._create_transcription_bucket()
        
        # Create DynamoDB tables for sessions and jobs
        self.session_table = self._create_session_table()
        self.jobs_table = self._create_jobs_table()
        
        # Create medical terminology tables
        self.medical_brands_table = self._create_medical_brands_table()
        self.medical_terms_table = self._create_medical_terms_table()
        
        # Database initialization not needed with RDS Data API
    
    def _create_kms_key(self) -> kms.Key:
        """Create KMS key for data encryption."""
        key = kms.Key(
            self,
            "DataEncryptionKey",
            description=f"KMS key for {self.app_name} {self.stage} data encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY if self.stage != "prod" else RemovalPolicy.RETAIN
        )
        
        # Add alias for easier management
        kms.Alias(
            self,
            "DataEncryptionKeyAlias",
            alias_name=f"alias/{self.app_name}-{self.stage}-data-key",
            target_key=key
        )
        
        return key
    
    def _create_database_cluster(self) -> rds.DatabaseCluster:
        """Create Aurora Serverless v2 PostgreSQL cluster."""
        
        # Create database credentials in Secrets Manager
        database_credentials = rds.DatabaseSecret(
            self,
            "DatabaseSecret",
            username="postgres",
            encryption_key=self.kms_key
        )
        
        # Create subnet group for database
        subnet_group = rds.SubnetGroup(
            self,
            "DatabaseSubnetGroup",
            description=f"Subnet group for {self.app_name} {self.stage} database",
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            removal_policy=RemovalPolicy.DESTROY if self.stage != "prod" else RemovalPolicy.RETAIN
        )
        
        # Create parameter group for PostgreSQL optimization
        parameter_group = rds.ParameterGroup(
            self,
            "DatabaseParameterGroup",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_15_4
            ),
            description=f"Parameter group for {self.app_name} {self.stage}",
            parameters={
                # Optimize for serverless workload
                "shared_preload_libraries": "pg_stat_statements,pg_hint_plan",
                "log_statement": "all" if self.stage == "dev" else "ddl",
                "log_min_duration_statement": "1000",  # Log slow queries
                "track_activity_query_size": "2048",
                "track_io_timing": "on"
            }
        )
        
        # Create database cluster
        cluster = rds.DatabaseCluster(
            self,
            "DatabaseCluster",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_15_4
            ),
            credentials=rds.Credentials.from_secret(database_credentials),
            
            # Network configuration
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[self.database_security_group],
            subnet_group=subnet_group,
            
            # Serverless v2 configuration
            serverless_v2_min_capacity=0.5,  # Minimum cost
            serverless_v2_max_capacity=16,   # Scale up to handle load
            
            # Writer instance (required)
            writer=rds.ClusterInstance.serverless_v2(
                "Writer",
                scale_with_writer=True,
                performance_insight_encryption_key=self.kms_key,
                performance_insight_retention=rds.PerformanceInsightRetention.DEFAULT
            ),
            
            # Database configuration
            default_database_name="transcription_evaluator",
            parameter_group=parameter_group,
            
            # Backup and maintenance
            backup=rds.BackupProps(
                retention=Duration.days(7 if self.stage == "dev" else 30),
                preferred_window="03:00-04:00"  # Low traffic window
            ),
            preferred_maintenance_window="Sun:04:00-Sun:05:00",
            
            # Security
            storage_encrypted=True,
            storage_encryption_key=self.kms_key,
            
            # Enable RDS Data API for Lambda access
            enable_data_api=True,
            
            # Monitoring
            monitoring_interval=Duration.seconds(60),
            monitoring_role=self._create_monitoring_role(),
            
            # Performance Insights
            performance_insight_encryption_key=self.kms_key,
            performance_insight_retention=rds.PerformanceInsightRetention.DEFAULT,
            
            # Deletion protection
            deletion_protection=True if self.stage == "prod" else False,
            removal_policy=RemovalPolicy.DESTROY if self.stage != "prod" else RemovalPolicy.RETAIN
        )
        
        # Add tags
        cdk.Tags.of(cluster).add("Environment", self.stage)
        cdk.Tags.of(cluster).add("Application", self.app_name)
        
        return cluster
    
    def _create_monitoring_role(self) -> aws_iam.Role:
        """Create IAM role for RDS monitoring."""
        return aws_iam.Role(
            self,
            "DatabaseMonitoringRole",
            assumed_by=aws_iam.ServicePrincipal("monitoring.rds.amazonaws.com"),
            managed_policies=[
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonRDSEnhancedMonitoringRole"
                )
            ]
        )
    
    def _create_application_bucket(self) -> s3.Bucket:
        """Create S3 bucket for application data storage."""
        bucket = s3.Bucket(
            self,
            "ApplicationBucket",
            bucket_name=f"{self.app_name.lower()}-{self.stage}-app-data-{cdk.Stack.of(self).account}",
            
            # Security
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.kms_key,
            enforce_ssl=True,
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            
            # Lifecycle management
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90)
                        )
                    ]
                ),
                s3.LifecycleRule(
                    id="DeleteIncompleteUploads",
                    enabled=True,
                    abort_incomplete_multipart_upload_after=Duration.days(1)
                )
            ],
            
            # Versioning for data protection
            versioned=True,
            
            # CORS for web application
            cors=[
                s3.CorsRule(
                    allowed_headers=["*"],
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.POST,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.DELETE
                    ],
                    allowed_origins=["http://localhost:3000", "https://localhost:3000"],
                    exposed_headers=["ETag"],
                    max_age=3000
                )
            ],
            
            # Event notifications
            event_bridge_enabled=True,
            
            # Cleanup policy
            removal_policy=RemovalPolicy.DESTROY if self.stage != "prod" else RemovalPolicy.RETAIN,
            auto_delete_objects=True if self.stage == "dev" else False
        )
        
        # TODO: Bucket notifications disabled to avoid Lambda conflicts
        # self._add_bucket_notifications(bucket)
        
        return bucket
    
    def _create_transcription_bucket(self) -> s3.Bucket:
        """Create S3 bucket for transcription files."""
        bucket = s3.Bucket(
            self,
            "TranscriptionBucket", 
            bucket_name=f"{self.app_name.lower()}-{self.stage}-transcriptions-{cdk.Stack.of(self).account}",
            
            # Security
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.kms_key,
            enforce_ssl=True,
            public_read_access=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            
            # Lifecycle management for audio files
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ArchiveAudioFiles",
                    enabled=True,
                    prefix="audio/",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.DEEP_ARCHIVE,
                            transition_after=Duration.days(365)
                        )
                    ]
                ),
                s3.LifecycleRule(
                    id="DeleteTempFiles",
                    enabled=True,
                    prefix="temp/",
                    expiration=Duration.days(7)
                )
            ],
            
            # Versioning
            versioned=True,
            
            # Cleanup policy
            removal_policy=RemovalPolicy.DESTROY if self.stage != "prod" else RemovalPolicy.RETAIN,
            auto_delete_objects=True if self.stage == "dev" else False
        )
        
        return bucket
    
    def _create_session_table(self) -> dynamodb.Table:
        """Create DynamoDB table for session management."""
        table = dynamodb.Table(
            self,
            "SessionTable",
            table_name=f"{self.app_name}-{self.stage}-sessions",
            
            # Primary key
            partition_key=dynamodb.Attribute(
                name="session_id",
                type=dynamodb.AttributeType.STRING
            ),
            
            # Billing mode
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            
            # TTL for automatic cleanup
            time_to_live_attribute="expires_at",
            
            # Security
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.kms_key,
            
            # Backup
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True if self.stage == "prod" else False
            ),
            
            # Cleanup
            removal_policy=RemovalPolicy.DESTROY if self.stage != "prod" else RemovalPolicy.RETAIN
        )
        
        # Add GSI for user lookup
        table.add_global_secondary_index(
            index_name="UserIndex",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
        
        return table
    
    
    def _create_jobs_table(self) -> dynamodb.Table:
        """Create DynamoDB table for job tracking."""
        table = dynamodb.Table(
            self,
            "JobsTable",
            table_name=f"{self.app_name}-{self.stage}-jobs",
            
            # Primary key
            partition_key=dynamodb.Attribute(
                name="job_id",
                type=dynamodb.AttributeType.STRING
            ),
            
            # Billing mode
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            
            # TTL for automatic cleanup of old jobs (30 days)
            time_to_live_attribute="expires_at",
            
            # Security
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.kms_key,
            
            # Backup
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True if self.stage == "prod" else False
            ),
            
            # Cleanup
            removal_policy=RemovalPolicy.DESTROY if self.stage != "prod" else RemovalPolicy.RETAIN
        )
        
        # Add GSI for user lookup
        table.add_global_secondary_index(
            index_name="UserIndex",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
        
        # Add GSI for status lookup  
        table.add_global_secondary_index(
            index_name="StatusIndex",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="updated_at",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
        
        return table
    
    def _create_medical_brands_table(self) -> dynamodb.Table:
        """Create DynamoDB table for medical brands with pronunciation and difficulty."""
        table = dynamodb.Table(
            self,
            "MedicalBrandsTable",
            table_name=f"{self.app_name}-{self.stage}-medical-brands",
            
            # Primary key
            partition_key=dynamodb.Attribute(
                name="brand_id",
                type=dynamodb.AttributeType.STRING
            ),
            
            # Billing mode
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            
            # Security
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.kms_key,
            
            # Backup
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True if self.stage == "prod" else False
            ),
            
            # Cleanup
            removal_policy=RemovalPolicy.DESTROY if self.stage != "prod" else RemovalPolicy.RETAIN
        )
        
        # Add GSI for category lookup (medical vertical)
        table.add_global_secondary_index(
            index_name="CategoryIndex",
            partition_key=dynamodb.Attribute(
                name="category",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
        
        # Add GSI for difficulty lookup
        table.add_global_secondary_index(
            index_name="DifficultyIndex",
            partition_key=dynamodb.Attribute(
                name="difficulty",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
        
        return table
    
    def _create_medical_terms_table(self) -> dynamodb.Table:
        """Create DynamoDB table for medical terms with pronunciation and difficulty."""
        table = dynamodb.Table(
            self,
            "MedicalTermsTable",
            table_name=f"{self.app_name}-{self.stage}-medical-terms",
            
            # Primary key
            partition_key=dynamodb.Attribute(
                name="term_id",
                type=dynamodb.AttributeType.STRING
            ),
            
            # Billing mode
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            
            # Security
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=self.kms_key,
            
            # Backup
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True if self.stage == "prod" else False
            ),
            
            # Cleanup
            removal_policy=RemovalPolicy.DESTROY if self.stage != "prod" else RemovalPolicy.RETAIN
        )
        
        # Add GSI for category lookup (medical vertical)
        table.add_global_secondary_index(
            index_name="CategoryIndex",
            partition_key=dynamodb.Attribute(
                name="category",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
        
        # Add GSI for difficulty lookup
        table.add_global_secondary_index(
            index_name="DifficultyIndex",
            partition_key=dynamodb.Attribute(
                name="difficulty",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
        
        return table
    
    @property
    def data_encryption_key(self) -> kms.Key:
        """Get the KMS key used for data encryption."""
        return self.kms_key
    
    def _add_bucket_notifications(self, bucket: s3.Bucket):
        """Add S3 bucket notifications for processing."""
        
        # Lambda for processing uploaded files
        processing_lambda = lambda_.Function(
            self,
            "FileProcessingLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="index.handler",
            code=lambda_.Code.from_inline('''
import json
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    try:
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']
            event_name = record['eventName']
            
            logger.info(f"Processing {event_name} for {bucket}/{key}")
            
            # Add your file processing logic here
            # For example: validate file format, extract metadata, etc.
            
        return {'statusCode': 200, 'body': 'Files processed successfully'}
        
    except Exception as e:
        logger.error(f"File processing error: {str(e)}")
        raise
            '''),
            description="Lambda for processing uploaded files",
            timeout=Duration.minutes(5),
            memory_size=512
        )
        
        # Grant Lambda permissions to read from S3
        bucket.grant_read(processing_lambda)
        
        # Add S3 notification
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(processing_lambda),
            s3.NotificationKeyFilter(prefix="uploads/")
        )
    
