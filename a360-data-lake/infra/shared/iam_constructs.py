"""Composable IAM constructs for common permission patterns."""

from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from constructs import Construct


class StandardPolicyStatements:
    """Standard IAM policy statements for common access patterns."""

    @staticmethod
    def s3_medallion_access(
        bronze_bucket: s3.IBucket,
        silver_bucket: s3.IBucket,
        gold_bucket: s3.IBucket,
        landing_bucket: s3.IBucket | None = None,
    ) -> list[iam.PolicyStatement]:
        """Standard medallion architecture S3 access permissions.

        Args:
            bronze_bucket: Bronze layer bucket
            silver_bucket: Silver layer bucket
            gold_bucket: Gold layer bucket
            landing_bucket: Optional landing bucket for raw data

        Returns:
            List of IAM policy statements for medallion access
        """
        statements = []
        buckets = [bronze_bucket, silver_bucket, gold_bucket]
        if landing_bucket:
            buckets.append(landing_bucket)

        # Read access to bronze (raw data)
        statements.append(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion",
                    "s3:ListBucket",
                ],
                resources=[
                    bronze_bucket.bucket_arn,
                    f"{bronze_bucket.bucket_arn}/*",
                ],
            ),
        )

        # Write access to silver and gold buckets
        for bucket in [silver_bucket, gold_bucket]:
            statements.append(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:GetObject",
                        "s3:GetObjectVersion",
                        "s3:PutObject",
                        "s3:DeleteObject",
                        "s3:ListBucket",
                    ],
                    resources=[
                        bucket.bucket_arn,
                        f"{bucket.bucket_arn}/*",
                    ],
                ),
            )

        # Landing bucket access (if provided)
        if landing_bucket:
            statements.append(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:GetObject",
                        "s3:GetObjectVersion",
                        "s3:PutObject",
                        "s3:ListBucket",
                    ],
                    resources=[
                        landing_bucket.bucket_arn,
                        f"{landing_bucket.bucket_arn}/*",
                    ],
                ),
            )

        return statements

    @staticmethod
    def kms_data_access(kms_key: kms.IKey) -> iam.PolicyStatement:
        """Standard KMS permissions for data encryption/decryption.

        Args:
            kms_key: KMS key for data encryption

        Returns:
            IAM policy statement for KMS access
        """
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "kms:Decrypt",
                "kms:DescribeKey",
                "kms:Encrypt",
                "kms:GenerateDataKey",
                "kms:ReEncrypt*",
            ],
            resources=[kms_key.key_arn],
        )

    @staticmethod
    def comprehend_medical_access() -> iam.PolicyStatement:
        """Standard Comprehend Medical permissions for PHI detection."""
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "comprehendmedical:DetectPHI",
                "comprehendmedical:DetectEntitiesV2",
                "comprehendmedical:InferICD10CM",
                "comprehendmedical:InferRxNorm",
                "comprehendmedical:InferSNOMEDCT",
            ],
            resources=["*"],
        )

    @staticmethod
    def bedrock_access(model_arns: list[str] | None = None) -> iam.PolicyStatement:
        """Standard Bedrock permissions for AI/ML operations.

        Args:
            model_arns: Optional list of specific model ARNs to limit access

        Returns:
            IAM policy statement for Bedrock access
        """
        resources = model_arns or ["*"]
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
            ],
            resources=resources,
        )

    @staticmethod
    def macie_classification_access() -> iam.PolicyStatement:
        """Standard Macie permissions for PII classification."""
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "macie2:CreateClassificationJob",
                "macie2:DescribeClassificationJob",
                "macie2:ListClassificationJobs",
                "macie2:GetFindings",
                "macie2:ListFindings",
            ],
            resources=["*"],
        )

    @staticmethod
    def dynamodb_table_access(table_arn: str) -> iam.PolicyStatement:
        """Standard DynamoDB table access permissions.

        Args:
            table_arn: ARN of the DynamoDB table

        Returns:
            IAM policy statement for DynamoDB access
        """
        return iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan",
            ],
            resources=[table_arn, f"{table_arn}/index/*"],
        )


class MedallionLambdaRole(Construct):
    """IAM role for Lambda functions in medallion architecture."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        role_name: str,
        medallion_buckets: dict[str, s3.IBucket],
        kms_key: kms.IKey | None = None,
        additional_statements: list[iam.PolicyStatement] | None = None,
        **kwargs,
    ) -> None:
        """Initialize medallion Lambda role.

        Args:
            scope: CDK construct scope
            construct_id: Construct identifier
            role_name: IAM role name
            medallion_buckets: Dict with keys: bronze, silver, gold, landing (optional)
            kms_key: Optional KMS key for data encryption
            additional_statements: Additional IAM policy statements
            **kwargs: Additional role properties
        """
        super().__init__(scope, construct_id)

        # Start with Lambda basic execution policy
        policy_statements = [
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=["arn:aws:logs:*:*:*"],
            ),
        ]

        # Add medallion S3 access
        policy_statements.extend(
            StandardPolicyStatements.s3_medallion_access(
                bronze_bucket=medallion_buckets["bronze"],
                silver_bucket=medallion_buckets["silver"],
                gold_bucket=medallion_buckets["gold"],
                landing_bucket=medallion_buckets.get("landing"),
            ),
        )

        # Add KMS access if key provided
        if kms_key:
            policy_statements.append(
                StandardPolicyStatements.kms_data_access(kms_key),
            )

        # Add any additional statements
        if additional_statements:
            policy_statements.extend(additional_statements)

        # Create IAM role
        self.role = iam.Role(
            self,
            "Role",
            role_name=role_name,
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                f"{construct_id}Policy": iam.PolicyDocument(
                    statements=policy_statements,
                ),
            },
            **kwargs,
        )

    @property
    def role_arn(self) -> str:
        """Get role ARN."""
        return self.role.role_arn


class ConsultationPipelinePolicies:
    """Pre-configured policies for consultation pipeline components."""

    @staticmethod
    def phi_detection_lambda_statements() -> list[iam.PolicyStatement]:
        """IAM statements for PHI detection Lambda."""
        return [
            StandardPolicyStatements.comprehend_medical_access(),
        ]

    @staticmethod
    def enrichment_lambda_statements(
        bedrock_model_arns: list[str] | None = None,
    ) -> list[iam.PolicyStatement]:
        """IAM statements for consultation enrichment Lambda."""
        return [
            StandardPolicyStatements.bedrock_access(bedrock_model_arns),
        ]

    @staticmethod
    def pii_redaction_lambda_statements() -> list[iam.PolicyStatement]:
        """IAM statements for PII redaction Lambda."""
        return [
            StandardPolicyStatements.macie_classification_access(),
        ]

    @staticmethod
    def job_tracking_lambda_statements(table_arn: str) -> list[iam.PolicyStatement]:
        """IAM statements for job tracking Lambda."""
        return [
            StandardPolicyStatements.dynamodb_table_access(table_arn),
        ]
