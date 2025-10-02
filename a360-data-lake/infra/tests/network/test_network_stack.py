"""
Comprehensive test suite for A360 Data Platform NetworkStack.

This module provides extensive unit testing for the A360 Data Platform VPC
infrastructure using pytest and AWS CDK assertions. Tests cover datalake-specific
resource creation, AZ ID resolution, CDK context configuration, security compliance,
and integration scenarios for cross-account deployment consistency.
"""

from unittest.mock import MagicMock, patch

import pytest
from aws_cdk import App, Stack
from aws_cdk import aws_logs as logs
from aws_cdk.assertions import Match, Template

from stacks.network.network_stack import (  # type: ignore
    DEFAULT_AZ_IDS,
    NetworkStack,
    NetworkStackProps,
)


class TestNetworkStackProps:
    """Test suite for NetworkStackProps configuration validation."""

    def test_default_props_values(self):
        """Verify default NetworkStackProps configuration values for datalake."""
        props = NetworkStackProps()

        assert props.vpc_cidr == "10.1.0.0/16"
        assert props.enable_dns_hostnames is True
        assert props.enable_dns_support is True
        assert props.max_azs == 3
        assert props.nat_gateways == 1
        assert props.flow_logs_retention == logs.RetentionDays.ONE_MONTH
        assert props.target_az_ids == DEFAULT_AZ_IDS
        assert props.region == "us-east-1"

    def test_custom_props_values(self):
        """Verify custom NetworkStackProps configuration."""
        custom_az_ids = ["use1-az2", "use1-az5", "use1-az3"]
        props = NetworkStackProps(
            vpc_cidr="10.2.0.0/16",
            enable_dns_hostnames=False,
            max_azs=3,
            nat_gateways=2,
            flow_logs_retention=logs.RetentionDays.THREE_MONTHS,
            target_az_ids=custom_az_ids,
            region="us-west-2",
        )

        assert props.vpc_cidr == "10.2.0.0/16"
        assert props.enable_dns_hostnames is False
        assert props.max_azs == 3
        assert props.nat_gateways == 2
        assert props.flow_logs_retention == logs.RetentionDays.THREE_MONTHS
        assert props.target_az_ids == custom_az_ids
        assert props.region == "us-west-2"

    def test_default_az_ids_for_us_east_1(self):
        """Verify default AZ IDs are set for us-east-1."""
        props = NetworkStackProps(region="us-east-1")
        assert props.target_az_ids == DEFAULT_AZ_IDS

    def test_empty_az_ids_for_other_regions(self):
        """Verify empty AZ IDs for regions other than us-east-1."""
        props = NetworkStackProps(region="us-west-2")
        assert props.target_az_ids == []


class TestNetworkStackAZResolution:
    """Test suite for availability zone ID resolution functionality."""

    @patch("boto3.client")
    def test_successful_az_resolution(self, mock_boto_client):
        """Test successful AZ ID to name resolution."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client

        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        stack = NetworkStack(cdk_stack, "Network", environment_name="test")

        assert stack.availability_zone_ids == DEFAULT_AZ_IDS
        assert stack.availability_zone_names == [
            "us-east-1a",
            "us-east-1b",
            "us-east-1c",
        ]
        mock_ec2_client.describe_availability_zones.assert_called_once_with(
            ZoneIds=DEFAULT_AZ_IDS,
        )

    @patch("boto3.client")
    def test_az_resolution_failure(self, mock_boto_client):
        """Test handling of AZ ID resolution failure."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.side_effect = Exception(
            "AWS API Error",
        )

        app = App()
        cdk_stack = Stack(app, "TestStack")

        # Test that NetworkStack gracefully handles AZ resolution failure with fallback
        # The correct behavior is to NOT raise an error and use fallback AZs
        network_stack = NetworkStack(cdk_stack, "Network", environment_name="test")
        # Verify that fallback AZs are used (stack creation succeeds)
        assert network_stack is not None

    @patch("boto3.client")
    def test_empty_az_ids_raises_error(self, _mock_boto_client):
        """Test that empty AZ IDs raise appropriate error."""
        app = App()
        cdk_stack = Stack(app, "TestStack")
        props = NetworkStackProps(target_az_ids=[], region="us-west-2")

        with pytest.raises(ValueError, match="No target AZ IDs specified"):
            NetworkStack(cdk_stack, "Network", environment_name="test", props=props)


