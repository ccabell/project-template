"""Enhanced CDK stack for Cognito RBAC and Verified Permissions.

This stack creates AWS managed authentication and authorization infrastructure
for the transcription evaluator service with:
    • AWS Cognito User Pool with role-based groups
    • Amazon Verified Permissions with Cedar policies
    • API Gateway with Cognito authorizers
    • Lambda functions for API handling
    • PostgreSQL RDS for data persistence
    • CloudWatch structured logging and monitoring
"""

import json
from aws_cdk import CfnOutput, CfnParameter, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_secretsmanager as secrets
from constructs import Construct


class CognitoRBACStack(Stack):
    """Stack for AWS-first RBAC using Cognito and Verified Permissions.
    
    Creates comprehensive authentication and authorization infrastructure
    using AWS managed services instead of custom implementations.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """Initialize the Cognito RBAC stack.
        
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

        # Core infrastructure
        self.vpc = self._create_vpc()
        self.database_cluster = self._create_database()
        self.s3_bucket = self._create_s3_bucket()
        
        # Authentication & Authorization
        self.user_pool, self.user_pool_client, self.identity_pool = self._create_cognito_infrastructure()
        self.user_groups = self._create_cognito_groups()
        self.verified_permissions_policy_store = self._create_verified_permissions()
        
        # API Infrastructure
        self.api_lambda = self._create_api_lambda()
        self.api_gateway = self._create_api_gateway()
        
        # Frontend hosting
        self.frontend_bucket = self._create_frontend_bucket()
        
        # Setup roles and permissions
        self._setup_cognito_identity_pool()
        self._create_outputs()

    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC for database and Lambda functions.
        
        Returns:
            VPC instance with private subnets
        """
        vpc = ec2.Vpc(
            self,
            "TranscriptionEvaluatorVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.1.0.0/16"),
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
            ],
            nat_gateways=1,  # Single NAT Gateway for cost optimization
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

        # S3 Gateway Endpoint (free)
        vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)]
        )

        return vpc

    def _create_database(self) -> rds.ServerlessCluster:
        """Create Aurora Serverless PostgreSQL cluster.
        
        Returns:
            Aurora Serverless cluster for application data
        """
        # Create database subnet group
        subnet_group = rds.SubnetGroup(
            self,
            "DatabaseSubnetGroup",
            description="Subnet group for transcription evaluator database",
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            )
        )

        # Database security group
        db_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=self.vpc,
            description="Security group for Aurora database",
            allow_all_outbound=False,
        )

        # Database credentials
        db_credentials = rds.Credentials.from_generated_secret(
            username="transcription_admin",
            secret_name=f"transcription-evaluator-{self.environment_name.value_as_string}-db-credentials",
            exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/\"\\@"
        )

        # Aurora Serverless v2 PostgreSQL  
        cluster = rds.DatabaseCluster(
            self,
            "TranscriptionDatabase",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_16_6
            ),
            vpc=self.vpc,
            credentials=db_credentials,
            cluster_identifier=f"transcription-evaluator-{self.environment_name.value_as_string}",
            default_database_name="transcription_evaluator",
            security_groups=[db_security_group],
            subnet_group=subnet_group,
            writer=rds.ClusterInstance.serverless_v2(
                "writer",
                scale_with_writer=True
            ),
            serverless_v2_min_capacity=0.5,
            serverless_v2_max_capacity=2,
            backup=rds.BackupProps(
                retention=Duration.days(7)
            ),
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=False
        )

        return cluster

    def _create_s3_bucket(self) -> s3.Bucket:
        """Create S3 bucket for application data storage.
        
        Returns:
            S3 bucket for transcript and audio files
        """
        bucket = s3.Bucket(
            self,
            "TranscriptionDataBucket",
            bucket_name=f"a360-{self.environment_name.value_as_string}-transcription-data",
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

    def _create_cognito_infrastructure(self) -> tuple[cognito.UserPool, cognito.UserPoolClient, cognito.CfnIdentityPool]:
        """Create comprehensive Cognito User Pool infrastructure.
        
        Returns:
            Tuple of User Pool, User Pool Client, and Identity Pool
        """
        # Create User Pool with comprehensive configuration
        user_pool = cognito.UserPool(
            self,
            "TranscriptionEvaluatorUserPool",
            user_pool_name=f"a360-{self.environment_name.value_as_string}-transcription-evaluator-users",
            self_sign_up_enabled=False,  # Admin-only user creation for RBAC
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=True
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(
                sms=False,
                otp=True
            ),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                given_name=cognito.StandardAttribute(required=True, mutable=True),
                family_name=cognito.StandardAttribute(required=True, mutable=True),
            ),
            custom_attributes={
                "department": cognito.StringAttribute(mutable=True),
                "role_level": cognito.NumberAttribute(mutable=True, min=1, max=4)
            },
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create User Pool Client with enhanced security
        user_pool_client = cognito.UserPoolClient(
            self,
            "TranscriptionEvaluatorUserPoolClient", 
            user_pool=user_pool,
            user_pool_client_name=f"a360-{self.environment_name.value_as_string}-transcription-evaluator-client",
            generate_secret=False,  # Required for browser-based applications
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                admin_user_password=True
            ),
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO],
            refresh_token_validity=Duration.days(30),
            id_token_validity=Duration.hours(1),  # Shorter for security
            access_token_validity=Duration.hours(1),
            prevent_user_existence_errors=True  # Security best practice
        )

        # Create Identity Pool for temporary AWS credentials
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

    def _create_cognito_groups(self) -> dict[str, cognito.CfnUserPoolGroup]:
        """Create Cognito groups for role-based access control.
        
        Returns:
            Dictionary of role names to Cognito groups
        """
        groups = {}
        
        # Define role hierarchy and permissions
        role_definitions = {
            "admin": {
                "description": "System administrators with full access",
                "precedence": 10
            },
            "evaluator": {
                "description": "Evaluators who assess transcription quality",
                "precedence": 20
            },
            "reviewer": {
                "description": "Reviewers who validate evaluations",
                "precedence": 30
            },
            "voice_actor": {
                "description": "Voice actors who create audio content",
                "precedence": 40
            }
        }

        for role_name, config in role_definitions.items():
            group = cognito.CfnUserPoolGroup(
                self,
                f"{role_name.title()}Group",
                user_pool_id=self.user_pool.user_pool_id,
                group_name=role_name,
                description=config["description"],
                precedence=config["precedence"]
            )
            groups[role_name] = group

        return groups

    def _create_verified_permissions(self) -> str:
        """Create Amazon Verified Permissions policy store with Cedar policies.
        
        Returns:
            Policy store ID for Verified Permissions
        """
        # Create IAM role for Verified Permissions
        avp_role = iam.Role(
            self,
            "VerifiedPermissionsRole",
            assumed_by=iam.ServicePrincipal("verifiedpermissions.amazonaws.com"),
            description="Service role for Amazon Verified Permissions"
        )

        # Create policy store using CDK's L1 construct
        from aws_cdk import aws_verifiedpermissions as avp
        
        policy_store = avp.CfnPolicyStore(
            self,
            "TranscriptionEvaluatorPolicyStore",
            schema=avp.CfnPolicyStore.SchemaDefinitionProperty(
                cedar_json=json.dumps({
                    "TranscriptionEvaluator": {
                        "entityTypes": {
                            "User": {
                                "memberOfTypes": ["Group"]
                            },
                            "Group": {},
                            "Script": {
                                "attributes": {
                                    "owner": {"type": "Entity", "name": "User"},
                                    "status": {"type": "String"},
                                    "created_date": {"type": "String"}
                                }
                            },
                            "Evaluation": {
                                "attributes": {
                                    "evaluator": {"type": "Entity", "name": "User"},
                                    "script": {"type": "Entity", "name": "Script"},
                                    "status": {"type": "String"}
                                }
                            }
                        },
                        "actions": {
                            "CreateScript": {
                                "appliesTo": {
                                    "resourceTypes": ["Script"],
                                    "principalTypes": ["User"]
                                }
                            },
                            "ViewScript": {
                                "appliesTo": {
                                    "resourceTypes": ["Script"],
                                    "principalTypes": ["User"]
                                }
                            },
                            "UpdateScript": {
                                "appliesTo": {
                                    "resourceTypes": ["Script"],
                                    "principalTypes": ["User"]
                                }
                            },
                            "DeleteScript": {
                                "appliesTo": {
                                    "resourceTypes": ["Script"],
                                    "principalTypes": ["User"]
                                }
                            },
                            "AssignScript": {
                                "appliesTo": {
                                    "resourceTypes": ["Script"],
                                    "principalTypes": ["User"]
                                }
                            },
                            "CreateEvaluation": {
                                "appliesTo": {
                                    "resourceTypes": ["Evaluation"],
                                    "principalTypes": ["User"]
                                }
                            },
                            "ViewEvaluation": {
                                "appliesTo": {
                                    "resourceTypes": ["Evaluation"],
                                    "principalTypes": ["User"]
                                }
                            },
                            "UpdateEvaluation": {
                                "appliesTo": {
                                    "resourceTypes": ["Evaluation"],
                                    "principalTypes": ["User"]
                                }
                            }
                        }
                    }
                })
            ),
            validation_settings=avp.CfnPolicyStore.ValidationSettingsProperty(
                mode="STRICT"
            )
        )

        # Create Cedar policies for each role
        self._create_cedar_policies(policy_store.attr_policy_store_id)

        return policy_store.attr_policy_store_id

    def _create_cedar_policies(self, policy_store_id: str) -> None:
        """Create Cedar policies for role-based permissions.
        
        Args:
            policy_store_id: Verified Permissions policy store ID
        """
        from aws_cdk import aws_verifiedpermissions as avp
        
        # Admin policy - full access
        avp.CfnPolicy(
            self,
            "AdminPolicy",
            policy_store_id=policy_store_id,
            definition=avp.CfnPolicy.PolicyDefinitionProperty(
                static=avp.CfnPolicy.StaticPolicyDefinitionProperty(
                    statement='permit(principal in Group::"admin", action, resource);',
                    description="Administrators have full access to all resources"
                )
            )
        )

        # Evaluator policy - can create evaluations and view scripts
        avp.CfnPolicy(
            self,
            "EvaluatorPolicy",
            policy_store_id=policy_store_id,
            definition=avp.CfnPolicy.PolicyDefinitionProperty(
                static=avp.CfnPolicy.StaticPolicyDefinitionProperty(
                    statement='''
                    permit(principal in Group::"evaluator", action in [Action::"ViewScript", Action::"CreateEvaluation", Action::"ViewEvaluation", Action::"UpdateEvaluation"], resource)
                    when { resource has owner && principal == resource.owner };
                    ''',
                    description="Evaluators can view scripts and manage their evaluations"
                )
            )
        )

        # Reviewer policy - can view and approve evaluations
        avp.CfnPolicy(
            self,
            "ReviewerPolicy",
            policy_store_id=policy_store_id,
            definition=avp.CfnPolicy.PolicyDefinitionProperty(
                static=avp.CfnPolicy.StaticPolicyDefinitionProperty(
                    statement='permit(principal in Group::"reviewer", action in [Action::"ViewScript", Action::"ViewEvaluation"], resource);',
                    description="Reviewers can view scripts and evaluations"
                )
            )
        )

        # Voice Actor policy - can create and manage scripts
        avp.CfnPolicy(
            self,
            "VoiceActorPolicy",
            policy_store_id=policy_store_id,
            definition=avp.CfnPolicy.PolicyDefinitionProperty(
                static=avp.CfnPolicy.StaticPolicyDefinitionProperty(
                    statement='''
                    permit(principal in Group::"voice_actor", action in [Action::"CreateScript", Action::"ViewScript", Action::"UpdateScript"], resource)
                    when { resource has owner && principal == resource.owner };
                    ''',
                    description="Voice actors can create and manage their own scripts"
                )
            )
        )

    def _create_api_lambda(self) -> lambda_.Function:
        """Create Lambda function for API handling.
        
        Returns:
            Lambda function for API Gateway integration
        """
        # Lambda execution role
        lambda_role = iam.Role(
            self,
            "ApiLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaVPCAccessExecutionRole")
            ]
        )

        # Add permissions for AWS services
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "cognito-idp:AdminGetUser",
                "cognito-idp:AdminListGroupsForUser",
                "cognito-idp:AdminAddUserToGroup",
                "cognito-idp:AdminRemoveUserFromGroup",
                "cognito-idp:AdminCreateUser",
                "cognito-idp:AdminDeleteUser",
                "cognito-idp:ListUsers"
            ],
            resources=[self.user_pool.user_pool_arn]
        ))

        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "verifiedpermissions:IsAuthorized",
                "verifiedpermissions:BatchIsAuthorized"
            ],
            resources=[f"arn:aws:verifiedpermissions:{self.region}:{self.account}:policy-store/{self.verified_permissions_policy_store}"]
        ))

        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "rds-data:ExecuteStatement",
                "rds-data:BatchExecuteStatement",
                "rds-data:BeginTransaction",
                "rds-data:CommitTransaction",
                "rds-data:RollbackTransaction"
            ],
            resources=[self.database_cluster.cluster_arn]
        ))

        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret"
            ],
            resources=[self.database_cluster.secret.secret_arn]
        ))

        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            resources=[
                self.s3_bucket.bucket_arn,
                f"{self.s3_bucket.bucket_arn}/*"
            ]
        ))

        # Lambda security group
        lambda_sg = ec2.SecurityGroup(
            self,
            "ApiLambdaSecurityGroup",
            vpc=self.vpc,
            description="Security group for API Lambda function",
            allow_all_outbound=True
        )

        # Allow Lambda to access database
        self.database_cluster.connections.allow_from(
            lambda_sg,
            ec2.Port.tcp(5432),
            "Allow Lambda to access Aurora"
        )

        # Create log group for API Lambda
        api_lambda_log_group = logs.LogGroup(
            self,
            "ApiLambdaFunctionLogGroup",
            log_group_name="/aws/lambda/ApiLambdaFunction",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create Lambda function
        api_lambda = lambda_.Function(
            self,
            "ApiLambdaFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler="index.handler",
            code=lambda_.Code.from_asset("../backend/lambda_functions/rbac_api_handler"),
            role=lambda_role,
            log_group=api_lambda_log_group,
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[lambda_sg],
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "COGNITO_USER_POOL_ID": self.user_pool.user_pool_id,
                "COGNITO_CLIENT_ID": self.user_pool_client.user_pool_client_id,
                "VERIFIED_PERMISSIONS_POLICY_STORE_ID": self.verified_permissions_policy_store,
                "DATABASE_CLUSTER_ARN": self.database_cluster.cluster_arn,
                "DATABASE_SECRET_ARN": self.database_cluster.secret.secret_arn,
                "S3_BUCKET_NAME": self.s3_bucket.bucket_name
            },
        )

        return api_lambda

    def _create_api_gateway(self) -> apigw.RestApi:
        """Create API Gateway with Cognito authorizer.
        
        Returns:
            API Gateway REST API
        """
        # Create Cognito authorizer
        cognito_authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            cognito_user_pools=[self.user_pool],
            authorizer_name="TranscriptionEvaluatorAuthorizer",
            identity_source="method.request.header.Authorization"
        )

        # Create API Gateway
        api = apigw.RestApi(
            self,
            "TranscriptionEvaluatorAPI",
            rest_api_name="Transcription Evaluator API",
            description="AWS-first RBAC API for Transcription Evaluator",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "X-Amz-Date", 
                    "Authorization",
                    "X-Api-Key",
                    "X-Amz-Security-Token"
                ]
            ),
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                logging_level=apigw.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True
            )
        )

        # Lambda integration
        lambda_integration = apigw.LambdaIntegration(
            self.api_lambda,
            proxy=True,
            integration_responses=[
                apigw.IntegrationResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": "'*'"
                    }
                )
            ]
        )

        # Create API resources
        api_resource = api.root.add_resource("api")
        
        # Health endpoint (no auth required)
        health_resource = api_resource.add_resource("health")
        health_resource.add_method(
            "GET",
            lambda_integration,
            method_responses=[
                apigw.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ]
        )

        # Protected API endpoints
        protected_resource = api_resource.add_resource("{proxy+}")
        protected_resource.add_method(
            "ANY",
            lambda_integration,
            authorizer=cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
            method_responses=[
                apigw.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True
                    }
                )
            ]
        )

        return api

    def _create_frontend_bucket(self) -> s3.Bucket:
        """Create S3 bucket for React frontend hosting.
        
        Returns:
            S3 bucket configured for static website hosting
        """
        frontend_bucket = s3.Bucket(
            self,
            "FrontendBucket",
            bucket_name=f"a360-{self.environment_name.value_as_string}-transcription-evaluator-frontend",
            website_index_document="index.html",
            website_error_document="index.html",  # SPA routing fallback
            public_read_access=True,
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

    def _setup_cognito_identity_pool(self) -> None:
        """Setup Cognito Identity Pool roles for temporary AWS credentials."""
        # Create authenticated role
        authenticated_role = iam.Role(
            self,
            "TranscriptionEvaluatorAuthenticatedRole",
            assumed_by=iam.FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                {
                    "StringEquals": {
                        "cognito-identity.amazonaws.com:aud": self.identity_pool.ref
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated"
                    }
                },
                "sts:AssumeRoleWithWebIdentity"
            ),
            description="Role for authenticated users in Transcription Evaluator"
        )

        # Add API Gateway invoke permissions
        authenticated_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["execute-api:Invoke"],
            resources=[f"{self.api_gateway.arn_for_execute_api()}/*"]
        ))

        # Add S3 permissions for authenticated users
        authenticated_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "s3:GetObject",
                "s3:PutObject"
            ],
            resources=[f"{self.s3_bucket.bucket_arn}/users/${{cognito-identity.amazonaws.com:sub}}/*"]
        ))

        # Attach role to Identity Pool
        cognito.CfnIdentityPoolRoleAttachment(
            self,
            "TranscriptionEvaluatorIdentityPoolRoleAttachment",
            identity_pool_id=self.identity_pool.ref,
            roles={
                "authenticated": authenticated_role.role_arn
            }
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for important resources."""
        # API Gateway outputs
        CfnOutput(
            self,
            "ApiGatewayUrl",
            value=self.api_gateway.url,
            description="API Gateway URL for frontend integration"
        )

        CfnOutput(
            self,
            "ApiGatewayId",
            value=self.api_gateway.rest_api_id,
            description="API Gateway REST API ID"
        )

        # Cognito outputs
        CfnOutput(
            self,
            "CognitoUserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID"
        )

        CfnOutput(
            self,
            "CognitoUserPoolClientId", 
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID"
        )

        CfnOutput(
            self,
            "CognitoIdentityPoolId",
            value=self.identity_pool.ref,
            description="Cognito Identity Pool ID"
        )

        CfnOutput(
            self,
            "CognitoRegion",
            value=self.region,
            description="AWS region for Cognito services"
        )

        # Verified Permissions outputs
        CfnOutput(
            self,
            "VerifiedPermissionsPolicyStoreId",
            value=self.verified_permissions_policy_store,
            description="Amazon Verified Permissions Policy Store ID"
        )

        # Database outputs
        CfnOutput(
            self,
            "DatabaseClusterArn",
            value=self.database_cluster.cluster_arn,
            description="Aurora PostgreSQL cluster ARN"
        )

        CfnOutput(
            self,
            "DatabaseSecretArn",
            value=self.database_cluster.secret.secret_arn,
            description="Database credentials secret ARN"
        )

        # Storage outputs
        CfnOutput(
            self,
            "S3BucketName",
            value=self.s3_bucket.bucket_name,
            description="S3 bucket for application data"
        )

        CfnOutput(
            self,
            "FrontendBucketName",
            value=self.frontend_bucket.bucket_name,
            description="S3 bucket for frontend hosting"
        )

        CfnOutput(
            self,
            "FrontendWebsiteURL",
            value=f"http://{self.frontend_bucket.bucket_website_domain_name}",
            description="Frontend website URL"
        )

        # Lambda outputs
        CfnOutput(
            self,
            "ApiLambdaFunctionName",
            value=self.api_lambda.function_name,
            description="API Lambda function name"
        )

        CfnOutput(
            self,
            "ApiLambdaFunctionArn",
            value=self.api_lambda.function_arn,
            description="API Lambda function ARN"
        )