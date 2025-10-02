"""
Custom resource for managing EFS filesystem cleanup.

Provides a construct for safely deleting EFS filesystems and mount targets
when SageMaker Studio domains are deleted.
"""

from aws_cdk import aws_iam as iam
from constructs import Construct

from .custom_resource_base import CustomResourceBase


class EfsCleanupResource(CustomResourceBase):
    """
    Custom resource for cleaning up EFS filesystems during stack deletion.

    This construct creates a custom resource that handles the safe deletion
    of EFS filesystems and mount targets when the parent stack is deleted.
    It ensures that mount targets are removed before attempting to delete
    the filesystem, preventing deletion failures.
    """

    def __init__(
        self, scope: Construct, construct_id: str, file_system_id: str, **kwargs
    ) -> None:
        """
        Initialize the EFS cleanup custom resource.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            file_system_id: ID of the EFS filesystem to manage
            **kwargs: Additional arguments to pass to the parent construct
        """
        iam_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "elasticfilesystem:DescribeFileSystems",
                "elasticfilesystem:DeleteFileSystem",
                "elasticfilesystem:DescribeMountTargets",
                "elasticfilesystem:DeleteMountTarget",
            ],
            resources=["*"],
        )

        super().__init__(
            scope,
            construct_id,
            properties={
                "fs_id": file_system_id,
            },
            lambda_file_path="efs_cleanup",
            iam_statements=[iam_policy],
            **kwargs,
        )
