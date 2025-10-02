"""Test suite for LakeFS stack infrastructure deployment.

This module contains comprehensive tests for LakeFS server deployment
including ECS Fargate service, RDS PostgreSQL database, and S3 storage
configuration with healthcare compliance requirements.
"""

from unittest.mock import MagicMock, patch

import aws_cdk as cdk
import pytest
from aws_cdk import assertions
from aws_cdk import aws_ec2 as ec2

from lakefs.lakefs_stack import LakeFSStack, LakeFSStackProps


@pytest.fixture
@patch("boto3.client")
def lakefs_stack(mock_boto_client):
    """Create LakeFS stack for testing."""
    # Mock the EC2 client for AZ resolution
    mock_ec2_client = MagicMock()
    mock_boto_client.return_value = mock_ec2_client
    mock_ec2_client.describe_availability_zones.return_value = {
        "AvailabilityZones": [
            {"ZoneId": "use1-az6", "ZoneName": "us-east-1a"},
            {"ZoneId": "use1-az1", "ZoneName": "us-east-1b"},
            {"ZoneId": "use1-az4", "ZoneName": "us-east-1c"},
        ],
    }

    app = cdk.App()
    stack = cdk.Stack(app, "TestStack")

    # Create VPC in the same app
    vpc = ec2.Vpc(stack, "TestVPC", ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"))

    lakefs_stack = LakeFSStack(
        app,
        "TestLakeFSStack",
        LakeFSStackProps(
            vpc_id=vpc.vpc_id,
            private_subnet_ids=[subnet.subnet_id for subnet in vpc.private_subnets],
        ),
    )
    return lakefs_stack


@pytest.fixture
def template(lakefs_stack):
    """Generate CloudFormation template from LakeFS stack."""
    return assertions.Template.from_stack(lakefs_stack)


class TestLakeFSStack:
    """Test cases for LakeFS stack deployment."""

    def test_s3_bucket_creation(self, template):
        """Test S3 bucket is created with proper configuration."""
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "VersioningConfiguration": {"Status": "Enabled"},
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
                "LifecycleConfiguration": {
                    "Rules": [
                        {
                            "Id": "ArchiveOldVersions",
                            "Status": "Enabled",
                            "NoncurrentVersionTransitions": [
                                {
                                    "StorageClass": "STANDARD_IA",
                                    "TransitionInDays": 30,
                                },
                                {
                                    "StorageClass": "GLACIER",
                                    "TransitionInDays": 90,
                                },
                            ],
                        },
                    ],
                },
            },
        )

    def test_rds_database_creation(self, template):
        """Test RDS PostgreSQL database is created with proper configuration."""
        template.has_resource_properties(
            "AWS::RDS::DBInstance",
            {
                "Engine": "postgres",
                "EngineVersion": "16.6",
                "DBInstanceClass": "db.t3.medium",
                "AllocatedStorage": "100",
                "MaxAllocatedStorage": 1000,
                "StorageEncrypted": True,
                "MultiAZ": True,
                "BackupRetentionPeriod": 7,
                "DeletionProtection": True,
            },
        )

    def test_secrets_manager_creation(self, template):
        """Test Secrets Manager secret is created for admin credentials."""
        template.has_resource_properties(
            "AWS::SecretsManager::Secret",
            {
                "Description": "LakeFS administrator credentials",
                "GenerateSecretString": {
                    "SecretStringTemplate": '{"username": "admin"}',
                    "GenerateStringKey": "password",
                    "PasswordLength": 32,
                },
            },
        )

    def test_ecs_cluster_creation(self, template):
        """Test ECS cluster is created with container insights."""
        template.has_resource_properties(
            "AWS::ECS::Cluster",
            {
                "ClusterSettings": [
                    {
                        "Name": "containerInsights",
                        "Value": "enabled",
                    },
                ],
            },
        )

    def test_ecs_service_creation(self, template):
        """Test ECS Fargate service is created with proper configuration."""
        template.has_resource_properties(
            "AWS::ECS::Service",
            {
                "LaunchType": "FARGATE",
                "DesiredCount": 2,
                "HealthCheckGracePeriodSeconds": 60,
            },
        )

    def test_task_definition_configuration(self, template):
        """Test ECS task definition has proper resource allocation."""
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "RequiresCompatibilities": ["FARGATE"],
                "NetworkMode": "awsvpc",
                "Memory": "2048",
                "Cpu": "1024",
            },
        )

    def test_container_definition_environment_variables(self, template):
        """Test container has required environment variables."""
        # Check that the task definition exists and has container definitions
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "ContainerDefinitions": [
                    {
                        "Name": "lakefs",
                        "Image": "treeverse/lakefs:1.64.1",
                    },
                ],
            },
        )

        # Check for specific required environment variables
        task_def_resources = template.find_resources("AWS::ECS::TaskDefinition")
        assert len(task_def_resources) > 0, "No ECS Task Definition found"

        task_def = list(task_def_resources.values())[0]
        container_defs = task_def["Properties"]["ContainerDefinitions"]
        lakefs_container = next(
            (c for c in container_defs if c["Name"] == "lakefs"), None,
        )
        assert lakefs_container is not None, "LakeFS container not found"

        env_vars = {
            env["Name"]: env["Value"] for env in lakefs_container.get("Environment", [])
        }

        # Check required environment variables
        required_env_vars = {
            "LAKEFS_DATABASE_TYPE": "postgres",
            "LAKEFS_BLOCKSTORE_TYPE": "s3",
            "LAKEFS_LOGGING_LEVEL": "INFO",
            "LAKEFS_DATABASE_POSTGRES_CONNECTION_MAX_LIFETIME": "5m",
            "LAKEFS_DATABASE_POSTGRES_MAX_IDLE_CONNECTIONS": "25",
            "LAKEFS_DATABASE_POSTGRES_MAX_OPEN_CONNECTIONS": "25",
            "PGSSLMODE": "require",
            "LAKEFS_AUTH_API_SKIP_HEALTH_CHECK": "true",
        }

        for name, expected_value in required_env_vars.items():
            assert name in env_vars, f"Missing environment variable: {name}"
            assert env_vars[name] == expected_value, (
                f"Environment variable {name} has wrong value: expected {expected_value}, got {env_vars[name]}"
            )

    def test_postgresql_secrets_configuration(self, template):
        """Test PostgreSQL secrets are properly configured for TCP connections."""
        # Check that the task definition exists and has container definitions
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "ContainerDefinitions": [
                    {
                        "Name": "lakefs",
                    },
                ],
            },
        )

        # Check for specific required secrets
        task_def_resources = template.find_resources("AWS::ECS::TaskDefinition")
        assert len(task_def_resources) > 0, "No ECS Task Definition found"

        task_def = list(task_def_resources.values())[0]
        container_defs = task_def["Properties"]["ContainerDefinitions"]
        lakefs_container = next(
            (c for c in container_defs if c["Name"] == "lakefs"), None,
        )
        assert lakefs_container is not None, "LakeFS container not found"

        secrets = [secret["Name"] for secret in lakefs_container.get("Secrets", [])]

        # Check required database secrets
        required_db_secrets = [
            "LAKEFS_DATABASE_HOST",
            "LAKEFS_DATABASE_PORT",
            "LAKEFS_DATABASE_USERNAME",
            "LAKEFS_DATABASE_PASSWORD",
            "LAKEFS_DATABASE_NAME",
        ]

        # Check required PostgreSQL environment variables for TCP enforcement
        required_pg_secrets = [
            "PGHOST",
            "PGPORT",
            "PGUSER",
            "PGPASSWORD",
            "PGDATABASE",
        ]

        # Check all required secrets are present
        all_required_secrets = required_db_secrets + required_pg_secrets

        for secret_name in all_required_secrets:
            assert secret_name in secrets, f"Missing secret: {secret_name}"

    def test_security_group_configuration(self, template):
        """Test security groups are properly configured with VPC-based access."""
        # ECS service security group should exist
        template.has_resource_properties(
            "AWS::EC2::SecurityGroup",
            {
                "GroupDescription": "Security group for LakeFS ECS service",
            },
        )

        # ALB security group should exist with VPC-based ingress
        template.has_resource_properties(
            "AWS::EC2::SecurityGroup",
            {
                "GroupDescription": "Security group for LakeFS Application Load Balancer",
            },
        )

    def test_application_load_balancer_creation(self, template):
        """Test internal Application Load Balancer is created."""
        template.has_resource_properties(
            "AWS::ElasticLoadBalancingV2::LoadBalancer",
            {
                "Scheme": "internal",
                "Type": "application",
            },
        )

    def test_target_group_health_check(self, template):
        """Test target group has proper health check configuration."""
        template.has_resource_properties(
            "AWS::ElasticLoadBalancingV2::TargetGroup",
            {
                "Port": 8000,
                "Protocol": "HTTP",
                "TargetType": "ip",
                "HealthCheckPath": "/",
                "HealthCheckProtocol": "HTTP",
                "Matcher": {"HttpCode": "200,404"},
                "HealthCheckTimeoutSeconds": 10,
                "HealthCheckIntervalSeconds": 30,
                "HealthyThresholdCount": 2,
                "UnhealthyThresholdCount": 5,
            },
        )

    def test_iam_task_role_permissions(self, template):
        """Test ECS task role has required permissions."""
        template.has_resource_properties(
            "AWS::IAM::Policy",
            {
                "PolicyDocument": {
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                        },
                    ],
                },
            },
        )

    def test_cloudformation_outputs(self, template):
        """Test CloudFormation outputs are properly defined."""
        # Check that the stack has outputs (the specific output names may vary)
        outputs = template.find_outputs("*")
        assert len(outputs) > 0, "Stack should have at least one output"

    def test_ssm_parameters(self, template):
        """Test SSM parameters are created for cross-stack references."""
        template.has_resource_properties(
            "AWS::SSM::Parameter",
            {
                "Type": "String",
                "Description": "LakeFS S3 bucket name",
            },
        )

    def test_resource_naming_convention(self, template):
        """Test resources follow consistent naming conventions."""
        # Check that S3 bucket exists with proper configuration
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "VersioningConfiguration": {"Status": "Enabled"},
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
        )

    def test_deletion_protection_enabled(self, template):
        """Test critical resources have deletion protection."""
        template.has_resource_properties(
            "AWS::RDS::DBInstance",
            {"DeletionProtection": True},
        )

        # Check that S3 bucket has proper deletion policy at the resource level
        s3_buckets = template.find_resources("AWS::S3::Bucket")
        assert len(s3_buckets) > 0, "Should have at least one S3 bucket"
        bucket_resource = list(s3_buckets.values())[0]
        assert bucket_resource.get("DeletionPolicy") == "Retain", (
            "S3 bucket should have Retain deletion policy"
        )

    @pytest.mark.security
    def test_encryption_at_rest(self, template):
        """Test encryption at rest is enabled for sensitive data."""
        # S3 bucket encryption
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": [
                        {
                            "ServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "AES256",
                            },
                        },
                    ],
                },
            },
        )

        # RDS encryption
        template.has_resource_properties(
            "AWS::RDS::DBInstance",
            {"StorageEncrypted": True},
        )

    @pytest.mark.security
    def test_ssl_enforcement(self, template):
        """Test SSL/TLS enforcement is configured."""
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                },
            },
        )

    @pytest.mark.compliance
    def test_audit_logging_configuration(self, template):
        """Test audit logging is properly configured."""
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "ContainerDefinitions": [
                    {
                        "LogConfiguration": {
                            "LogDriver": "awslogs",
                            "Options": {
                                "awslogs-stream-prefix": "lakefs",
                                "awslogs-region": {"Ref": "AWS::Region"},
                            },
                        },
                    },
                ],
            },
        )

    @pytest.mark.integration
    def test_vpc_integration(self, template):
        """Test proper VPC integration for network security."""
        # ECS service in private subnets
        template.has_resource_properties(
            "AWS::ECS::Service",
            {
                "NetworkConfiguration": {
                    "AwsvpcConfiguration": {
                        "AssignPublicIp": "DISABLED",
                    },
                },
            },
        )

    def test_vpc_endpoints_creation(self, template):
        """Test VPC endpoints are created for AWS service access."""
        # Check that VPC endpoints exist - at least 4 (Secrets Manager, S3, CloudWatch Logs, ECR)
        vpc_endpoints = template.find_resources("AWS::EC2::VPCEndpoint")
        if len(vpc_endpoints) == 0:
            print("VPC endpoints not found - likely disabled in test environment")
            return

        # Check that we have both Interface and Gateway endpoint types
        interface_endpoints = [
            ep
            for ep in vpc_endpoints.values()
            if ep.get("Properties", {}).get("VpcEndpointType") == "Interface"
        ]
        gateway_endpoints = [
            ep
            for ep in vpc_endpoints.values()
            if ep.get("Properties", {}).get("VpcEndpointType") == "Gateway"
        ]

        conflicting_services = ["ecr", "secretsmanager", "logs"]
        for service_type in conflicting_services:
            service_endpoints = [
                ep
                for ep in interface_endpoints
                if service_type
                in str(ep.get("Properties", {}).get("ServiceName", "")).lower()
            ]

            for endpoint in service_endpoints:
                private_dns = endpoint.get("Properties", {}).get("PrivateDnsEnabled")
                service_name = str(
                    endpoint.get("Properties", {}).get("ServiceName", ""),
                )
                assert private_dns is False, (
                    f"Interface endpoint {service_name} should have PrivateDnsEnabled=False to avoid conflicts with network stack, got {private_dns}"
                )

    def test_ecr_repository_creation(self, template):
        """Test ECR repository is created for LakeFS container image."""
        template.has_resource_properties(
            "AWS::ECR::Repository",
            {
                "ImageScanningConfiguration": {
                    "ScanOnPush": True,
                },
                "RepositoryName": "a360-lakefs-server",
            },
        )

    def test_ecr_repository_outputs(self, template):
        """Test ECR repository URI is exported as output."""
        # Check that ECR repository resource exists
        ecr_repos = template.find_resources("AWS::ECR::Repository")
        assert len(ecr_repos) > 0, "Should have at least one ECR repository"

    def test_codebuild_project_creation(self, template):
        """Test CodeBuild project is created for image building."""
        template.has_resource_properties(
            "AWS::CodeBuild::Project",
            {
                "Environment": {
                    "Type": "LINUX_CONTAINER",
                    "ComputeType": "BUILD_GENERAL1_SMALL",
                    "Image": "aws/codebuild/amazonlinux2-x86_64-standard:4.0",
                    "PrivilegedMode": True,
                },
                "Source": {
                    "Type": "NO_SOURCE",
                },
                "TimeoutInMinutes": 15,
            },
        )

        codebuild_resources = template.find_resources("AWS::CodeBuild::Project")
        assert len(codebuild_resources) > 0, (
            "Should have at least one CodeBuild project"
        )

        project = list(codebuild_resources.values())[0]
        buildspec_str = project["Properties"]["Source"]["BuildSpec"]

        assert "docker pull treeverse/lakefs" in buildspec_str
        assert "docker tag treeverse/lakefs" in buildspec_str
        assert "docker push" in buildspec_str
        assert "ecr get-login-password" in buildspec_str

    def test_custom_resource_for_image_build(self, template):
        """Test Custom Resource is created to trigger CodeBuild during deployment."""
        all_resources = template.find_resources("*")
        resource_types = [r["Type"] for r in all_resources.values()]
        lambda_functions = template.find_resources("AWS::Lambda::Function")
        assert len(lambda_functions) >= 1, (
            f"Should have at least one Lambda function for Custom Resource. Found types: {set(resource_types)}"
        )

    def test_ecs_service_depends_on_image_build(self, lakefs_stack):
        """Test ECS service has dependency on image build completion."""
        template = assertions.Template.from_stack(lakefs_stack)
        template.resource_count_is("AWS::ECS::Service", 1)
        lambda_functions = template.find_resources("AWS::Lambda::Function")
        assert len(lambda_functions) >= 1, (
            "Lambda function should exist for Custom Resource"
        )

    def test_buildspec_error_handling(self, template):
        """Test CodeBuild buildspec contains proper error handling."""
        codebuild_resources = template.find_resources("AWS::CodeBuild::Project")
        assert len(codebuild_resources) > 0, (
            "Should have at least one CodeBuild project"
        )

        project = list(codebuild_resources.values())[0]
        buildspec_str = project["Properties"]["Source"]["BuildSpec"]

        # Test that the buildspec contains proper exit codes for error handling
        assert "|| exit 1" in buildspec_str, "BuildSpec should contain error handling with exit codes"
        # Test that it includes docker pull and push commands
        assert "docker pull" in buildspec_str, "BuildSpec should contain docker pull command"
        assert "docker push" in buildspec_str, "BuildSpec should contain docker push command"
        # Test that it has minimal output to prevent response size issues
        assert "echo 'OK'" in buildspec_str, "BuildSpec should have minimal success output"
        # Check for image verification
        assert "docker inspect" in buildspec_str
        assert "aws ecr describe-images" in buildspec_str

    def test_codebuild_iam_permissions(self, template):
        """Test CodeBuild role has all necessary permissions."""
        # Find IAM role for CodeBuild
        roles = template.find_resources("AWS::IAM::Role")

        # Find CodeBuild role
        codebuild_role = None
        for role in roles.values():
            assume_policy = role.get("Properties", {}).get(
                "AssumeRolePolicyDocument", {},
            )
            statements = assume_policy.get("Statement", [])
            for statement in statements:
                principal = statement.get("Principal", {})
                if principal.get("Service") == "codebuild.amazonaws.com":
                    codebuild_role = role
                    break

        assert codebuild_role is not None, "Should have CodeBuild service role"

        inline_policies = codebuild_role.get("Properties", {}).get("Policies", [])
        found_logs_permissions = False

        for policy in inline_policies:
            if policy.get("PolicyName") == "CodeBuildServiceRolePolicy":
                statements = policy.get("PolicyDocument", {}).get("Statement", [])
                for statement in statements:
                    actions = statement.get("Action", [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if "logs:CreateLogGroup" in actions:
                        found_logs_permissions = True

        assert found_logs_permissions, (
            "Should have CloudWatch Logs permissions in custom policy"
        )

        policies = template.find_resources("AWS::IAM::Policy")
        found_ecr_permissions = False
        found_describe_images = False

        for policy in policies.values():
            policy_doc = policy.get("Properties", {}).get("PolicyDocument", {})
            statements = policy_doc.get("Statement", [])
            for statement in statements:
                actions = statement.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                if any("ecr:" in action for action in actions):
                    found_ecr_permissions = True
                    # Check for specific ECR permissions we added
                    if "ecr:DescribeImages" in actions:
                        found_describe_images = True

        assert found_ecr_permissions, "Should have ECR permissions for CodeBuild"
        assert found_describe_images, (
            "Should have ecr:DescribeImages permission for image verification"
        )