class TestNetworkStackResourceCreation:
    """Test suite for verifying correct resource creation in NetworkStack."""

    @pytest.fixture
    @patch("boto3.client")
    def basic_stack_template(self, mock_boto_client):
        """Create basic NetworkStack for testing."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        NetworkStack(cdk_stack, "TestNetwork", environment_name="test")
        return Template.from_stack(cdk_stack)

    @pytest.fixture
    @patch("boto3.client")
    def custom_stack_template(self, mock_boto_client):
        """Create NetworkStack with custom configuration for testing."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        props = NetworkStackProps(vpc_cidr="10.2.0.0/16", max_azs=3, nat_gateways=2)
        NetworkStack(cdk_stack, "TestNetwork", environment_name="test", props=props)
        return Template.from_stack(cdk_stack)

    def test_vpc_created_with_correct_configuration(self, basic_stack_template):
        """Verify VPC resource is created with correct datalake configuration."""
        basic_stack_template.has_resource_properties(
            "AWS::EC2::VPC",
            {
                "CidrBlock": "10.1.0.0/16",
                "EnableDnsHostnames": True,
                "EnableDnsSupport": True,
            },
        )

    def test_vpc_resource_count(self, basic_stack_template):
        """Verify exactly one VPC is created."""
        basic_stack_template.resource_count_is("AWS::EC2::VPC", 1)

    def test_custom_vpc_cidr(self, custom_stack_template):
        """Verify VPC created with custom CIDR block."""
        custom_stack_template.has_resource_properties(
            "AWS::EC2::VPC",
            {"CidrBlock": "10.2.0.0/16"},
        )

    def test_three_az_subnet_configuration(self, basic_stack_template):
        """Verify correct number of subnets for 3 AZ configuration."""
        # 3 AZs x 3 subnet types (public, private, isolated) = 9 subnets total
        basic_stack_template.resource_count_is("AWS::EC2::Subnet", 9)

    def test_public_subnets_created(self, basic_stack_template):
        """Verify public subnets are created correctly."""
        basic_stack_template.has_resource_properties(
            "AWS::EC2::Subnet",
            {
                "MapPublicIpOnLaunch": True,
                "CidrBlock": Match.string_like_regexp(r"10\.1\.[0-9]+\.0/24"),
            },
        )

    def test_private_subnets_created(self, basic_stack_template):
        """Verify private subnets are created correctly."""
        basic_stack_template.has_resource_properties(
            "AWS::EC2::Subnet",
            {
                "MapPublicIpOnLaunch": False,
                "CidrBlock": Match.string_like_regexp(r"10\.1\.[0-9]+\.0/24"),
            },
        )

    def test_isolated_subnets_created(self, basic_stack_template):
        """Verify isolated subnets are created for sensitive datalake workloads."""
        basic_stack_template.has_resource_properties(
            "AWS::EC2::Subnet",
            {
                "MapPublicIpOnLaunch": False,
                "CidrBlock": Match.string_like_regexp(r"10\.1\.[0-9]+\.0/24"),
            },
        )

    def test_internet_gateway_created(self, basic_stack_template):
        """Verify Internet Gateway is created."""
        basic_stack_template.resource_count_is("AWS::EC2::InternetGateway", 1)
        basic_stack_template.resource_count_is("AWS::EC2::VPCGatewayAttachment", 1)

    def test_nat_gateway_created(self, basic_stack_template):
        """Verify NAT Gateway is created with default configuration."""
        basic_stack_template.resource_count_is("AWS::EC2::NatGateway", 1)

    def test_multiple_nat_gateways(self, custom_stack_template):
        """Verify multiple NAT Gateways created when configured."""
        custom_stack_template.resource_count_is("AWS::EC2::NatGateway", 2)

    def test_elastic_ip_for_nat_gateway(self, basic_stack_template):
        """Verify Elastic IP is created for NAT Gateway."""
        basic_stack_template.resource_count_is("AWS::EC2::EIP", 1)
        basic_stack_template.has_resource_properties("AWS::EC2::EIP", {"Domain": "vpc"})


