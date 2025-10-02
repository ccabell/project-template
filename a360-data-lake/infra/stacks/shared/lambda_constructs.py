"""Enhanced DRY Lambda construct with PowerTools, Bedrock, and Comprehend support.

This module provides a standardized Lambda construct that includes AWS Lambda
PowerTools, Bedrock access, Amazon Comprehend Medical permissions, and Amazon
Macie integration for consistent function deployment across the consultation
pipeline.

The construct ensures all Lambda functions follow production standards with
proper logging, metrics, tracing, and security configurations.
"""

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct


class PowertoolsLambdaConstruct(Construct):
    """Enhanced Lambda construct with PowerTools and healthcare service integrations.

    This construct provides a standardized way to deploy Lambda functions with
    AWS Lambda PowerTools pre-configured, along with necessary permissions for
    Amazon Bedrock, Comprehend Medical, Macie, and S3 operations.

    Features:
    - AWS Lambda PowerTools (Python 3.12, ARM64)
    - CloudWatch Insights integration
    - Structured logging with correlation IDs
    - Metrics and tracing enabled
    - Bedrock model access
    - Comprehend Medical permissions
    - Macie classification job access
    - S3 bucket operations
    - Least-privilege IAM policies
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        code_path: str,
        handler: str = "index.handler",
        service_name: str,
        namespace: str,
        runtime: lambda_.Runtime = lambda_.Runtime.PYTHON_3_12,
        architecture: lambda_.Architecture = lambda_.Architecture.ARM_64,
        timeout: cdk.Duration | None = None,
        memory_size: int = 512,
        environment: dict[str, str] | None = None,
        s3_buckets: list[str] | None = None,
        enable_bedrock: bool = False,
        enable_comprehend_medical: bool = False,
        enable_macie: bool = False,
        additional_policies: list[iam.PolicyStatement] | None = None,
    ) -> None:
        """Initialize the PowerTools Lambda construct.

        Args:
            scope: CDK scope for this construct.
            construct_id: Unique identifier for this construct.
            code_path: Path to Lambda function code.
            handler: Lambda handler function (default: index.handler).
            service_name: Service name for PowerTools (kebab-case).
            namespace: Namespace for PowerTools metrics.
            runtime: Lambda runtime (default: Python 3.12).
            architecture: Lambda architecture (default: ARM64).
            timeout: Function timeout (default: 5 minutes).
            memory_size: Memory allocation in MB (default: 512).
            environment: Additional environment variables.
            s3_buckets: List of S3 bucket names for access permissions.
            enable_bedrock: Enable Amazon Bedrock permissions.
            enable_comprehend_medical: Enable Comprehend Medical permissions.
            enable_macie: Enable Amazon Macie permissions.
            additional_policies: Additional IAM policy statements.
        """
        super().__init__(scope, construct_id)

        # Set defaults for mutable default arguments
        if timeout is None:
            timeout = cdk.Duration.minutes(5)

        self._service_name = service_name
        self._namespace = namespace
        self._s3_buckets = s3_buckets or []
        self._enable_bedrock = enable_bedrock
        self._enable_comprehend_medical = enable_comprehend_medical
        self._enable_macie = enable_macie
        self._additional_policies = additional_policies or []

        self._role = self._create_execution_role()

        lambda_environment = self._build_environment_variables(environment)

        self.function = lambda_.Function(
            self,
            "Function",
            runtime=runtime,
            architecture=architecture,
            handler=handler,
            code=lambda_.Code.from_asset(code_path),
            role=self._role,
            timeout=timeout,
            memory_size=memory_size,
            environment=lambda_environment,
            layers=[
                lambda_.LayerVersion.from_layer_version_arn(
                    self,
                    "PowerToolsLayer",
                    layer_version_arn=f"arn:aws:lambda:{cdk.Aws.REGION}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-arm64:18",
                ),
                lambda_.LayerVersion.from_layer_version_arn(
                    self,
                    "CloudWatchInsightsLayer",
                    layer_version_arn=f"arn:aws:lambda:{cdk.Aws.REGION}:580247275435:layer:LambdaInsightsExtension-Arm64:5",
                ),
            ],
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

    def _create_execution_role(self) -> iam.Role:
        """Create IAM execution role with necessary permissions.

        Returns:
            IAM role for Lambda execution with healthcare service permissions.
        """
        role = iam.Role(
            self,
            "ExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole",
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "CloudWatchLambdaInsightsExecutionRolePolicy",
                ),
            ],
        )

        # Add S3 permissions for specified buckets
        if self._s3_buckets:
            s3_resources = []
            for bucket in self._s3_buckets:
                s3_resources.extend(
                    [
                        f"arn:aws:s3:::{bucket}",
                        f"arn:aws:s3:::{bucket}/*",
                    ],
                )

            role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:ListBucket",
                        "s3:GetObjectVersion",
                        "s3:PutObjectAcl",
                        "s3:GetObjectAcl",
                    ],
                    resources=s3_resources,
                ),
            )

        if self._enable_bedrock:
            role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "bedrock:InvokeModel",
                        "bedrock:GetFoundationModel",
                        "bedrock:ListFoundationModels",
                    ],
                    resources=[
                        f"arn:aws:bedrock:{cdk.Aws.REGION}::foundation-model/cohere.embed-english-v3",
                        f"arn:aws:bedrock:{cdk.Aws.REGION}::foundation-model/amazon.titan-embed-text-v2:0",
                        f"arn:aws:bedrock:{cdk.Aws.REGION}::foundation-model/anthropic.claude-sonnet-4-20250514-v1:0",
                    ],
                ),
            )

        if self._enable_comprehend_medical:
            role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "comprehendmedical:DetectPHI",
                        "comprehendmedical:DetectEntitiesV2",
                        "comprehendmedical:InferICD10CM",
                        "comprehendmedical:InferRxNorm",
                        "comprehendmedical:InferSNOMEDCT",
                    ],
                    resources=["*"],
                ),
            )

        if self._enable_macie:
            role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "macie2:CreateClassificationJob",
                        "macie2:GetClassificationJob",
                        "macie2:ListClassificationJobs",
                        "macie2:DescribeClassificationJob",
                        "macie2:GetFindings",
                        "macie2:ListFindings",
                    ],
                    resources=[
                        f"arn:aws:macie2:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:classification-job/*",
                    ],
                ),
            )

        if self._enable_macie:
            role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "textract:DetectDocumentText",
                        "textract:AnalyzeDocument",
                        "textract:StartDocumentTextDetection",
                        "textract:GetDocumentTextDetection",
                        "textract:StartDocumentAnalysis",
                        "textract:GetDocumentAnalysis",
                    ],
                    resources=["*"],
                ),
            )

        for policy_statement in self._additional_policies:
            role.add_to_policy(policy_statement)

        return role

    def _build_environment_variables(
        self,
        additional_env: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build environment variables with PowerTools configuration.

        Args:
            additional_env: Additional environment variables to include.

        Returns:
            Complete environment variables dict with PowerTools settings.
        """
        env_vars = {
            # PowerTools configuration
            "POWERTOOLS_SERVICE_NAME": self._service_name,
            "POWERTOOLS_LOG_LEVEL": "INFO",
            "POWERTOOLS_LOGGER_SAMPLE_RATE": "0.1",
            "POWERTOOLS_LOGGER_LOG_EVENT": "false",
            "POWERTOOLS_METRICS_NAMESPACE": self._namespace,
            "POWERTOOLS_TRACER_CAPTURE_RESPONSE": "true",
            "POWERTOOLS_TRACER_CAPTURE_ERROR": "true",
            # Lambda Insights
            "AWS_LAMBDA_EXEC_WRAPPER": "/opt/otel-instrument",
            # Python optimizations
            "PYTHONPATH": "/var/runtime:/var/task:/opt/python",
            "PYTHONUNBUFFERED": "1",
        }

        if self._enable_bedrock:
            env_vars.update(
                {
                    "BEDROCK_REGION": cdk.Aws.REGION,
                    "COHERE_EMBED_MODEL_ID": "cohere.embed-english-v3",
                    "TITAN_EMBED_MODEL_ID": "amazon.titan-embed-text-v2:0",
                    "CLAUDE_MODEL_ID": "anthropic.claude-sonnet-4-20250514-v1:0",
                },
            )

        if additional_env:
            env_vars.update(additional_env)

        return env_vars

    def add_s3_bucket_access(self, bucket_name: str) -> None:
        """Add S3 bucket access permissions to the Lambda function.

        Args:
            bucket_name: Name of the S3 bucket to grant access to.
        """
        self._role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetObjectVersion",
                    "s3:PutObjectAcl",
                    "s3:GetObjectAcl",
                ],
                resources=[
                    f"arn:aws:s3:::{bucket_name}",
                    f"arn:aws:s3:::{bucket_name}/*",
                ],
            ),
        )

    def add_sns_topic_publish(self, topic_arn: str) -> None:
        """Add SNS topic publish permissions.

        Args:
            topic_arn: ARN of the SNS topic to grant publish access to.
        """
        self._role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["sns:Publish"],
                resources=[topic_arn],
            ),
        )

    def add_dynamodb_table_access(self, table_arn: str) -> None:
        """Add DynamoDB table access permissions.

        Args:
            table_arn: ARN of the DynamoDB table to grant access to.
        """
        self._role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:BatchGetItem",
                    "dynamodb:BatchWriteItem",
                ],
                resources=[table_arn, f"{table_arn}/index/*"],
            ),
        )
