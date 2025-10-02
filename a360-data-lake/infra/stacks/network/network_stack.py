"""Network infrastructure stack for A360 Data Platform with configurable VPC endpoints.

This module provides the foundational network infrastructure for the A360 datalake
including VPC setup, subnets, NAT Gateway configuration, and tiered VPC endpoints
for AWS services. It implements gateway endpoints (always free) plus three
configurable priority tiers controlled by CDK context parameters for cost
optimization with environment-specific configuration.

The stack includes VPC Flow Logs for comprehensive network monitoring and
security analysis, with endpoints configured for optimal performance, security,
and cost efficiency across consistent availability zones using specific AZ IDs
for cross-account datalake deployments.

Architecture:
    - VPC with public, private, and isolated subnets across 3 specific AZ IDs
    - Single NAT Gateway for cost optimization and external API access
    - Gateway endpoints for S3 and DynamoDB (always enabled, no cost)
    - Three configurable interface endpoint tiers via CDK context parameters:
      * High priority: Essential datalake and platform services (currently empty)
      * Medium priority: Core application services (currently empty)
      * Lower priority: Optional and development services (currently empty)
    - AZ ID-based subnet selection for cross-account deployment consistency
    - VPC Flow Logs for network traffic analysis and compliance
    - Environment-specific endpoint configuration via cdk.json context
"""

import logging
from dataclasses import dataclass
from typing import Any, cast

import aws_cdk as cdk
import boto3
from aws_cdk import CfnOutput, RemovalPolicy, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_ssm as ssm
from cdk_nag import NagSuppressions
from constructs import Construct

logging.basicConfig(level=logging.ERROR)

# Specific AZ IDs for us-east-1 that provide consistent cross-account deployment
DEFAULT_AZ_IDS = [
    "use1-az6",
    "use1-az1",
    "use1-az4",
]


@dataclass(frozen=True)
class NetworkStackProps:
    """Configuration properties for network stack deployment.

    Attributes:
        vpc_cidr: CIDR block for the VPC, optimized for datalake workloads.
        enable_dns_hostnames: Whether to enable DNS hostnames in the VPC.
        enable_dns_support: Whether to enable DNS support in the VPC.
        max_azs: Maximum number of Availability Zones to use for subnets.
        nat_gateways: Number of NAT gateways to create for high availability.
        flow_logs_retention: CloudWatch log retention period for VPC Flow Logs.
        target_az_ids: Specific AZ IDs to use for consistent deployment.
        region: AWS region for AZ ID resolution.
    """

    vpc_cidr: str = "10.1.0.0/16"
    enable_dns_hostnames: bool = True
    enable_dns_support: bool = True
    max_azs: int = 3
    nat_gateways: int = 1
    flow_logs_retention: logs.RetentionDays = logs.RetentionDays.ONE_MONTH
    target_az_ids: list[str] | None = None
    region: str = "us-east-1"

    def __post_init__(self):
        """Set default AZ IDs if not provided."""
        if self.target_az_ids is None:
            if self.region == "us-east-1":
                object.__setattr__(self, "target_az_ids", DEFAULT_AZ_IDS)
            else:
                object.__setattr__(self, "target_az_ids", [])


