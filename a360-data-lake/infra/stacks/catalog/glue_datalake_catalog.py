import json
from dataclasses import dataclass
from typing import Final

from aws_cdk import Aws
from aws_cdk import aws_glue as glue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from aws_cdk import custom_resources as cr
from constructs import Construct

from stacks.configs.account_config import LakeFormationConfig, get_lakeformation_config


@dataclass(frozen=True)
class GlueDataLakeCatalogProps:
    """Configuration properties for GlueDataLakeCatalog construct.

    Attributes:
        datalake_raw_bucket: S3 bucket for raw data storage.
        datalake_stage_bucket: S3 bucket for staged data processing.
        datalake_analytics_bucket: S3 bucket for analytics results.
        lf_workflow_role_arn: ARN of Lake Formation workflow role.
        cmk_arn: ARN of customer-managed KMS key for encryption.
        skip_database_creation: Flag to skip creating databases if they already exist.
    """

    datalake_raw_bucket: s3.IBucket
    datalake_stage_bucket: s3.IBucket
    datalake_analytics_bucket: s3.IBucket
    lf_workflow_role_arn: str
    cmk_arn: str
    skip_database_creation: bool = False


class GlueDataLakeCatalog(Construct):
    """AWS CDK construct for secure data lake catalog using AWS Glue.

    This construct deploys a production-grade data lake catalog with:
    - Encrypted Glue Data Catalog using customer-managed KMS key
    - Secure configuration for CloudWatch logs and job bookmarks
    - Separate databases for raw, stage, and analytics data
    - Configured crawlers for automated schema discovery

    Attributes:
        raw_database_name: Name of the raw data Glue database.
        stage_database_name: Name of the staged data Glue database.
        analytics_database_name: Name of the analytics data Glue database.
    """

    DATABASE_NAMES: Final[dict[str, str]] = {
        "raw": "raw",
        "stage": "stage",
        "analytics": "analytics",
    }

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: GlueDataLakeCatalogProps,
    ) -> None:
        """Initializes the GlueDataLakeCatalog construct.

        Sets up the Glue Data Catalog with encryption, security configuration,
        databases, crawlers, and cross-account sharing.

        Args:
            scope: Parent construct scope.
            construct_id: Unique identifier for this construct.
            props: Configuration properties for the catalog.
        """
        super().__init__(scope, construct_id)
        self._props = props

        self._raw_database: glue.CfnDatabase | None = None
        self._stage_database: glue.CfnDatabase | None = None
        self._analytics_database: glue.CfnDatabase | None = None

        self.raw_database_name = self.DATABASE_NAMES["raw"]
        self.stage_database_name = self.DATABASE_NAMES["stage"]
        self.analytics_database_name = self.DATABASE_NAMES["analytics"]

        datalake_cmk = kms.Key.from_key_arn(self, "DatalakeCMK", props.cmk_arn)

        self._configure_catalog_encryption(datalake_cmk)
        security_config = self._configure_security_settings(props.cmk_arn)
        self._create_databases(props)  # This will set the database references
        self._create_crawlers(props, security_config)

        config = get_lakeformation_config()
        self._configure_catalog_sharing(config)

        self._configure_key_policy_for_cdk(
            key_arn=props.cmk_arn,
            cdk_role_arn=f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/{construct_id}-DeployRole",
        )

    def _configure_key_policy_for_cdk(
        self,
        key_arn: str,
        cdk_role_arn: str,
    ) -> None:
        """Grants the specified CloudFormation or CDK deployment role permissions to use the KMS key.

        Uses the exact STS assumed role ARN as the principal in the KMS key resource policy
        to ensure the custom resource and other deployment operations can perform the necessary
        KMS decrypt actions.

        Args:
            key_arn: The ARN of the KMS key that needs to allow decryption permissions.
            cdk_role_arn: The full STS assumed role ARN of the CloudFormation or CDK deployment role.
        """
        existing_key = kms.Key.from_key_arn(
            self,
            "ExistingKeyForCDKDeployment",
            key_arn,
        )
        existing_key.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ArnPrincipal(cdk_role_arn)],
                actions=[
                    "kms:Decrypt",
                    "kms:Encrypt",
                    "kms:GenerateDataKey*",
                    "kms:ReEncrypt*",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            ),
        )

    def _configure_catalog_encryption(self, datalake_cmk: kms.IKey) -> None:
        """Configures encryption settings for the Glue Data Catalog.

        Args:
            datalake_cmk: KMS key for catalog encryption.
        """
        glue.CfnDataCatalogEncryptionSettings(
            self,
            "DataCatalogEncryption",
            catalog_id=Aws.ACCOUNT_ID,
            data_catalog_encryption_settings=glue.CfnDataCatalogEncryptionSettings.DataCatalogEncryptionSettingsProperty(
                encryption_at_rest=glue.CfnDataCatalogEncryptionSettings.EncryptionAtRestProperty(
                    catalog_encryption_mode="SSE-KMS",
                    sse_aws_kms_key_id=datalake_cmk.key_id,
                ),
            ),
        )

    def _configure_security_settings(
        self,
        cmk_arn: str,
    ) -> glue.CfnSecurityConfiguration:
        """Configures security settings for Glue jobs and monitoring.

        Args:
            cmk_arn (str): ARN of the KMS key for encryption.

        Returns:
            glue.CfnSecurityConfiguration: The newly created Glue security configuration resource.
        """
        return glue.CfnSecurityConfiguration(
            self,
            "DatalakeGlueSecurityConfiguration",
            encryption_configuration=glue.CfnSecurityConfiguration.EncryptionConfigurationProperty(
                cloud_watch_encryption=glue.CfnSecurityConfiguration.CloudWatchEncryptionProperty(
                    cloud_watch_encryption_mode="SSE-KMS",
                    kms_key_arn=cmk_arn,
                ),
                job_bookmarks_encryption=glue.CfnSecurityConfiguration.JobBookmarksEncryptionProperty(
                    job_bookmarks_encryption_mode="CSE-KMS",
                    kms_key_arn=cmk_arn,
                ),
                s3_encryptions=[
                    glue.CfnSecurityConfiguration.S3EncryptionProperty(
                        s3_encryption_mode="DISABLED",
                    ),
                ],
            ),
            name="datalakeGlueSecurityConfig",
        )

    def _create_databases(self, props: GlueDataLakeCatalogProps) -> None:
        """Creates Glue databases for the data lake zones.

        Args:
            props: Configuration properties with S3 bucket references.
        """
        if props.skip_database_creation:
            # Skip database creation if instructed to do so
            self._raw_database = None
            self._stage_database = None
            self._analytics_database = None
            return

        # Only create databases if not skipped
        self._raw_database = glue.CfnDatabase(
            self,
            "CatalogRawDB",
            catalog_id=Aws.ACCOUNT_ID,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=self.raw_database_name,
                location_uri=f"s3://{props.datalake_raw_bucket.bucket_name}/",
                description="Raw data landing zone database",
            ),
        )

        self._stage_database = glue.CfnDatabase(
            self,
            "CatalogStageDB",
            catalog_id=Aws.ACCOUNT_ID,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=self.stage_database_name,
                location_uri=f"s3://{props.datalake_stage_bucket.bucket_name}/",
                description="Processed data staging database",
            ),
        )

        self._analytics_database = glue.CfnDatabase(
            self,
            "CatalogAnalyticsDB",
            catalog_id=Aws.ACCOUNT_ID,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=self.analytics_database_name,
                location_uri=f"s3://{props.datalake_analytics_bucket.bucket_name}/",
                description="Analytics-ready data database",
            ),
        )

    def get_database(self, name: str) -> glue.CfnDatabase:
        """Gets the database construct by name.

        Args:
            name: Name of the database to retrieve.

        Returns:
            The database construct.
        """
        database_map = {
            self.raw_database_name: self._raw_database,
            self.stage_database_name: self._stage_database,
            self.analytics_database_name: self._analytics_database,
        }
        return database_map[name]

    def _create_crawlers(
        self,
        props: GlueDataLakeCatalogProps,
        security_config: glue.CfnSecurityConfiguration,
    ) -> None:
        """Creates Glue crawlers for automated schema discovery and enforces dependency
        on the Glue security configuration.

        Args:
            props (GlueDataLakeCatalogProps): Catalog configuration properties containing role and bucket info.
            security_config (glue.CfnSecurityConfiguration): The security configuration resource that must exist before the crawlers.
        """
        raw_crawler = glue.CfnCrawler(
            self,
            "RawBucketCrawler",
            name="lakeFormationRawBucketCrawler",
            description="Crawls the Raw bucket in the Lake Formation data lake",
            role=props.lf_workflow_role_arn,
            database_name=self.raw_database_name,
            targets={
                "s3Targets": [
                    {"path": f"s3://{props.datalake_raw_bucket.bucket_name}/"},
                ],
            },
            crawler_security_configuration="datalakeGlueSecurityConfig",
        )
        raw_crawler.node.add_dependency(security_config)

        stage_crawler = glue.CfnCrawler(
            self,
            "StageBucketCrawler",
            name="lakeFormationStageBucketCrawler",
            description="Crawls the Stage bucket in the Lake Formation data lake",
            role=props.lf_workflow_role_arn,
            database_name=self.stage_database_name,
            targets={
                "s3Targets": [
                    {"path": f"s3://{props.datalake_stage_bucket.bucket_name}/"},
                ],
            },
            crawler_security_configuration="datalakeGlueSecurityConfig",
        )
        stage_crawler.node.add_dependency(security_config)

        analytics_crawler = glue.CfnCrawler(
            self,
            "AnalyticsBucketCrawler",
            name="lakeFormationAnalyticsBucketCrawler",
            description="Crawls the Analytics bucket in the Lake Formation data lake",
            role=props.lf_workflow_role_arn,
            database_name=self.analytics_database_name,
            targets={
                "s3Targets": [
                    {"path": f"s3://{props.datalake_analytics_bucket.bucket_name}/"},
                ],
            },
            crawler_security_configuration="datalakeGlueSecurityConfig",
        )
        analytics_crawler.node.add_dependency(security_config)

    def _create_crawler(
        self,
        id_: str,
        name: str,
        description: str,
        role_arn: str,
        database_name: str,
        bucket: s3.IBucket,
    ) -> None:
        """Creates a single Glue crawler with specified configuration.

        Args:
            id_: Unique identifier for the crawler resource.
            name: Name of the crawler to create.
            description: Description of the crawler's purpose.
            role_arn: ARN of IAM role for crawler execution.
            database_name: Target Glue database name.
            bucket: S3 bucket to crawl.
        """
        glue.CfnCrawler(
            self,
            id_,
            name=name,
            description=description,
            role=role_arn,
            database_name=database_name,
            targets={"s3Targets": [{"path": f"s3://{bucket.bucket_name}/"}]},
            crawler_security_configuration="datalakeGlueSecurityConfig",
        )

    def _configure_catalog_sharing(
        self,
        config: LakeFormationConfig,
    ) -> None:
        """Configures cross-account sharing for the Glue Data Catalog.

        Establishes a Glue catalog policy that enables both RAM-based sharing and
        direct cross-account access. Configures the policy using CDK's AWS custom
        resources with minimal required permissions.

        Args:
            config: LakeFormationConfig object containing producer and consumer
                account configurations.

        Raises:
            ValueError: If configuration is invalid
            TypeError: If configuration format is incorrect
        """
        glue_catalog_role_access = cr.AwsCustomResourcePolicy.from_statements(
            [
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "kms:Decrypt",
                        "kms:Encrypt",
                        "kms:GenerateDataKey*",
                        "kms:ReEncrypt*",
                        "kms:DescribeKey",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "glue:PutResourcePolicy",
                        "glue:GetResourcePolicy",
                        "glue:DeleteResourcePolicy",
                    ],
                    resources=["*"],
                ),
            ],
        )

        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["glue:ShareResource"],
                    "Principal": {"Service": ["ram.amazonaws.com"]},
                    "Resource": [
                        f"arn:aws:glue:{config.producer_account.region}:{config.producer_account.account_id}:table/*/*",
                        f"arn:aws:glue:{config.producer_account.region}:{config.producer_account.account_id}:database/*",
                        f"arn:aws:glue:{config.producer_account.region}:{config.producer_account.account_id}:catalog",
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": ["glue:*"],
                    "Principal": {
                        "AWS": [
                            acc.account_id
                            for acc in config.consumer_accounts
                            if acc.enabled
                        ],
                    },
                    "Resource": [
                        f"arn:aws:glue:{config.producer_account.region}:{config.producer_account.account_id}:catalog",
                        f"arn:aws:glue:{config.producer_account.region}:{config.producer_account.account_id}:database/*",
                        f"arn:aws:glue:{config.producer_account.region}:{config.producer_account.account_id}:table/*/*",
                    ],
                },
            ],
        }

        cr.AwsCustomResource(
            self,
            "GlueResourcePolicyCustomResource",
            on_create=cr.AwsSdkCall(
                service="Glue",
                action="putResourcePolicy",
                parameters={
                    "PolicyInJson": json.dumps(policy_document),
                    "EnableHybrid": "TRUE",
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    "GlueCrossAccountResourcePolicy",
                ),
            ),
            on_update=cr.AwsSdkCall(
                service="Glue",
                action="putResourcePolicy",
                parameters={
                    "PolicyInJson": json.dumps(policy_document),
                    "EnableHybrid": "TRUE",
                },
                physical_resource_id=cr.PhysicalResourceId.of(
                    "GlueCrossAccountResourcePolicy",
                ),
            ),
            install_latest_aws_sdk=False,
            policy=glue_catalog_role_access,
        )
