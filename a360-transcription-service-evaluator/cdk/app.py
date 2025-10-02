"""CDK application for A360 Transcription Service Evaluator with nested stacks.

This CDK application deploys the transcription evaluator service using
nested stacks for better organization and AWS best practices.

The application creates:
    • Network stack with VPC, security groups, and endpoints
    • Auth stack with Cognito User Pool and Verified Permissions
    • Data stack with Aurora Serverless, S3, DynamoDB, and database initialization
    • Compute stack with ECS Fargate services
    • API stack with API Gateway integration
"""

import aws_cdk as cdk
from stacks.api_stack import ApiStack
from stacks.auth_stack import AuthStack
from stacks.compute_stack import ComputeStack
from stacks.data_stack import DataStack
from stacks.frontend_stack import FrontendStack
from stacks.network_stack import NetworkStack
# from custom_constructs.parameter_store_construct import ParameterStoreConstruct

app = cdk.App()

# Get configuration from CDK context or environment variables
stage = app.node.try_get_context("stage") or "dev"
account = app.node.try_get_context("account") or "471112502741"
region = app.node.try_get_context("region") or "us-east-1"

# Create environment configuration
env = cdk.Environment(
    account=account,
    region=region,
)

# Main stack that contains all nested stacks
main_stack = cdk.Stack(
    app,
    f"A360TranscriptionEvaluator-{stage}",
    env=env,
    description="A360 Transcription Service Evaluator with AWS-first RBAC architecture",
    termination_protection=False,
)

# Create nested stacks in dependency order
network_stack = NetworkStack(
    main_stack, "NetworkNestedStack", app_name="A360TranscriptionEvaluator", stage=stage
)

auth_stack = AuthStack(
    main_stack, "AuthNestedStack", app_name="A360TranscriptionEvaluator", stage=stage
)

data_stack = DataStack(
    main_stack,
    "DataNestedStack",
    app_name="A360TranscriptionEvaluator",
    stage=stage,
    vpc=network_stack.vpc,
    database_security_group=network_stack.database_security_group,
)

# TODO: Temporarily disable ComputeStack to isolate the circular dependency
# compute_stack = ComputeStack(
#     main_stack,
#     "ComputeNestedStack",
#     app_name="A360TranscriptionEvaluator",
#     stage=stage,
#     vpc=network_stack.vpc,
#     ecs_security_group=network_stack.ecs_security_group,
#     alb_security_group=network_stack.alb_security_group,
#     lambda_security_group=network_stack.lambda_security_group,
#     database_cluster=data_stack.database_cluster,
#     user_pool=auth_stack.user_pool,
#     user_pool_client=auth_stack.user_pool_client,
#     policy_store=auth_stack.policy_store,
#     application_bucket=data_stack.application_bucket,
# )

api_stack = ApiStack(
    main_stack,
    "ApiNestedStack",
    app_name="A360TranscriptionEvaluator",
    stage=stage,
    user_pool=auth_stack.user_pool,
    user_pool_client=auth_stack.user_pool_client,
    database_cluster=data_stack.database_cluster,
    application_bucket=data_stack.application_bucket,
    transcription_bucket=data_stack.transcription_bucket,
    session_table=data_stack.session_table,
    jobs_table=data_stack.jobs_table,
    medical_brands_table=data_stack.medical_brands_table,
    medical_terms_table=data_stack.medical_terms_table,
    data_encryption_key=data_stack.data_encryption_key,
)

# Get API Gateway URL for frontend configuration  
api_gateway_url = api_stack.api_gateway.url

frontend_stack = FrontendStack(
    main_stack,
    "FrontendNestedStack", 
    app_name="A360TranscriptionEvaluator",
    stage=stage,
    api_gateway_url=api_gateway_url,
)

# NOTE: ParameterStore temporarily disabled to resolve circular dependency
# Will be re-enabled after core infrastructure deploys successfully

# Stack outputs
cdk.CfnOutput(
    main_stack,
    "DatabaseEndpoint",
    value=data_stack.database_cluster.cluster_endpoint.hostname,
    description="Aurora PostgreSQL cluster endpoint",
)

cdk.CfnOutput(
    main_stack,
    "CognitoUserPoolId",
    value=auth_stack.user_pool.user_pool_id,
    description="Cognito User Pool ID for authentication",
)

cdk.CfnOutput(
    main_stack,
    "ApiGatewayUrl",
    value=api_gateway_url,
    description="API Gateway endpoint URL",
)

cdk.CfnOutput(
    main_stack,
    "FrontendUrl",
    value=frontend_stack.website_url,
    description="Frontend CloudFront distribution URL",
)

cdk.CfnOutput(
    main_stack,
    "S3BucketName",
    value=frontend_stack.website_bucket.bucket_name,
    description="S3 bucket name for frontend deployment",
)

app.synth()
