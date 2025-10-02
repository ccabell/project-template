"""Module for common utility functions used across CDK stacks.

This module provides utility functions for retrieving Lambda layers,
loading configuration files, and accessing KMS keys and other AWS resources.
"""

import json
from pathlib import Path
from typing import Any

from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_ssm as ssm
from constructs import Construct


def get_powertools_layer(scope: Construct, region: str) -> lambda_.ILayerVersion:
    """Get the AWS Lambda Powertools layer for Python 3.12 on arm64.

    Args:
        scope: Construct scope for resource lookup.
        region: AWS region for layer ARN.

    Returns:
        The Lambda layer for AWS Powertools.
    """
    return lambda_.LayerVersion.from_layer_version_arn(
        scope,
        "PowertoolsLayer",
        f"arn:aws:lambda:{region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-arm64:7",
    )


def get_lambda_insights_layer(scope: Construct, region: str) -> lambda_.ILayerVersion:
    """Get the AWS Lambda Insights layer for arm64 architecture.

    Args:
        scope: Construct scope for resource lookup.
        region: AWS region for layer ARN.

    Returns:
        The Lambda layer for Lambda Insights.
    """
    return lambda_.LayerVersion.from_layer_version_arn(
        scope,
        "LambdaInsightsLayer",
        f"arn:aws:lambda:{region}:580247275435:layer:LambdaInsightsExtension-Arm64:22",
    )


def get_transcription_kms_key(scope: Construct, stage_prefix: str) -> kms.IKey:
    """Get KMS key for transcription encryption from SSM parameter.

    Args:
        scope: Construct scope for resource lookup.
        stage_prefix: Stage prefix for SSM parameter lookup.

    Returns:
        The KMS key for encryption.
    """
    transcription_kms_key_arn = ssm.StringParameter.from_string_parameter_attributes(
        scope,
        "TranscriptionKMSKeyArn",
        parameter_name=f"/{stage_prefix}Ae360Backend/TranscriptionKMSKeyArn",
    ).string_value

    return kms.Key.from_key_arn(scope, "TranscriptionKey", transcription_kms_key_arn)


def load_json_config(file_path: str, base_path: Path) -> dict[str, Any]:
    """Load JSON configuration from file relative to the base path.

    Args:
        file_path: Path to the JSON configuration file.
        base_path: Base directory to resolve the file path against.

    Returns:
        Dictionary containing the loaded JSON configuration.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    config_path = base_path / file_path
    with open(config_path) as f:
        return json.load(f)


def get_xray_policy() -> iam.PolicyStatement:
    """Get IAM policy statement for X-Ray permissions.

    Returns:
        PolicyStatement with X-Ray permissions.
    """
    return iam.PolicyStatement(
        actions=[
            "xray:PutTraceSegments",
            "xray:PutTelemetryRecords",
            "xray:GetSamplingRules",
            "xray:GetSamplingTargets",
            "xray:GetSamplingStatisticSummaries",
        ],
        resources=["*"],
    )
