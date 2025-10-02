"""Compute stack for A360 Transcription Service Evaluator.

This stack creates compute infrastructure including ECS Fargate services,
Lambda functions, and related compute resources following AWS best practices.
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_rds as rds,
    aws_s3 as s3,
    aws_cognito as cognito,
    aws_verifiedpermissions as avp,
    aws_ecr_assets as ecr_assets,
    aws_dynamodb as dynamodb,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
from custom_constructs.powertools_lambda_construct import PowertoolsLambdaConstruct


class ComputeStack(cdk.NestedStack):
    """Compute infrastructure stack."""
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_name: str,
        stage: str,
        vpc: ec2.Vpc,
        ecs_security_group: ec2.SecurityGroup,
        alb_security_group: ec2.SecurityGroup,  # Not used for NLB but kept for compatibility
        lambda_security_group: ec2.SecurityGroup,
        database_cluster: rds.DatabaseCluster,
        user_pool: cognito.UserPool,
        user_pool_client: cognito.UserPoolClient,
        policy_store: "avp.CfnPolicyStore",
        application_bucket: s3.Bucket,
        cloudfront_url: str = None,
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)
        
        self.app_name = app_name
        self.stage = stage
        self.vpc = vpc
        self.ecs_security_group = ecs_security_group
        self.alb_security_group = alb_security_group
        self.cloudfront_url = cloudfront_url
        self.lambda_security_group = lambda_security_group
        self.database_cluster = database_cluster
        self.user_pool = user_pool
        self.user_pool_client = user_pool_client
        self.policy_store = policy_store
        self.application_bucket = application_bucket
        
        # Create ECS cluster
        self.ecs_cluster = self._create_ecs_cluster()
        
        # Create Docker image asset (automatically creates ECR repository)
        self.docker_image = self._create_docker_image()
        
        # Create ALB
        self.load_balancer = self._create_load_balancer()
        
        # Create ECS service
        self.ecs_service = self._create_ecs_service()
        
        # Create Lambda functions
        self._create_lambda_functions()
    
    def _create_ecs_cluster(self) -> ecs.Cluster:
        """Create ECS cluster for Fargate services."""
        cluster = ecs.Cluster(
            self,
            "EcsCluster",
            cluster_name=f"{self.app_name}-{self.stage}-cluster",
            vpc=self.vpc,
            enable_fargate_capacity_providers=True,
            container_insights_v2=ecs.ContainerInsights.ENABLED
        )
        
        # Add tags
        cdk.Tags.of(cluster).add("Environment", self.stage)
        cdk.Tags.of(cluster).add("Application", self.app_name)
        
        return cluster
    
    def _create_docker_image(self) -> ecr_assets.DockerImageAsset:
        """Create Docker image asset that automatically builds and pushes to ECR."""
        docker_image = ecr_assets.DockerImageAsset(
            self,
            "DockerImage",
            directory="../",
            platform=ecr_assets.Platform.LINUX_ARM64,
            file="Dockerfile",
            build_args={
                "BUILDPLATFORM": "linux/arm64",
                "TARGETPLATFORM": "linux/arm64"
            },
            exclude=[
                "cdk/",
                "docs/",
                ".git/",
                ".venv/",
                "*.md",
                ".gitignore",
                ".archive/"
            ]
        )
        
        cdk.Tags.of(docker_image).add("Environment", self.stage)
        cdk.Tags.of(docker_image).add("Application", self.app_name)
        
        return docker_image
    
    def _create_load_balancer(self) -> elbv2.NetworkLoadBalancer:
        """Create Network Load Balancer for API Gateway VpcLink compatibility."""
        nlb = elbv2.NetworkLoadBalancer(
            self,
            "NetworkLoadBalancer",
            vpc=self.vpc,
            internet_facing=True,
            load_balancer_name=f"a360-transcription-{self.stage}-nlb",
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            )
        )
        
        # Add tags
        cdk.Tags.of(nlb).add("Environment", self.stage)
        cdk.Tags.of(nlb).add("Application", self.app_name)
        
        return nlb
    
    def _create_ecs_service(self) -> ecs.FargateService:
        """Create ECS Fargate service for the web application."""
        
        # Create task definition with ARM64 architecture
        task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            family=f"{self.app_name}-{self.stage}-task",
            memory_limit_mib=1024,
            cpu=512,
            runtime_platform=ecs.RuntimePlatform(
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
                cpu_architecture=ecs.CpuArchitecture.ARM64
            ),
            execution_role=self._create_execution_role(),
            task_role=self._create_task_role()
        )
        
        # Add container
        task_definition.add_container(
            "WebContainer",
            image=ecs.ContainerImage.from_docker_image_asset(self.docker_image),
            port_mappings=[
                ecs.PortMapping(
                    container_port=8000,
                    protocol=ecs.Protocol.TCP
                )
            ],
            environment=self._get_environment_variables(),
            # Secrets will be added after creating the execution role to avoid circular dependencies
            secrets={},
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="ecs",
                log_group=logs.LogGroup(
                    self,
                    "EcsLogGroup",
                    log_group_name=f"/ecs/{self.app_name}-{self.stage}",
                    retention=logs.RetentionDays.ONE_MONTH,
                    removal_policy=RemovalPolicy.DESTROY
                )
            ),
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(120)  # 2 minutes for FastAPI startup
            )
        )
        
        # Create Fargate service
        service = ecs.FargateService(
            self,
            "FargateService",
            service_name=f"{self.app_name}-{self.stage}-service",
            cluster=self.ecs_cluster,
            task_definition=task_definition,
            desired_count=2 if self.stage == "prod" else 1,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[self.ecs_security_group],
            enable_execute_command=True,
            platform_version=ecs.FargatePlatformVersion.LATEST,
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
            health_check_grace_period=Duration.seconds(300),  # 5 minutes for app startup
            min_healthy_percent=100,  # Ensure zero-downtime deployments
            max_healthy_percent=200   # Allow up to 2x desired count during deployments
        )
        
        # Create target group for NLB
        target_group = elbv2.NetworkTargetGroup(
            self,
            "TargetGroup",
            vpc=self.vpc,
            port=8000,
            protocol=elbv2.Protocol.TCP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                enabled=True,
                interval=Duration.seconds(30),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
                protocol=elbv2.Protocol.TCP,
                port="8000"
            ),
            deregistration_delay=Duration.seconds(30)
        )
        
        # Add targets
        service.attach_to_network_target_group(target_group)
        
        # Add listener
        self.load_balancer.add_listener(
            "TcpListener",
            port=80,
            protocol=elbv2.Protocol.TCP,
            default_target_groups=[target_group]
        )
        
        return service
    
    def _get_environment_variables(self) -> dict:
        """Get environment variables for ECS task."""
        env_vars = {
            "TRANSCRIPTION_EVALUATOR_STAGE": self.stage,
            "TRANSCRIPTION_EVALUATOR_S3_BUCKET": self.application_bucket.bucket_name,
            "TRANSCRIPTION_EVALUATOR_COGNITO_USER_POOL_ID": self.user_pool.user_pool_id,
            "TRANSCRIPTION_EVALUATOR_DATABASE_HOST": self.database_cluster.cluster_endpoint.hostname,
            "TRANSCRIPTION_EVALUATOR_DATABASE_PORT": "5432",
            "TRANSCRIPTION_EVALUATOR_DATABASE_NAME": "transcription_evaluator",
            "TRANSCRIPTION_EVALUATOR_AWS_REGION": cdk.Stack.of(self).region,
            # Required by FastAPI app (cognito_main.py)
            "COGNITO_USER_POOL_ID": self.user_pool.user_pool_id,
            "COGNITO_CLIENT_ID": self.user_pool_client.user_pool_client_id,
            "VERIFIED_PERMISSIONS_POLICY_STORE_ID": self.policy_store.attr_policy_store_id,
        }
        
        # Add CloudFront URL if provided
        if self.cloudfront_url:
            env_vars["CLOUDFRONT_URL"] = self.cloudfront_url
        
        return env_vars
    
    def _create_execution_role(self) -> iam.Role:
        """Create ECS task execution role."""
        role = iam.Role(
            self,
            "EcsExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ]
        )
        
        # Add permissions for ECR and Secrets Manager
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage"
                ],
                resources=["*"]
            )
        )
        
        # Database secret permissions will be granted to the task role instead
        
        return role
    
    def _create_task_role(self) -> iam.Role:
        """Create ECS task role with application permissions."""
        role = iam.Role(
            self,
            "EcsTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )
        
        # Add permissions for AWS services used by the application
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminListGroupsForUser",
                    "cognito-idp:GetUser"
                ],
                resources=[self.user_pool.user_pool_arn]
            )
        )
        
        # Grant permissions for the application S3 bucket
        self.application_bucket.grant_read_write(role)
        
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"
                ],
                resources=["arn:aws:dynamodb:*:*:table/*"]  # Will be restricted to specific tables
            )
        )
        
        # Grant generic permissions to read secrets (database secret ARN passed via environment)
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                resources=[f"arn:aws:secretsmanager:{cdk.Stack.of(self).region}:{cdk.Stack.of(self).account}:secret:*"]
            )
        )
        
        # Grant permissions to read Parameter Store parameters
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "ssm:GetParametersByPath"
                ],
                resources=[
                    f"arn:aws:ssm:{cdk.Stack.of(self).region}:{cdk.Stack.of(self).account}:parameter/{self.app_name.lower()}/{self.stage}/*"
                ]
            )
        )
        
        # Grant permissions to invoke Bedrock models for ground truth generation (cross-region)
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:*:{cdk.Stack.of(self).account}:inference-profile/*"
                ]
            )
        )
        
        return role
    

    def _create_lambda_functions(self):
        """Lambda functions are handled by specialized stacks.
        
        Database initialization is handled by the Data stack.
        API Lambda functions will be handled by the API stack.
        This compute stack focuses on ECS Fargate services.
        """
        # No placeholder Lambda functions - they're handled by appropriate stacks
        pass