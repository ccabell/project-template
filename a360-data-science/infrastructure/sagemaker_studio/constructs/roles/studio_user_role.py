"""
SageMaker Studio user role definition.

Provides an IAM role construct for user-specific execution roles in
SageMaker Studio environments.
"""

from aws_cdk import aws_iam as iam
from constructs import Construct


class StudioUserRole(iam.Role):
    """
    Execution role for SageMaker Studio user profiles.

    This role provides the necessary permissions for data scientists and
    ML engineers working in SageMaker Studio, including access to S3, ability
    to create SageMaker resources, and EC2 networking permissions required
    for Studio functionality.

    Attributes:
        role_arn: ARN of the created IAM role.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        domain_name: str,
    ) -> None:
        """
        Initialize the SageMaker Studio user role.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            domain_name: Name of the SageMaker Studio domain
        """
        super().__init__(
            scope,
            construct_id,
            role_name=f"{domain_name}DataScientistRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("sagemaker.amazonaws.com")
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonBedrockFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3FullAccess"),
            ],
            inline_policies={
                "S3AccessPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["s3:List*", "s3:HeadBucket"],
                            resources=["*"],
                        ),
                    ]
                ),
                "SageMakerPassRolePolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["iam:PassRole"],
                            resources=["arn:aws:iam::*:role/*"],
                            conditions={
                                "StringEquals": {
                                    "iam:PassedToService": "sagemaker.amazonaws.com"
                                }
                            },
                        ),
                    ]
                ),
                "SageMakerResourceCreationPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sagemaker:Delete*",
                                "sagemaker:Stop*",
                                "sagemaker:Update*",
                                "sagemaker:Start*",
                                "sagemaker:Create*",
                                "sagemaker:DisassociateTrialComponent",
                                "sagemaker:AssociateTrialComponent",
                                "sagemaker:BatchPutMetrics",
                            ],
                            resources=["*"],
                            conditions={
                                "StringEquals": {
                                    "aws:PrincipalTag/workspace_id": "${sagemaker:ResourceTag/workspace_id}"
                                }
                            },
                        ),
                    ]
                ),
                "SageMakerPresignedUrlPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["sagemaker:CreatePresignedDomainUrl"],
                            resources=["*"],
                            conditions={
                                "StringEquals": {
                                    "sagemaker:ResourceTag/workspace_id": "${aws:PrincipalTag/workspace_id}"
                                }
                            },
                        ),
                    ]
                ),
                "SageMakerReadPermissionsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sagemaker:AddTags",
                                "sagemaker:InvokeEndpoint",
                                "sagemaker:CreateApp",
                                "sagemaker:Describe*",
                                "sagemaker:List*",
                            ],
                            resources=["*"],
                        ),
                    ]
                ),
                "KmsPermissionsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "kms:Get*",
                                "kms:Decrypt",
                                "kms:List*",
                                "kms:ReEncryptFrom",
                                "kms:GenerateDataKey",
                                "kms:Encrypt",
                                "kms:ReEncryptTo",
                                "kms:Describe*",
                            ],
                            resources=["*"],
                        ),
                    ]
                ),
                "NetworkPermissionsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "ec2:Describe*",
                                "ec2:CreateNetworkInterface",
                                "ec2:CreateNetworkInterfacePermission",
                                "ec2:CreateVpcEndpoint",
                                "ec2:DeleteNetworkInterface",
                                "ec2:DeleteNetworkInterfacePermission",
                                "ec2:AttachClassicLinkVpc",
                                "ec2:AcceptVpcPeeringConnection",
                                "ec2:DescribeVpcAttribute",
                                "ec2:AssociateVpcCidrBlock",
                            ],
                            resources=["*"],
                        ),
                    ]
                ),
                "SnsPermissionsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sns:CreateTopic",
                                "sns:DeleteTopic",
                                "sns:ListTopics",
                                "sns:Subscribe",
                                "sns:TagResource",
                            ],
                            resources=["*"],
                        ),
                    ]
                ),
            },
        )
