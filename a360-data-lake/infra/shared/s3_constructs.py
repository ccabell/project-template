"""Composable S3 constructs for consistent bucket configurations."""

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from constructs import Construct


class StandardLifecyclePolicies:
    """Standard lifecycle policies for different data patterns."""

    @staticmethod
    def intelligent_tiering() -> list[s3.LifecycleRule]:
        """Immediate intelligent tiering for cost optimization."""
        return [
            s3.LifecycleRule(
                id="IntelligentTiering",
                enabled=True,
                transitions=[
                    s3.Transition(
                        storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                        transition_after=cdk.Duration.days(0),
                    ),
                ],
            ),
        ]

    @staticmethod
    def medallion_data_tiering(retain_days: int = 365) -> list[s3.LifecycleRule]:
        """Tiering for medallion architecture data with long retention."""
        return [
            s3.LifecycleRule(
                id="MedallionDataLifecycle",
                enabled=True,
                transitions=[
                    s3.Transition(
                        storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                        transition_after=cdk.Duration.days(0),
                    ),
                    s3.Transition(
                        storage_class=s3.StorageClass.GLACIER,
                        transition_after=cdk.Duration.days(90),
                    ),
                    s3.Transition(
                        storage_class=s3.StorageClass.DEEP_ARCHIVE,
                        transition_after=cdk.Duration.days(365),
                    ),
                ],
                expiration=cdk.Duration.days(retain_days * 7),  # 7 year retention
            ),
        ]

    @staticmethod
    def code_artifacts(retain_days: int = 30) -> list[s3.LifecycleRule]:
        """Lifecycle for code artifacts and temporary files."""
        return [
            s3.LifecycleRule(
                id="CodeArtifactsCleanup",
                enabled=True,
                expiration=cdk.Duration.days(retain_days),
                noncurrent_version_expiration=cdk.Duration.days(7),
            ),
        ]


