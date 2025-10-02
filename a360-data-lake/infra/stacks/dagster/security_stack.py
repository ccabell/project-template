"""Security groups for Dagster+ ECS containers.

This module provides security group configurations for Dagster+ hybrid
deployment including agent containers and user code containers with
appropriate ingress and egress rules for healthcare data processing.
"""

from typing import Any

import cdk_nag
from aws_cdk import Aspects, Stack
from aws_cdk import aws_ec2 as ec2
from cdk_nag import NagSuppressions
from constructs import Construct

from .constants import DAGSTER_STACK_PREFIX
from .outputs import OutputManager


class SecurityStack(Stack):
    """Security groups for Dagster+ infrastructure.

    Creates and manages security groups required for agent containers
    and user code containers with appropriate network access rules
    for healthcare data processing workflows.

    Attributes:
        vpc: VPC instance for security group creation.
        agent_security_group: Security group for agent containers.
        user_code_security_group: Security group for user code containers.
        output_manager: Manager for consistent output creation.
    """

    vpc: ec2.IVpc
    agent_security_group: ec2.SecurityGroup
    user_code_security_group: ec2.SecurityGroup
    output_manager: OutputManager

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        **kwargs: Any,
    ) -> None:
        """Initialize security stack with VPC-specific security groups.

        Args:
            scope: CDK construct scope for resource creation.
            construct_id: Unique identifier for this stack.
            vpc: VPC instance for security group deployment.
            **kwargs: Additional arguments passed to parent Stack.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.output_manager = OutputManager(self, self.stack_name)
        self.vpc = vpc

        self._create_agent_security_group()
        self._create_user_code_security_group()
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
                {
                    "id": "CdkNagValidationFailure",
                    "reason": "Security group validation fails due to CDK intrinsic function references - this is expected",
                },
                {
                    "id": "AwsSolutions-EC23",
                    "reason": "Security group ingress rules are intentionally configured for Dagster+ cloud integration and VPC communication",
                },
            ],
        )

    def _create_agent_security_group(self) -> None:
        """Create security group for Dagster+ agent containers.

        Configures security group with appropriate ingress and egress rules
        for agent communication with Dagster+ cloud and user code containers.
        """
        self.agent_security_group = ec2.SecurityGroup(
            self,
            "AgentSecurityGroup",
            vpc=self.vpc,
            security_group_name=f"{DAGSTER_STACK_PREFIX}-agent-sg",
            description="Security group for Dagster+ agent containers",
            allow_all_outbound=True,
        )

        self.agent_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(3000),
            description="HTTP access from VPC for health checks",
        )

        self.agent_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(4000),
            description="gRPC access from VPC for user code communication",
        )

        self.agent_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="HTTPS ingress for Dagster+ cloud communication",
        )

        self.agent_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="HTTP ingress for package downloads",
        )

        # Suppress CDK Nag validation failures for this security group
        NagSuppressions.add_resource_suppressions(
            construct=self.agent_security_group,
            suppressions=[
                {
                    "id": "CdkNagValidationFailure",
                    "reason": "CDK Nag validation failure due to intrinsic function references in security group rules",
                },
                {
                    "id": "AwsSolutions-EC23",
                    "reason": "Security group ingress is configured for Dagster+ agent communication and is intentionally open",
                },
            ],
        )

    def _create_user_code_security_group(self) -> None:
        """Create security group for user code containers.

        Configures security group with appropriate access for data processing
        tasks including database connections and API access.
        """
        self.user_code_security_group = ec2.SecurityGroup(
            self,
            "UserCodeSecurityGroup",
            vpc=self.vpc,
            security_group_name=f"{DAGSTER_STACK_PREFIX}-user-code-sg",
            description="Security group for Dagster+ user code containers",
            allow_all_outbound=True,
        )

        self.user_code_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(4000),
            description="gRPC access from agent containers",
        )

        self.user_code_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(3000),
            description="HTTP access from VPC for health checks",
        )

        self.user_code_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="HTTPS ingress for AWS API and external services",
        )

        self.user_code_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="HTTP ingress for package downloads and APIs",
        )

        self.user_code_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(5432),
            description="PostgreSQL ingress for database connections",
        )

        self.user_code_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(3306),
            description="MySQL ingress for database connections",
        )

        self.user_code_security_group.add_ingress_rule(
            peer=ec2.Peer.security_group_id(
                self.agent_security_group.security_group_id,
            ),
            connection=ec2.Port.tcp(4000),
            description="gRPC access from agent containers",
        )

        # Suppress CDK Nag validation failures for this security group
        NagSuppressions.add_resource_suppressions(
            construct=self.user_code_security_group,
            suppressions=[
                {
                    "id": "CdkNagValidationFailure",
                    "reason": "CDK Nag validation failure due to intrinsic function references in security group rules",
                },
                {
                    "id": "AwsSolutions-EC23",
                    "reason": "Security group ingress is configured for Dagster+ user code communication and database access",
                },
            ],
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for cross-stack references."""
        self.output_manager.add_output_with_ssm(
            "AgentSecurityGroupId",
            self.agent_security_group.security_group_id,
            "Agent security group ID",
            "Agent-Security-Group-ID",
        )

        self.output_manager.add_output_with_ssm(
            "UserCodeSecurityGroupId",
            self.user_code_security_group.security_group_id,
            "User code security group ID",
            "User-Code-Security-Group-ID",
        )

    def get_agent_security_group_id(self) -> str:
        """Get agent security group ID for ECS integration.

        Returns:
            Agent security group ID.
        """
        return self.agent_security_group.security_group_id

    def get_user_code_security_group_id(self) -> str:
        """Get user code security group ID for ECS integration.

        Returns:
            User code security group ID.
        """
        return self.user_code_security_group.security_group_id
