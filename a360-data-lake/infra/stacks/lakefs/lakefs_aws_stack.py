#!/usr/bin/env python3
"""LakeFS AWS Infrastructure Stack
=============================

Creates AWS infrastructure for LakeFS deployment:
- ECS Fargate service for LakeFS
- RDS PostgreSQL for metadata
- S3 bucket for data storage
- ALB for load balancing
- IAM roles and security groups
"""

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from aws_cdk import (
    aws_elasticloadbalancingv2 as elbv2,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_rds as rds,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from aws_cdk import (
    aws_ssm as ssm,
)
from constructs import Construct


class LakeFSStack(Stack):
    """LakeFS AWS deployment stack with dynamic account resolution."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get account and region dynamically
        account_id = self.account
        region = self.region

        # Environment prefix for resource naming
        env = self.node.try_get_context("environment") or "dev"

        # ========================================
        # VPC and Networking
        # ========================================

        # Get existing VPC or create new one
        vpc = ec2.Vpc.from_lookup(
            self, "VPC",
            is_default=True,  # Use default VPC for simplicity
        )

        # Security groups
        lakefs_sg = ec2.SecurityGroup(
            self, "LakeFSSecurityGroup",
            vpc=vpc,
            description="Security group for LakeFS service",
            allow_all_outbound=True,
        )

        db_sg = ec2.SecurityGroup(
            self, "LakeFSDBSecurityGroup",
            vpc=vpc,
            description="Security group for LakeFS PostgreSQL database",
        )

        # Allow LakeFS to connect to database
        db_sg.add_ingress_rule(
            peer=lakefs_sg,
            connection=ec2.Port.tcp(5432),
            description="Allow LakeFS to connect to PostgreSQL",
        )

        # ALB Security Group
        alb_sg = ec2.SecurityGroup(
            self, "LakeFSALBSecurityGroup",
            vpc=vpc,
            description="Security group for LakeFS ALB",
        )

        # Allow HTTP/HTTPS traffic to ALB
        alb_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP traffic",
        )
        alb_sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS traffic",
        )

        # Allow ALB to connect to LakeFS service
        lakefs_sg.add_ingress_rule(
            peer=alb_sg,
            connection=ec2.Port.tcp(8000),
            description="Allow ALB to connect to LakeFS",
        )

        # ========================================
        # S3 Storage for LakeFS Data
        # ========================================

        # Main data bucket with dynamic naming
        data_bucket = s3.Bucket(
            self, "LakeFSDataBucket",
            bucket_name=f"a360-lakefs-data-{env}-{account_id}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,  # Keep data on stack deletion
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ArchiveOldVersions",
                    enabled=True,
                    noncurrent_version_transitions=[
                        s3.NoncurrentVersionTransition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30),
                        ),
                        s3.NoncurrentVersionTransition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90),
                        ),
                    ],
                ),
            ],
        )

        # ========================================
        # RDS PostgreSQL for LakeFS Metadata
        # ========================================

        # Database credentials in Secrets Manager
        db_credentials = rds.Credentials.from_generated_secret(
            username="lakefs_admin",
            secret_name=f"lakefs-db-credentials-{env}",
        )

        # Auth encryption secret in Secrets Manager
        auth_secret = secretsmanager.Secret(
            self, "LakeFSAuthSecret",
            description="LakeFS authentication encryption secret",
            secret_name=f"lakefs-auth-secret-{env}",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"encrypt_key": ""}',
                generate_string_key="encrypt_key",
                exclude_characters='"\\/@',
                password_length=32,
            ),
        )

        # PostgreSQL instance
        database = rds.DatabaseInstance(
            self, "LakeFSDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_6,
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MICRO,  # Start small, can scale up
            ),
            vpc=vpc,
            security_groups=[db_sg],
            credentials=db_credentials,
            database_name="lakefs",
            allocated_storage=20,
            storage_encrypted=True,
            backup_retention=Duration.days(7),
            deletion_protection=False,  # Set to True in production
            removal_policy=RemovalPolicy.DESTROY,  # Change to RETAIN in production
        )

        # ========================================
        # IAM Role for LakeFS Service
        # ========================================

        lakefs_task_role = iam.Role(
            self, "LakeFSTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM role for LakeFS ECS task",
        )

        # Grant S3 permissions
        lakefs_task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:GetBucketVersioning",
                    "s3:PutBucketVersioning",
                ],
                resources=[
                    data_bucket.bucket_arn,
                    f"{data_bucket.bucket_arn}/*",
                ],
            ),
        )

        # Grant Secrets Manager permissions
        lakefs_task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=[
                    database.secret.secret_arn,
                    auth_secret.secret_arn,
                ],
            ),
        )

        # ========================================
        # ECS Cluster and Service
        # ========================================

        # ECS Cluster
        cluster = ecs.Cluster(
            self, "LakeFSCluster",
            vpc=vpc,
            cluster_name=f"lakefs-cluster-{env}",
        )

        # Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self, "LakeFSTaskDefinition",
            memory_limit_mib=2048,
            cpu=1024,
            task_role=lakefs_task_role,
        )

        # CloudWatch log group
        log_group = logs.LogGroup(
            self, "LakeFSLogGroup",
            log_group_name=f"/ecs/lakefs-{env}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # LakeFS container
        lakefs_container = task_definition.add_container(
            "lakefs",
            image=ecs.ContainerImage.from_registry("treeverse/lakefs:1.64.1"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="lakefs",
                log_group=log_group,
            ),
            environment={
                "LAKEFS_DATABASE_TYPE": "postgres",
                "LAKEFS_BLOCKSTORE_TYPE": "s3",
                "LAKEFS_BLOCKSTORE_S3_REGION": region,
                "LAKEFS_BLOCKSTORE_S3_FORCE_PATH_STYLE": "false",
                "LAKEFS_BLOCKSTORE_S3_DISCOVER_BUCKET_REGION": "true",
                "LAKEFS_LOGGING_LEVEL": "INFO",
            },
            secrets={
                "LAKEFS_DATABASE_POSTGRES_CONNECTION_STRING": ecs.Secret.from_secrets_manager(
                    database.secret,
                    field="connectionString",
                ),
                "LAKEFS_AUTH_ENCRYPT_SECRET_KEY": ecs.Secret.from_secrets_manager(
                    auth_secret,
                    field="encrypt_key",
                ),
            },
            port_mappings=[
                ecs.PortMapping(
                    container_port=8000,
                    protocol=ecs.Protocol.TCP,
                ),
            ],
        )

        # ECS Service
        service = ecs.FargateService(
            self, "LakeFSService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,  # Start with 1, can scale up
            security_groups=[lakefs_sg],
            assign_public_ip=True,  # Needed for image pull
            health_check_grace_period=Duration.minutes(5),
        )

        # ========================================
        # Application Load Balancer
        # ========================================

        # ALB
        alb = elbv2.ApplicationLoadBalancer(
            self, "LakeFSALB",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_sg,
        )

        # Target Group
        target_group = elbv2.ApplicationTargetGroup(
            self, "LakeFSTargetGroup",
            vpc=vpc,
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                enabled=True,
                healthy_http_codes="200",
                path="/api/v1/healthcheck",
                protocol=elbv2.Protocol.HTTP,
                timeout=Duration.seconds(5),
                interval=Duration.seconds(30),
                healthy_threshold_count=2,
                unhealthy_threshold_count=5,
            ),
        )

        # Add ECS service to target group
        service.attach_to_application_target_group(target_group)

        # ALB Listener
        listener = alb.add_listener(
            "LakeFSListener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_target_groups=[target_group],
        )

        # ========================================
        # SSM Parameters for Integration
        # ========================================

        # Store LakeFS endpoint for other services to use
        ssm.StringParameter(
            self, "LakeFSEndpointParameter",
            parameter_name=f"/lakefs/{env}/endpoint",
            string_value=f"http://{alb.load_balancer_dns_name}",
            description=f"LakeFS endpoint URL for {env} environment",
        )

        # Store bucket name for repository creation
        ssm.StringParameter(
            self, "LakeFSBucketParameter",
            parameter_name=f"/lakefs/{env}/bucket",
            string_value=data_bucket.bucket_name,
            description=f"LakeFS S3 bucket name for {env} environment",
        )

        # ========================================
        # Outputs
        # ========================================

        self.lakefs_endpoint = f"http://{alb.load_balancer_dns_name}"
        self.data_bucket_name = data_bucket.bucket_name
        self.database_endpoint = database.instance_endpoint.hostname

        # Export values for cross-stack references
        self.export_value(
            self.lakefs_endpoint,
            name=f"LakeFSEndpoint-{env}",
        )

        self.export_value(
            self.data_bucket_name,
            name=f"LakeFSBucket-{env}",
        )
