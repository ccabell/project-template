"""CDK stack for transcription evaluator service.

This stack creates a secure, production-ready deployment of the
transcription evaluator service using ECS Fargate with:
    • Private VPC deployment for security
    • Application Load Balancer with internal access only  
    • ECR repository for container images
    • IAM roles with least privilege access
    • Security groups with minimal required permissions
    • S3 bucket access for transcript evaluation data
"""

from aws_cdk import CfnOutput, CfnParameter, Duration, RemovalPolicy, Stack
from aws_cdk import aws_certificatemanager as acm
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_route53 as route53
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_apigatewayv2 as apigateway
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_cognito as cognito
from constructs import Construct


class TranscriptionEvaluatorStack(Stack):
    """Stack for deploying transcription evaluator service on ECS Fargate.
    
    Creates secure, production-ready infrastructure for the transcription
    evaluation service with internal-only access and proper security controls.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """Initialize the transcription evaluator stack.
        
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
            description="Environment name (e.g., sandbox, dev, staging, prod)"
        )

        self.vpc = self._create_vpc()
        self.s3_bucket = self._create_s3_bucket()
        self.frontend_bucket = self._create_frontend_bucket()
        self.cognito_user_pool, self.cognito_user_pool_client, self.cognito_identity_pool = self._create_cognito_user_pool()
        self.task_security_group, self.alb_security_group = self._create_security_groups()
        self.task_role = self._create_task_role()
        self.fargate_service = self._create_fargate_service()
        self.api_gateway = self._create_api_gateway()
        self._setup_cognito_identity_pool()
        # Temporarily disable CloudFront to get backend working first
        # self.cloudfront = self._create_cloudfront_distribution()
        self._create_outputs()

    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC with private subnets for secure deployment.
        
        Returns:
            VPC instance configured for internal service deployment
        """
        vpc = ec2.Vpc(
            self,
            "TranscriptionEvaluatorVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.1.0.0/16"),
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
            nat_gateways=0,
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

        # Add VPC endpoints for AWS services (cost-optimized selection)
        vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED)]
        )

        # Essential VPC endpoints for ECS operations
        endpoint_security_group = ec2.SecurityGroup(
            self,
            "VPCEndpointSecurityGroup",
            vpc=vpc,
            description="Security group for VPC endpoints",
            allow_all_outbound=False,
        )

        endpoint_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="HTTPS from VPC"
        )

        # ECR endpoints for container image pulls
        vpc.add_interface_endpoint(
            "ECREndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[endpoint_security_group],
        )

        vpc.add_interface_endpoint(
            "ECRDockerEndpoint", 
            service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[endpoint_security_group],
        )

        # CloudWatch Logs endpoint for logging
        vpc.add_interface_endpoint(
            "CloudWatchLogsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[endpoint_security_group],
        )

        return vpc

    def _create_s3_bucket(self) -> s3.Bucket:
        """Create S3 bucket for storing transcript evaluation data.
        
        Returns:
            S3 bucket for transcript evaluation storage
        """
        bucket = s3.Bucket(
            self,
            "TranscriptEvaluationsBucket",
            bucket_name=f"a360-{self.environment_name.value_as_string}-transcript-evaluations",
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
            ]
        )

        return bucket

    def _create_frontend_bucket(self) -> s3.Bucket:
        """Create S3 bucket for hosting React frontend.
        
        Returns:
            S3 bucket for frontend hosting
        """
        frontend_bucket = s3.Bucket(
            self,
            "FrontendBucket",
            bucket_name=f"a360-{self.environment_name.value_as_string}-transcription-evaluator-frontend",
            website_index_document="index.html",
            website_error_document="index.html",  # SPA routing fallback
            public_read_access=True,  # Enable public read for static website
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=False,
                ignore_public_acls=False,
                block_public_policy=False,
                restrict_public_buckets=False
            ),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False
        )

        return frontend_bucket

    def _create_cognito_user_pool(self) -> tuple[cognito.UserPool, cognito.UserPoolClient, cognito.CfnIdentityPool]:
        """Create Cognito User Pool and Identity Pool for authentication.
        
        Returns:
            Tuple of User Pool, User Pool Client, and Identity Pool
        """
        # Create User Pool
        user_pool = cognito.UserPool(
            self,
            "TranscriptionEvaluatorUserPool",
            user_pool_name=f"a360-{self.environment_name.value_as_string}-transcription-evaluator-users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create User Pool Client (without OAuth for now due to HTTP restriction)
        user_pool_client = cognito.UserPoolClient(
            self,
            "TranscriptionEvaluatorUserPoolClient", 
            user_pool=user_pool,
            user_pool_client_name=f"a360-{self.environment_name.value_as_string}-transcription-evaluator-client",
            generate_secret=False,  # Required for browser-based apps
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                admin_user_password=True
            ),
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO],
            refresh_token_validity=Duration.days(30),
            id_token_validity=Duration.hours(24),
            access_token_validity=Duration.hours(24)
        )

        # Create Identity Pool (without roles yet)
        identity_pool = cognito.CfnIdentityPool(
            self,
            "TranscriptionEvaluatorIdentityPool",
            identity_pool_name=f"a360-{self.environment_name.value_as_string}-transcription-evaluator-identity",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=user_pool_client.user_pool_client_id,
                    provider_name=user_pool.user_pool_provider_name
                )
            ]
        )

        return user_pool, user_pool_client, identity_pool

    def _setup_cognito_identity_pool(self) -> None:
        """Setup Cognito Identity Pool roles after API Gateway is created."""
        # Create authenticated role for Identity Pool
        authenticated_role = iam.Role(
            self,
            "TranscriptionEvaluatorAuthenticatedRole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                {
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": self.cognito_identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    }
                },
                "sts:AssumeRoleWithWebIdentity"
            ),
            description="Role for authenticated users in Transcription Evaluator"
        )

        # Add permissions to access the API Gateway
        authenticated_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["execute-api:Invoke"],
            resources=[
                f"arn:aws:execute-api:{self.region}:{self.account}:{self.api_gateway.api_id}/*/*/*"
            ]
        ))

        # Attach role to Identity Pool
        cognito.CfnIdentityPoolRoleAttachment(
            self,
            "TranscriptionEvaluatorIdentityPoolRoleAttachment",
            identity_pool_id=self.cognito_identity_pool.ref,
            roles={
                "authenticated": authenticated_role.role_arn
            }
        )

    def _create_security_groups(self) -> tuple[ec2.SecurityGroup, ec2.SecurityGroup]:
        """Create security groups for the service.
        
        Returns:
            Tuple of (task security group, ALB security group)
        """
        task_security_group = ec2.SecurityGroup(
            self,
            "TranscriptionEvaluatorTaskSG",
            vpc=self.vpc,
            description="Security group for transcription evaluator tasks",
            allow_all_outbound=True,
        )

        # Create ALB security group that allows VPC Link access
        alb_security_group = ec2.SecurityGroup(
            self,
            "TranscriptionEvaluatorALBSG",
            vpc=self.vpc,
            description="Security group for transcription evaluator ALB",
            allow_all_outbound=False,
        )

        # ALB can reach tasks on port 8000
        task_security_group.add_ingress_rule(
            peer=alb_security_group,
            connection=ec2.Port.tcp(8000),
            description="Allow ALB to reach tasks"
        )

        # ALB can reach internet for health checks only - no public internet access
        alb_security_group.add_egress_rule(
            peer=task_security_group,
            connection=ec2.Port.tcp(8000),
            description="ALB to tasks"
        )
        
        # Allow VPC Link to reach ALB (allow inbound from VPC CIDR)
        alb_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(80),
            description="Allow VPC Link to reach ALB"
        )
        

        return task_security_group, alb_security_group

    def _create_task_role(self) -> iam.Role:
        """Create IAM role for ECS tasks with minimal permissions.
        
        Returns:
            IAM role for ECS task execution
        """
        task_role = iam.Role(
            self,
            "TranscriptionEvaluatorTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="Role for transcription evaluator ECS tasks",
        )

        # S3 access for transcript data (restricted to specific bucket)
        task_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            resources=[
                self.s3_bucket.bucket_arn,
                f"{self.s3_bucket.bucket_arn}/*"
            ]
        ))

        # CloudWatch Logs permissions
        task_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream", 
                "logs:PutLogEvents"
            ],
            resources=[
                f"arn:aws:logs:{self.region}:{self.account}:log-group:/transcription-evaluator/*"
            ]
        ))

        return task_role

    def _create_fargate_service(self) -> ecs_patterns.ApplicationLoadBalancedFargateService:
        """Create ECS Fargate service with Application Load Balancer.
        
        Returns:
            ECS Fargate service with internal ALB
        """
        # Create ECS cluster
        cluster = ecs.Cluster(
            self,
            "TranscriptionEvaluatorCluster",
            vpc=self.vpc,
            cluster_name="transcription-evaluator"
        )

        # Create log group
        log_group = logs.LogGroup(
            self,
            "TranscriptionEvaluatorLogGroup",
            log_group_name="/transcription-evaluator/service",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create task definition with ARM64 runtime platform
        task_definition = ecs.FargateTaskDefinition(
            self,
            "TranscriptionEvaluatorTaskDef",
            memory_limit_mib=2048,
            cpu=1024,
            task_role=self.task_role,
            runtime_platform=ecs.RuntimePlatform(
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
                cpu_architecture=ecs.CpuArchitecture.ARM64
            ),
        )

        # Build Docker image from source code for ARM64 platform
        docker_image = ecs.ContainerImage.from_asset(
            "../",  # Build from the parent directory (transcription_evaluator root)
            file="Dockerfile",
            platform=ecr_assets.Platform.LINUX_ARM64
        )

        # Add container to task definition
        container = task_definition.add_container(
            "TranscriptionEvaluatorContainer",
            image=docker_image,
            logging=ecs.AwsLogDriver(
                stream_prefix="transcription-evaluator",
                log_group=log_group
            ),
            environment={
                "AWS_DEFAULT_REGION": self.region,
                "STORAGE_BACKEND": "s3",
                "S3_BUCKET_NAME": self.s3_bucket.bucket_name
            },
            memory_limit_mib=2048,
        )

        container.add_port_mappings(
            ecs.PortMapping(
                container_port=8000,
                protocol=ecs.Protocol.TCP
            )
        )

        # Create Fargate service with internal ALB
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "TranscriptionEvaluatorService",
            cluster=cluster,
            task_definition=task_definition,
            public_load_balancer=False,  # Internal ALB only
            listener_port=80,
            desired_count=1,
            task_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            service_name="transcription-evaluator",
        )

        # Configure health check
        fargate_service.target_group.configure_health_check(
            path="/health",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3
        )

        # Replace the default ALB security group with our configured one
        fargate_service.load_balancer.add_security_group(self.alb_security_group)
        
        # Apply task security group to service
        fargate_service.service.connections.add_security_group(self.task_security_group)

        return fargate_service

    def _create_api_gateway(self) -> apigateway.HttpApi:
        """Create HTTP API Gateway for public access to internal service.
        
        Returns:
            API Gateway HTTP API
        """
        # Create VPC Link for HTTP API (supports ALB)
        vpc_link = apigateway.VpcLink(
            self,
            "TranscriptionEvaluatorVpcLink", 
            vpc=self.vpc,
            subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            )
        )

        # Create HTTP API Gateway (supports ALB integration)
        api = apigateway.HttpApi(
            self,
            "TranscriptionEvaluatorAPI",
            api_name="Transcription Evaluator API",
            description="Public API for Transcription Evaluator service",
            cors_preflight=apigateway.CorsPreflightOptions(
                allow_origins=["*"],  # Will be restricted to CloudFront in production
                allow_methods=[apigateway.CorsHttpMethod.GET, apigateway.CorsHttpMethod.POST, apigateway.CorsHttpMethod.OPTIONS],
                allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key"],
                max_age=Duration.days(10)
            )
        )

        # Create ALB integration
        alb_integration = integrations.HttpAlbIntegration(
            "ALBIntegration",
            listener=self.fargate_service.listener,
            vpc_link=vpc_link
        )

        # Add routes that forward to root paths on the ALB
        api.add_routes(
            path="/{proxy+}",
            methods=[apigateway.HttpMethod.ANY],
            integration=alb_integration
        )
        
        # Add specific health route
        api.add_routes(
            path="/health",
            methods=[apigateway.HttpMethod.GET],
            integration=alb_integration
        )

        return api

    def _create_cloudfront_distribution(self) -> cloudfront.Distribution:
        """Create CloudFront distribution for frontend and API.
        
        Returns:
            CloudFront distribution
        """
        # Create Origin Access Identity for S3
        origin_access_identity = cloudfront.OriginAccessIdentity(
            self,
            "FrontendOAI",
            comment="OAI for Transcription Evaluator frontend"
        )

        # Grant read access to CloudFront
        self.frontend_bucket.grant_read(origin_access_identity)

        # Create CloudFront distribution
        distribution = cloudfront.Distribution(
            self,
            "TranscriptionEvaluatorDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    bucket=self.frontend_bucket,
                    origin_access_identity=origin_access_identity
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                compress=True
            ),
            additional_behaviors={
                "/api/*": cloudfront.BehaviorOptions(
                    origin=origins.HttpOrigin(
                        domain_name=self.api_gateway.api_endpoint.replace("https://", "").split("/")[0],
                        origin_id="api-gateway-origin",
                        custom_headers={
                            "User-Agent": "CloudFront"
                        }
                    ),
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                    origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN
                )
            },
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0)
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0)
                )
            ],
            comment="CloudFront distribution for Transcription Evaluator"
        )

        return distribution

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for important resources."""
        CfnOutput(
            self,
            "ServiceURL",
            value=f"http://{self.fargate_service.load_balancer.load_balancer_dns_name}",
            description="Internal URL for transcription evaluator service"
        )

        CfnOutput(
            self,
            "ContainerImageInfo",
            value="Container image built and deployed via CDK asset bundling",
            description="Container image deployment info"
        )

        CfnOutput(
            self,
            "ClusterName",
            value=self.fargate_service.cluster.cluster_name,
            description="ECS cluster name"
        )

        CfnOutput(
            self,
            "ServiceName",
            value=self.fargate_service.service.service_name,
            description="ECS service name"
        )

        CfnOutput(
            self,
            "S3BucketName",
            value=self.s3_bucket.bucket_name,
            description="S3 bucket name for transcript evaluations"
        )

        CfnOutput(
            self,
            "S3BucketArn",
            value=self.s3_bucket.bucket_arn,
            description="S3 bucket ARN for transcript evaluations"
        )

        CfnOutput(
            self,
            "FrontendBucketName",
            value=self.frontend_bucket.bucket_name,
            description="S3 bucket name for frontend hosting"
        )

        CfnOutput(
            self,
            "FrontendBucketArn",
            value=self.frontend_bucket.bucket_arn,
            description="S3 bucket ARN for frontend hosting"
        )

        CfnOutput(
            self,
            "ApiGatewayUrl",
            value=self.api_gateway.api_endpoint,
            description="API Gateway URL for public API access"
        )

        CfnOutput(
            self,
            "ApiGatewayId",
            value=self.api_gateway.api_id,
            description="API Gateway HTTP API ID"
        )

        # Temporarily commented out CloudFront outputs
        # CfnOutput(
        #     self,
        #     "CloudFrontDistributionId",
        #     value=self.cloudfront.distribution_id,
        #     description="CloudFront distribution ID"
        # )

        # CfnOutput(
        #     self,
        #     "CloudFrontDomainName",
        #     value=self.cloudfront.distribution_domain_name,
        #     description="CloudFront distribution domain name"
        # )

        # CfnOutput(
        #     self,
        #     "WebsiteURL",
        #     value=f"https://{self.cloudfront.distribution_domain_name}",
        #     description="Frontend website URL via CloudFront"
        # )

        CfnOutput(
            self,
            "WebsiteURL",
            value=f"http://{self.frontend_bucket.bucket_website_domain_name}",
            description="Frontend website URL via S3 (temporary)"
        )

        CfnOutput(
            self,
            "CognitoUserPoolId",
            value=self.cognito_user_pool.user_pool_id,
            description="Cognito User Pool ID"
        )

        CfnOutput(
            self,
            "CognitoUserPoolClientId",
            value=self.cognito_user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID"
        )

        CfnOutput(
            self,
            "CognitoIdentityPoolId",
            value=self.cognito_identity_pool.ref,
            description="Cognito Identity Pool ID"
        )

        CfnOutput(
            self,
            "CognitoRegion",
            value=self.region,
            description="AWS region for Cognito"
        )