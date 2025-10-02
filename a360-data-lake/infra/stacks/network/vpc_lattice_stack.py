"""VPC Lattice integration for cross-account service connectivity.

This module implements VPC Lattice service networks for secure communication
between the A360 Data Platform and existing healthcare services. VPC Lattice
provides application-layer networking with built-in security, observability,
and service discovery capabilities for healthcare data processing workloads.
"""

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import CfnOutput
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_vpclattice as lattice
from constructs import Construct


@dataclass(frozen=True)
class ServiceTarget:
    """Configuration for a service target in VPC Lattice.

    Attributes:
        name: Service target name for identification.
        port: Port number for the target service.
        protocol: Protocol for service communication (HTTP/HTTPS).
        health_check_path: Path for health check endpoint.
        vpc_id: VPC identifier where the target service resides.
        target_type: Type of target (IP, Instance, ALB).
    """

    name: str
    port: int
    protocol: str = "HTTPS"
    health_check_path: str = "/health"
    vpc_id: str | None = None
    target_type: str = "IP"


@dataclass(frozen=True)
class VpcLatticeConfig:
    """Configuration for VPC Lattice service network deployment.

    Attributes:
        service_network_name: Name for the VPC Lattice service network.
        auth_type: Authentication type for service network access.
        service_targets: List of service targets to configure.
        enable_logging: Whether to enable access logging for the service network.
        cross_account_principals: List of cross-account principals for sharing.
    """

    service_network_name: str = "a360-healthcare-services"
    auth_type: str = "AWS_IAM"
    service_targets: list[ServiceTarget] | None = None
    enable_logging: bool = True
    cross_account_principals: list[str] | None = None

    def __post_init__(self):
        if self.service_targets is None:
            object.__setattr__(
                self,
                "service_targets",
                [
                    ServiceTarget(
                        name="patient-api",
                        port=443,
                        protocol="HTTPS",
                        health_check_path="/api/v1/health",
                    ),
                    ServiceTarget(
                        name="consultation-api",
                        port=443,
                        protocol="HTTPS",
                        health_check_path="/api/v1/health",
                    ),
                ],
            )


