"""API stack for A360 Transcription Service Evaluator.

This stack creates API Gateway with Cognito authorizers and integrations
with the ECS service and Lambda functions following AWS best practices.
"""

import aws_cdk as cdk
from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from constructs import Construct
from custom_constructs.powertools_lambda_construct import PowertoolsLambdaConstruct


class ApiStack(cdk.NestedStack):
    """API Gateway infrastructure stack."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_name: str,
        stage: str,
        user_pool: cognito.UserPool,
        user_pool_client: cognito.UserPoolClient,
        database_cluster: rds.DatabaseCluster,
        application_bucket: s3.Bucket,
        transcription_bucket: s3.Bucket,
        session_table: dynamodb.Table,
        jobs_table: dynamodb.Table,
        medical_brands_table: dynamodb.Table,
        medical_terms_table: dynamodb.Table,
        data_encryption_key: kms.Key,
        cloudfront_url: str = None,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.app_name = app_name
        self.stage = stage
        self.user_pool = user_pool
        self.user_pool_client = user_pool_client
        self.database_cluster = database_cluster
        self.application_bucket = application_bucket
        self.transcription_bucket = transcription_bucket
        self.session_table = session_table
        self.jobs_table = jobs_table
        self.medical_brands_table = medical_brands_table
        self.medical_terms_table = medical_terms_table
        self.data_encryption_key = data_encryption_key
        self.cloudfront_url = cloudfront_url

        # Create API Gateway
        self.api_gateway = self._create_api_gateway()
        
        # Create Lambda function for API handling
        self.api_lambda = self._create_api_lambda()
        
        # Create Cognito authorizer and API routes
        self.cognito_authorizer = self._create_cognito_authorizer()
        self._create_api_routes()

    def _get_cors_allowed_origins(self) -> list:
        """Get CORS allowed origins based on stage and cloudfront URL."""
        origins = ["http://localhost:3000", "http://localhost:8000"]
        
        if self.cloudfront_url:
            origins.append(self.cloudfront_url)
        
        if self.stage == "dev":
            # For dev, allow all origins for testing
            return ["*"]
        else:
            # For production, use specific origins only
            return origins
    
    def _get_cloudfront_origin_header(self) -> str:
        """Get the CloudFront origin header value for API Gateway responses."""
        if self.cloudfront_url:
            return f"'{self.cloudfront_url}'"
        elif self.stage == "dev":
            return "'*'"
        else:
            return "'https://your-production-domain.com'"


    def _create_api_gateway(self) -> apigateway.RestApi:
        """Create API Gateway REST API."""

        logs.LogGroup(
            self,
            "ApiGatewayLogGroup",
            log_group_name=f"/aws/apigateway/{self.app_name}-{self.stage}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.RETAIN if self.stage == "prod" else RemovalPolicy.DESTROY,
        )

        api = apigateway.RestApi(
            self,
            "ApiGateway",
            rest_api_name=f"{self.app_name}-{self.stage}-api",
            description=f"API Gateway for {self.app_name} {self.stage} environment",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS
                if self.stage == "dev"
                else self._get_cors_allowed_origins(),
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "X-Amz-Date",
                    "Authorization",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                ],
                allow_credentials=True,
            ),
            cloud_watch_role=True,
            deploy=True,
            deploy_options=apigateway.StageOptions(
                stage_name=self.stage,
                throttling_rate_limit=1000,
                throttling_burst_limit=2000,
            ),
            binary_media_types=[
                "audio/*",
                "video/*",
                "image/*",
                "application/octet-stream",
            ],
            api_key_source_type=apigateway.ApiKeySourceType.HEADER,
            endpoint_configuration=apigateway.EndpointConfiguration(
                types=[apigateway.EndpointType.REGIONAL]
            ),
        )

        cdk.Tags.of(api).add("Environment", self.stage)
        cdk.Tags.of(api).add("Application", self.app_name)

        # Add gateway responses for proper CORS handling on auth failures
        api.add_gateway_response(
            "UnauthorizedResponse",
            type=apigateway.ResponseType.UNAUTHORIZED,
            response_headers={
                "Access-Control-Allow-Origin": "'*'",
                "Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                "Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
            },
        )
        
        api.add_gateway_response(
            "AccessDeniedResponse", 
            type=apigateway.ResponseType.ACCESS_DENIED,
            response_headers={
                "Access-Control-Allow-Origin": "'*'",
                "Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                "Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
            },
        )
        
        api.add_gateway_response(
            "AuthorizerFailureResponse",
            type=apigateway.ResponseType.AUTHORIZER_FAILURE,
            response_headers={
                "Access-Control-Allow-Origin": "'*'",
                "Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                "Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
            },
        )
        
        # Add gateway response for 502 Bad Gateway errors
        api.add_gateway_response(
            "BadGatewayResponse",
            type=apigateway.ResponseType.BAD_REQUEST_BODY,
            response_headers={
                "Access-Control-Allow-Origin": "'*'",
                "Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                "Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
            },
        )
        
        # Add gateway response for integration failures (5xx errors)
        api.add_gateway_response(
            "IntegrationFailureResponse",
            type=apigateway.ResponseType.INTEGRATION_FAILURE,
            response_headers={
                "Access-Control-Allow-Origin": "'*'",
                "Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                "Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
            },
        )
        
        api.add_gateway_response(
            "DefaultResponse",
            type=apigateway.ResponseType.DEFAULT_4_XX,
            response_headers={
                "Access-Control-Allow-Origin": "'*'",
                "Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'", 
                "Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
            },
        )

        return api

    def _create_cognito_authorizer(self) -> apigateway.CognitoUserPoolsAuthorizer:
        """Create Cognito User Pools authorizer."""
        authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            cognito_user_pools=[self.user_pool],
            authorizer_name=f"{self.app_name}-{self.stage}-cognito-authorizer",
            identity_source="method.request.header.Authorization",
            results_cache_ttl=Duration.minutes(5),
        )

        return authorizer

    def _create_api_lambda(self) -> PowertoolsLambdaConstruct:
        """Create API handler Lambda function."""
        
        # Construct resource names/ARNs to avoid circular dependencies
        region = cdk.Stack.of(self).region
        account = cdk.Stack.of(self).account
        
        # Database secret ARN (follows CDK pattern)
        db_secret_arn = f"arn:aws:secretsmanager:{region}:{account}:secret:DatabaseSecret-*"
        db_cluster_arn = f"arn:aws:rds:{region}:{account}:cluster:*"
        
        # DynamoDB table names and ARNs  
        session_table_name = f"{self.app_name}-{self.stage}-sessions"
        cache_table_name = f"{self.app_name}-{self.stage}-cache"
        jobs_table_name = f"{self.app_name}-{self.stage}-jobs"
        medical_brands_table_name = f"{self.app_name}-{self.stage}-medical-brands"
        medical_terms_table_name = f"{self.app_name}-{self.stage}-medical-terms"
        session_table_arn = f"arn:aws:dynamodb:{region}:{account}:table/{session_table_name}"
        cache_table_arn = f"arn:aws:dynamodb:{region}:{account}:table/{cache_table_name}"
        jobs_table_arn = f"arn:aws:dynamodb:{region}:{account}:table/{jobs_table_name}"
        medical_brands_table_arn = f"arn:aws:dynamodb:{region}:{account}:table/{medical_brands_table_name}"
        medical_terms_table_arn = f"arn:aws:dynamodb:{region}:{account}:table/{medical_terms_table_name}"
        
        # S3 bucket names and ARNs
        app_bucket_name = f"{self.app_name.lower()}-{self.stage}-app-data-{account}"
        transcription_bucket_name = f"{self.app_name.lower()}-{self.stage}-transcriptions-{account}"
        app_bucket_arn = f"arn:aws:s3:::{app_bucket_name}"
        transcription_bucket_arn = f"arn:aws:s3:::{transcription_bucket_name}"
        
        api_lambda_construct = PowertoolsLambdaConstruct(
            self,
            "ApiHandlerLambda",
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "../backend/lambda_functions/api_handler",
                bundling=cdk.BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install . -t /asset-output && cp -au . /asset-output"
                    ]
                )
            ),
            service_name="api-handler",
            namespace="TranscriptionService",
            description="API handler Lambda for transcription service operations",
            timeout=Duration.minutes(15),
            memory_size=512,
            environment={
                "DB_SECRET_ARN": db_secret_arn,
                "DB_CLUSTER_ARN": db_cluster_arn,
                "COGNITO_USER_POOL_ID": self.user_pool.user_pool_id,
                "RECORDINGS_BUCKET": transcription_bucket_name,
                "SCRIPTS_BUCKET": app_bucket_name,
                "BRANDS_TERMS_TABLE_NAME": cache_table_name,
                "MEDICAL_BRANDS_TABLE_NAME": medical_brands_table_name,
                "MEDICAL_TERMS_TABLE_NAME": medical_terms_table_name,
                "JOBS_TABLE_NAME": f"{self.app_name}-{self.stage}-jobs",
                "DEBUG_IAM_FIX": "2025-08-25-v2",
            }
        )
        
        # Grant Lambda permissions using explicit IAM policies to avoid circular dependencies
        
        # Database secret access
        api_lambda_construct.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                resources=[db_secret_arn]
            )
        )
        
        # RDS Data API access
        api_lambda_construct.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "rds-data:BatchExecuteStatement",
                    "rds-data:BeginTransaction", 
                    "rds-data:CommitTransaction",
                    "rds-data:ExecuteStatement",
                    "rds-data:RollbackTransaction"
                ],
                resources=[db_cluster_arn]
            )
        )
        
        # S3 access
        api_lambda_construct.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket"
                ],
                resources=[
                    app_bucket_arn,
                    f"{app_bucket_arn}/*",
                    transcription_bucket_arn,
                    f"{transcription_bucket_arn}/*"
                ]
            )
        )
        
        # DynamoDB access
        api_lambda_construct.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"
                ],
                resources=[
                    session_table_arn,
                    cache_table_arn,
                    jobs_table_arn,
                    medical_brands_table_arn,
                    medical_terms_table_arn,
                    f"{jobs_table_arn}/index/*",  # Allow access to all GSIs
                    f"{medical_brands_table_arn}/index/*",
                    f"{medical_terms_table_arn}/index/*"
                ]
            )
        )
        
        # KMS permissions for DynamoDB encryption
        api_lambda_construct.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:Encrypt",
                    "kms:GenerateDataKey"
                ],
                resources=[self.data_encryption_key.key_arn]
            )
        )
        
        # Cognito User Pool access for reader assignments
        api_lambda_construct.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:ListUsers",
                    "cognito-idp:AdminListGroupsForUser",
                    "cognito-idp:AdminGetUser"
                ],
                resources=[self.user_pool.user_pool_arn]
            )
        )
        
        # Bedrock access
        api_lambda_construct.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=[
                    f"arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:*:{account}:inference-profile/*"
                ]
            )
        )
        
        # Lambda invoke for async processing (allow invoking any Lambda function)
        api_lambda_construct.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[f"arn:aws:lambda:{region}:{account}:function:*"]
            )
        )
        
        return api_lambda_construct


    def _create_api_routes(self):
        """Create Lambda-only API routes."""

        # Health check endpoint (no auth required)
        health_resource = self.api_gateway.root.add_resource("health")
        health_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorization_type=apigateway.AuthorizationType.NONE,
        )

        # Generate endpoints
        generate_resource = self.api_gateway.root.add_resource("generate")

        # Verticals endpoint (no auth required)
        verticals_resource = generate_resource.add_resource("verticals")
        verticals_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorization_type=apigateway.AuthorizationType.NONE,
        )

        # Ground truth endpoint (requires auth) - this is the key endpoint that was timing out
        ground_truth_resource = generate_resource.add_resource("ground-truth")
        ground_truth_resource.add_method(
            "POST",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Auth endpoints (public access)
        auth_resource = self.api_gateway.root.add_resource("auth")

        # Login endpoint
        login_resource = auth_resource.add_resource("login")
        login_resource.add_method(
            "POST",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorization_type=apigateway.AuthorizationType.NONE,
        )

        # Token refresh endpoint
        refresh_resource = auth_resource.add_resource("refresh")
        refresh_resource.add_method(
            "POST",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorization_type=apigateway.AuthorizationType.NONE,
        )

        # User info endpoint (requires auth)
        me_resource = auth_resource.add_resource("me")
        me_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # API endpoints for job management
        api_resource = self.api_gateway.root.add_resource("api")
        
        # Jobs endpoints (requires auth)
        jobs_resource = api_resource.add_resource("jobs")
        
        # List user jobs: GET /api/jobs
        jobs_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Get job status: GET /api/jobs/{jobId}
        job_resource = jobs_resource.add_resource("{jobId}")
        job_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Assignment endpoints (requires auth)
        assignments_resource = self.api_gateway.root.add_resource("assignments")
        
        # List user assignments: GET /assignments/my
        my_assignments_resource = assignments_resource.add_resource("my")
        my_assignments_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Create assignment: POST /assignments
        assignments_resource.add_method(
            "POST",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Get available readers: GET /assignments/readers
        readers_resource = assignments_resource.add_resource("readers")
        readers_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Assignment actions: PUT /assignments/{assignmentId}/status
        assignment_resource = assignments_resource.add_resource("{assignmentId}")
        assignment_status_resource = assignment_resource.add_resource("status")
        assignment_status_resource.add_method(
            "PUT",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Update assignment priority: PUT /assignments/{assignmentId}/priority
        assignment_priority_resource = assignment_resource.add_resource("priority")
        assignment_priority_resource.add_method(
            "PUT",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Update assignment reader: PUT /assignments/{assignmentId}/reader
        assignment_reader_resource = assignment_resource.add_resource("reader")
        assignment_reader_resource.add_method(
            "PUT",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Delete assignment: DELETE /assignments/{assignmentId}
        assignment_resource.add_method(
            "DELETE",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Get all assignments (admin only): GET /assignments/all
        all_assignments_resource = assignments_resource.add_resource("all")
        all_assignments_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Brands endpoints (requires auth)
        brands_resource = api_resource.add_resource("brands")
        
        # Get brands: GET /api/brands
        brands_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Add brand: POST /api/brands
        brands_resource.add_method(
            "POST",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Delete brand: DELETE /api/brands/{brandName}
        brand_resource = brands_resource.add_resource("{brandName}")
        brand_resource.add_method(
            "DELETE",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Terms endpoints (requires auth)
        terms_resource = api_resource.add_resource("terms")
        
        # Get terms: GET /api/terms
        terms_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Add term: POST /api/terms
        terms_resource.add_method(
            "POST",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Delete term: DELETE /api/terms/{termName}
        term_resource = terms_resource.add_resource("{termName}")
        term_resource.add_method(
            "DELETE",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # Job detail endpoints (requires auth) - direct access without /api prefix
        jobs_direct_resource = self.api_gateway.root.add_resource("jobs")
        job_detail_resource = jobs_direct_resource.add_resource("{jobId}")
        job_detail_resource.add_method(
            "GET",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )
        
        # Update job script: PUT /api/jobs/{jobId}/script
        job_script_resource = job_resource.add_resource("script")
        job_script_resource.add_method(
            "PUT",
            integration=apigateway.LambdaIntegration(
                handler=self.api_lambda.function,
                proxy=True,
                allow_test_invoke=False,
            ),
            authorizer=self.cognito_authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

    def _create_deployment(self):
        """Create API Gateway deployment."""
        deployment = apigateway.Deployment(
            self,
            "ApiDeployment",
            api=self.api_gateway,
            description=f"Deployment for {self.app_name} {self.stage}",
        )

        # Create stage
        stage = apigateway.Stage(
            self,
            "ApiStage",
            deployment=deployment,
            stage_name=self.stage,
            # Stage configuration
            throttling_rate_limit=1000,
            throttling_burst_limit=2000,
            # Logging configuration
            logging_level=apigateway.MethodLoggingLevel.INFO
            if self.stage == "prod"
            else apigateway.MethodLoggingLevel.ERROR,
            data_trace_enabled=self.stage == "dev",
            metrics_enabled=True,
            # Caching configuration
            caching_enabled=self.stage == "prod",
            cache_cluster_enabled=self.stage == "prod",
            cache_cluster_size="0.5" if self.stage == "prod" else None,
            # Variables
            variables={"environment": self.stage, "application": self.app_name},
        )

        self.api_gateway.add_usage_plan(
            "UsagePlan",
            name=f"{self.app_name}-{self.stage}-usage-plan",
            description=f"Usage plan for {self.app_name} {self.stage}",
            throttle=apigateway.ThrottleSettings(rate_limit=1000, burst_limit=2000),
            quota=apigateway.QuotaSettings(limit=10000, period=apigateway.Period.DAY),
            api_stages=[
                apigateway.UsagePlanPerApiStage(api=self.api_gateway, stage=stage)
            ],
        )
