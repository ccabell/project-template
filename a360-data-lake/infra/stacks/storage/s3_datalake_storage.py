from dataclasses import dataclass
from typing import Final, cast

from aws_cdk import Aws, Duration, RemovalPolicy, Tags
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from constructs import Construct

from stacks.configs.account_config import (  # type: ignore
    LakeFormationConfig,
    get_lakeformation_config,
)


class KmsKeyPolicyGenerator:
    """Generates and applies KMS key policies for Lake Formation.

    This class generates KMS key policies for cross-account Lake Formation access,
    supporting multiple consumer accounts and AWS services.

    Attributes:
        config: Lake Formation configuration specifying producer and consumer accounts.
    """

    SUPPORTED_SERVICES: Final[list[str]] = [
        "glue",
        "athena",
        "elasticmapreduce",
        "emr-serverless",
        "quicksight",
        "s3",
        "sagemaker",
        "bedrock",
        "forecast",
        "comprehend",
        "rekognition",
        "translate",
        "transcribe",
        "personalize",
        "textract",
    ]

    def __init__(self, config: LakeFormationConfig) -> None:
        """Initializes policy generator with Lake Formation configuration.

        Args:
            config: Lake Formation configuration containing producer/consumer accounts.
        """
        self.config = config

    def generate_key_policy_statements(self, region: str) -> list[iam.PolicyStatement]:
        """Generates KMS key policy statements for Lake Formation access.

        Args:
            region: AWS region for service endpoints.

        Returns:
            List of policy statements granting appropriate KMS permissions.

        Raises:
            ValueError: If producer account ID is not specified.
        """
        if not self.config.producer_account.account_id:
            msg = "Producer account ID must be specified"
            raise ValueError(msg)

        statements = []

        statements.append(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[
                    cast(
                        "iam.IPrincipal",
                        iam.AccountPrincipal(self.config.producer_account.account_id),
                    ),
                ],
                actions=["kms:*"],
                resources=["*"],
            ),
        )

        for consumer in self.config.consumer_accounts:
            if not consumer.enabled:
                continue

            via_service_values = [
                f"{service}.{region}.amazonaws.com"
                for service in self.SUPPORTED_SERVICES
            ]

            statements.append(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    principals=[cast("iam.IPrincipal", iam.AnyPrincipal())],
                    actions=[
                        "kms:Decrypt",
                        "kms:DescribeKey",
                        "kms:Encrypt",
                        "kms:ReEncrypt*",
                        "kms:GenerateDataKey*",
                    ],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "kms:CallerAccount": consumer.account_id,
                            "kms:ViaService": via_service_values,
                        },
                    },
                ),
            )

        return statements

    def create_key_policy(self, key: kms.Key, region: str) -> None:
        """Applies generated policy statements to KMS key.

        Args:
            key: KMS key to update with generated policy.
            region: AWS region for service endpoints.
        """
        statements = self.generate_key_policy_statements(region)
        for statement in statements:
            key.add_to_resource_policy(statement)


@dataclass(frozen=True)
class BucketConfig:
    """Configuration for a data lake bucket.

    This class defines the configuration parameters for creating data lake
    buckets with consistent settings across the infrastructure.

    Attributes:
        name_prefix: Prefix for the bucket name.
        encryption_key: KMS key for bucket encryption.
            May be None for buckets using S3-managed encryption.
        logs_bucket: Bucket for server access logging.
        logs_prefix: Prefix for log objects within logs bucket.
        lifecycle_rules: Optional lifecycle rules for data tiering.
            None indicates no lifecycle management.
    """

    name_prefix: str
    encryption_key: kms.IKey | None
    logs_bucket: s3.IBucket
    logs_prefix: str
    lifecycle_rules: list[s3.LifecycleRule] | None = None