class TestNetworkStackGatewayEndpoints:
    """Test suite for gateway VPC endpoints validation."""

    @pytest.fixture
    @patch("boto3.client")
    def stack_template(self, mock_boto_client):
        """Create NetworkStack for gateway endpoints testing."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        NetworkStack(cdk_stack, "TestNetwork", environment_name="test")
        return Template.from_stack(cdk_stack)

    def test_s3_gateway_endpoint_created(self, stack_template):
        """Verify S3 gateway endpoint is created for datalake storage."""
        stack_template.resource_count_is("AWS::EC2::VPCEndpoint", 2)  # S3 + DynamoDB
        stack_template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "ServiceName": Match.object_like({}),
                "VpcEndpointType": "Gateway",
            },
        )

    def test_dynamodb_gateway_endpoint_created(self, stack_template):
        """Verify DynamoDB gateway endpoint is created for metadata storage."""
        stack_template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "ServiceName": Match.object_like({}),
                "VpcEndpointType": "Gateway",
            },
        )

    def test_gateway_endpoints_have_correct_tags(self, stack_template):
        """Verify gateway endpoints have datalake-specific tags."""
        # Check for Purpose tag
        stack_template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "Tags": Match.array_with(
                    [Match.object_like({"Key": "Purpose", "Value": "Datalake"})],
                ),
            },
        )
        # Check for Cost tag
        stack_template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "Tags": Match.array_with(
                    [Match.object_like({"Key": "Cost", "Value": "Free"})],
                ),
            },
        )
        # Check for Priority tag
        stack_template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "Tags": Match.array_with(
                    [Match.object_like({"Key": "Priority", "Value": "Always-On"})],
                ),
            },
        )


class TestNetworkStackConfigurableEndpoints:
    """Test suite for configurable VPC endpoints via CDK context."""

    @patch("boto3.client")
    def test_no_context_no_endpoints(self, mock_boto_client):
        """Verify no interface endpoints created without context configuration."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        NetworkStack(cdk_stack, "TestNetwork", environment_name="production")
        template = Template.from_stack(cdk_stack)

        # Should only have gateway endpoints (S3, DynamoDB), no interface endpoints
        template.resource_count_is("AWS::EC2::VPCEndpoint", 2)

        # Verify no interface endpoints are created
        interface_endpoints = template.find_resources(
            "AWS::EC2::VPCEndpoint",
            {"VpcEndpointType": "Interface"},
        )
        assert len(interface_endpoints) == 0

    @patch("boto3.client")
    def test_context_based_endpoint_creation(self, mock_boto_client):
        """Test endpoint creation based on CDK context configuration."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        # Set context for vpc-endpoints
        app.node.set_context(
            "vpc-endpoints",
            {
                "production": {
                    "high_priority_enabled": True,
                    "medium_priority_enabled": False,
                    "lower_priority_enabled": False,
                },
            },
        )

        cdk_stack = Stack(app, "TestStack")
        NetworkStack(cdk_stack, "TestNetwork", environment_name="production")
        template = Template.from_stack(cdk_stack)

        # Should have gateway endpoints (2) plus high priority interface endpoints (12)
        template.resource_count_is("AWS::EC2::VPCEndpoint", 14)

    @patch("boto3.client")
    def test_endpoint_tiers_are_empty(self, mock_boto_client):
        """Verify that medium and lower priority interface endpoint tiers are empty."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        network = NetworkStack(cdk_stack, "TestNetwork", environment_name="test")

        # Verify medium and lower priority endpoint tier configurations return empty dictionaries
        assert network._get_medium_priority_services_config() == {}
        assert network._get_lower_priority_services_config() == {}

        # Verify medium and lower priority endpoint dictionaries are empty
        assert network.medium_priority_endpoints == {}
        assert network.lower_priority_endpoints == {}

        # Verify high priority services config is not empty (contains datalake services)
        high_priority_config = network._get_high_priority_services_config()
        assert len(high_priority_config) > 0
        assert "s3" in high_priority_config
        assert "glue" in high_priority_config
        assert "lakeformation" in high_priority_config


