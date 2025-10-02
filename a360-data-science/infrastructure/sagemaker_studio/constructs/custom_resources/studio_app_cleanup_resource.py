"""
Custom resource for cleaning up SageMaker Studio applications and spaces.

Provides a construct for safely deleting Studio applications, spaces, and user profiles
when SageMaker Studio domains or profiles are deleted.
"""

from aws_cdk import aws_iam as iam
from constructs import Construct

from .custom_resource_base import CustomResourceBase


class StudioAppCleanupResource(CustomResourceBase):
    """
    Custom resource for cleaning up Studio applications and spaces.

    This construct creates a custom resource that handles the safe deletion
    of Studio applications, spaces, and user profiles when the parent stack
    is deleted. It ensures that resources are deleted in the correct order,
    preventing deletion failures.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        domain_id: str,
        user_profile_name: str,
        space_name: str,
        **kwargs,
    ) -> None:
        """
        Initialize the Studio app cleanup custom resource.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            domain_id: SageMaker Studio domain ID
            user_profile_name: Name of the user profile to clean up
            space_name: Name of the space to clean up
            **kwargs: Additional arguments to pass to the parent construct
        """
        iam_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "sagemaker:ListApps",
                "sagemaker:ListSpaces",
                "sagemaker:DeleteApp",
                "sagemaker:DeleteSpace",
                "sagemaker:DeleteUserProfile",
                "sagemaker:DescribeUserProfile",
                "sagemaker:DescribeSpace",
                "sagemaker:DescribeApp",
            ],
            resources=["*"],
        )

        super().__init__(
            scope,
            construct_id,
            properties={
                "domain_id": domain_id,
                "user_profile_name": user_profile_name,
                "space_name": space_name,
            },
            lambda_file_path="studio_app_cleanup",
            iam_statements=[iam_policy],
            **kwargs,
        )
