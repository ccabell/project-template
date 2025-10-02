"""Frontend stack for A360 Transcription Service Evaluator.

This stack creates S3 bucket for static website hosting with CloudFront distribution
following AWS best practices for React applications.
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3_deployment as s3deploy,
    RemovalPolicy,
    Duration,
)
from constructs import Construct


class FrontendStack(cdk.NestedStack):
    """Frontend infrastructure stack for React application."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_name: str,
        stage: str,
        api_gateway_url: str,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        self.app_name = app_name
        self.stage = stage
        self.api_gateway_url = api_gateway_url

        # Create S3 bucket for website hosting
        self.website_bucket = self._create_website_bucket()

        # Create CloudFront distribution
        self.distribution = self._create_cloudfront_distribution()

        # Deploy frontend build files to S3
        self._deploy_frontend_files()

        # Output the website URL
        self.website_url = f"https://{self.distribution.distribution_domain_name}"

    def _create_website_bucket(self) -> s3.Bucket:
        """Create S3 bucket for static website hosting."""
        bucket = s3.Bucket(
            self,
            "WebsiteBucket",
            bucket_name=f"{self.app_name.lower()}-{self.stage}-frontend-{cdk.Stack.of(self).account}",
            website_index_document="index.html",
            website_error_document="error.html",
            public_read_access=False,  # Will use CloudFront OAC
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY if self.stage != "prod" else RemovalPolicy.RETAIN,
            auto_delete_objects=self.stage != "prod",
            versioned=False,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteIncompleteMultipartUploads",
                    abort_incomplete_multipart_upload_after=Duration.days(7),
                    enabled=True,
                )
            ],
        )

        # Add tags
        cdk.Tags.of(bucket).add("Environment", self.stage)
        cdk.Tags.of(bucket).add("Application", self.app_name)
        cdk.Tags.of(bucket).add("Purpose", "Frontend")

        return bucket

    def _create_cloudfront_distribution(self) -> cloudfront.Distribution:
        """Create CloudFront distribution for the React app."""
        # S3 origin with OAI (simpler approach for CDK v2)
        oai = cloudfront.OriginAccessIdentity(
            self,
            "OAI",
            comment=f"OAI for {self.app_name} {self.stage} frontend",
        )

        # Grant CloudFront access to S3 bucket
        self.website_bucket.grant_read(oai)

        # S3 origin
        s3_origin = origins.S3BucketOrigin.with_origin_access_identity(
            bucket=self.website_bucket,
            origin_access_identity=oai,
        )

        # CloudFront distribution
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=s3_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5),
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5),
                ),
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,
            enabled=True,
            comment=f"{self.app_name} {self.stage} frontend distribution",
        )

        # Add tags
        cdk.Tags.of(distribution).add("Environment", self.stage)
        cdk.Tags.of(distribution).add("Application", self.app_name)
        cdk.Tags.of(distribution).add("Purpose", "Frontend")

        return distribution

    def _deploy_frontend_files(self) -> None:
        """Deploy React build files to S3 bucket."""
        s3deploy.BucketDeployment(
            self,
            "FrontendDeployment",
            sources=[s3deploy.Source.asset("../frontend/build")],
            destination_bucket=self.website_bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
            prune=True,
        )