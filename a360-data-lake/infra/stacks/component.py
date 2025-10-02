from dataclasses import dataclass
from typing import Any

import aws_cdk as cdk
import cdk_nag
from aws_cdk import Aspects
from aws_cdk import aws_glue as glue
from aws_cdk import aws_lakeformation as lakeformation
from cdk_nag import NagSuppressions
from constructs import Construct

from stacks.access.ram_datalake_permissions import (  # type: ignore
    RamDatalakePermissions,
    RamDatalakePermissionsProps,
)
from stacks.catalog.glue_datalake_catalog import (  # type: ignore
    GlueDataLakeCatalog,
    GlueDataLakeCatalogProps,
)
from stacks.management.lakeformation_datalake_management import (  # type: ignore
    LakeFormationDatalakeManagement,
    LakeFormationDatalakeManagementProps,
)
from stacks.network.network_stack import NetworkStack, NetworkStackProps  # type: ignore
from stacks.network.vpc_lattice_stack import (  # type: ignore
    ServiceTarget,
    VpcLatticeConfig,
    VpcLatticeStack,
)
from stacks.permissions.iam_datalake_permissions import (  # type: ignore
    IamDatalakePermissions,
    IamDatalakePermissionsProps,
)
from stacks.storage.s3_datalake_storage import S3DatalakeStorage  # type: ignore


@dataclass
class DataFoundationProps:
    """Configuration properties for the DataFoundation stack.

    Attributes:
        env: AWS environment configuration parameters for deployment.
        stack_name: Name identifier for the CloudFormation stack.
        tags: Resource tags to apply across the infrastructure.
    """

    env: dict[str, str] | None = None
    stack_name: str | None = None
    tags: dict[str, str] | None = None