class S3DatalakeStorage(Construct):
    """AWS CDK construct for secure data lake S3 storage infrastructure.

    This construct establishes a comprehensive S3-based data lake with:
    - Customer-managed KMS key for encryption
    - Separate buckets for raw, stage, and analytics data
    - Server access logging configuration
    - Intelligent tiering lifecycle policies
    - SSL enforcement
    - Version control

    The data lake follows a three-tier architecture:
    - Raw: Initial data ingestion with archival policies
    - Stage: Data transformation and processing
    - Analytics: Business-ready data for analysis

    Attributes:
        datalake_raw_bucket: S3 bucket for raw data storage.
        datalake_stage_bucket: S3 bucket for staged data processing.
        datalake_analytics_bucket: S3 bucket for analytics results.
        athena_bucket: S3 bucket for Athena query results.
        cmk_arn: ARN of customer-managed KMS key for encryption.
    """

    BUCKET_PREFIX: Final[str] = "a360-datalake"

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        """Initializes the S3 data lake storage infrastructure.

        Args:
            scope: Parent construct scope.
            construct_id: Unique identifier for this construct.
            **kwargs: Additional construct arguments.
        """
        super().__init__(scope, construct_id, **kwargs)

        cmk = self._create_encryption_key()
        logs_bucket = self._create_logs_bucket()

        self._datalake_raw_bucket = self._create_raw_bucket(cmk, logs_bucket)
        self._datalake_stage_bucket = self._create_stage_bucket(cmk, logs_bucket)
        self._datalake_analytics_bucket = self._create_analytics_bucket(
            cmk,
            logs_bucket,
        )
        self._athena_bucket = self._create_athena_bucket(logs_bucket)
        self._cmk_arn = cmk.key_arn

    def _create_encryption_key(self) -> kms.Key:
        """Creates customer-managed KMS key for data lake encryption.

        Creates and configures a KMS key with appropriate permissions for both
        producer and consumer accounts in the Lake Formation setup.

        Returns:
            Configured KMS key with cross-account permissions.
        """
        key = kms.Key(
            self,
            "DatalakeCMK",
            enable_key_rotation=True,
            alias=f"alias/{self.BUCKET_PREFIX}-datalake-cmk",
            description="KMS key for data lake encryption",
            removal_policy=RemovalPolicy.RETAIN,
            pending_window=Duration.days(7),
        )

        config = get_lakeformation_config()
        policy_generator = KmsKeyPolicyGenerator(config)
        policy_generator.create_key_policy(key, Aws.REGION)

        return key

    def _create_logs_bucket(self) -> s3.Bucket:
        """Creates centralized bucket for server access logging.

        Returns:
            Configured S3 bucket for log storage.
        """
        bucket = s3.Bucket(
            self,
            "DatalakeLogsBucket",
            bucket_name=f"{self.BUCKET_PREFIX}-logs-bucket-{Aws.ACCOUNT_ID}-{Aws.REGION}",
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=False,
            enforce_ssl=True,
        )

        Tags.of(bucket).add("datalake_bucket", "datalake_logs")

        bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:PutObject"],
                principals=[
                    cast(
                        "iam.IPrincipal",
                        iam.ServicePrincipal("logging.s3.amazonaws.com"),
                    ),
                ],
                resources=[f"{bucket.bucket_arn}/*"],
            ),
        )

        return bucket

    def _create_raw_bucket(
        self,
        cmk: kms.Key,
        logs_bucket: s3.Bucket,
    ) -> s3.Bucket:
        """Creates raw data ingestion bucket with archival policies.

        Args:
            cmk: KMS key for bucket encryption.
            logs_bucket: Bucket for server access logging.

        Returns:
            Configured S3 bucket for raw data storage.
        """
        lifecycle_rules = [
            s3.LifecycleRule(
                transitions=[
                    s3.Transition(
                        storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                        transition_after=Duration.days(365),
                    ),
                    s3.Transition(
                        storage_class=s3.StorageClass.GLACIER,
                        transition_after=Duration.days(365 * 3),
                    ),
                ],
            ),
        ]

        config = BucketConfig(
            name_prefix="raw",
            encryption_key=cast("kms.IKey", cmk),
            logs_bucket=logs_bucket,
            logs_prefix="datalake-raw-bucket",
            lifecycle_rules=lifecycle_rules,
        )

        return self._create_datalake_bucket("Raw", config)

    def _create_stage_bucket(
        self,
        cmk: kms.Key,
        logs_bucket: s3.Bucket,
    ) -> s3.Bucket:
        """Creates staging bucket for data processing.

        Args:
            cmk: KMS key for bucket encryption.
            logs_bucket: Bucket for server access logging.

        Returns:
            Configured S3 bucket for staged data.
        """
        config = BucketConfig(
            name_prefix="stage",
            encryption_key=cast("kms.IKey", cmk),
            logs_bucket=logs_bucket,
            logs_prefix="datalake-stage-bucket",
        )

        return self._create_datalake_bucket("Stage", config)

    def _create_analytics_bucket(
        self,
        cmk: kms.Key,
        logs_bucket: s3.Bucket,
    ) -> s3.Bucket:
        """Creates analytics bucket for processed data.

        Args:
            cmk: KMS key for bucket encryption.
            logs_bucket: Bucket for server access logging.

        Returns:
            Configured S3 bucket for analytics data.
        """
        config = BucketConfig(
            name_prefix="analytics",
            encryption_key=cast("kms.IKey", cmk),
            logs_bucket=logs_bucket,
            logs_prefix="datalake-analytics-bucket",
        )

        return self._create_datalake_bucket("Analytics", config)

    def _create_athena_bucket(self, logs_bucket: s3.Bucket) -> s3.Bucket:
        """Creates bucket for Athena query results.

        Args:
            logs_bucket: Bucket for server access logging.

        Returns:
            Configured S3 bucket for Athena results.
        """
        return s3.Bucket(
            self,
            "AthenaBucket",
            bucket_name=f"{self.BUCKET_PREFIX}-athena-bucket-{Aws.ACCOUNT_ID}-{Aws.REGION}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            server_access_logs_bucket=logs_bucket,
            server_access_logs_prefix="athenaBucket",
        )

    def _create_datalake_bucket(
        self,
        name_suffix: str,
        config: BucketConfig,
    ) -> s3.Bucket:
        """Creates a data lake bucket with standard configuration.

        Args:
            name_suffix: Suffix for bucket identifier.
            config: Configuration parameters for the bucket.

        Returns:
            Configured S3 bucket with encryption and logging.
        """
        bucket = s3.Bucket(
            self,
            f"Datalake{name_suffix}Bucket",
            bucket_name=f"{self.BUCKET_PREFIX}-{config.name_prefix}-bucket-{Aws.ACCOUNT_ID}-{Aws.REGION}",
            encryption_key=config.encryption_key,
            encryption=s3.BucketEncryption.KMS
            if config.encryption_key
            else s3.BucketEncryption.S3_MANAGED,
            bucket_key_enabled=bool(config.encryption_key),
            versioned=True,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=False,
            server_access_logs_bucket=config.logs_bucket,
            server_access_logs_prefix=config.logs_prefix,
            lifecycle_rules=config.lifecycle_rules or [],
        )

        if config.encryption_key:
            bucket.node.add_dependency(config.encryption_key)

        bucket.node.add_dependency(config.logs_bucket)

        Tags.of(bucket).add("datalake_bucket", f"datalake_{config.name_prefix}")

        return bucket

    @property
    def datalake_raw_bucket(self) -> s3.Bucket:
        """S3 bucket for raw data storage."""
        return self._datalake_raw_bucket

    @property
    def datalake_stage_bucket(self) -> s3.Bucket:
        """S3 bucket for staged data processing."""
        return self._datalake_stage_bucket

    @property
    def datalake_analytics_bucket(self) -> s3.Bucket:
        """S3 bucket for analytics results."""
        return self._datalake_analytics_bucket

    @property
    def athena_bucket(self) -> s3.Bucket:
        """S3 bucket for Athena query results."""
        return self._athena_bucket

    @property
    def cmk_arn(self) -> str:
        """ARN of customer-managed KMS key for encryption."""
        return self._cmk_arn
