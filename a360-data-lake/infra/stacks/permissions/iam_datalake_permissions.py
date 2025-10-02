from dataclasses import dataclass

from aws_cdk import Aws, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lakeformation as lakeformation
from aws_cdk import aws_s3 as s3
from constructs import Construct

from stacks.configs.account_config import (  # type: ignore
    LakeFormationConfig,
    get_lakeformation_config,
)


@dataclass(frozen=True)
class IamDatalakePermissionsProps:
    """Configuration properties for IAM data lake permissions.

    This class defines the required configuration for setting up IAM permissions
    for a secure data lake environment, including bucket definitions and encryption
    configuration.

    Attributes:
        datalake_raw_bucket: S3 bucket for raw data storage.
        datalake_stage_bucket: S3 bucket for staged data processing.
        datalake_analytics_bucket: S3 bucket for analytics results.
        athena_bucket: S3 bucket for Athena query results.
        cmk_arn: ARN of customer-managed KMS key for encryption.
        cross_account_ids: List of cross-account IDs for cross-account sharing.
    """

    datalake_raw_bucket: s3.IBucket
    datalake_stage_bucket: s3.IBucket
    datalake_analytics_bucket: s3.IBucket
    athena_bucket: s3.IBucket
    cmk_arn: str
    cross_account_ids: list[str] | None = None