class DataFoundation(cdk.Stack):
    """AWS CDK stack for secure data lake foundation infrastructure.

    Deploys a comprehensive data lake infrastructure with:
    - Secure S3 storage buckets for data lake zones
    - IAM permissions for data access
    - Lake Formation integration for governance
    - Glue Catalog for metadata management
    - Cross-account sharing capabilities
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: DataFoundationProps | None = None,
        **kwargs: Any,
    ) -> None:
        """Initializes the data foundation infrastructure stack.

        Deploys all necessary components for a secure, well-governed data lake:
        - S3 storage buckets for different data zones
        - IAM roles and permissions for access control
        - Lake Formation integration for fine-grained permissions
        - Glue Catalog for metadata management
        - Cross-account sharing via Resource Access Manager

        Args:
            scope: Parent construct scope.
            construct_id: Unique identifier for this construct.
            props: Optional configuration properties.
            **kwargs: Additional keyword arguments passed to the Stack.
        """
        super().__init__(
            scope,
            construct_id,
            **(props.env if (props and props.env) else {}),
            **kwargs,
        )

        # Create network infrastructure first
        self.network = NetworkStack(
            self,
            "MdaDataFoundationNetworkStack",
            props=NetworkStackProps(
                vpc_cidr="10.1.0.0/16",
                max_azs=2,
                nat_gateways=1,
            ),
        )

        # Enable VPC endpoints for secure AWS service access
        environment = self.node.try_get_context("stage") or "staging"
        self.network.enable_interface_endpoints_for_environment(environment)

        # Create VPC Lattice for cross-account service connectivity
        patient_services_account = (
            self.node.try_get_context("patient_services_account") or "590183989543"
        )
        self.vpc_lattice = VpcLatticeStack(
            self,
            "MdaDataFoundationVpcLatticeStack",
            vpc=self.network.vpc,
            config=VpcLatticeConfig(
                service_network_name="a360-healthcare-services",
                cross_account_principals=[
                    f"arn:aws:iam::{patient_services_account}:root",
                ],
                service_targets=[
                    ServiceTarget(
                        name="patient-api",
                        port=443,
                        health_check_path="/api/v1/health",
                    ),
                    ServiceTarget(
                        name="consultation-websocket",
                        port=443,
                        health_check_path="/health",
                    ),
                ],
            ),
        )

        self.storage = S3DatalakeStorage(self, "MdaDataFoundationStorageStack")

        self.permissions = IamDatalakePermissions(
            self,
            "MdaDataFoundationPermissionsStack",
            IamDatalakePermissionsProps(
                datalake_raw_bucket=self.storage.datalake_raw_bucket,
                datalake_stage_bucket=self.storage.datalake_stage_bucket,
                datalake_analytics_bucket=self.storage.datalake_analytics_bucket,
                athena_bucket=self.storage.athena_bucket,
                cmk_arn=self.storage.cmk_arn,
                cross_account_ids=["590183989543"],
            ),
        )

        # Create Glue databases before Lake Formation resources
        self.raw_database = glue.CfnDatabase(
            self,
            "RawDatabase",
            catalog_id=cdk.Aws.ACCOUNT_ID,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="raw",
                description="Raw bucket data lake zone",
            ),
        )

        self.stage_database = glue.CfnDatabase(
            self,
            "StageDatabase",
            catalog_id=cdk.Aws.ACCOUNT_ID,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="stage",
                description="Stage bucket data lake zone",
            ),
        )

        self.analytics_database = glue.CfnDatabase(
            self,
            "AnalyticsDatabase",
            catalog_id=cdk.Aws.ACCOUNT_ID,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name="analytics",
                description="Analytics bucket data lake zone",
            ),
        )

        # Create Lake Formation tag first
        self.bucket_tag = lakeformation.CfnTag(
            self,
            "LFBucketTag",
            catalog_id=cdk.Aws.ACCOUNT_ID,
            tag_key="bucket",
            tag_values=["raw", "stage", "analytics"],
        )

        # Create Lake Formation resources
        self.raw_resource = lakeformation.CfnResource(
            self,
            "LFRawResource",
            resource_arn=self.storage.datalake_raw_bucket.bucket_arn,
            use_service_linked_role=False,
            role_arn=self.permissions.lf_custom_service_role_arn,
        )

        self.stage_resource = lakeformation.CfnResource(
            self,
            "LFStageResource",
            resource_arn=self.storage.datalake_stage_bucket.bucket_arn,
            use_service_linked_role=False,
            role_arn=self.permissions.lf_custom_service_role_arn,
        )

        self.analytics_resource = lakeformation.CfnResource(
            self,
            "LFAnalyticsResource",
            resource_arn=self.storage.datalake_analytics_bucket.bucket_arn,
            use_service_linked_role=False,
            role_arn=self.permissions.lf_custom_service_role_arn,
        )

        # Create Lake Formation tag associations after resources
        self.raw_tag_association = lakeformation.CfnTagAssociation(
            self,
            "LFRawBucketTag",
            lf_tags=[
                lakeformation.CfnTagAssociation.LFTagPairProperty(
                    catalog_id=cdk.Aws.ACCOUNT_ID,
                    tag_key="bucket",
                    tag_values=["raw"],
                ),
            ],
            resource=lakeformation.CfnTagAssociation.ResourceProperty(
                database=lakeformation.CfnTagAssociation.DatabaseResourceProperty(
                    catalog_id=cdk.Aws.ACCOUNT_ID,
                    name="raw",
                ),
            ),
        )

        self.stage_tag_association = lakeformation.CfnTagAssociation(
            self,
            "LFStageBucketTag",
            lf_tags=[
                lakeformation.CfnTagAssociation.LFTagPairProperty(
                    catalog_id=cdk.Aws.ACCOUNT_ID,
                    tag_key="bucket",
                    tag_values=["stage"],
                ),
            ],
            resource=lakeformation.CfnTagAssociation.ResourceProperty(
                database=lakeformation.CfnTagAssociation.DatabaseResourceProperty(
                    catalog_id=cdk.Aws.ACCOUNT_ID,
                    name="stage",
                ),
            ),
        )

        self.analytics_tag_association = lakeformation.CfnTagAssociation(
            self,
            "LFAnalyticsBucketTag",
            lf_tags=[
                lakeformation.CfnTagAssociation.LFTagPairProperty(
                    catalog_id=cdk.Aws.ACCOUNT_ID,
                    tag_key="bucket",
                    tag_values=["analytics"],
                ),
            ],
            resource=lakeformation.CfnTagAssociation.ResourceProperty(
                database=lakeformation.CfnTagAssociation.DatabaseResourceProperty(
                    catalog_id=cdk.Aws.ACCOUNT_ID,
                    name="analytics",
                ),
            ),
        )

        # Add dependencies to ensure correct creation order
        self.raw_tag_association.node.add_dependency(self.bucket_tag)
        self.raw_tag_association.node.add_dependency(self.raw_database)
        self.raw_tag_association.node.add_dependency(self.raw_resource)

        self.stage_tag_association.node.add_dependency(self.bucket_tag)
        self.stage_tag_association.node.add_dependency(self.stage_database)
        self.stage_tag_association.node.add_dependency(self.stage_resource)

        self.analytics_tag_association.node.add_dependency(self.bucket_tag)
        self.analytics_tag_association.node.add_dependency(self.analytics_database)
        self.analytics_tag_association.node.add_dependency(self.analytics_resource)

        self.management = LakeFormationDatalakeManagement(
            self,
            "MdaDataFoundationManagementStack",
            LakeFormationDatalakeManagementProps(
                datalake_raw_bucket=self.storage.datalake_raw_bucket,
                datalake_stage_bucket=self.storage.datalake_stage_bucket,
                datalake_analytics_bucket=self.storage.datalake_analytics_bucket,
                data_admin_user_arn=self.permissions.data_admin_user_arn,
                data_engineer_user_arn=self.permissions.data_engineer_user_arn,
                data_analyst_user_arn=self.permissions.data_analyst_user_arn,
                lf_custom_service_role_arn=self.permissions.lf_custom_service_role_arn,
                lf_workflow_role_arn=self.permissions.lf_workflow_role_arn,
                skip_resource_registration=True,
            ),
        )

        # Ensure Lake Formation management depends on tag associations
        self.management.node.add_dependency(self.raw_tag_association)
        self.management.node.add_dependency(self.stage_tag_association)
        self.management.node.add_dependency(self.analytics_tag_association)

        self.catalog = GlueDataLakeCatalog(
            self,
            "MdaDataFoundationCatalogStack",
            GlueDataLakeCatalogProps(
                datalake_raw_bucket=self.storage.datalake_raw_bucket,
                datalake_stage_bucket=self.storage.datalake_stage_bucket,
                datalake_analytics_bucket=self.storage.datalake_analytics_bucket,
                lf_workflow_role_arn=self.permissions.lf_workflow_role_arn,
                cmk_arn=self.storage.cmk_arn,
                skip_database_creation=True,
            ),
        )

        # Ensure catalog is created after Lake Formation management
        self.catalog.node.add_dependency(self.management)

        self.ram_sharing = RamDatalakePermissions(
            self,
            "MdaDataFoundationRamSharingStack",
            RamDatalakePermissionsProps(principals=["590183989543"]),
        )

        # RAM sharing comes after everything else
        self.ram_sharing.node.add_dependency(self.catalog)

        # Apply cross-account permissions after all resources are created
        self.permissions.apply_cross_account_permissions()

        self._configure_security_checks()
        self._create_cross_stack_outputs()

    def _configure_security_checks(self) -> None:
        """Configures security analysis and compliance rules for the infrastructure.

        Implements AWS Solutions security checks and necessary suppressions for the
        development environment. This includes:

        1. AWS Solutions security check aspects for comprehensive scanning
        2. IAM-related suppressions for Lake Formation integration
        3. Lambda validation suppressions for CloudFormation intrinsic functions
        """
        Aspects.of(self).add(cdk_nag.AwsSolutionsChecks())
        NagSuppressions.add_stack_suppressions(
            stack=self,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lake Formation integration requires wildcard permissions",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS managed policies required for Lake Formation roles",
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Custom resource Lambda requires intrinsic functions",
                },
            ],
        )

    def _create_cross_stack_outputs(self) -> None:
        """Create CloudFormation outputs for LakeFS stack cross-stack references.

        Exports VPC ID, private subnet IDs, and KMS key ARN for use by
        the independent LakeFS stack.
        """
        # Export VPC ID
        cdk.CfnOutput(
            self,
            "VpcId",
            value=self.network.vpc.vpc_id,
            description="VPC ID for LakeFS stack deployment",
            export_name="MDADataFoundation-VPC-ID",
        )

        # Export private subnet IDs (as comma-separated list)
        private_subnet_ids = [
            subnet.subnet_id for subnet in self.network.vpc.private_subnets
        ]
        cdk.CfnOutput(
            self,
            "PrivateSubnetIds",
            value=",".join(private_subnet_ids),
            description="Private subnet IDs for LakeFS deployment",
            export_name="MDADataFoundation-Private-Subnet-IDs",
        )

        # Export KMS key ARN
        cdk.CfnOutput(
            self,
            "KmsKeyArn",
            value=self.storage.cmk_arn,
            description="KMS key ARN for encryption",
            export_name="MDADataFoundation-KMS-Key-ARN",
        )