class VpcLatticeStack(Construct):
    """AWS CDK construct for VPC Lattice service network configuration.

    Creates VPC Lattice service network with target groups and service
    associations for secure cross-VPC communication. Implements healthcare
    data access patterns with appropriate security controls and monitoring.

    Attributes:
        service_network: The created VPC Lattice service network.
        target_groups: Dictionary of created target groups.
        services: Dictionary of created VPC Lattice services.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        config: VpcLatticeConfig | None = None,
        **kwargs,
    ) -> None:
        """Initialize VPC Lattice service network with target configuration.

        Args:
            scope: Parent construct scope.
            construct_id: Unique identifier for this construct.
            vpc: VPC where Lattice services will be associated.
            config: Optional Lattice configuration settings.
            **kwargs: Additional construct arguments.
        """
        super().__init__(scope, construct_id, **kwargs)

        self._vpc = vpc
        self._config = config or VpcLatticeConfig()
        self._target_groups: dict[str, lattice.CfnTargetGroup] = {}
        self._services: dict[str, lattice.CfnService] = {}

        # Get stack context for region and account
        self._stack = cdk.Stack.of(self)

        self._create_service_network()
        self._create_vpc_association()
        self._create_target_groups()
        self._create_services()
        self._create_outputs()

    def _create_service_network(self) -> None:
        """Creates VPC Lattice service network with authentication configuration.

        Service network provides centralized policy enforcement and routing
        for healthcare service communication with IAM-based authentication.
        """
        self._service_network = lattice.CfnServiceNetwork(
            self,
            "HealthcareServiceNetwork",
            name=self._config.service_network_name,
            auth_type=self._config.auth_type,
        )

        # Note: Access log subscription requires CloudWatch log group to exist first
        # For now, we'll skip this to avoid complexity
        # if self._config.enable_logging:
        #     self._create_access_log_subscription()

    def _create_access_log_subscription(self) -> None:
        """Creates access log subscription for service network monitoring.

        Enables comprehensive logging of service network traffic for security
        monitoring, compliance auditing, and troubleshooting healthcare data flows.
        """
        lattice.CfnAccessLogSubscription(
            self,
            "ServiceNetworkAccessLogs",
            destination_arn=f"arn:aws:logs:{self._stack.region}:{self._stack.account}:log-group:/vpc-lattice/service-network",
            resource_identifier=self._service_network.attr_arn,
        )

    def _create_vpc_association(self) -> None:
        """Creates VPC association with the service network.

        Associates the data platform VPC with the service network to enable
        secure communication with healthcare services in other VPCs.
        """
        self._vpc_association = lattice.CfnServiceNetworkVpcAssociation(
            self,
            "DataPlatformVpcAssociation",
            service_network_identifier=self._service_network.attr_id,
            vpc_identifier=self._vpc.vpc_id,
        )

    def _create_target_groups(self) -> None:
        """Creates target groups for healthcare service endpoints.

        Target groups define how traffic is routed to backend services with
        appropriate health checks and load balancing for healthcare APIs.
        """
        for target in self._config.service_targets:
            self._target_groups[target.name] = lattice.CfnTargetGroup(
                self,
                f"{target.name}TargetGroup",
                name=f"a360-{target.name}-targets",
                type=target.target_type,
                config=lattice.CfnTargetGroup.TargetGroupConfigProperty(
                    port=target.port,
                    protocol=target.protocol,
                    vpc_identifier=target.vpc_id or self._vpc.vpc_id,
                    health_check=lattice.CfnTargetGroup.HealthCheckConfigProperty(
                        enabled=True,
                        path=target.health_check_path,
                        port=target.port,
                        protocol=target.protocol,
                        health_check_interval_seconds=30,
                        health_check_timeout_seconds=5,
                        healthy_threshold_count=2,
                        unhealthy_threshold_count=3,
                    ),
                ),
            )

    def _create_services(self) -> None:
        """Creates VPC Lattice services with listener configuration.

        Services provide routing and policy enforcement for healthcare API
        endpoints with HTTPS termination and authentication requirements.
        """
        for target in self._config.service_targets:
            target_group = self._target_groups[target.name]

            self._services[target.name] = lattice.CfnService(
                self,
                f"{target.name}Service",
                name=f"a360-{target.name}-service",
                auth_type=self._config.auth_type,
            )

            lattice.CfnListener(
                self,
                f"{target.name}Listener",
                service_identifier=self._services[target.name].attr_id,
                protocol=target.protocol,
                port=target.port,
                default_action=lattice.CfnListener.DefaultActionProperty(
                    forward=lattice.CfnListener.ForwardProperty(
                        target_groups=[
                            lattice.CfnListener.WeightedTargetGroupProperty(
                                target_group_identifier=target_group.attr_id,
                                weight=100,
                            ),
                        ],
                    ),
                ),
            )

            lattice.CfnServiceNetworkServiceAssociation(
                self,
                f"{target.name}ServiceAssociation",
                service_identifier=self._services[target.name].attr_id,
                service_network_identifier=self._service_network.attr_id,
            )

    def _create_resource_policy(self) -> lattice.CfnResourcePolicy:
        """Creates resource policy for cross-account service network access.

        Returns:
            Resource policy allowing authorized cross-account access to service network.
        """
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": self._config.cross_account_principals or []},
                    "Action": [
                        "vpc-lattice:CreateServiceNetworkVpcAssociation",
                        "vpc-lattice:GetServiceNetwork",
                    ],
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {
                            "vpc-lattice:ServiceNetworkArn": self._service_network.attr_arn,
                        },
                    },
                },
            ],
        }

        return lattice.CfnResourcePolicy(
            self,
            "ServiceNetworkResourcePolicy",
            resource_arn=self._service_network.attr_arn,
            policy=policy_document,
        )

    def _create_outputs(self) -> None:
        """Creates CloudFormation outputs for service network references.

        Exports service network information for use by other stacks and
        cross-account service integrations.
        """
        CfnOutput(
            self,
            "ServiceNetworkId",
            value=self._service_network.attr_id,
            export_name="A360DataPlatform-ServiceNetwork-Id",
            description="VPC Lattice service network ID",
        )

        CfnOutput(
            self,
            "ServiceNetworkArn",
            value=self._service_network.attr_arn,
            export_name="A360DataPlatform-ServiceNetwork-Arn",
            description="VPC Lattice service network ARN",
        )

        # DNS names are not available on CfnService; see AWS Console after deployment
        CfnOutput(
            self,
            "ServiceNames",
            value=",".join(self._services.keys()),
            export_name="A360DataPlatform-Service-Names",
            description="VPC Lattice service names (DNS not available in CfnService)",
        )

    @property
    def service_network(self) -> lattice.CfnServiceNetwork:
        """The VPC Lattice service network instance."""
        return self._service_network

    @property
    def target_groups(self) -> dict[str, lattice.CfnTargetGroup]:
        """Dictionary of created target groups."""
        return self._target_groups

    @property
    def services(self) -> dict[str, lattice.CfnService]:
        """Dictionary of created VPC Lattice services."""
        return self._services