class IamDatalakePermissions(Construct):
    """AWS CDK construct for creating IAM permissions for data lake access.

    This construct creates all necessary IAM roles and permissions for
    Lake Formation, Glue, and cross-account data access.

    Attributes:
        data_admin_user_arn: ARN of the data admin user.
        data_engineer_user_arn: ARN of the data engineer user.
        data_analyst_user_arn: ARN of the data analyst user.
        lf_custom_service_role_arn: ARN of Lake Formation custom service role.
        lf_workflow_role_arn: ARN of Lake Formation workflow role.
        _bucket_cross_account_configs: Stored cross-account configs for deferred processing.
    """

    CLOUDWATCH_LOG_PREFIX = "/aws/lakeformation"

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: IamDatalakePermissionsProps,
    ) -> None:
        """Initializes IAM permissions for data lake access.

        Creates and configures all IAM roles and permissions required for secure
        data lake operations, including:
        - Lake Formation workflow execution role
        - Data admin user and group with elevated permissions
        - Data engineer user and group for ETL operations
        - Data analyst user and group for read access
        - Lake Formation service role

        Args:
            scope: Construct scope.
            construct_id: Unique identifier for this construct.
            props: Configuration properties.
        """
        super().__init__(scope, construct_id)

        # Create workflow role for Data Lake tasks
        workflow_role = self._create_workflow_role(props)
        self._lf_workflow_role_arn = workflow_role.role_arn

        # Create service role for Lake Formation
        service_role = self._create_service_role()
        self._lf_custom_service_role_arn = service_role.role_arn

        # Create admin user and group
        admin_user, _ = self._create_data_admin(props)
        self._data_admin_user_arn = admin_user.user_arn

        # Create data engineer user and group
        engineer_user, _ = self._create_data_engineer(props, workflow_role)
        self._data_engineer_user_arn = engineer_user.user_arn

        # Create data analyst user and group
        analyst_user, _ = self._create_data_analyst(props)
        self._data_analyst_user_arn = analyst_user.user_arn

        # Define Lake Formation admin settings
        self._setup_catalog_administrators()

        # Store configuration for deferred cross-account setup
        config = get_lakeformation_config()
        if config:
            self._bucket_cross_account_configs = {"props": props, "config": config}

    def _create_workflow_role(self, props: IamDatalakePermissionsProps) -> iam.Role:
        """Creates Lake Formation workflow execution role.

        Args:
            props: Configuration properties containing bucket information.

        Returns:
            Configured IAM role for Lake Formation workflows.
        """
        role = iam.Role(
            self,
            "LFWorkflowRole",
            role_name="lakeFormationWorkflowRole",
            description="Custom Lake Formation workflow role with read-only access to data lake buckets and CMK",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
        )
        workflow_access = iam.Policy(
            self,
            "LFWorkflowRoleAccessPolicy",
            policy_name="lakeFormationWorkflowRoleAccessPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "lakeformation:GetDataAccess",
                        "lakeformation:GrantPermissions",
                    ],
                    resources=["*"],
                ),
            ],
        )
        pass_role = iam.Policy(
            self,
            "LFPassWorkflowRolePolicy",
            policy_name="lakeFormationPassWorkflowRolePolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["iam:PassRole"],
                    resources=[f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/{role.role_name}"],
                ),
            ],
        )
        bucket_access = self._create_bucket_access_policy(
            "LFDatalakeBucketsReadWritePolicy",
            "lakeFormationDatalakeBucketsReadWritePolicy",
            props,
            read_buckets=[
                props.datalake_raw_bucket,
                props.datalake_stage_bucket,
                props.datalake_analytics_bucket,
            ],
            write_buckets=[
                props.datalake_raw_bucket,
                props.datalake_stage_bucket,
                props.datalake_analytics_bucket,
            ],
        )
        key_access = self._create_kms_access_policy(
            "DatalakeBucketsKeyPolicy",
            "datalakeBucketsKeyPolicy",
            props.cmk_arn,
        )
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AWSGlueServiceRole",
            ),
        )
        role.attach_inline_policy(workflow_access)
        role.attach_inline_policy(pass_role)
        role.attach_inline_policy(bucket_access)
        role.attach_inline_policy(key_access)
        return role

    def _create_service_role(self) -> iam.Role:
        """Creates Lake Formation service role with necessary permissions.

        Creates and configures an IAM role for Lake Formation services with permissions
        for cross-account operations, S3 bucket access, and CloudWatch logging.

        Returns:
            Configured IAM role with required policies for Lake Formation service operations.

        Raises:
            iam.PolicyValidationError: If policy creation fails due to invalid statements.
        """
        role = iam.Role(
            self,
            "LFCustomServiceRole",
            role_name="lakeFormationCustomServiceRole",
            description="Custom service role used by Lake Formation with required data lake access permissions",
            assumed_by=iam.ServicePrincipal("lakeformation.amazonaws.com"),
        )
        role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                actions=["sts:AssumeRole"],
                principals=[
                    iam.ServicePrincipal("lakeformation.amazonaws.com"),
                    iam.ServicePrincipal("glue.amazonaws.com"),
                ],
            ),
        )
        pass_role = iam.Policy(
            self,
            "LFPassCustomServiceRolePolicy",
            policy_name="lakeFormationPassCustomServiceRolePolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["iam:PassRole"],
                    resources=[f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/{role.role_name}"],
                ),
            ],
        )
        s3_access = iam.Policy(
            self,
            "LFServiceRoleS3Policy",
            policy_name="lakeFormationServiceRoleS3Policy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "s3:ListBucket",
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject",
                    ],
                    resources=["arn:aws:s3:::*"],
                ),
            ],
        )
        cloudwatch = iam.Policy(
            self,
            "LFWriteCloudWatchLogsPolicy",
            policy_name="lakeFormationWriteCloudWatchLogsPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "logs:CreateLogStream",
                        "logs:CreateLogGroup",
                        "logs:PutLogEvents",
                    ],
                    resources=[
                        f"arn:aws:logs::{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:{self.CLOUDWATCH_LOG_PREFIX}/*",
                        f"arn:aws:logs::{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:{self.CLOUDWATCH_LOG_PREFIX}/*:log-stream:*",
                    ],
                ),
            ],
        )
        role.attach_inline_policy(pass_role)
        role.attach_inline_policy(s3_access)
        role.attach_inline_policy(cloudwatch)
        return role

    def _create_data_admin(
        self,
        props: IamDatalakePermissionsProps,
    ) -> tuple[iam.User, iam.Group]:
        """Creates data admin user and group with elevated permissions.

        This function configures the data admin user and group to manage Lake Formation,
        AWS Glue, and cross-account sharing tasks. It attaches necessary managed and inline
        policies to enable resource sharing with external AWS accounts.

        Args:
            props: Configuration properties containing bucket information.

        Returns:
            A tuple containing the created IAM user and IAM group for the data admin.
        """
        group = iam.Group(
            self,
            "LakeFormationDataAdminGroup",
            group_name="lakeFormationDataAdminGroup",
        )
        user = iam.User(
            self,
            "LFDataAdminUser",
            user_name="lakeFormationDataAdminUser",
            groups=[group],
        )
        service_role = iam.Policy(
            self,
            "CreateLFServiceRolePolicy",
            policy_name="createLakeFormationServiceRolePolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["iam:CreateServiceLinkedRole"],
                    resources=["*"],
                    conditions={
                        "StringEquals": {
                            "iam:AWSServiceName": "lakeformation.amazonaws.com",
                        },
                    },
                ),
                iam.PolicyStatement(
                    actions=["iam:PutRolePolicy"],
                    resources=[
                        f"arn:aws:iam::{Aws.ACCOUNT_ID}:role/aws-service-role/lakeformation.amazonaws.com/AWSServiceRoleForLakeFormationDataAccess",
                    ],
                ),
                iam.PolicyStatement(
                    actions=["s3:ListBucket", "s3:GetObject"],
                    resources=[
                        f"{props.datalake_raw_bucket.bucket_arn}",
                        f"{props.datalake_raw_bucket.bucket_arn}/*",
                        f"{props.datalake_stage_bucket.bucket_arn}",
                        f"{props.datalake_stage_bucket.bucket_arn}/*",
                        f"{props.datalake_analytics_bucket.bucket_arn}",
                        f"{props.datalake_analytics_bucket.bucket_arn}/*",
                    ],
                ),
            ],
        )
        cross_account = iam.Policy(
            self,
            "LFCrossAccountPermsPolicy",
            policy_name="lakeFormationCrossAccountPermsPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "ram:AcceptResourceShareInvitation",
                        "ram:RejectResourceShareInvitation",
                        "ec2:DescribeAvailabilityZones",
                        "ram:EnableSharingWithAwsOrganization",
                        "ram:AssociateResourceShare",
                        "ram:DisassociateResourceShare",
                        "ram:GetResourceShares",
                    ],
                    resources=["*"],
                ),
            ],
        )
        managed_policies = [
            "AWSLakeFormationDataAdmin",
            "AWSGlueConsoleFullAccess",
            "CloudWatchLogsReadOnlyAccess",
            "AWSLakeFormationCrossAccountManager",
            "AmazonAthenaFullAccess",
            "IAMReadOnlyAccess",
        ]
        for policy_name in managed_policies:
            group.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name(policy_name),
            )
        key_access = self._create_kms_access_policy(
            "DatalakeBucketsKeyPolicyDataAdmin",
            "datalakeBucketsKeyPolicy",
            props.cmk_arn,
        )
        group.attach_inline_policy(service_role)
        group.attach_inline_policy(cross_account)
        group.attach_inline_policy(key_access)
        return user, group

    def _create_data_engineer(
        self,
        props: IamDatalakePermissionsProps,
        workflow_role: iam.Role,
    ) -> tuple[iam.User, iam.Group]:
        """Creates data engineer user and group with ETL permissions.

        Args:
            props: Configuration properties containing bucket information.
            workflow_role: Lake Formation workflow role for PassRole permissions.

        Returns:
            Tuple of (user, group) for data engineer role.
        """
        group = iam.Group(
            self,
            "LakeFormationDataEngineerGroup",
            group_name="lakeFormationDataEngineerGroup",
        )
        user = iam.User(
            self,
            "LFDataEngineerUser",
            user_name="lakeFormationDataEngineerUser",
            groups=[group],
        )
        lf_access = iam.Policy(
            self,
            "LFDataEngineerAccessPolicy",
            policy_name="lakeFormationDataEngineerAccessPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "lakeformation:GetDataAccess",
                        "lakeformation:GrantPermissions",
                        "lakeformation:RevokePermissions",
                        "lakeformation:BatchGrantPermissions",
                        "lakeformation:BatchRevokePermissions",
                        "lakeformation:ListPermissions",
                        "lakeformation:AddLFTagsToResource",
                        "lakeformation:RemoveLFTagsFromResource",
                        "lakeformation:GetResourceLFTags",
                        "lakeformation:ListLFTags",
                        "lakeformation:GetLFTag",
                        "lakeformation:SearchTablesByLFTags",
                        "lakeformation:SearchDatabasesByLFTags",
                    ],
                    resources=["*"],
                ),
            ],
        )
        governed_tables = iam.Policy(
            self,
            "LFGovernedTablesPolicy",
            policy_name="lakeFormationGovernedTablesPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "lakeformation:StartTransaction",
                        "lakeformation:CommitTransaction",
                        "lakeformation:CancelTransaction",
                        "lakeformation:ExtendTransaction",
                        "lakeformation:DescribeTransaction",
                        "lakeformation:ListTransactions",
                        "lakeformation:GetTableObjects",
                        "lakeformation:UpdateTableObjects",
                        "lakeformation:DeleteObjectsOnCancel",
                    ],
                    resources=["*"],
                ),
            ],
        )
        pass_role = iam.Policy(
            self,
            "EngineerWorkflowPassRolePolicy",
            policy_name="lakeFormationPassWorkflowRolePolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["iam:PassRole"],
                    resources=[workflow_role.role_arn],
                ),
            ],
        )
        bucket_access = self._create_bucket_access_policy(
            "LFDatalakeBucketsDataEngineerPolicy",
            "lakeFormationDatalakeBucketsDataEngineerPolicy",
            props,
            read_buckets=[
                props.datalake_raw_bucket,
                props.datalake_stage_bucket,
                props.datalake_analytics_bucket,
            ],
            write_buckets=[
                props.datalake_stage_bucket,
                props.datalake_analytics_bucket,
            ],
        )
        managed_policies = [
            "AmazonAthenaFullAccess",
            "AWSGlueConsoleFullAccess",
            "IAMReadOnlyAccess",
        ]
        for policy_name in managed_policies:
            group.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name(policy_name),
            )
        group.attach_inline_policy(lf_access)
        group.attach_inline_policy(governed_tables)
        group.attach_inline_policy(pass_role)
        group.attach_inline_policy(bucket_access)
        return user, group

    def _create_data_analyst(
        self,
        props: IamDatalakePermissionsProps,
    ) -> tuple[iam.User, iam.Group]:
        """Creates data analyst user and group with read-focused permissions.

        Args:
            props: Configuration properties containing bucket information.

        Returns:
            Tuple of (user, group) for data analyst role.
        """
        group = iam.Group(
            self,
            "LakeFormationDataAnalystGroup",
            group_name="lakeFormationDataAnalystGroup",
        )
        user = iam.User(
            self,
            "LFDataAnalystUser",
            user_name="lakeFormationDataAnalystUser",
            groups=[group],
        )
        lf_access = iam.Policy(
            self,
            "LFDataAnalystAccessPolicy",
            policy_name="lakeFormationDataAnalystAccessPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "lakeformation:GetDataAccess",
                        "glue:GetTable",
                        "glue:GetTables",
                        "glue:SearchTables",
                        "glue:GetDatabase",
                        "glue:GetDatabases",
                        "glue:GetPartitions",
                        "lakeformation:GetResourceLFTags",
                        "lakeformation:ListLFTags",
                        "lakeformation:GetLFTag",
                        "lakeformation:SearchTablesByLFTags",
                        "lakeformation:SearchDatabasesByLFTags",
                    ],
                    resources=["*"],
                ),
            ],
        )
        bucket_access = self._create_bucket_access_policy(
            "LFDatalakeBucketsDataAnalystPolicy",
            "lakeFormationDatalakeBucketsDataAnalystPolicy",
            props,
            read_buckets=[
                props.datalake_raw_bucket,
                props.datalake_stage_bucket,
                props.datalake_analytics_bucket,
            ],
            write_buckets=[props.datalake_analytics_bucket],
        )
        managed_policies = ["AmazonAthenaFullAccess", "IAMReadOnlyAccess"]
        for policy_name in managed_policies:
            group.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name(policy_name),
            )
        group.attach_inline_policy(lf_access)
        group.attach_inline_policy(bucket_access)
        return user, group

    def _create_bucket_access_policy(
        self,
        id_: str,
        name: str,
        props: IamDatalakePermissionsProps,
        read_buckets: list[s3.IBucket],
        write_buckets: list[s3.IBucket],
    ) -> iam.Policy:
        """Creates S3 bucket access policy with read/write permissions.

        Args:
            id_: Unique identifier for the policy resource.
            name: Name of the policy to create.
            props: Configuration properties containing bucket information.
            read_buckets: List of buckets to grant read access.
            write_buckets: List of buckets to grant write access.

        Returns:
            Configured IAM policy for bucket access.
        """
        statements = []
        if read_buckets:
            statements.append(
                iam.PolicyStatement(
                    actions=["s3:ListBucket"],
                    resources=[bucket.bucket_arn for bucket in read_buckets],
                ),
            )
            statements.append(
                iam.PolicyStatement(
                    actions=["s3:GetObject"],
                    resources=[f"{bucket.bucket_arn}*" for bucket in read_buckets],
                ),
            )
        if write_buckets:
            if not any(bucket in read_buckets for bucket in write_buckets):
                statements.append(
                    iam.PolicyStatement(
                        actions=["s3:ListBucket"],
                        resources=[bucket.bucket_arn for bucket in write_buckets],
                    ),
                )
            statements.append(
                iam.PolicyStatement(
                    actions=["s3:PutObject", "s3:DeleteObject"],
                    resources=[f"{bucket.bucket_arn}*" for bucket in write_buckets],
                ),
            )
        return iam.Policy(self, id_, policy_name=name, statements=statements)

    def _create_kms_access_policy(
        self,
        id_: str,
        name: str,
        key_arn: str,
        config: LakeFormationConfig | None = None,
    ) -> iam.Policy:
        """Creates KMS key access policy for data lake encryption.

        Creates IAM policy granting encryption operations access to specified KMS key
        including consumer account access for cross-account operations.

        Args:
            id_: Unique identifier for the policy resource.
            name: Name of the policy to create.
            key_arn: ARN of the KMS key to grant access to.
            config: Optional Lake Formation configuration containing consumer accounts.

        Returns:
            Configured IAM policy for KMS key access.

        Raises:
            iam.PolicyValidationError: If policy validation fails.
        """
        statements = [
            iam.PolicyStatement(
                actions=[
                    "kms:Encrypt",
                    "kms:Decrypt",
                    "kms:ReEncryptFrom",
                    "kms:ReEncryptTo",
                    "kms:GenerateDataKey",
                    "kms:GenerateDataKeyWithoutPlaintext",
                    "kms:GenerateDataKeyPair",
                    "kms:GenerateDataKeyPairWithoutPlaintext",
                    "kms:DescribeKey",
                ],
                resources=[key_arn],
            ),
        ]
        if config:
            consumer_accounts = [
                consumer.account_id
                for consumer in config.consumer_accounts
                if consumer.enabled
            ]
            statements.append(
                iam.PolicyStatement(
                    actions=["kms:Decrypt", "kms:DescribeKey", "kms:GenerateDataKey"],
                    resources=[key_arn],
                    principals=[
                        iam.AccountPrincipal(account_id)
                        for account_id in consumer_accounts
                    ],
                ),
            )
        return iam.Policy(self, id_, policy_name=name, statements=statements)

    def _add_cross_account_bucket_policy(
        self,
        buckets: list[s3.IBucket],
        config: LakeFormationConfig,
    ) -> None:
        """Adds cross-account bucket policy to multiple buckets.

        Args:
            buckets: List of S3 buckets to apply the policy to
            config: Lake Formation configuration containing consumer account information
        """
        consumer_accounts = [
            c.account_id for c in config.consumer_accounts if c.enabled
        ]

        for bucket in buckets:
            policy_statement = iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
                resources=[bucket.bucket_arn, f"{bucket.bucket_arn}/*"],
                principals=[
                    iam.ArnPrincipal(
                        f"arn:aws:iam::{account_id}:role/A360-SageMaker-Studio-DomainDefaultRole",
                    )
                    for account_id in consumer_accounts
                ],
            )
            bucket.add_to_resource_policy(policy_statement)

    def apply_cross_account_permissions(self) -> None:
        """Applies cross-account permissions to all data lake buckets.

        This method applies both bucket policies and Lake Formation sharing
        configurations for cross-account access.
        """
        if hasattr(self, "_bucket_cross_account_configs"):
            props = self._bucket_cross_account_configs["props"]
            config = self._bucket_cross_account_configs["config"]

            # Apply bucket policies to all three buckets
            self._add_cross_account_bucket_policy(
                [
                    props.datalake_raw_bucket,
                    props.datalake_stage_bucket,
                    props.datalake_analytics_bucket,
                ],
                config,
            )

    def _setup_catalog_administrators(self) -> None:
        """Registers CDK roles and the data admin user as Lake Formation administrators with full control."""
        synthesizer = Stack.of(self).synthesizer

        # Get resolved role ARNs
        cfn_exec_role_arn = synthesizer.cloud_formation_execution_role_arn.replace(
            "${AWS::Partition}",
            Aws.PARTITION,
        )
        deploy_role_arn = (
            getattr(synthesizer, "deploy_role_arn", "").replace(
                "${AWS::Partition}",
                Aws.PARTITION,
            )
            if hasattr(synthesizer, "deploy_role_arn")
            else None
        )

        # Build admin list
        admins = [
            lakeformation.CfnDataLakeSettings.DataLakePrincipalProperty(
                data_lake_principal_identifier=self._data_admin_user_arn,
            ),
            lakeformation.CfnDataLakeSettings.DataLakePrincipalProperty(
                data_lake_principal_identifier=cfn_exec_role_arn,
            ),
        ]

        if deploy_role_arn:
            admins.append(
                lakeformation.CfnDataLakeSettings.DataLakePrincipalProperty(
                    data_lake_principal_identifier=deploy_role_arn,
                ),
            )

        # Register as Lake Formation admins (appears in Catalog creators UI)
        lakeformation.CfnDataLakeSettings(self, "LFAdminSettings", admins=admins)

    @property
    def data_admin_user_arn(self) -> str:
        """ARN of the data admin user."""
        return self._data_admin_user_arn

    @property
    def data_engineer_user_arn(self) -> str:
        """ARN of the data engineer user."""
        return self._data_engineer_user_arn

    @property
    def data_analyst_user_arn(self) -> str:
        """ARN of the data analyst user."""
        return self._data_analyst_user_arn

    @property
    def lf_workflow_role_arn(self) -> str:
        """ARN of the Lake Formation workflow role."""
        return self._lf_workflow_role_arn

    @property
    def lf_custom_service_role_arn(self) -> str:
        """ARN of the Lake Formation custom service role."""
        return self._lf_custom_service_role_arn