class SecureDataBucket(Construct):
    """Secure S3 bucket with consistent configuration for data storage."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        bucket_name: str,
        kms_key: kms.IKey | None = None,
        lifecycle_rules: list[s3.LifecycleRule] | None = None,
        versioned: bool = True,
        encryption: s3.BucketEncryption = s3.BucketEncryption.KMS,
        **kwargs,
    ) -> None:
        """Initialize secure data bucket.

        Args:
            scope: CDK construct scope
            construct_id: Construct identifier
            bucket_name: S3 bucket name
            kms_key: KMS key for encryption (optional)
            lifecycle_rules: Custom lifecycle rules (defaults to intelligent tiering)
            versioned: Enable versioning (default: True)
            encryption: Encryption type (default: KMS)
            **kwargs: Additional S3 bucket properties
        """
        super().__init__(scope, construct_id)

        # Use intelligent tiering by default if no lifecycle rules provided
        if lifecycle_rules is None:
            lifecycle_rules = StandardLifecyclePolicies.intelligent_tiering()

        # Default secure configuration
        bucket_props = {
            "bucket_name": bucket_name,
            "encryption": encryption,
            "block_public_access": s3.BlockPublicAccess.BLOCK_ALL,
            "versioned": versioned,
            "lifecycle_rules": lifecycle_rules,
            "object_ownership": s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            **kwargs,
        }

        # Add KMS key if provided
        if kms_key and encryption == s3.BucketEncryption.KMS:
            bucket_props["encryption_key"] = kms_key

        self.bucket = s3.Bucket(self, "Bucket", **bucket_props)

        # Add TLS enforcement policy
        self._add_tls_enforcement_policy()

        # Set object ownership using CDK bucket properties (not bucket policy)
        # Object ownership controls are configured at bucket level, not via IAM policies

    @property
    def bucket_name(self) -> str:
        """Get bucket name."""
        return self.bucket.bucket_name

    @property
    def bucket_arn(self) -> str:
        """Get bucket ARN."""
        return self.bucket.bucket_arn

    def _add_tls_enforcement_policy(self) -> None:
        """Add policy to enforce TLS connections."""
        self.bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="DenyInsecureConnections",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["s3:*"],
                resources=[
                    self.bucket.bucket_arn,
                    f"{self.bucket.bucket_arn}/*",
                ],
                conditions={
                    "Bool": {
                        "aws:SecureTransport": "false",
                    },
                },
            ),
        )


class MedallionBucketSet(Construct):
    """Set of medallion architecture buckets (bronze, silver, gold) with consistent configuration."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        data_type: str,  # e.g., "consultation", "podcast"
        kms_key: kms.IKey | None = None,
        create_landing: bool = True,
        existing_bronze_bucket: str | None = None,
        **kwargs,
    ) -> None:
        """Initialize medallion bucket set.

        Args:
            scope: CDK construct scope
            construct_id: Construct identifier
            env_name: Environment name (dev, prod, etc.)
            data_type: Type of data (consultation, podcast, etc.)
            kms_key: KMS key for encryption
            create_landing: Create landing bucket for raw ingestion
            existing_bronze_bucket: Use existing bronze bucket name
            **kwargs: Additional bucket properties
        """
        super().__init__(scope, construct_id)

        self.env_name = env_name
        self.data_type = data_type
        self.kms_key = kms_key

        # Create landing bucket for raw data ingestion
        if create_landing:
            self.landing_bucket = SecureDataBucket(
                self,
                "LandingBucket",
                bucket_name=f"a360-{env_name}-{data_type}-landing",
                kms_key=kms_key,
                lifecycle_rules=StandardLifecyclePolicies.intelligent_tiering(),
                **kwargs,
            ).bucket

        # Bronze bucket (raw data)
        if existing_bronze_bucket:
            # For external buckets, don't create any CDK constructs - just store the name
            self.bronze_bucket_name = existing_bronze_bucket
            self.bronze_bucket = None  # Explicitly set to None to avoid CDK management
        else:
            self.bronze_bucket = SecureDataBucket(
                self,
                "BronzeBucket",
                bucket_name=f"a360-{env_name}-{data_type}-bronze",
                kms_key=kms_key,
                lifecycle_rules=StandardLifecyclePolicies.medallion_data_tiering(),
                **kwargs,
            ).bucket
            self.bronze_bucket_name = self.bronze_bucket.bucket_name

        # Silver bucket (cleaned/processed data)
        self.silver_bucket = SecureDataBucket(
            self,
            "SilverBucket",
            bucket_name=f"a360-{env_name}-{data_type}-silver",
            kms_key=kms_key,
            lifecycle_rules=StandardLifecyclePolicies.medallion_data_tiering(),
            **kwargs,
        ).bucket

        # Gold bucket (enriched/analytics-ready data)
        self.gold_bucket = SecureDataBucket(
            self,
            "GoldBucket",
            bucket_name=f"a360-{env_name}-{data_type}-gold",
            kms_key=kms_key,
            lifecycle_rules=StandardLifecyclePolicies.medallion_data_tiering(),
            **kwargs,
        ).bucket

    def get_all_buckets(self) -> list[s3.IBucket]:
        """Get all buckets in medallion order (Landing → Bronze → Silver → Gold)."""
        buckets: list[s3.IBucket] = []
        if hasattr(self, "landing_bucket"):
            buckets.append(self.landing_bucket)
        if self.bronze_bucket is not None:
            buckets.append(self.bronze_bucket)
        buckets.extend([self.silver_bucket, self.gold_bucket])
        return buckets


class CodeArtifactBucket(SecureDataBucket):
    """S3 bucket optimized for code artifacts and temporary files."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        bucket_name: str,
        retain_days: int = 30,
        **kwargs,
    ) -> None:
        """Initialize code artifact bucket.

        Args:
            scope: CDK construct scope
            construct_id: Construct identifier
            bucket_name: S3 bucket name
            retain_days: Days to retain artifacts
            **kwargs: Additional bucket properties
        """
        super().__init__(
            scope,
            construct_id,
            bucket_name=bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=StandardLifecyclePolicies.code_artifacts(retain_days),
            versioned=True,
            **kwargs,
        )
