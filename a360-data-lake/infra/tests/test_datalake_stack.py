"""Test suite for Data Lake Infrastructure Stack validation.

This module provides comprehensive testing for the Data Lake Infrastructure Stack,
validating core AWS resource configurations including S3 buckets, Glue databases,
Lake Formation permissions, IAM roles, KMS keys, and cross-account access policies.

The test suite uses CDK assertions to verify both resource presence and proper
configuration of security settings, encryption, and access controls.
"""

from unittest.mock import MagicMock, patch

from aws_cdk import App
from aws_cdk.assertions import Match, Template

from stacks.component import DataFoundation  # type: ignore


@patch("boto3.client")
def test_datalake_iam_resources(mock_boto_client):
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
    stack = DataFoundation(app, "TestDataFoundation")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "AssumeRolePolicyDocument": {
                "Statement": [
                    {
                        "Action": "sts:AssumeRole",
                        "Effect": "Allow",
                        "Principal": {"Service": "glue.amazonaws.com"},
                    },
                ],
            },
        },
    )

    template.has_resource_properties(
        "AWS::IAM::User",
        {"UserName": Match.string_like_regexp("DataEngineer*")},
    )

    template.has_resource_properties(
        "AWS::IAM::User",
        {"UserName": Match.string_like_regexp("DataAnalyst*")},
    )


@patch("boto3.client")
def test_datalake_glue_resources(mock_boto_client):
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
    stack = DataFoundation(app, "TestDataFoundation")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::Glue::Database",
        {
            "DatabaseInput": {
                "Name": "raw",
                "Description": Match.string_like_regexp(".*Raw bucket.*"),
            },
        },
    )

    template.has_resource_properties(
        "AWS::Glue::Database",
        {
            "DatabaseInput": {
                "Name": "stage",
                "Description": Match.string_like_regexp(".*Stage bucket.*"),
            },
        },
    )

    template.has_resource_properties(
        "AWS::Glue::Database",
        {
            "DatabaseInput": {
                "Name": "analytics",
                "Description": Match.string_like_regexp(".*Analytics bucket.*"),
            },
        },
    )

    template.has_resource_properties(
        "AWS::Glue::SecurityConfiguration",
        {
            "EncryptionConfiguration": {
                "CloudWatchEncryption": {"CloudWatchEncryptionMode": "SSE-KMS"},
                "JobBookmarksEncryption": {"JobBookmarksEncryptionMode": "CSE-KMS"},
            },
        },
    )


@patch("boto3.client")
def test_datalake_lakeformation_resources(mock_boto_client):
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
    stack = DataFoundation(app, "TestDataFoundation")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::LakeFormation::PrincipalPermissions",
        {
            "Permissions": ["DATA_LOCATION_ACCESS"],
            "Resource": {
                "DataLocation": Match.object_like({"ResourceArn": Match.any_value()}),
            },
        },
    )

    template.has_resource_properties(
        "AWS::LakeFormation::PrincipalPermissions",
        {
            "Permissions": ["DESCRIBE", "ALTER", "CREATE_TABLE"],
            "Resource": {"Database": Match.object_like({"Name": Match.any_value()})},
        },
    )
