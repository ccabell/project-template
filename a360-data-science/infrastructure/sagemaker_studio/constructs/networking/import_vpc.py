"""
VPC import construct for SageMaker Studio deployments.

Provides a standardized approach for importing and configuring existing VPCs
for use with SageMaker Studio deployments, including security groups and
network monitoring capabilities.
"""

from typing import List, Optional

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_logs as logs
from constructs import Construct


class VpcImportConstruct(Construct):
    """
    Construct for importing and configuring an existing VPC for SageMaker Studio.

    This construct provides a standardized approach for importing existing VPCs
    and configuring them for use with SageMaker Studio, including flow logging,
    subnet selection, and security group configuration.

    Attributes:
        vpc: The imported VPC instance
        security_group: Security group created for SageMaker Studio
        private_subnets: List of private subnets suitable for SageMaker Studio
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc_id: str,
        enable_flow_logs: bool = True,
        flow_log_retention_days: logs.RetentionDays = logs.RetentionDays.ONE_WEEK,
        subnet_group_name: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        Initialize the VPC import construct.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            vpc_id: ID of the existing VPC to import
            enable_flow_logs: Whether to enable VPC flow logs
            flow_log_retention_days: How long to retain flow logs
            subnet_group_name: Name of subnet group to use (if any)
            **kwargs: Additional arguments to pass to the parent construct
        """
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = ec2.Vpc.from_lookup(self, "ImportedVpc", vpc_id=vpc_id)

        self.security_group = ec2.SecurityGroup(
            self,
            "SageMakerSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=True,
            description="Security group for SageMaker Studio",
        )

        if enable_flow_logs:
            self._setup_flow_logs(flow_log_retention_days)

        if subnet_group_name:
            self.private_subnets = self.vpc.select_subnets(
                subnet_group_name=subnet_group_name
            ).subnets
        else:
            self.private_subnets = self.vpc.private_subnets

    def _setup_flow_logs(self, retention_days: logs.RetentionDays) -> None:
        """
        Setup VPC flow logs with CloudWatch integration.

        Args:
            retention_days: How long to retain flow logs in CloudWatch
        """
        flow_log_group = logs.LogGroup(
            self,
            "VpcFlowLogGroup",
            retention=retention_days,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        flow_log_role = cdk.aws_iam.Role(
            self,
            "VpcFlowLogRole",
            assumed_by=cdk.aws_iam.ServicePrincipal("vpc-flow-logs.amazonaws.com"),
        )

        ec2.FlowLog(
            self,
            "VpcFlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(self.vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(
                flow_log_group, flow_log_role
            ),
        )

    @property
    def private_subnet_ids(self) -> List[str]:
        """
        Get IDs of private subnets for SageMaker Studio.

        Returns:
            List of private subnet IDs
        """
        return [subnet.subnet_id for subnet in self.private_subnets]

    @property
    def security_group_id(self) -> str:
        """
        Get ID of the security group for SageMaker Studio.

        Returns:
            Security group ID
        """
        return self.security_group.security_group_id