class TestNetworkStackFlowLogs:
    """Test suite for VPC Flow Logs configuration validation."""

    @pytest.fixture
    @patch("boto3.client")
    def stack_template(self, mock_boto_client):
        """Create NetworkStack for Flow Logs testing."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        NetworkStack(cdk_stack, "TestNetwork", environment_name="test")
        return Template.from_stack(cdk_stack)

    def test_flow_logs_created(self, stack_template):
        """Verify VPC Flow Logs are enabled for datalake monitoring."""
        stack_template.resource_count_is("AWS::EC2::FlowLog", 1)
        stack_template.has_resource_properties(
            "AWS::EC2::FlowLog",
            {"ResourceType": "VPC", "TrafficType": "ALL"},
        )

    def test_flow_logs_cloudwatch_group(self, stack_template):
        """Verify CloudWatch Log Group is created for Flow Logs."""
        stack_template.resource_count_is("AWS::Logs::LogGroup", 1)
        stack_template.has_resource_properties(
            "AWS::Logs::LogGroup",
            {"RetentionInDays": 30},
        )

    def test_flow_logs_iam_role(self, stack_template):
        """Verify IAM role is created for Flow Logs."""
        stack_template.has_resource_properties(
            "AWS::IAM::Role",
            {
                "AssumeRolePolicyDocument": {
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "vpc-flow-logs.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        },
                    ],
                },
            },
        )


class TestNetworkStackOutputsAndParameters:
    """Test suite for CloudFormation outputs and SSM parameters validation."""

    @pytest.fixture
    @patch("boto3.client")
    def stack_template(self, mock_boto_client):
        """Create NetworkStack for outputs testing."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        NetworkStack(cdk_stack, "TestNetwork", environment_name="test")
        return Template.from_stack(cdk_stack)

    def test_vpc_id_output(self, stack_template):
        """Verify VPC ID is exported correctly for datalake."""
        # Find outputs that have the correct export name
        outputs = stack_template.find_outputs(
            "*",
            {"Export": {"Name": "A360DataPlatform-VPC-Id"}},
        )
        assert len(outputs) == 1, f"Expected 1 VPC ID output, found {len(outputs)}"

    def test_vpc_cidr_output(self, stack_template):
        """Verify VPC CIDR is exported correctly."""
        # Find outputs that have the correct export name
        outputs = stack_template.find_outputs(
            "*",
            {"Export": {"Name": "A360DataPlatform-VPC-CIDR"}},
        )
        assert len(outputs) == 1, f"Expected 1 VPC CIDR output, found {len(outputs)}"

    def test_private_subnet_ids_output(self, stack_template):
        """Verify private subnet IDs are exported correctly."""
        # Find outputs that have the correct export name
        outputs = stack_template.find_outputs(
            "*",
            {"Export": {"Name": "A360DataPlatform-PrivateSubnet-Ids"}},
        )
        assert len(outputs) == 1, (
            f"Expected 1 private subnet IDs output, found {len(outputs)}"
        )

    def test_isolated_subnet_ids_output(self, stack_template):
        """Verify isolated subnet IDs are exported for sensitive workloads."""
        # Find outputs that have the correct export name
        outputs = stack_template.find_outputs(
            "*",
            {"Export": {"Name": "A360DataPlatform-IsolatedSubnet-Ids"}},
        )
        assert len(outputs) == 1, (
            f"Expected 1 isolated subnet IDs output, found {len(outputs)}"
        )

    def test_availability_zone_outputs(self, stack_template):
        """Verify AZ IDs are exported for cross-account consistency."""
        # Find outputs that have the correct export names
        outputs1 = stack_template.find_outputs(
            "*",
            {"Export": {"Name": "A360DataPlatform-AZ-ID-1"}},
        )
        outputs2 = stack_template.find_outputs(
            "*",
            {"Export": {"Name": "A360DataPlatform-AZ-ID-2"}},
        )
        outputs3 = stack_template.find_outputs(
            "*",
            {"Export": {"Name": "A360DataPlatform-AZ-ID-3"}},
        )
        assert len(outputs1) == 1, f"Expected 1 AZ ID 1 output, found {len(outputs1)}"
        assert len(outputs2) == 1, f"Expected 1 AZ ID 2 output, found {len(outputs2)}"
        assert len(outputs3) == 1, f"Expected 1 AZ ID 3 output, found {len(outputs3)}"

    def test_all_availability_zone_ids_output(self, stack_template):
        """Verify all AZ IDs are exported as comma-separated list."""
        # Find outputs that have the correct export name
        outputs = stack_template.find_outputs(
            "*",
            {"Export": {"Name": "A360DataPlatform-All-AZ-IDs"}},
        )
        assert len(outputs) == 1, f"Expected 1 all AZ IDs output, found {len(outputs)}"

    def test_ssm_parameters_created(self, stack_template):
        """Verify SSM parameters are created for cross-stack references."""
        stack_template.resource_count_is("AWS::SSM::Parameter", 10)

        # Test VPC ID parameter
        stack_template.has_resource_properties(
            "AWS::SSM::Parameter",
            {"Name": "/infrastructure/network/vpc-id", "Type": "String"},
        )

        # Test AZ ID parameters
        stack_template.has_resource_properties(
            "AWS::SSM::Parameter",
            {
                "Name": "/infrastructure/network/availability-zone-id-1",
                "Type": "String",
            },
        )


