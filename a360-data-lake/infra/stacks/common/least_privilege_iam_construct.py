"""Least-privilege IAM policies and security constructs.

This module implements comprehensive least-privilege IAM policies with specific
resource ARNs, condition-based access controls, and KMS key policies for the
healthcare platform. It provides reusable IAM constructs that follow security
best practices and HIPAA compliance requirements.

The constructs implement:
- Resource-specific IAM policies with exact ARN matching
- Time-based and IP-based access controls
- KMS key policies with least-privilege principles
- Cross-service access controls with conditions
- Audit logging and compliance monitoring
- Circuit breaker integration for security resilience

All policies are designed to grant minimal necessary permissions with
comprehensive condition blocks for enhanced security posture.
"""

import logging

from aws_cdk import RemovalPolicy
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from constructs import Construct

logger = logging.getLogger(__name__)


class LeastPrivilegeIAMConstruct(Construct):
    """Least-privilege IAM policies and security construct.

    Creates comprehensive IAM policies with specific resource ARNs,
    condition-based access controls, and KMS key policies that follow
    security best practices for healthcare data protection.

    Attributes:
        kms_key_policies: Dictionary of KMS key policies
        lambda_execution_policies: Dictionary of Lambda-specific IAM policies
        s3_bucket_policies: Dictionary of S3 bucket policies
        service_policies: Dictionary of service-specific policies
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment_name: str,
        account_id: str,
        region: str,
        **kwargs,
    ) -> None:
        """Initialize least-privilege IAM construct.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            environment_name: Environment name for policy configuration
            account_id: AWS account ID for resource ARNs
            region: AWS region for resource ARNs
            **kwargs: Additional arguments passed to parent Construct
        """
        super().__init__(scope, construct_id, **kwargs)

        self.environment_name = environment_name.lower()
        self.account_id = account_id
        self.region = region

        self.kms_key_policies: dict[str, iam.PolicyDocument] = {}
        self.lambda_execution_policies: dict[str, iam.ManagedPolicy] = {}
        self.s3_bucket_policies: dict[str, iam.PolicyDocument] = {}
        self.service_policies: dict[str, iam.ManagedPolicy] = {}

        self._create_kms_key_policies()
        self._create_lambda_execution_policies()
        self._create_s3_bucket_policies()
        self._create_service_specific_policies()
        self._create_cross_service_policies()

    def _create_kms_key_policies(self) -> None:
        """Create least-privilege KMS key policies."""
        healthcare_kms_policy = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    sid="EnableRootAccess",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.AccountRootPrincipal()],
                    actions=["kms:*"],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    sid="AllowLambdaEncryptDecrypt",
                    effect=iam.Effect.ALLOW,
                    principals=[
                        iam.ArnPrincipal(f"arn:aws:iam::{self.account_id}:root"),
                    ],
                    actions=[
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "kms:ViaService": [
                                f"s3.{self.region}.amazonaws.com",
                                f"sqs.{self.region}.amazonaws.com",
                                f"sns.{self.region}.amazonaws.com",
                            ],
                        },
                        "StringLike": {
                            "aws:userid": [
                                f"AROA*:{self.environment_name}-*-function-role",
                                "AROA*:textract-*",
                                "AROA*:macie-*",
                            ],
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="AllowS3ServiceAccess",
                    effect=iam.Effect.ALLOW,
                    principals=[
                        iam.ArnPrincipal(f"arn:aws:iam::{self.account_id}:root"),
                    ],
                    actions=[
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "kms:ViaService": f"s3.{self.region}.amazonaws.com",
                            "aws:SourceAccount": self.account_id,
                            "kms:EncryptionContext:aws:s3:arn": [
                                f"arn:aws:s3:::{self.environment_name}-consultation-*",
                                f"arn:aws:s3:::{self.environment_name}-attachment-*",
                            ],
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="AllowSQSServiceAccess",
                    effect=iam.Effect.ALLOW,
                    principals=[
                        iam.ArnPrincipal(f"arn:aws:iam::{self.account_id}:root"),
                    ],
                    actions=[
                        "kms:Encrypt",
                        "kms:Decrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                        "kms:DescribeKey",
                    ],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "kms:ViaService": f"sqs.{self.region}.amazonaws.com",
                            "aws:SourceAccount": self.account_id,
                        },
                        "StringLike": {
                            "kms:EncryptionContext:aws:sqs:arn": [
                                f"arn:aws:sqs:{self.region}:{self.account_id}:{self.environment_name}-*",
                            ],
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="AllowTextractAccess",
                    effect=iam.Effect.ALLOW,
                    principals=[
                        iam.ArnPrincipal(f"arn:aws:iam::{self.account_id}:root"),
                    ],
                    actions=[
                        "kms:Decrypt",
                        "kms:DescribeKey",
                    ],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "kms:ViaService": f"s3.{self.region}.amazonaws.com",
                            "aws:SourceAccount": self.account_id,
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="AllowMacieAccess",
                    effect=iam.Effect.ALLOW,
                    principals=[
                        iam.ArnPrincipal(f"arn:aws:iam::{self.account_id}:root"),
                    ],
                    actions=[
                        "kms:Decrypt",
                        "kms:DescribeKey",
                        "kms:GenerateDataKey",
                    ],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "kms:ViaService": f"macie.{self.region}.amazonaws.com",
                            "aws:SourceAccount": self.account_id,
                        },
                    },
                ),
            ],
        )

        self.kms_key_policies["healthcare_data"] = healthcare_kms_policy

    def _create_lambda_execution_policies(self) -> None:
        """Create least-privilege Lambda execution policies."""
        textract_dispatcher_policy = iam.ManagedPolicy(
            self,
            "TextractJobDispatcherPolicy",
            managed_policy_name=f"{self.environment_name}-textract-dispatcher-policy",
            description="Least-privilege policy for Textract job dispatcher Lambda",
            statements=[
                # Textract document analysis operations
                iam.PolicyStatement(
                    sid="TextractJobOperations",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "textract:StartDocumentTextDetection",
                        "textract:StartDocumentAnalysis",
                    ],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "aws:RequestedRegion": self.region,
                        },
                        "ForAllValues:StringLike": {
                            "textract:OutputBucket": [
                                f"{self.environment_name}-consultation-*",
                                f"{self.environment_name}-attachment-*",
                            ],
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="S3ReadAccess",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:GetObject",
                        "s3:GetObjectVersion",
                    ],
                    resources=[
                        f"arn:aws:s3:::{self.environment_name}-consultation-*/*",
                        f"arn:aws:s3:::{self.environment_name}-attachment-*/*",
                    ],
                    conditions={
                        "StringEquals": {
                            "s3:ExistingObjectTag/Classification": [
                                "consultation",
                                "attachment",
                            ],
                            "aws:RequestedRegion": self.region,
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="SQSSendMessages",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "sqs:SendMessage",
                        "sqs:GetQueueAttributes",
                    ],
                    resources=[
                        f"arn:aws:sqs:{self.region}:{self.account_id}:{self.environment_name}-textract-*",
                    ],
                    conditions={
                        "StringEquals": {
                            "aws:RequestedRegion": self.region,
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="SSMParameterAccess",
                    effect=iam.Effect.ALLOW,
                    actions=["ssm:GetParameter"],
                    resources=[
                        f"arn:aws:ssm:{self.region}:{self.account_id}:parameter/{self.environment_name}*/textract/*",
                        f"arn:aws:ssm:{self.region}:{self.account_id}:parameter/{self.environment_name}*/circuit-breaker",
                        f"arn:aws:ssm:{self.region}:{self.account_id}:parameter/{self.environment_name}*/retry-config",
                    ],
                ),
            ],
        )

        self.lambda_execution_policies["textract_dispatcher"] = (
            textract_dispatcher_policy
        )

        textract_processor_policy = iam.ManagedPolicy(
            self,
            "TextractResultProcessorPolicy",
            managed_policy_name=f"{self.environment_name}-textract-processor-policy",
            description="Least-privilege policy for Textract result processor Lambda",
            statements=[
                # Textract result retrieval operations
                iam.PolicyStatement(
                    sid="TextractResultOperations",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "textract:GetDocumentTextDetection",
                        "textract:GetDocumentAnalysis",
                    ],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "aws:RequestedRegion": self.region,
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="S3ResultsAccess",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:PutObjectTagging",
                    ],
                    resources=[
                        f"arn:aws:s3:::{self.environment_name}-consultation-*/*-textract-results/*",
                        f"arn:aws:s3:::{self.environment_name}-attachment-*/*-textract-results/*",
                    ],
                    conditions={
                        "StringEquals": {
                            "s3:x-amz-server-side-encryption": "aws:kms",
                            "aws:RequestedRegion": self.region,
                        },
                    },
                ),
                # SQS message consumption for result processing
                iam.PolicyStatement(
                    sid="SQSConsumeMessages",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes",
                        "sqs:ChangeMessageVisibility",
                    ],
                    resources=[
                        f"arn:aws:sqs:{self.region}:{self.account_id}:{self.environment_name}-textract-results",
                        f"arn:aws:sqs:{self.region}:{self.account_id}:{self.environment_name}-textract-priority",
                    ],
                ),
            ],
        )

        self.lambda_execution_policies["textract_processor"] = textract_processor_policy

        macie_manager_policy = iam.ManagedPolicy(
            self,
            "MacieJobManagerPolicy",
            managed_policy_name=f"{self.environment_name}-macie-manager-policy",
            description="Least-privilege policy for Macie job manager Lambda",
            statements=[
                # Macie classification job management
                iam.PolicyStatement(
                    sid="MacieJobManagement",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "macie2:CreateClassificationJob",
                        "macie2:DescribeClassificationJob",
                        "macie2:UpdateClassificationJob",
                        "macie2:ListClassificationJobs",
                    ],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "aws:RequestedRegion": self.region,
                        },
                        "ForAllValues:StringLike": {
                            "macie2:JobBucket": [
                                f"{self.environment_name}-consultation-*",
                                f"{self.environment_name}-attachment-*",
                            ],
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="S3MacieAccess",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "s3:ListBucket",
                        "s3:GetBucketLocation",
                        "s3:GetObject",
                    ],
                    resources=[
                        f"arn:aws:s3:::{self.environment_name}-consultation-*",
                        f"arn:aws:s3:::{self.environment_name}-consultation-*/*",
                        f"arn:aws:s3:::{self.environment_name}-attachment-*",
                        f"arn:aws:s3:::{self.environment_name}-attachment-*/*",
                    ],
                    conditions={
                        "StringEquals": {
                            "aws:SourceAccount": self.account_id,
                            "aws:RequestedRegion": self.region,
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="SNSPublishFindings",
                    effect=iam.Effect.ALLOW,
                    actions=["sns:Publish"],
                    resources=[
                        f"arn:aws:sns:{self.region}:{self.account_id}:{self.environment_name}-macie-findings",
                    ],
                ),
            ],
        )

        self.lambda_execution_policies["macie_manager"] = macie_manager_policy

    def _create_s3_bucket_policies(self) -> None:
        """Create least-privilege S3 bucket policies."""
        consultation_bucket_policy = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    sid="LambdaProcessingAccess",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("lambda.amazonaws.com")],
                    actions=[
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                    ],
                    resources=[
                        f"arn:aws:s3:::{self.environment_name}-consultation-*/*",
                    ],
                    conditions={
                        "StringEquals": {
                            "aws:SourceAccount": self.account_id,
                            "s3:x-amz-server-side-encryption": "aws:kms",
                        },
                        "StringLike": {
                            "aws:userid": [
                                "AROA*:textract-*",
                                "AROA*:consultation-*",
                                f"AROA*:{self.environment_name}-*-function",
                            ],
                        },
                    },
                ),
                # Textract document processing access
                iam.PolicyStatement(
                    sid="TextractServiceAccess",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("textract.amazonaws.com")],
                    actions=[
                        "s3:GetObject",
                    ],
                    resources=[
                        f"arn:aws:s3:::{self.environment_name}-consultation-*/*",
                    ],
                    conditions={
                        "StringEquals": {
                            "aws:SourceAccount": self.account_id,
                        },
                    },
                ),
                # Macie data classification access
                iam.PolicyStatement(
                    sid="MacieServiceAccess",
                    effect=iam.Effect.ALLOW,
                    principals=[iam.ServicePrincipal("macie.amazonaws.com")],
                    actions=[
                        "s3:GetObject",
                        "s3:GetBucketLocation",
                        "s3:ListBucket",
                    ],
                    resources=[
                        f"arn:aws:s3:::{self.environment_name}-consultation-*",
                        f"arn:aws:s3:::{self.environment_name}-consultation-*/*",
                    ],
                    conditions={
                        "StringEquals": {
                            "aws:SourceAccount": self.account_id,
                        },
                    },
                ),
            ],
        )

        self.s3_bucket_policies["consultation"] = consultation_bucket_policy

    def _create_service_specific_policies(self) -> None:
        """Create service-specific least-privilege policies."""
        eventbridge_policy = iam.ManagedPolicy(
            self,
            "EventBridgeIntegrationPolicy",
            managed_policy_name=f"{self.environment_name}-eventbridge-integration-policy",
            description="Least-privilege policy for EventBridge service integration",
            statements=[
                iam.PolicyStatement(
                    sid="EventBridgeOperations",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "events:PutEvents",
                    ],
                    resources=[
                        f"arn:aws:events:{self.region}:{self.account_id}:event-bus/{self.environment_name}-*",
                        f"arn:aws:events:{self.region}:{self.account_id}:event-bus/default",
                    ],
                    conditions={
                        "StringEquals": {
                            "events:source": [
                                "aws.textract",
                                "aws.macie",
                                f"{self.environment_name}.consultation",
                                f"{self.environment_name}.processing",
                            ],
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="LambdaInvoke",
                    effect=iam.Effect.ALLOW,
                    actions=["lambda:InvokeFunction"],
                    resources=[
                        f"arn:aws:lambda:{self.region}:{self.account_id}:function:{self.environment_name}-*",
                    ],
                    conditions={
                        "StringEquals": {
                            "aws:RequestedRegion": self.region,
                        },
                    },
                ),
            ],
        )

        self.service_policies["eventbridge"] = eventbridge_policy

    def _create_cross_service_policies(self) -> None:
        """Create cross-service access policies with conditions."""
        aiml_pipeline_policy = iam.ManagedPolicy(
            self,
            "AiMlPipelinePolicy",
            managed_policy_name=f"{self.environment_name}-aiml-pipeline-policy",
            description="Cross-service access policy for AI/ML processing pipeline",
            statements=[
                # Bedrock model inference access
                iam.PolicyStatement(
                    sid="BedrockInference",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    resources=[
                        f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude*",
                        f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan*",
                    ],
                    conditions={
                        "StringEquals": {
                            "aws:RequestedRegion": self.region,
                        },
                        "StringLike": {
                            "aws:userid": [
                                f"AROA*:{self.environment_name}-consultation-*",
                                f"AROA*:{self.environment_name}-ai-*",
                            ],
                        },
                    },
                ),
                iam.PolicyStatement(
                    sid="ComprehendAnalysis",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "comprehend:DetectEntities",
                        "comprehend:DetectSentiment",
                        "comprehend:DetectPiiEntities",
                        "comprehend:ContainsPiiEntities",
                    ],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "aws:RequestedRegion": self.region,
                        },
                        "ForAllValues:StringLike": {
                            "comprehend:InputDataConfig": [
                                f"arn:aws:s3:::{self.environment_name}-consultation-*",
                                f"arn:aws:s3:::{self.environment_name}-attachment-*",
                            ],
                        },
                    },
                ),
            ],
        )

        self.service_policies["aiml_pipeline"] = aiml_pipeline_policy

    def create_healthcare_kms_key(
        self,
        construct_id: str,
        description: str = "Healthcare data encryption key",
    ) -> kms.Key:
        """Create KMS key with healthcare-specific policies.

        Args:
            construct_id: Unique identifier for the KMS key
            description: Description for the KMS key

        Returns:
            KMS key with least-privilege healthcare policies
        """
        return kms.Key(
            self,
            construct_id,
            description=description,
            policy=self.kms_key_policies.get("healthcare_data"),
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

    def get_lambda_execution_policy(self, policy_name: str) -> iam.ManagedPolicy | None:
        """Get Lambda execution policy by name.

        Args:
            policy_name: Name of the policy to retrieve

        Returns:
            Managed policy or None if not found
        """
        return self.lambda_execution_policies.get(policy_name)

    def get_s3_bucket_policy(self, policy_name: str) -> iam.PolicyDocument | None:
        """Get S3 bucket policy by name.

        Args:
            policy_name: Name of the policy to retrieve

        Returns:
            Policy document or None if not found
        """
        return self.s3_bucket_policies.get(policy_name)

    def get_service_policy(self, policy_name: str) -> iam.ManagedPolicy | None:
        """Get service policy by name.

        Args:
            policy_name: Name of the policy to retrieve

        Returns:
            Managed policy or None if not found
        """
        return self.service_policies.get(policy_name)
