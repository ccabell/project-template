"""
CDK stack for voice actor transcription platform using Lambda architecture.

This stack creates a serverless voice actor platform with:
• API Gateway with Lambda integration
• WebSocket API for real-time audio recording
• DynamoDB tables for data storage
• S3 buckets for audio recordings and scripts
• Cognito for authentication with Google SSO support
• Role-based access control
"""

from aws_cdk import (
    CfnOutput,
    CfnParameter,
    Duration,
    RemovalPolicy,
    Stack,
    aws_lambda_event_sources,
)
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class VoiceActorStack(Stack):
    """Stack for deploying voice actor transcription platform on Lambda."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """Initialize the voice actor stack.

        Args:
            scope: CDK construct scope
            construct_id: Stack identifier
            **kwargs: Additional stack arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        # Parameters
        self.environment_name = CfnParameter(
            self,
            "EnvironmentName",
            type="String",
            default="sandbox",
            description="Environment name (e.g., sandbox, dev, staging, prod)",
        )

        # Create resources
        self.vpc = self._create_vpc()
        self.s3_buckets = self._create_s3_buckets()
        self.rds_database = self._create_rds_database()
        self.dynamodb_tables = self._create_dynamodb_tables()
        self.cognito_resources = self._create_cognito_resources()
        self.lambda_functions = self._create_lambda_functions()
        self.api_gateway = self._create_api_gateway()
        self._configure_cognito_permissions()
        self.websocket_api = self._create_websocket_api()
        self.frontend_bucket = self._create_frontend_bucket()
        self._create_outputs()

    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC for RDS and Lambda functions."""
        vpc = ec2.Vpc(
            self,
            "VoiceActorVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.2.0.0/16"),
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Database",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=28,
                ),
            ],
            nat_gateways=0,
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

        # Add VPC endpoints for Lambda functions
        vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        # VPC endpoint for RDS
        endpoint_security_group = ec2.SecurityGroup(
            self,
            "VPCEndpointSG",
            vpc=vpc,
            description="Security group for VPC endpoints",
            allow_all_outbound=False,
        )

        endpoint_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="HTTPS from VPC",
        )

        return vpc

    def _create_rds_database(self) -> rds.DatabaseCluster:
        """Create Aurora PostgreSQL database cluster with Data API."""

        # Database security group
        db_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSG",
            vpc=self.vpc,
            description="Security group for RDS PostgreSQL",
            allow_all_outbound=False,
        )

        # Allow Lambda functions to access database
        lambda_security_group = ec2.SecurityGroup(
            self,
            "LambdaSG",
            vpc=self.vpc,
            description="Security group for Lambda functions",
            allow_all_outbound=True,
        )

        db_security_group.add_ingress_rule(
            peer=lambda_security_group,
            connection=ec2.Port.tcp(5432),
            description="PostgreSQL from Lambda functions",
        )

        # Database subnet group
        db_subnet_group = rds.SubnetGroup(
            self,
            "DatabaseSubnetGroup",
            description="Subnet group for RDS PostgreSQL",
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
        )

        # Aurora PostgreSQL cluster with Data API
        cluster = rds.DatabaseCluster(
            self,
            "VoiceActorDatabase",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_17_5
            ),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            writer=rds.ClusterInstance.serverless_v2(
                "writer",
                enable_performance_insights=True,
                performance_insight_retention=rds.PerformanceInsightRetention.MONTHS_1,
            ),
            serverless_v2_min_capacity=0.5,
            serverless_v2_max_capacity=16,
            storage_type=rds.DBClusterStorageType.AURORA_IOPT1,
            cloudwatch_logs_exports=["postgresql"],
            cloudwatch_logs_retention=logs.RetentionDays.ONE_WEEK,
            monitoring_interval=Duration.minutes(1),
            default_database_name="voice_actor_db",
            enable_data_api=True,
            backup=rds.BackupProps(
                retention=Duration.days(14), preferred_window="08:00-09:00"
            ),
        )

        # Store Lambda security group for later use
        self.lambda_security_group = lambda_security_group

        return cluster

    def _create_s3_buckets(self) -> dict:
        """Create S3 buckets for recordings and scripts."""

        # Recordings bucket
        recordings_bucket = s3.Bucket(
            self,
            "RecordingsBucket",
            bucket_name=f"a360-{self.environment_name.value_as_string}-voice-actor-recordings",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldVersions",
                    abort_incomplete_multipart_upload_after=Duration.days(7),
                    noncurrent_version_expiration=Duration.days(30),
                )
            ],
            cors=[
                s3.CorsRule(
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.POST,
                    ],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3000,
                )
            ],
        )

        # Scripts bucket
        scripts_bucket = s3.Bucket(
            self,
            "ScriptsBucket",
            bucket_name=f"a360-{self.environment_name.value_as_string}-voice-actor-scripts",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        return {"recordings": recordings_bucket, "scripts": scripts_bucket}

    def _create_dynamodb_tables(self) -> dict:
        """Create DynamoDB tables for data storage."""

        # Scripts table
        scripts_table = dynamodb.Table(
            self,
            "ScriptsTable",
            table_name=f"a360-{self.environment_name.value_as_string}-scripts",
            partition_key=dynamodb.Attribute(
                name="script_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )

        # User configurations table
        user_configs_table = dynamodb.Table(
            self,
            "UserConfigsTable",
            table_name=f"a360-{self.environment_name.value_as_string}-user-configs",
            partition_key=dynamodb.Attribute(
                name="user_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )

        # Recordings table
        recordings_table = dynamodb.Table(
            self,
            "RecordingsTable",
            table_name=f"a360-{self.environment_name.value_as_string}-recordings",
            partition_key=dynamodb.Attribute(
                name="user_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="recording_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
        )

        # WebSocket connections table
        connections_table = dynamodb.Table(
            self,
            "ConnectionsTable",
            table_name=f"a360-{self.environment_name.value_as_string}-websocket-connections",
            partition_key=dynamodb.Attribute(
                name="connection_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
        )

        # Brands and terms table
        brands_terms_table = dynamodb.Table(
            self,
            "BrandsTermsTable",
            table_name=f"a360-{self.environment_name.value_as_string}-brands-terms",
            partition_key=dynamodb.Attribute(
                name="type", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="name", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Jobs table for async processing
        jobs_table = dynamodb.Table(
            self,
            "JobsTable",
            table_name=f"a360-{self.environment_name.value_as_string}-jobs",
            partition_key=dynamodb.Attribute(
                name="job_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            time_to_live_attribute="ttl",
        )

        # Add Global Secondary Index for efficient user_id queries
        jobs_table.add_global_secondary_index(
            index_name="UserIdIndex",
            partition_key=dynamodb.Attribute(
                name="user_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at", type=dynamodb.AttributeType.STRING
            ),
        )

        # SQS queue for large job processing
        large_jobs_queue = sqs.Queue(
            self,
            "LargeJobsQueue",
            queue_name=f"a360-{self.environment_name.value_as_string}-large-jobs",
            visibility_timeout=Duration.minutes(20),  # Longer than Lambda timeout
            retention_period=Duration.days(14),  # Keep messages for 2 weeks
            delivery_delay=Duration.seconds(0),
            receive_message_wait_time=Duration.seconds(20),  # Long polling
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Dead letter queue for failed large jobs
        large_jobs_dlq = sqs.Queue(
            self,
            "LargeJobsDLQ",
            queue_name=f"a360-{self.environment_name.value_as_string}-large-jobs-dlq",
            retention_period=Duration.days(14),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Configure DLQ for main queue
        large_jobs_queue.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("sqs.amazonaws.com")],
                actions=["sqs:SendMessage"],
                resources=[large_jobs_dlq.queue_arn],
            )
        )

        return {
            "scripts": scripts_table,
            "user_configs": user_configs_table,
            "recordings": recordings_table,
            "connections": connections_table,
            "brands_terms": brands_terms_table,
            "jobs": jobs_table,
            "large_jobs_queue": large_jobs_queue,
            "large_jobs_dlq": large_jobs_dlq,
        }

    def _create_cognito_resources(self) -> dict:
        """Create Cognito resources for authentication."""

        # User Pool
        user_pool = cognito.UserPool(
            self,
            "VoiceActorUserPool",
            user_pool_name=f"a360-{self.environment_name.value_as_string}-voice-actors",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # User Pool Client
        user_pool_client = cognito.UserPoolClient(
            self,
            "VoiceActorUserPoolClient",
            user_pool=user_pool,
            user_pool_client_name=f"a360-{self.environment_name.value_as_string}-voice-actor-client",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(
                user_password=True, user_srp=True, admin_user_password=True
            ),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO
            ],
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=[
                    "https://localhost:3000/callback",
                    "https://your-domain.com/callback",
                ],  # Update with actual URLs
            ),
            refresh_token_validity=Duration.days(30),
            id_token_validity=Duration.hours(24),
            access_token_validity=Duration.hours(24),
        )

        # Identity Pool
        identity_pool = cognito.CfnIdentityPool(
            self,
            "VoiceActorIdentityPool",
            identity_pool_name=f"a360-{self.environment_name.value_as_string}-voice-actor-identity",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=user_pool_client.user_pool_client_id,
                    provider_name=user_pool.user_pool_provider_name,
                )
            ],
        )

        # IAM roles for Identity Pool
        authenticated_role = iam.Role(
            self,
            "CognitoAuthenticatedRole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                conditions={
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    },
                },
            ),
            inline_policies={
                "CognitoAuthenticatedPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["execute-api:Invoke"],
                            resources=["*"],
                        ),
                        # Standard Cognito Identity permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "mobileanalytics:PutEvents",
                                "cognito-sync:*",
                                "cognito-identity:*",
                            ],
                            resources=["*"],
                        ),
                    ]
                )
            },
        )

        unauthenticated_role = iam.Role(
            self,
            "CognitoUnauthenticatedRole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                conditions={
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "unauthenticated"
                    },
                },
            ),
            inline_policies={
                "CognitoUnauthenticatedPolicy": iam.PolicyDocument(
                    statements=[
                        # Minimal permissions for unauthenticated users
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["mobileanalytics:PutEvents", "cognito-sync:*"],
                            resources=["*"],
                        ),
                    ]
                )
            },
        )

        # Attach roles to Identity Pool
        cognito.CfnIdentityPoolRoleAttachment(
            self,
            "IdentityPoolRoleAttachment",
            identity_pool_id=identity_pool.ref,
            roles={
                "authenticated": authenticated_role.role_arn,
                "unauthenticated": unauthenticated_role.role_arn,
            },
        )

        # Google Identity Provider (placeholder - requires Google OAuth credentials)
        # google_provider = cognito.UserPoolIdentityProviderGoogle(
        #     self,
        #     "GoogleProvider",
        #     user_pool=user_pool,
        #     client_id="your-google-client-id",  # Replace with actual Google OAuth client ID
        #     client_secret="your-google-client-secret",  # Replace with actual Google OAuth client secret
        #     scopes=["email", "openid", "profile"]
        # )

        return {
            "user_pool": user_pool,
            "user_pool_client": user_pool_client,
            "identity_pool": identity_pool,
            "authenticated_role": authenticated_role,
        }

    def _create_lambda_functions(self) -> dict:
        """Create Lambda functions."""

        # Lambda execution role
        lambda_role = iam.Role(
            self,
            "VoiceActorLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaVPCAccessExecutionRole"
                ),
            ],
            inline_policies={
                "VoiceActorPolicy": iam.PolicyDocument(
                    statements=[
                        # DynamoDB permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "dynamodb:GetItem",
                                "dynamodb:PutItem",
                                "dynamodb:UpdateItem",
                                "dynamodb:DeleteItem",
                                "dynamodb:Query",
                                "dynamodb:Scan",
                            ],
                            resources=[
                                self.dynamodb_tables["scripts"].table_arn,
                                self.dynamodb_tables["user_configs"].table_arn,
                                self.dynamodb_tables["recordings"].table_arn,
                                self.dynamodb_tables["connections"].table_arn,
                                self.dynamodb_tables["brands_terms"].table_arn,
                                self.dynamodb_tables["jobs"].table_arn,
                            ],
                        ),
                        # S3 permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:DeleteObject",
                                "s3:ListBucket",
                            ],
                            resources=[
                                self.s3_buckets["recordings"].bucket_arn,
                                f"{self.s3_buckets['recordings'].bucket_arn}/*",
                                self.s3_buckets["scripts"].bucket_arn,
                                f"{self.s3_buckets['scripts'].bucket_arn}/*",
                            ],
                        ),
                        # Cognito permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "cognito-idp:AdminGetUser",
                                "cognito-idp:AdminListGroupsForUser",
                            ],
                            resources=[
                                self.cognito_resources["user_pool"].user_pool_arn
                            ],
                        ),
                        # Bedrock permissions - ALL ACTIONS GRANTED
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeDataAutomationJob",
                                "bedrock:InvokeFlow",
                                "bedrock:InvokeInlineAgent",
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                            ],
                            resources=[
                                # Foundation models - allow access across all US regions for cross-region inference
                                "arn:aws:bedrock:us-*::foundation-model/*",
                                # Account-specific resources in current region
                                f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:application-inference-profile/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:async-invoke/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:bedrock-marketplace-model-endpoint/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:custom-model-deployment/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:default-prompt-router/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:imported-model/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:prompt-router/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:provisioned-model/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:flow-alias/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:blueprint/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:data-automation-profile/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:data-automation-project/*",
                            ],
                        ),
                        # Secrets Manager permissions for RDS
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["secretsmanager:GetSecretValue"],
                            resources=[self.rds_database.secret.secret_arn],
                        ),
                        # RDS Data API permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "rds-data:ExecuteStatement",
                                "rds-data:BatchExecuteStatement",
                                "rds-data:BeginTransaction",
                                "rds-data:CommitTransaction",
                                "rds-data:RollbackTransaction",
                            ],
                            resources=[self.rds_database.cluster_arn],
                        ),
                        # Lambda invoke permissions for async processing
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["lambda:InvokeFunction"],
                            resources=[
                                f"arn:aws:lambda:{self.region}:{self.account}:function:*"
                            ],
                        ),
                        # SQS permissions for large job processing
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sqs:SendMessage",
                                "sqs:ReceiveMessage",
                                "sqs:DeleteMessage",
                                "sqs:GetQueueAttributes",
                                "sqs:ChangeMessageVisibility",
                            ],
                            resources=[
                                self.dynamodb_tables["large_jobs_queue"].queue_arn,
                                self.dynamodb_tables["large_jobs_dlq"].queue_arn,
                            ],
                        ),
                    ]
                )
            },
        )

        # Use AWS PowerTools layer and create our own dependencies layer
        powertools_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "PowerToolsLayer",
            layer_version_arn="arn:aws:lambda:us-east-1:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-arm64:18",
        )

        # Create log group for API Lambda
        api_lambda_log_group = logs.LogGroup(
            self,
            "VoiceActorAPIFunctionLogGroup",
            log_group_name="/aws/lambda/VoiceActorAPIFunction",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Main API Lambda function using source code directory
        api_lambda = lambda_.Function(
            self,
            "VoiceActorAPIFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset("../backend/lambda_functions/api_handler"),
            timeout=Duration.minutes(15),  # Maximum timeout for long generations
            memory_size=1024,  # Increased memory for better performance
            role=lambda_role,
            architecture=lambda_.Architecture.ARM_64,
            layers=[powertools_layer],
            log_group=api_lambda_log_group,
            environment={
                "DB_SECRET_ARN": self.rds_database.secret.secret_arn,
                "DB_CLUSTER_ARN": self.rds_database.cluster_arn,
                "COGNITO_USER_POOL_ID": self.cognito_resources[
                    "user_pool"
                ].user_pool_id,
                "SCRIPTS_TABLE_NAME": self.dynamodb_tables["scripts"].table_name,
                "USER_CONFIGS_TABLE_NAME": self.dynamodb_tables[
                    "user_configs"
                ].table_name,
                "RECORDINGS_TABLE_NAME": self.dynamodb_tables["recordings"].table_name,
                "BRANDS_TERMS_TABLE_NAME": self.dynamodb_tables[
                    "brands_terms"
                ].table_name,
                "JOBS_TABLE_NAME": self.dynamodb_tables["jobs"].table_name,
                "RECORDINGS_BUCKET": self.s3_buckets["recordings"].bucket_name,
                "SCRIPTS_BUCKET": self.s3_buckets["scripts"].bucket_name,
                "LARGE_JOBS_QUEUE_URL": self.dynamodb_tables[
                    "large_jobs_queue"
                ].queue_url,
            },
        )

        # Create log group for Large Job Processor Lambda
        large_job_processor_log_group = logs.LogGroup(
            self,
            "LargeJobProcessorFunctionLogGroup",
            log_group_name="/aws/lambda/LargeJobProcessorFunction",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Large job processor Lambda function
        large_job_processor_lambda = lambda_.Function(
            self,
            "LargeJobProcessorFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "../backend/lambda_functions/large_job_processor"
            ),
            timeout=Duration.minutes(15),  # Maximum timeout for large generations
            memory_size=1024,
            role=lambda_role,
            architecture=lambda_.Architecture.ARM_64,
            layers=[powertools_layer],
            log_group=large_job_processor_log_group,
            environment={
                "DB_SECRET_ARN": self.rds_database.secret.secret_arn,
                "DB_CLUSTER_ARN": self.rds_database.cluster_arn,
                "JOBS_TABLE_NAME": self.dynamodb_tables["jobs"].table_name,
                "LARGE_JOBS_QUEUE_URL": self.dynamodb_tables[
                    "large_jobs_queue"
                ].queue_url,
            },
        )

        # SQS event source for large job processor
        large_job_processor_lambda.add_event_source(
            aws_lambda_event_sources.SqsEventSource(
                self.dynamodb_tables["large_jobs_queue"],
                batch_size=1,  # Process one job at a time
                max_batching_window=Duration.seconds(5),
                report_batch_item_failures=True,
            )
        )

        # Create log group for WebSocket Lambda
        websocket_lambda_log_group = logs.LogGroup(
            self,
            "VoiceActorWebSocketFunctionLogGroup",
            log_group_name="/aws/lambda/VoiceActorWebSocketFunction",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # WebSocket Lambda function
        websocket_lambda = lambda_.Function(
            self,
            "VoiceActorWebSocketFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset(
                "../backend/lambda_functions/websocket_handler"
            ),
            timeout=Duration.seconds(30),
            memory_size=1024,
            role=lambda_role,
            architecture=lambda_.Architecture.ARM_64,
            layers=[powertools_layer],
            log_group=websocket_lambda_log_group,
            environment={
                "RECORDINGS_BUCKET": self.s3_buckets["recordings"].bucket_name,
                "CONNECTIONS_TABLE": self.dynamodb_tables["connections"].table_name,
            },
        )

        return {
            "api": api_lambda,
            "websocket": websocket_lambda,
            "large_job_processor": large_job_processor_lambda,
        }

    def _create_api_gateway(self) -> apigw.RestApi:
        """Create API Gateway for REST API with Cognito authorization."""

        api = apigw.RestApi(
            self,
            "VoiceActorAPI",
            rest_api_name="Voice Actor Platform API",
            description="REST API for Voice Actor Transcription Platform",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "Authorization",
                    "X-Amz-Date",
                    "X-Api-Key",
                ],
            ),
        )

        # Create Cognito authorizer for authenticated endpoints
        cognito_authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            cognito_user_pools=[self.cognito_resources["user_pool"]],
            authorizer_name="VoiceActorCognitoAuthorizer",
            identity_source="method.request.header.Authorization",
        )

        # Lambda integration
        lambda_integration = apigw.LambdaIntegration(self.lambda_functions["api"])

        # Public endpoints (no authorization required)
        api.root.add_resource("health").add_method("GET", lambda_integration)

        # API routes
        api_resource = api.root.add_resource("api")

        # Generate endpoints (PROTECTED for job persistence)
        generate_resource = api_resource.add_resource("generate")
        generate_resource.add_resource("ground-truth").add_method(
            "POST",
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )
        generate_resource.add_resource("verticals").add_method(
            "GET", lambda_integration
        )

        # Analyze endpoints (public)
        analyze_resource = api_resource.add_resource("analyze")
        analyze_resource.add_resource("single").add_method("POST", lambda_integration)

        # Brands and Terms endpoints (public for now)
        brands_resource = api_resource.add_resource("brands")
        brands_resource.add_method("GET", lambda_integration)
        brands_resource.add_method("POST", lambda_integration)
        brands_resource.add_method("DELETE", lambda_integration)

        terms_resource = api_resource.add_resource("terms")
        terms_resource.add_method("GET", lambda_integration)
        terms_resource.add_method("POST", lambda_integration)
        terms_resource.add_method("DELETE", lambda_integration)

        # Jobs endpoints (PROTECTED - require Cognito authentication)
        jobs_resource = api_resource.add_resource("jobs")
        jobs_resource.add_method(
            "GET",
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )  # Get user jobs

        job_detail_resource = jobs_resource.add_resource("{job_id}")
        job_detail_resource.add_method(
            "GET",
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )  # Get specific job

        # User-specific endpoints (PROTECTED)
        user_resource = api_resource.add_resource("user")
        user_profile_resource = user_resource.add_resource("profile")
        user_profile_resource.add_method(
            "GET",
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # Scripts routes (PROTECTED)
        scripts_resource = api_resource.add_resource("scripts")
        scripts_resource.add_method(
            "GET",
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )
        scripts_resource.add_method(
            "POST",
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        script_detail_resource = scripts_resource.add_resource("{script_id}")
        script_detail_resource.add_method(
            "GET",
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        # Recordings routes (PROTECTED)
        recordings_resource = api_resource.add_resource("recordings")
        recordings_resource.add_method(
            "GET",
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        recordings_start_resource = recordings_resource.add_resource("start")
        recordings_start_resource.add_method(
            "POST",
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        recordings_submit_resource = recordings_resource.add_resource("submit")
        recordings_submit_resource.add_method(
            "POST",
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        return api

    def _create_websocket_api(self) -> apigwv2.WebSocketApi:
        """Create WebSocket API for real-time audio streaming."""

        # WebSocket API
        websocket_api = apigwv2.WebSocketApi(
            self,
            "VoiceActorWebSocketAPI",
            api_name="Voice Actor WebSocket API",
            description="WebSocket API for real-time audio recording",
        )

        # Lambda integration
        lambda_integration = integrations.WebSocketLambdaIntegration(
            "WebSocketLambdaIntegration", self.lambda_functions["websocket"]
        )

        # Add routes
        websocket_api.add_route("$connect", integration=lambda_integration)

        websocket_api.add_route("$disconnect", integration=lambda_integration)

        websocket_api.add_route("audio_chunk", integration=lambda_integration)

        websocket_api.add_route("start_recording", integration=lambda_integration)

        websocket_api.add_route("stop_recording", integration=lambda_integration)

        # Create stage
        apigwv2.WebSocketStage(
            self,
            "WebSocketStage",
            web_socket_api=websocket_api,
            stage_name="prod",
            auto_deploy=True,
        )

        # Update WebSocket Lambda with API endpoint
        self.lambda_functions["websocket"].add_environment(
            "WEBSOCKET_API_ENDPOINT",
            f"https://{websocket_api.api_id}.execute-api.{self.region}.amazonaws.com/prod",
        )

        return websocket_api

    def _create_frontend_bucket(self) -> s3.Bucket:
        """Create S3 bucket for frontend hosting."""

        frontend_bucket = s3.Bucket(
            self,
            "FrontendBucket",
            bucket_name=f"a360-{self.environment_name.value_as_string}-voice-actor-frontend",
            website_index_document="index.html",
            website_error_document="index.html",
            public_read_access=True,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                ignore_public_acls=False,
                block_public_policy=False,
                restrict_public_buckets=False,
            ),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
        )

        return frontend_bucket

    def _configure_cognito_permissions(self) -> None:
        """Configure Cognito Identity Pool permissions after API Gateway is created."""
        # Add API Gateway invoke permissions to the authenticated role
        authenticated_role = self.cognito_resources["authenticated_role"]
        authenticated_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["execute-api:Invoke"],
                resources=[f"{self.api_gateway.arn_for_execute_api()}*"],
            )
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs."""

        CfnOutput(
            self,
            "ApiGatewayUrl",
            value=self.api_gateway.url,
            description="API Gateway URL",
        )

        CfnOutput(
            self,
            "WebSocketApiUrl",
            value=f"wss://{self.websocket_api.api_id}.execute-api.{self.region}.amazonaws.com/prod",
            description="WebSocket API URL",
        )

        CfnOutput(
            self,
            "FrontendUrl",
            value=f"http://{self.frontend_bucket.bucket_website_domain_name}",
            description="Frontend website URL",
        )

        CfnOutput(
            self,
            "CognitoUserPoolId",
            value=self.cognito_resources["user_pool"].user_pool_id,
            description="Cognito User Pool ID",
        )

        CfnOutput(
            self,
            "CognitoUserPoolClientId",
            value=self.cognito_resources["user_pool_client"].user_pool_client_id,
            description="Cognito User Pool Client ID",
        )

        CfnOutput(
            self,
            "CognitoIdentityPoolId",
            value=self.cognito_resources["identity_pool"].ref,
            description="Cognito Identity Pool ID",
        )

        CfnOutput(
            self,
            "RecordingsBucketName",
            value=self.s3_buckets["recordings"].bucket_name,
            description="S3 bucket for audio recordings",
        )

        CfnOutput(
            self,
            "ScriptsBucketName",
            value=self.s3_buckets["scripts"].bucket_name,
            description="S3 bucket for scripts",
        )