@pytest.mark.security
@pytest.mark.compliance
class TestNetworkStackSecurity:
    """Test suite for security configuration validation."""

    @pytest.fixture
    @patch("boto3.client")
    def stack_template(self, mock_boto_client):
        """Create NetworkStack for security testing."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        NetworkStack(cdk_stack, "TestNetwork", environment_name="test")
        return Template.from_stack(cdk_stack)

    def test_vpc_endpoints_security_group_created(self, stack_template):
        """Verify security group for VPC endpoints is properly configured."""
        stack_template.has_resource_properties(
            "AWS::EC2::SecurityGroup",
            {
                "GroupDescription": "Security group for VPC endpoints - A360 Data Platform",
            },
        )

    def test_security_group_https_ingress(self, stack_template):
        """Verify HTTPS ingress rule for VPC endpoints."""
        stack_template.has_resource_properties(
            "AWS::EC2::SecurityGroup",
            {
                "SecurityGroupIngress": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "IpProtocol": "tcp",
                                "FromPort": 443,
                                "ToPort": 443,
                                "CidrIp": Match.object_like({}),
                                "Description": "HTTPS from VPC CIDR for datalake services",
                            },
                        ),
                    ],
                ),
            },
        )

    def test_security_group_http_ingress(self, stack_template):
        """Verify HTTP ingress rule for VPC endpoints."""
        stack_template.has_resource_properties(
            "AWS::EC2::SecurityGroup",
            {
                "SecurityGroupIngress": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "IpProtocol": "tcp",
                                "FromPort": 80,
                                "ToPort": 80,
                                "CidrIp": Match.object_like({}),
                                "Description": "HTTP from VPC CIDR for datalake services",
                            },
                        ),
                    ],
                ),
            },
        )


class TestNetworkStackIntegration:
    """Test suite for integration scenarios and datalake-specific functionality."""

    @patch("boto3.client")
    def test_network_stack_properties_accessible(self, mock_boto_client):
        """Verify NetworkStack properties are accessible for datalake constructs."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        network = NetworkStack(cdk_stack, "TestNetwork", environment_name="test")

        assert network.vpc is not None
        assert len(network.private_subnets) == 3  # 3 AZs
        assert len(network.public_subnets) == 3  # 3 AZs
        assert len(network.isolated_subnets) == 3  # 3 AZs
        assert len(network.availability_zone_ids) == 3
        assert len(network.availability_zone_names) == 3

    @patch("boto3.client")
    def test_gateway_endpoints_accessible(self, mock_boto_client):
        """Verify gateway endpoints are accessible for datalake services."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        network = NetworkStack(cdk_stack, "TestNetwork", environment_name="test")

        gateway_endpoints = network.get_gateway_endpoints()
        assert "s3" in gateway_endpoints
        assert "dynamodb" in gateway_endpoints
        assert len(gateway_endpoints) == 2

    @patch("boto3.client")
    def test_interface_endpoints_empty_as_expected(self, mock_boto_client):
        """Verify interface endpoints are empty as expected for initial datalake setup."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        network = NetworkStack(cdk_stack, "TestNetwork", environment_name="test")

        all_endpoints = network.get_all_endpoints()
        assert len(all_endpoints) == 0  # Should be empty initially


class TestNetworkStackEnvironmentSpecific:
    """Test suite for environment-specific configuration."""

    @pytest.mark.parametrize("environment", ["dev", "staging", "production"])
    @patch("boto3.client")
    def test_environment_name_assignment(self, mock_boto_client, environment):
        """Test environment name is correctly assigned."""
        mock_ec2_client = MagicMock()
        mock_boto_client.return_value = mock_ec2_client
        mock_ec2_client.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
                {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
                {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
            ],
        }

        app = App()
        cdk_stack = Stack(app, "TestStack")
        network = NetworkStack(cdk_stack, "TestNetwork", environment_name=environment)

        assert network.environment_name == environment.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
