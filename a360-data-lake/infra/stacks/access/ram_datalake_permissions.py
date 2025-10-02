from aws_cdk import Aws, CfnTag, RemovalPolicy
from aws_cdk import aws_ram as ram
from constructs import Construct


class RamDatalakePermissionsProps:
    """Configuration properties for RamDatalakePermissions.

    Attributes:
        principals: List of AWS account IDs or principals to share with.
        allow_external_principals: Whether to allow principals outside the organization.
    """

    def __init__(
        self,
        principals: list[str] | None,
        allow_external_principals: bool = True,
    ) -> None:
        """Initializes the configuration properties for cross-account sharing via AWS RAM.

        Args:
            principals: List of AWS account IDs or ARN principals to share the Glue Catalog with.
            allow_external_principals: Flag to enable or disable sharing with external principals.
        """
        self.principals = principals if principals else []
        self.allow_external_principals = allow_external_principals


class RamDatalakePermissions(Construct):
    """AWS CDK construct for sharing the Glue Data Catalog using AWS Resource Access Manager.

    This construct creates a resource share for the Glue Catalog. It allows multiple account IDs
    to be granted permissions to the data catalog for cross-account data lake use cases.

    Attributes:
        resource_share_arn: ARN of the created AWS RAM resource share.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: RamDatalakePermissionsProps,
    ) -> None:
        """Initializes the RAM-based sharing construct for the Glue Data Catalog.

        Creates a resource share with optional external principal support. Principals can be
        AWS account IDs or ARN strings. The Glue Catalog ARN is automatically derived from the
        current account and region.

        Args:
            scope: Parent construct scope.
            construct_id: Unique identifier for this construct.
            props: Configuration properties for the resource share, including principals and
                external sharing settings.
        """
        super().__init__(scope, construct_id)

        resource_share = ram.CfnResourceShare(
            self,
            "GlueCatalogResourceShare",
            name="DatalakeGlueCatalogShare",
            resource_arns=[f"arn:aws:glue:{Aws.REGION}:{Aws.ACCOUNT_ID}:catalog"],
            principals=props.principals,
            allow_external_principals=props.allow_external_principals,
            tags=[
                CfnTag(key="Name", value="GlueCatalogShare"),
            ],
        )

        resource_share.apply_removal_policy(RemovalPolicy.RETAIN)
        resource_share.cfn_options.metadata = {
            "Description": "Resource share for the Glue Catalog to enable cross-account data lake access.",
        }

        self._resource_share_arn = resource_share.attr_arn

    @property
    def resource_share_arn(self) -> str:
        """Returns the ARN of the created AWS RAM resource share.

        Returns:
            ARN of the resource share.
        """
        return self._resource_share_arn