class NetworkStack(Construct):
    """Network infrastructure for A360 Data Platform with tiered configurable VPC endpoints.

    Creates VPC infrastructure optimized for datalake workloads, security, cost
    efficiency, and cross-account deployment consistency. Implements gateway endpoints
    (always free) plus three configurable tiers of interface endpoints controlled by
    CDK context parameters for environment-specific cost optimization while ensuring
    reliable deployment across different AWS accounts using specific AZ IDs.

    Endpoint Categories:
        Gateway endpoints: S3 and DynamoDB (always enabled, no cost)
        High priority: Essential datalake and platform services (configurable, currently empty)
        Medium priority: Core application services (configurable, currently empty)
        Lower priority: Optional development services (configurable, currently empty)

    Attributes:
        vpc: Primary VPC instance with DNS resolution enabled
        vpc_endpoints_security_group: Security group for VPC endpoints
        high_priority_endpoints: Dictionary of high priority configurable endpoints
        medium_priority_endpoints: Dictionary of medium priority configurable endpoints
        lower_priority_endpoints: Dictionary of lower priority configurable endpoints
        gateway_endpoints: Dictionary of created gateway endpoints
        flow_logs_role: IAM role for VPC Flow Logs
        flow_logs: VPC Flow Logs configuration
        availability_zone_ids: List of AZ IDs for consistent cross-account deployment
        availability_zone_names: List of resolved AZ names for this account
        environment_name: Environment name for deployment logic
    """

    vpc_endpoints_security_group: ec2.SecurityGroup
    high_priority_endpoints: dict[str, ec2.InterfaceVpcEndpoint]
    medium_priority_endpoints: dict[str, ec2.InterfaceVpcEndpoint]
    lower_priority_endpoints: dict[str, ec2.InterfaceVpcEndpoint]
    gateway_endpoints: dict[str, ec2.GatewayVpcEndpoint]
    flow_logs_role: iam.Role
    flow_logs: ec2.FlowLog
    availability_zone_ids: list[str]
    availability_zone_names: list[str]
    environment_name: str

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment_name: str = "production",
        props: NetworkStackProps | None = None,
        **kwargs,
    ) -> None:
        """Initialize network stack with VPC and configurable tiered endpoints for datalake.

        Creates VPC infrastructure with optimized subnet configuration for datalake
        workloads, implements essential VPC endpoints plus configurable endpoint
        tiers controlled by CDK context parameters, and configures flow logging for
        security monitoring. Uses specific AZ IDs for consistent cross-account
        datalake deployments.

        Args:
            scope: CDK construct scope for resource creation
            construct_id: Unique identifier for this stack
            environment_name: Environment name for deployment logic (e.g., "production", "staging", "dev")
            props: Optional configuration properties for the network stack
            **kwargs: Additional arguments passed to parent Stack
        """
        super().__init__(scope, construct_id)

        # Fix: Only call .lower() if environment_name is a string
        if isinstance(environment_name, str):
            self.environment_name = environment_name.lower()
        else:
            self.environment_name = "production"
        self._props = props or NetworkStackProps()

        self._resolve_availability_zones()
        self._create_vpc()
        self._create_flow_logs()
        self._create_vpc_endpoints_security_group()
        self._create_gateway_endpoints()
        self._create_configurable_endpoints()
        self._create_outputs_and_parameters()

    def _resolve_availability_zones(self) -> None:
        """Resolve AZ IDs to AZ names for consistent cross-account datalake deployment.

        Uses boto3 to resolve the target AZ IDs to the corresponding AZ names
        for this AWS account. This ensures that datalake resources are deployed
        to the same physical availability zones across different AWS accounts
        while accounting for account-specific AZ name mappings.
        """
        self.availability_zone_ids = self._props.target_az_ids or []
        self.availability_zone_names = []

        if not self.availability_zone_ids:
            msg = (
                f"No target AZ IDs specified for region {self._props.region}. "
                "AZ IDs are required for consistent cross-account datalake deployment."
            )
            raise ValueError(
                msg,
            )

        try:
            client = boto3.client("ec2", region_name=self._props.region)
            azs = client.describe_availability_zones(ZoneIds=self.availability_zone_ids)

            # Maintain order based on target AZ IDs
            for target_az_id in self.availability_zone_ids:
                for az in azs.get("AvailabilityZones", []):
                    if az.get("ZoneId") == target_az_id:
                        self.availability_zone_names.append(az.get("ZoneName"))
                        break

            logging.info(
                f"Resolved AZ IDs {self.availability_zone_ids} to zone names {self.availability_zone_names}",
            )

        except Exception as e:
            logging.warning(f"Failed to resolve AZ IDs to zone names: {e}")
            # Fallback to default zone names for synthesis (when credentials not available)
            fallback_zones = {
                "use1-az1": "us-east-1a",
                "use1-az2": "us-east-1b",
                "use1-az4": "us-east-1c",
                "use1-az6": "us-east-1d",
            }
            for az_id in self.availability_zone_ids:
                if az_id in fallback_zones:
                    self.availability_zone_names.append(fallback_zones[az_id])
                else:
                    # Generic fallback for unknown zones
                    self.availability_zone_names.append(
                        f"us-east-1{chr(97 + len(self.availability_zone_names))}",
                    )

            logging.warning(
                f"Using fallback zone names: {self.availability_zone_names} for AZ IDs: {self.availability_zone_ids}",
            )

        if len(self.availability_zone_names) != len(self.availability_zone_ids):
            msg = (
                f"Could not resolve all AZ IDs. Expected {len(self.availability_zone_ids)}, "
                f"resolved {len(self.availability_zone_names)}."
            )
            raise ValueError(
                msg,
            )

    def _create_vpc(self) -> None:
        """Create VPC with optimized subnet configuration for datalake workloads.

        Establishes VPC with public, private, and isolated subnets across
        the resolved availability zones that correspond to the target AZ IDs.
        Configures single NAT Gateway for cost optimization while maintaining
        external connectivity for datalake ingestion and processing. Uses
        resolved AZ names to ensure VPC endpoints work consistently across
        all AWS accounts.
        """
        self._vpc = ec2.Vpc(
            self,
            "DataPlatformVPC",
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    cidr_mask=24,
                    subnet_type=ec2.SubnetType.PUBLIC,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    cidr_mask=24,
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    cidr_mask=24,
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                ),
            ],
            nat_gateway_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            nat_gateways=self._props.nat_gateways,
            enable_dns_hostnames=self._props.enable_dns_hostnames,
            enable_dns_support=self._props.enable_dns_support,
            ip_addresses=ec2.IpAddresses.cidr(self._props.vpc_cidr),
            availability_zones=self.availability_zone_names,
        )

    def _create_flow_logs(self) -> None:
        """Configure VPC Flow Logs for datalake network traffic monitoring.

        Creates CloudWatch log group and IAM role for flow logs,
        enabling comprehensive network traffic analysis and security monitoring
        for datalake workloads. Essential for compliance and security auditing
        of data processing activities.
        """
        flow_logs_log_group = logs.LogGroup(
            self,
            "VpcFlowLogsGroup",
            log_group_name=f"/aws/vpc/flowlogs/{self._vpc.vpc_id}",
            retention=self._props.flow_logs_retention,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.flow_logs_role = iam.Role(
            self,
            "VpcFlowLogsRole",
            assumed_by=cast(
                "iam.IPrincipal",
                iam.ServicePrincipal("vpc-flow-logs.amazonaws.com"),
            ),
            inline_policies={
                "FlowLogsDeliveryRolePolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                                "logs:DescribeLogGroups",
                                "logs:DescribeLogStreams",
                            ],
                            resources=[
                                flow_logs_log_group.log_group_arn,
                                f"{flow_logs_log_group.log_group_arn}:*",
                            ],
                        ),
                    ],
                ),
            },
        )
        # cdk-nag suppression for wildcard permissions
        NagSuppressions.add_resource_suppressions(
            self.flow_logs_role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard permissions are required for VPC Flow Logs to deliver logs to CloudWatch.",
                },
            ],
            apply_to_children=True,
        )

        self.flow_logs = ec2.FlowLog(
            self,
            "VpcFlowLogs",
            resource_type=ec2.FlowLogResourceType.from_vpc(self._vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(
                flow_logs_log_group,
                self.flow_logs_role,
            ),
            traffic_type=ec2.FlowLogTrafficType.ALL,
        )

    def _create_vpc_endpoints_security_group(self) -> None:
        """Create security group for VPC endpoints used by datalake services.

        Configures security group with appropriate ingress rules for HTTPS
        and HTTP traffic from the VPC CIDR block, optimized for datalake
        service communication patterns.
        """
        self.vpc_endpoints_security_group = ec2.SecurityGroup(
            self,
            "VpcEndpointsSecurityGroup",
            vpc=self._vpc,
            description="Security group for VPC endpoints - A360 Data Platform",
            allow_all_outbound=True,
        )
        # cdk-nag suppression for EC23 intrinsic function warning
        NagSuppressions.add_resource_suppressions(
            self.vpc_endpoints_security_group,
            [
                {
                    "id": "AwsSolutions-EC23",
                    "reason": "Intrinsic function is required for dynamic CIDR assignment.",
                },
            ],
            apply_to_children=True,
        )

        self.vpc_endpoints_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self._vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="HTTPS from VPC CIDR for datalake services",
        )

        self.vpc_endpoints_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(self._vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(80),
            description="HTTP from VPC CIDR for datalake services",
        )

    def _create_gateway_endpoints(self) -> None:
        """Create gateway VPC endpoints for S3 and DynamoDB - essential for datalake.

        Gateway endpoints provide free, high-performance access to S3 (primary
        datalake storage) and DynamoDB (metadata and catalog storage) without
        internet routing. These are always enabled as they have no additional
        cost and are fundamental to datalake operations. Routes are automatically
        added to all route tables in selected subnets.
        """
        self.gateway_endpoints = {}

        # S3 Gateway Endpoint - Critical for datalake storage access
        s3_endpoint = ec2.GatewayVpcEndpoint(
            self,
            "S3GatewayEndpoint",
            vpc=self._vpc,
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[
                ec2.SubnetSelection(
                    subnets=self._vpc.private_subnets + self._vpc.isolated_subnets,
                ),
            ],
        )

        Tags.of(s3_endpoint).add("Name", "S3 Datalake Storage Gateway Endpoint")
        Tags.of(s3_endpoint).add("Service", "S3 Object Storage")
        Tags.of(s3_endpoint).add("Domain", "Networking")
        Tags.of(s3_endpoint).add("Stack", cdk.Stack.of(self).stack_name)
        Tags.of(s3_endpoint).add("Type", "Gateway")
        Tags.of(s3_endpoint).add("Cost", "Free")
        Tags.of(s3_endpoint).add("Priority", "Always-On")
        Tags.of(s3_endpoint).add("Environment", self.environment_name)
        Tags.of(s3_endpoint).add("Purpose", "Datalake")

        self.gateway_endpoints["s3"] = s3_endpoint

        # DynamoDB Gateway Endpoint - For metadata and catalog storage
        dynamodb_endpoint = ec2.GatewayVpcEndpoint(
            self,
            "DynamoDBGatewayEndpoint",
            vpc=self._vpc,
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            subnets=[
                ec2.SubnetSelection(
                    subnets=self._vpc.private_subnets + self._vpc.isolated_subnets,
                ),
            ],
        )

        Tags.of(dynamodb_endpoint).add(
            "Name",
            "DynamoDB Metadata Store Gateway Endpoint",
        )
        Tags.of(dynamodb_endpoint).add("Service", "DynamoDB NoSQL Database")
        Tags.of(dynamodb_endpoint).add("Domain", "Networking")
        Tags.of(dynamodb_endpoint).add("Stack", cdk.Stack.of(self).stack_name)
        Tags.of(dynamodb_endpoint).add("Type", "Gateway")
        Tags.of(dynamodb_endpoint).add("Cost", "Free")
        Tags.of(dynamodb_endpoint).add("Priority", "Always-On")
        Tags.of(dynamodb_endpoint).add("Environment", self.environment_name)
        Tags.of(dynamodb_endpoint).add("Purpose", "Datalake")

        self.gateway_endpoints["dynamodb"] = dynamodb_endpoint

    def _create_configurable_endpoints(self) -> None:
        """Create configurable interface VPC endpoints based on CDK context configuration.

        Creates tiered interface endpoints based on context parameters defined
        in cdk.json for each environment. This allows for cost optimization
        by selectively enabling endpoint tiers based on operational needs
        and environment-specific datalake requirements.

        Currently, all interface endpoint tiers are intentionally empty to focus
        on core datalake functionality with only the essential S3 and DynamoDB
        gateway endpoints enabled.

        Deployment logic:
        - Reads vpc-endpoints context parameters for current environment
        - Creates endpoints based on enabled tiers in context configuration
        - Supports per-environment tier configuration for datalake workloads
        """
        self.high_priority_endpoints = {}
        self.medium_priority_endpoints = {}
        self.lower_priority_endpoints = {}

        vpc_endpoints_context = self.node.try_get_context("vpc-endpoints")
        if not vpc_endpoints_context:
            logging.info(
                "No vpc-endpoints context found, skipping configurable interface endpoints",
            )
            return

        env_config = vpc_endpoints_context.get(self.environment_name, {})

        if env_config.get("high_priority_enabled", False):
            self.high_priority_endpoints = self._create_endpoint_tier(
                "high_priority",
                self._get_high_priority_services_config(),
                "High-Priority",
            )

        if env_config.get("medium_priority_enabled", False):
            self.medium_priority_endpoints = self._create_endpoint_tier(
                "medium_priority",
                self._get_medium_priority_services_config(),
                "Medium-Priority",
            )

        if env_config.get("lower_priority_enabled", False):
            self.lower_priority_endpoints = self._create_endpoint_tier(
                "lower_priority",
                self._get_lower_priority_services_config(),
                "Lower-Priority",
            )

    def enable_interface_endpoints_for_environment(self, environment: str) -> None:
        """Enable interface endpoints based on environment name.

        This method provides a simple way to enable interface endpoints
        for specific environments, similar to the VpcEndpointsStack functionality.

        Args:
            environment: Environment name (e.g., "prod", "staging", "dev")
        """
        if environment.lower() == "prod":
            # Enable high priority endpoints for production
            self.high_priority_endpoints = self._create_endpoint_tier(
                "high_priority",
                self._get_high_priority_services_config(),
                "High-Priority",
            )

    def _create_endpoint_tier(
        self,
        tier_name: str,
        services_config: dict[str, dict[str, Any]],
        priority_label: str,
    ) -> dict[str, ec2.InterfaceVpcEndpoint]:
        """Create VPC endpoints for a specific priority tier for datalake services.

        Creates interface endpoints for services in the specified tier with
        appropriate tagging and error handling for deployment resilience.
        Endpoints are distributed across the specified availability zones
        to ensure they are only created where the services are available.

        Args:
            tier_name: Internal tier name for resource identification
            services_config: Configuration dictionary for services in this tier
            priority_label: Human-readable priority label for tagging

        Returns:
            Dictionary mapping service names to created endpoints
        """
        endpoints = {}

        for service_name, service_config in services_config.items():
            try:
                endpoint_id = f"{service_name.replace('-', '').replace('_', '').title()}InterfaceEndpoint"
                display_name = service_config.get("display_name", service_name.upper())

                endpoint = ec2.InterfaceVpcEndpoint(
                    self,
                    endpoint_id,
                    vpc=self._vpc,
                    service=service_config["service"],
                    subnets=ec2.SubnetSelection(
                        subnets=self._vpc.private_subnets,
                        availability_zones=self.availability_zone_names,
                    ),
                    security_groups=[self.vpc_endpoints_security_group],
                    private_dns_enabled=service_config.get("private_dns_enabled", True),
                    open=False,
                )

                Tags.of(endpoint).add("Name", f"{display_name} VPC Endpoint")
                Tags.of(endpoint).add("Service", display_name)
                Tags.of(endpoint).add("Domain", "Networking")
                Tags.of(endpoint).add("Stack", cdk.Stack.of(self).stack_name)
                Tags.of(endpoint).add("Priority", priority_label)
                Tags.of(endpoint).add("Type", "Interface")
                Tags.of(endpoint).add("Tier", tier_name)
                Tags.of(endpoint).add("Environment", self.environment_name)
                Tags.of(endpoint).add("Purpose", "Datalake")

                endpoints[service_name] = endpoint
            except Exception as e:
                logging.exception(
                    f"Warning: Could not create {tier_name} endpoint for {service_name}: {e}",
                )

        return endpoints

    def _get_high_priority_services_config(self) -> dict[str, dict[str, Any]]:
        """Get configuration for high priority interface VPC endpoints for datalake.

        Returns configuration for essential datalake platform services that would
        require private connectivity for core functionality. These services are
        essential for datalake operations and should be available via private
        endpoints in production environments.

        High priority services for datalake include:
        - AWS Glue: Data catalog and ETL services
        - Lake Formation: Data lake security and governance
        - Athena: Interactive query service
        - Secrets Manager: Credential management for data sources
        - SSM: Systems management for data processing instances
        - KMS: Key management for data encryption
        - CloudWatch Logs: Logging for data processing workflows
        - ECR: Container registry for data processing containers

        Returns:
            Dictionary mapping service names to endpoint configurations
        """
        return {
            "s3": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.s3",
                ),
                "display_name": "S3",
                "private_dns_enabled": True,
            },
            "glue": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.glue",
                ),
                "display_name": "AWS Glue",
                "private_dns_enabled": True,
            },
            "lakeformation": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.lakeformation",
                ),
                "display_name": "Lake Formation",
                "private_dns_enabled": True,
            },
            "athena": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.athena",
                ),
                "display_name": "Athena",
                "private_dns_enabled": True,
            },
            "secretsmanager": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.secretsmanager",
                ),
                "display_name": "Secrets Manager",
                "private_dns_enabled": True,
            },
            "ssm": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.ssm",
                ),
                "display_name": "Systems Manager",
                "private_dns_enabled": True,
            },
            "ssmmessages": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.ssmmessages",
                ),
                "display_name": "SSM Messages",
                "private_dns_enabled": True,
            },
            "ec2messages": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.ec2messages",
                ),
                "display_name": "EC2 Messages",
                "private_dns_enabled": True,
            },
            "kms": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.kms",
                ),
                "display_name": "KMS",
                "private_dns_enabled": True,
            },
            "logs": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.logs",
                ),
                "display_name": "CloudWatch Logs",
                "private_dns_enabled": True,
            },
            "ecr-api": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.ecr.api",
                ),
                "display_name": "ECR API",
                "private_dns_enabled": True,
            },
            "ecr-dkr": {
                "service": ec2.InterfaceVpcEndpointService(
                    "com.amazonaws.us-east-1.ecr.dkr",
                ),
                "display_name": "ECR Docker",
                "private_dns_enabled": True,
            },
        }

    def _get_medium_priority_services_config(self) -> dict[str, dict[str, Any]]:
        """Get configuration for medium priority interface VPC endpoints for datalake.

        Returns configuration for core datalake application services and
        monitoring tools that provide essential platform functionality but may
        be acceptable to route through NAT Gateway during cost optimization
        periods. Currently empty to focus on core datalake operations.

        Future medium priority services for datalake might include:
        - CloudWatch: Observability and monitoring
        - CloudTrail: Audit logging for compliance
        - EventBridge: Event routing for data pipeline triggers
        - SNS/SQS: Messaging for data processing workflows
        - Secrets Manager: Credential management for data sources

        Returns:
            Dictionary mapping service names to endpoint configurations (currently empty)
        """
        return {}

    def _get_lower_priority_services_config(self) -> dict[str, dict[str, Any]]:
        """Get configuration for lower priority interface VPC endpoints for datalake.

        Returns configuration for optional and development services that provide
        enhanced datalake functionality but are not essential for core platform
        operations. Currently empty to focus on core datalake operations.

        Future lower priority services for datalake might include:
        - SageMaker: Machine learning model training and inference
        - Athena: Interactive query service
        - EMR: Big data processing clusters
        - Redshift: Data warehouse analytics
        - QuickSight: Business intelligence and visualization

        Returns:
            Dictionary mapping service names to endpoint configurations (currently empty)
        """
        return {}

    def _create_outputs_and_parameters(self) -> None:
        """Create CloudFormation outputs and SSM parameters for datalake cross-stack references.

        Exports VPC details and availability zone information for use by other
        datalake stacks, ensuring consistent AZ references for cross-account
        deployments and proper resource placement for data processing workloads.
        """
        # Export VPC ID for other datalake stacks to reference
        CfnOutput(
            self,
            "VpcId",
            value=self._vpc.vpc_id,
            export_name="A360DataPlatform-VPC-Id",
            description="VPC ID for A360 Data Platform datalake",
        )

        ssm.StringParameter(
            self,
            "VpcIdParameter",
            parameter_name="/infrastructure/network/vpc-id",
            string_value=self._vpc.vpc_id,
            description="VPC ID for datalake cross-stack references",
        )

        # Export VPC CIDR for security group configurations
        CfnOutput(
            self,
            "VpcCidr",
            value=self._vpc.vpc_cidr_block,
            export_name="A360DataPlatform-VPC-CIDR",
            description="VPC CIDR block for A360 Data Platform datalake",
        )

        ssm.StringParameter(
            self,
            "VpcCidrParameter",
            parameter_name="/infrastructure/network/vpc-cidr",
            string_value=self._vpc.vpc_cidr_block,
            description="VPC CIDR block for datalake security group rules",
        )

        # Export private subnet IDs for datalake services
        private_subnet_ids = [subnet.subnet_id for subnet in self._vpc.private_subnets]
        CfnOutput(
            self,
            "PrivateSubnetIds",
            value=",".join(private_subnet_ids),
            export_name="A360DataPlatform-PrivateSubnet-Ids",
            description="Private subnet IDs for A360 Data Platform datalake services",
        )

        # Export isolated subnet IDs for sensitive datalake workloads
        isolated_subnet_ids = [
            subnet.subnet_id for subnet in self._vpc.isolated_subnets
        ]
        CfnOutput(
            self,
            "IsolatedSubnetIds",
            value=",".join(isolated_subnet_ids),
            export_name="A360DataPlatform-IsolatedSubnet-Ids",
            description="Isolated subnet IDs for sensitive datalake workloads",
        )

        # Export private subnet route table IDs for proper subnet importing
        private_subnet_route_table_ids = [
            subnet.route_table.route_table_id for subnet in self._vpc.private_subnets
        ]
        CfnOutput(
            self,
            "PrivateSubnetRouteTableIds",
            value=",".join(private_subnet_route_table_ids),
            export_name="A360DataPlatform-PrivateSubnet-RouteTable-Ids",
            description="Private subnet route table IDs for proper subnet importing",
        )

        # Export availability zone information for consistent datalake deployment
        for i, (az_id, az_name) in enumerate(
            zip(self.availability_zone_ids, self.availability_zone_names, strict=False),
        ):
            CfnOutput(
                self,
                f"AvailabilityZoneId{i + 1}",
                value=az_id,
                export_name=f"A360DataPlatform-AZ-ID-{i + 1}",
                description=f"Availability Zone ID {i + 1} for cross-account datalake consistency",
            )

            ssm.StringParameter(
                self,
                f"AvailabilityZoneIdParam{i + 1}",
                parameter_name=f"/infrastructure/network/availability-zone-id-{i + 1}",
                string_value=az_id,
                description=f"Availability Zone ID {i + 1} for cross-account datalake consistency",
            )

            ssm.StringParameter(
                self,
                f"AvailabilityZoneNameParam{i + 1}",
                parameter_name=f"/infrastructure/network/availability-zone-name-{i + 1}",
                string_value=az_name,
                description=f"Availability Zone Name {i + 1} for this datalake account",
            )

        # Export all AZ IDs as comma-separated list
        az_ids_list = ",".join(self.availability_zone_ids)
        az_names_list = ",".join(self.availability_zone_names)

        CfnOutput(
            self,
            "AllAvailabilityZoneIds",
            value=az_ids_list,
            export_name="A360DataPlatform-All-AZ-IDs",
            description="Comma-separated list of all availability zone IDs for datalake",
        )

        ssm.StringParameter(
            self,
            "AllAvailabilityZoneIdsParam",
            parameter_name="/infrastructure/network/all-availability-zone-ids",
            string_value=az_ids_list,
            description="Comma-separated list of all availability zone IDs for datalake",
        )

        ssm.StringParameter(
            self,
            "AllAvailabilityZoneNamesParam",
            parameter_name="/infrastructure/network/all-availability-zone-names",
            string_value=az_names_list,
            description="Comma-separated list of all availability zone names for datalake account",
        )

    @property
    def vpc(self) -> ec2.IVpc:
        """The VPC instance for the datalake platform."""
        return self._vpc

    @property
    def private_subnets(self) -> list[ec2.ISubnet]:
        """Private subnets for datalake services."""
        return self._vpc.private_subnets

    @property
    def isolated_subnets(self) -> list[ec2.ISubnet]:
        """Isolated subnets for sensitive datalake workloads."""
        return self._vpc.isolated_subnets

    @property
    def public_subnets(self) -> list[ec2.ISubnet]:
        """Public subnets for load balancers and internet-facing datalake services."""
        return self._vpc.public_subnets

    def get_endpoints_security_group(self) -> ec2.SecurityGroup:
        """Get security group used by VPC endpoints for datalake services.

        Returns:
            Security group configured for VPC endpoint access
        """
        return self.vpc_endpoints_security_group

    def get_all_endpoints(self) -> dict[str, ec2.InterfaceVpcEndpoint]:
        """Get all created interface endpoints across all tiers for datalake.

        Returns:
            Dictionary mapping endpoint names to VPC endpoint instances
        """
        return {
            **self.high_priority_endpoints,
            **self.medium_priority_endpoints,
            **self.lower_priority_endpoints,
        }

    def get_gateway_endpoints(self) -> dict[str, ec2.GatewayVpcEndpoint]:
        """Get all created gateway endpoints for datalake.

        Returns:
            Dictionary mapping gateway endpoint names to VPC endpoint instances
        """
        return self.gateway_endpoints
