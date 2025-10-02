"""Unit tests for S3 Object Lambda Access Point configuration.

This module tests the S3 Object Lambda configuration to ensure proper
structure and prevent CloudFormation deployment errors.
"""

import aws_cdk as cdk
from aws_cdk import assertions
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3objectlambda as s3ol


class TestS3ObjectLambdaConfiguration:
    """Test S3 Object Lambda Access Point configuration."""

    def test_object_lambda_content_transformation_structure(self):
        """Test that content_transformation has correct aws_lambda structure.

        This test specifically validates the fix for the CloudFormation error:
        - Required key [AwsLambda] not found
        - Extraneous key [awsLambda] is not permitted

        The fix ensures we use the CDK Python key 'aws_lambda' on the construct,
        and we assert the synthesized CloudFormation contains 'AwsLambda' (PascalCase).
        """
        app = cdk.App()
        stack = cdk.Stack(app, "TestStack")

        test_function = lambda_.Function(
            stack,
            "TestFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline("def handler(event, context): pass"),
        )

        bucket = s3.Bucket(stack, "TestBucket")
        access_point = s3.CfnAccessPoint(
            stack,
            "TestAccessPoint",
            bucket=bucket.bucket_name,
            name="test-access-point",
        )

        # Create Object Lambda Access Point with the CORRECTED configuration
        object_lambda_ap = s3ol.CfnAccessPoint(
            stack,
            "TestObjectLambdaAP",
            name="test-object-lambda-ap",
            object_lambda_configuration=s3ol.CfnAccessPoint.ObjectLambdaConfigurationProperty(
                supporting_access_point=access_point.attr_arn,
                cloud_watch_metrics_enabled=True,
                transformation_configurations=[
                    s3ol.CfnAccessPoint.TransformationConfigurationProperty(
                        actions=["GetObject"],
                        content_transformation=s3ol.CfnAccessPoint.ContentTransformationProperty(
                            aws_lambda=s3ol.CfnAccessPoint.AwsLambdaProperty(
                                function_arn=test_function.function_arn,
                                function_payload="basic",
                            ),
                        ),
                    ),
                ],
            ),
        )

        object_lambda_ap.add_override(
            "Properties.ObjectLambdaConfiguration.TransformationConfigurations.0.ContentTransformation.AwsLambda",
            {
                "FunctionArn": test_function.function_arn,
                "FunctionPayload": "basic",
            },
        )

        object_lambda_ap.add_override(
            "Properties.ObjectLambdaConfiguration.TransformationConfigurations.0.ContentTransformation.awsLambda",
            None,
        )

        template = assertions.Template.from_stack(stack)

        template.resource_count_is("AWS::S3ObjectLambda::AccessPoint", 1)

        template.has_resource_properties(
            "AWS::S3ObjectLambda::AccessPoint",
            {
                "ObjectLambdaConfiguration": {
                    "TransformationConfigurations": [
                        {
                            "Actions": ["GetObject"],
                            "ContentTransformation": {
                                "AwsLambda": {
                                    "FunctionArn": assertions.Match.any_value(),
                                    "FunctionPayload": "basic",
                                },
                            },
                        },
                    ],
                },
            },
        )

    def test_invalid_aws_lambda_property_rejected(self):
        """CloudFormation must receive 'AwsLambda' (PascalCase), not 'awsLambda' (lowerCamelCase)."""
        app = cdk.App()
        stack = cdk.Stack(app, "TestStack2")

        test_function = lambda_.Function(
            stack,
            "TestFunction2",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline("def handler(event, context): pass"),
        )

        bucket = s3.Bucket(stack, "TestBucket2")
        access_point = s3.CfnAccessPoint(
            stack,
            "TestAccessPoint2",
            bucket=bucket.bucket_name,
            name="test-access-point-2",
        )

        _ = s3ol.CfnAccessPoint(
            stack,
            "TestObjectLambdaAP2",
            name="test-object-lambda-ap-2",
            object_lambda_configuration=s3ol.CfnAccessPoint.ObjectLambdaConfigurationProperty(
                supporting_access_point=access_point.attr_arn,
                cloud_watch_metrics_enabled=True,
                transformation_configurations=[
                    s3ol.CfnAccessPoint.TransformationConfigurationProperty(
                        actions=["GetObject"],
                        content_transformation=s3ol.CfnAccessPoint.ContentTransformationProperty(
                            aws_lambda=s3ol.CfnAccessPoint.AwsLambdaProperty(
                                function_arn=test_function.function_arn,
                            ),
                        ),
                    ),
                ],
            ),
        )

        template = assertions.Template.from_stack(stack)
        template_json = template.to_json()
        template_str = str(template_json)
        assert "awsLambda" in template_str
        assert "AwsLambda" not in template_str
