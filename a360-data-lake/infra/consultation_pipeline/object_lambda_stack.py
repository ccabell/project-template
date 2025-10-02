"""Object Lambda stack for consultation redaction.

This module implements the S3 Object Lambda Access Points for PII/PHI redaction
that depend on resources from the ConsultationMedallionStack.
"""

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3objectlambda as s3ol
from constructs import Construct
from shared.lambda_constructs import PowertoolsLambdaConstruct


class ConsultationObjectLambdaStack(cdk.Stack):
    """CDK stack for S3 Object Lambda Access Points with redaction capabilities.

    This stack creates Object Lambda Access Points that depend on resources
    exported from the ConsultationMedallionStack, breaking the circular dependency.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str = "prod",
        medallion_stack_name: str,
        **kwargs,
    ) -> None:
        """Initialize the Object Lambda stack.

        Args:
            scope: CDK scope for this stack.
            construct_id: Unique identifier for this stack.
            env_name: Deployment environment (prod, staging, dev).
            medallion_stack_name: Name of the medallion stack to import from.
            **kwargs: Additional CDK stack arguments.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.medallion_stack_name = medallion_stack_name

        # Import resources from the medallion stack
        self._import_medallion_resources()

        # Create Object Lambda redactor function
        self._create_object_lambda_redactor()

        # Configure Object Lambda Access Points
        self._configure_object_lambda_access_points()

    def _import_medallion_resources(self) -> None:
        """Import resources exported from the medallion stack."""
        self.landing_bucket_name = cdk.Fn.import_value(
            f"ConsultationMedallion-{self.env_name}-LandingBucketName",
        )

        self.landing_bucket_arn = cdk.Fn.import_value(
            f"ConsultationMedallion-{self.env_name}-LandingBucketArn",
        )

    def _create_object_lambda_redactor(self) -> None:
        """Create the Lambda function for Object Lambda redaction."""
        self.object_lambda_redactor = PowertoolsLambdaConstruct(
            self,
            "ObjectLambdaRedactor",
            code_path="consultation_pipeline/lambda/object_lambda_redactor",
            service_name="consultation-object-redactor",
            namespace="ConsultationPipeline",
            memory_size=1024,
            timeout=cdk.Duration.minutes(5),
            s3_buckets=[self.landing_bucket_name],
            enable_comprehend_medical=False,
            enable_macie=False,
            environment={
                "LANDING_BUCKET": self.landing_bucket_name,
            },
        )

        # Add permissions for Object Lambda response writing
        self.object_lambda_redactor.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3-object-lambda:WriteGetObjectResponse"],
                resources=[
                    f"arn:aws:s3-object-lambda:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:accesspoint/a360-{self.env_name}-olap-basic",
                    f"arn:aws:s3-object-lambda:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:accesspoint/a360-{self.env_name}-olap-strict",
                ],
            ),
        )

    def _configure_object_lambda_access_points(self) -> None:
        """Configure S3 Object Lambda Access Points for basic and strict redaction."""
        # Create S3 Access Point on landing bucket
        self.access_point = s3.CfnAccessPoint(
            self,
            "LandingAccessPoint",
            bucket=self.landing_bucket_name,
            name=f"a360-{self.env_name}-landing-ap",
        )

        # Create Object Lambda Access Points for basic and strict redaction
        for level in ["basic", "strict"]:
            object_lambda_ap = s3ol.CfnAccessPoint(
                self,
                f"ObjectLambdaAP{level.title()}",
                name=f"a360-{self.env_name}-olap-{level}",
                object_lambda_configuration=s3ol.CfnAccessPoint.ObjectLambdaConfigurationProperty(
                    supporting_access_point=self.access_point.attr_arn,
                    cloud_watch_metrics_enabled=True,
                    transformation_configurations=[
                        s3ol.CfnAccessPoint.TransformationConfigurationProperty(
                            actions=["GetObject"],
                            content_transformation=s3ol.CfnAccessPoint.ContentTransformationProperty(
                                aws_lambda=s3ol.CfnAccessPoint.AwsLambdaProperty(
                                    function_arn=self.object_lambda_redactor.function.function_arn,
                                    function_payload=level,  # Pass the redaction level as payload
                                ),
                            ),
                        ),
                    ],
                ),
            )

            # Force the correct CloudFormation property names
            # The CDK construct generates 'awsLambda' but CloudFormation expects 'AwsLambda'
            object_lambda_ap.add_override(
                "Properties.ObjectLambdaConfiguration.TransformationConfigurations.0.ContentTransformation.AwsLambda",
                {
                    "FunctionArn": self.object_lambda_redactor.function.function_arn,
                    "FunctionPayload": level,
                },
            )

            # Remove the incorrect 'awsLambda' property
            object_lambda_ap.add_override(
                "Properties.ObjectLambdaConfiguration.TransformationConfigurations.0.ContentTransformation.awsLambda",
                None,
            )

            # Allow S3 Object Lambda to invoke the redactor function
            ap_name = f"a360-{self.env_name}-olap-{level}"
            self.object_lambda_redactor.function.add_permission(
                f"InvokeByS3ObjectLambda-{level}",
                principal=iam.ServicePrincipal("s3-object-lambda.amazonaws.com"),
                source_account=cdk.Aws.ACCOUNT_ID,
                source_arn=f"arn:aws:s3-object-lambda:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:accesspoint/{ap_name}",
            )

            # Export Object Lambda Access Point ARN
            cdk.CfnOutput(
                self,
                f"ObjectLambdaAP{level.title()}Arn",
                value=object_lambda_ap.attr_arn,
                export_name=f"ConsultationObjectLambda-{self.env_name}-{level.title()}ApArn",
            )
