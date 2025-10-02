"""Network stack for A360 Transcription Service Evaluator.

This stack creates the network infrastructure including VPC, subnets,
security groups, and networking components following AWS best practices.
"""

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_logs as logs
from constructs import Construct


class NetworkStack(cdk.NestedStack):
    """Network infrastructure stack."""

    def __init__(
        self, scope: Construct, construct_id: str, app_name: str, stage: str, **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.app_name = app_name
        self.stage = stage

        # Create VPC with best practices
        self.vpc = self._create_vpc()

        # Create security groups (order matters for dependencies)
        self.alb_security_group = self._create_alb_security_group()
        self.ecs_security_group = self._create_ecs_security_group()
        self.lambda_security_group = self._create_lambda_security_group()
        self.database_security_group = self._create_database_security_group()

        # Add cross-security group rules after all are created
        self._configure_security_group_rules()

        # Create VPC endpoints for AWS services
        self._create_vpc_endpoints()

    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC with public and private subnets."""
        vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name=f"{self.app_name}-{self.stage}-vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=3,  # Use 3 AZs for high availability
            enable_dns_hostnames=True,
            enable_dns_support=True,
            subnet_configuration=[
                # Public subnets for ALB and NAT Gateway
                ec2.SubnetConfiguration(
                    name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
                ),
                # Private subnets for ECS and Lambda
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                # Isolated subnets for RDS
                ec2.SubnetConfiguration(
                    name="Database",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=28,
                ),
            ],
            nat_gateways=2,  # One per AZ for high availability
        )

        # Add tags
        cdk.Tags.of(vpc).add("Name", f"{self.app_name}-{self.stage}-vpc")
        cdk.Tags.of(vpc).add("Environment", self.stage)

        return vpc

    def _create_ecs_security_group(self) -> ec2.SecurityGroup:
        """Create security group for ECS tasks."""
        sg = ec2.SecurityGroup(
            self,
            "EcsSecurityGroup",
            vpc=self.vpc,
            description="Security group for ECS Fargate tasks",
            security_group_name=f"{self.app_name}-{self.stage}-ecs-sg",
            allow_all_outbound=True,
        )

        # Allow inbound traffic from ALB
        sg.add_ingress_rule(
            peer=ec2.Peer.security_group_id(self.alb_security_group.security_group_id),
            connection=ec2.Port.tcp(8000),
            description="Allow inbound from ALB",
        )
        
        # Allow inbound traffic from Network Load Balancer
        sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(8000),
            description="Allow NLB to reach ECS tasks on port 8000",
        )

        # Using default outbound rules

        return sg

    def _create_lambda_security_group(self) -> ec2.SecurityGroup:
        """Create security group for Lambda functions."""
        sg = ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=self.vpc,
            description="Security group for Lambda functions",
            security_group_name=f"{self.app_name}-{self.stage}-lambda-sg",
            allow_all_outbound=True,
        )

        return sg

    def _create_database_security_group(self) -> ec2.SecurityGroup:
        """Create security group for RDS database."""
        sg = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=self.vpc,
            description="Security group for Aurora database",
            security_group_name=f"{self.app_name}-{self.stage}-db-sg",
        )

        # Allow inbound from ECS on PostgreSQL port
        sg.add_ingress_rule(
            peer=ec2.Peer.security_group_id(self.ecs_security_group.security_group_id),
            connection=ec2.Port.tcp(5432),
            description="Allow ECS to access database",
        )

        # Allow inbound from Lambda on PostgreSQL port
        sg.add_ingress_rule(
            peer=ec2.Peer.security_group_id(
                self.lambda_security_group.security_group_id
            ),
            connection=ec2.Port.tcp(5432),
            description="Allow Lambda to access database",
        )

        return sg

    def _create_alb_security_group(self) -> ec2.SecurityGroup:
        """Create security group for Application Load Balancer."""
        sg = ec2.SecurityGroup(
            self,
            "AlbSecurityGroup",
            vpc=self.vpc,
            description="Security group for Application Load Balancer",
            security_group_name=f"{self.app_name}-{self.stage}-alb-sg",
            allow_all_outbound=True,
        )

        # Allow inbound HTTPS traffic
        sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow inbound HTTPS",
        )

        # Allow inbound HTTP traffic
        sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow inbound HTTP",
        )

        # Using default outbound to avoid SG-to-SG circular dependencies

        return sg

    def _configure_security_group_rules(self):
        """Configure cross-security group rules after all security groups are created."""

        # ALB uses default outbound; no explicit SG-to-SG egress to avoid circular dependencies

        # Outbound from ECS and Lambda allowed by default; database SG restricts inbound

    def _create_vpc_endpoints(self):
        """Create VPC endpoints for AWS services to reduce costs and improve security."""

        # S3 Gateway Endpoint (free)
        self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            ],
        )

        # DynamoDB Gateway Endpoint (free)
        self.vpc.add_gateway_endpoint(
            "DynamoDbEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            subnets=[
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            ],
        )

        # Interface endpoints for critical services (cost-optimized)
        # Use a dedicated endpoint security group to avoid SG-to-SG coupling
        endpoint_sg = ec2.SecurityGroup(
            self,
            "VpcEndpointSecurityGroup",
            vpc=self.vpc,
            description="Security group for VPC interface endpoints",
            allow_all_outbound=True,
        )
        endpoint_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS from within VPC",
        )

        interface_endpoints = [
            ("SecretsManager", ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER),
        ]

        for name, service in interface_endpoints:
            self.vpc.add_interface_endpoint(
                f"{name}Endpoint",
                service=service,
                subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    availability_zones=self.vpc.availability_zones[:2],
                ),
                security_groups=[endpoint_sg],
            )

        # Create VPC Flow Logs for security monitoring
        vpc_flow_log_group = logs.LogGroup(
            self,
            "VpcFlowLogGroup",
            log_group_name=f"/aws/vpc/flowlogs/{self.app_name}-{self.stage}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # Create flow logs with S3 destination to avoid IAM role complexity
        ec2.FlowLog(
            self,
            "VpcFlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(self.vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(vpc_flow_log_group),
            traffic_type=ec2.FlowLogTrafficType.REJECT,
        )
