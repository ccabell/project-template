"""Service discovery namespace for Dagster+ code servers.

This module provides service discovery infrastructure for Dagster+ user
code containers using AWS Cloud Map for internal service communication
and health monitoring within the VPC.
"""

from typing import Any

import cdk_nag
from aws_cdk import Aspects, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_servicediscovery as servicediscovery
from cdk_nag import NagSuppressions
from constructs import Construct

from .constants import DAGSTER_STACK_PREFIX
from .outputs import OutputManager


class ServiceDiscoveryStack(Stack):
    """Service discovery infrastructure for Dagster+ code servers.

    Creates and manages AWS Cloud Map private DNS namespace for service
    discovery of user code containers and health monitoring integration
    with ECS services.

    Attributes:
        vpc: VPC instance for namespace deployment.
        namespace: Private DNS namespace for service discovery.
        output_manager: Manager for consistent output creation.
    """

    vpc: ec2.IVpc
    namespace: servicediscovery.PrivateDnsNamespace
    output_manager: OutputManager

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        **kwargs: Any,
    ) -> None:
        """Initialize service discovery stack with VPC namespace.

        Args:
            scope: CDK construct scope for resource creation.
            construct_id: Unique identifier for this stack.
            vpc: VPC instance for namespace deployment.
            **kwargs: Additional arguments passed to parent Stack.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.output_manager = OutputManager(self, self.stack_name)
        self.vpc = vpc

        self._create_private_dns_namespace()
        self._create_outputs()
        self._configure_security_checks()

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

    def _create_private_dns_namespace(self) -> None:
        """Create private DNS namespace for service discovery.

        Configures AWS Cloud Map namespace for internal service discovery
        and health monitoring of Dagster+ user code containers.
        """
        self.namespace = servicediscovery.PrivateDnsNamespace(
            self,
            "DagsterCodeServerNamespace",
            name=f"{DAGSTER_STACK_PREFIX.lower()}.local",
            vpc=self.vpc,
            description="Private DNS namespace for Dagster+ code server discovery",
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for cross-stack references."""
        self.output_manager.add_output_with_ssm(
            "NamespaceId",
            self.namespace.namespace_id,
            "Service discovery namespace ID",
            "Namespace-ID",
        )

        self.output_manager.add_output_with_ssm(
            "NamespaceName",
            self.namespace.namespace_name,
            "Service discovery namespace name",
            "Namespace-Name",
        )

        self.output_manager.add_output_with_ssm(
            "NamespaceArn",
            self.namespace.namespace_arn,
            "Service discovery namespace ARN",
            "Namespace-ARN",
        )

    def get_namespace_id(self) -> str:
        """Get namespace ID for ECS service integration.

        Returns:
            Service discovery namespace ID.
        """
        return self.namespace.namespace_id

    def get_namespace_name(self) -> str:
        """Get namespace name for configuration.

        Returns:
            Service discovery namespace name.
        """
        return self.namespace.namespace_name

    def get_namespace_arn(self) -> str:
        """Get namespace ARN for IAM permissions.

        Returns:
            Service discovery namespace ARN.
        """
        return self.namespace.namespace_arn
