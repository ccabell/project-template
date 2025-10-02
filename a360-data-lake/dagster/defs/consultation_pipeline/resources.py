"""Resources for consultation pipeline processing."""

import os

import boto3
from dagster import ConfigurableResource
from dagster_aws.s3 import S3Resource
from typing import Dict, Any

# Import LakeFS resource
try:
    from ..lakefs.resources import LakeFSResource
except ImportError:
    # Fallback if LakeFS resources not available
    LakeFSResource = None


class MacieResource(ConfigurableResource):
    """Resource for Amazon Macie PII detection services."""

    region_name: str = "us-east-1"

    def get_client(self):
        """Get Macie client."""
        return boto3.client("macie2", region_name=self.region_name)


class ComprehendMedicalResource(ConfigurableResource):
    """Resource for Amazon Comprehend Medical PHI detection."""

    region_name: str = "us-east-1"

    def get_client(self):
        """Get Comprehend Medical client."""
        return boto3.client("comprehendmedical", region_name=self.region_name)


class ConsultationPipelineResources:
    """Factory for consultation pipeline resources."""

    @staticmethod
    def get_resources() -> Dict[str, Any]:
        """Get all resources needed for consultation pipeline."""
        resources = {
            "s3": S3Resource(region_name="us-east-1"),
            "macie": MacieResource(region_name="us-east-1"),
            "comprehend_medical": ComprehendMedicalResource(region_name="us-east-1"),
            "bedrock": BedrockResource(region_name="us-east-1"),
        }

        # Add LakeFS resource if available  
        admin_arn = os.getenv("LAKEFS_ADMIN_SECRET_ARN")  
        if LakeFSResource and admin_arn:  
            resources["lakefs"] = LakeFSResource(  
                endpoint_url=os.getenv("LAKEFS_ENDPOINT_URL", "http://lakefs-internal.us-east-1.amazonaws.com:8000"),  
                admin_secret_arn=admin_arn,  
                region_name=os.getenv("AWS_REGION", "us-east-1"),  
            )  

        return resources


# Import from the existing AWS resources if they exist
try:
    from ..aws.resources import BedrockResource
except ImportError:
    # Fallback implementation if the resources don't exist yet
    class BedrockResource(ConfigurableResource):
        """Resource for Amazon Bedrock services."""

        region_name: str = "us-east-1"

        def get_client(self):
            """Get Bedrock client."""
            return boto3.client("bedrock-runtime", region_name=self.region_name)

        def invoke_model(self, model_id: str, body: str) -> Dict[str, Any]:
            """Invoke a Bedrock model."""
            import json

            client = self.get_client()
            response = client.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )

            return json.loads(response["body"].read())
