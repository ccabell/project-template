"""podcast medallion architecture CDK stack.

This module implements the medallion architecture (bronze/silver/gold) for
clinical podcast data processing with comprehensive PII/PHI redaction
capabilities using Amazon Macie, Textract, and Comprehend Medical.

The stack creates S3 buckets for each layer, Lambda functions for processing,
and proper IAM permissions following least-privilege principles.
"""

from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_kms as kms
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from shared.s3_constructs import MedallionBucketSet


class PodcastPipelineMedallionStack(cdk.Stack):
    """CDK stack implementing medallion architecture for podcast transcription pipeline.

    This stack creates the infrastructure for processing clinical podcast
    data through bronze (raw), silver (cleaned/redacted), and gold (enriched)
    layers.

    Key Components:
    - Landing zone S3 bucket with Macie + Textract PII detection
    - Bronze layer for raw podcast transcripts
    - Silver layer for PHI-redacted clinical text
    - Gold layer for embeddings and enriched analytics
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str = "prod",
        existing_bronze_bucket: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the podcast medallion stack.

        Args:
            scope: CDK scope for this stack.
            construct_id: Unique identifier for this stack.
            env_name: Deployment environment (prod, staging, dev).
            existing_bronze_bucket: Existing bronze bucket name.
            **kwargs: Additional CDK stack arguments.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.existing_bronze_bucket = existing_bronze_bucket
        self._create_s3_buckets()
        self._create_ssm_parameters()
        self._export_resources()

    def _create_s3_buckets(self) -> None:
        """Create S3 buckets for each medallion layer."""
        # Customer-managed KMS key
        self.data_kms_key = kms.Key(
            self,
            "DataKmsKey",
            alias=f"alias/podcast-transcripts-pipeline-{self.env_name}",
            enable_key_rotation=True,
        )

        medallion_buckets = MedallionBucketSet(
            self,
            "MedallionBuckets",
            env_name=self.env_name,
            data_type="podcast",
            kms_key=self.data_kms_key,
            create_landing=True,
            existing_bronze_bucket=self.existing_bronze_bucket,
        )

        self.landing_bucket = medallion_buckets.landing_bucket

        if not self.existing_bronze_bucket:
            self.bronze_bucket = medallion_buckets.bronze_bucket
        self.bronze_bucket_name = medallion_buckets.bronze_bucket_name
        self.silver_bucket = medallion_buckets.silver_bucket
        self.gold_bucket = medallion_buckets.gold_bucket

    def _create_ssm_parameters(self) -> None:
        """Create SSM parameters for configuration management."""
        ssm.StringParameter(
            self,
            "LandingBucketParam",
            parameter_name=f"/podcast-transcripts-pipeline/{self.env_name}/landing-bucket",
            string_value=self.landing_bucket.bucket_name,
        )

        if not self.existing_bronze_bucket:
            ssm.StringParameter(
                self,
                "BronzeBucketParam",
                parameter_name=f"/podcast-transcripts-pipeline/{self.env_name}/bronze-bucket",
                string_value=self.bronze_bucket_name,
            )

        ssm.StringParameter(
            self,
            "SilverBucketParam",
            parameter_name=f"/podcast-transcripts-pipeline/{self.env_name}/silver-bucket",
            string_value=self.silver_bucket.bucket_name,
        )

        ssm.StringParameter(
            self,
            "GoldBucketParam",
            parameter_name=f"/podcast-transcripts-pipeline/{self.env_name}/gold-bucket",
            string_value=self.gold_bucket.bucket_name,
        )

    def _export_resources(self) -> None:
        """Export resources needed by the Object Lambda stack."""
        cdk.CfnOutput(
            self,
            "LandingBucketName",
            value=self.landing_bucket.bucket_name,
            export_name=f"podcastMedallion-{self.env_name}-LandingBucketName",
        )

        # Export landing bucket ARN
        cdk.CfnOutput(
            self,
            "LandingBucketArn",
            value=self.landing_bucket.bucket_arn,
            export_name=f"podcastMedallion-{self.env_name}-LandingBucketArn",
        )
