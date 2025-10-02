"""
SageMaker Studio default role definition.

Provides an IAM role construct for the default execution role used by
SageMaker Studio domains and shared resources.
"""

from aws_cdk import aws_iam as iam
from constructs import Construct


class StudioDefaultRole(iam.Role):
    """
    Default execution role for SageMaker Studio domain.

    This role provides the necessary permissions for SageMaker Studio domain
    operations, including KMS encryption/decryption, CloudWatch logging,
    SageMaker API actions, and AWS Bedrock access required for Studio functionality.

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
        Initialize the SageMaker Studio default role.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            domain_name: Name of the SageMaker Studio domain
        """
        super().__init__(
            scope,
            construct_id,
            role_name=f"{domain_name}DefaultRole",
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
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSCloudFormationFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSCodePipeline_FullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerPipelinesIntegrations"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodeStarFullAccess"),
            ],
            inline_policies={
                "KmsEncryptionPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "kms:Get*",
                                "kms:Decrypt",
                                "kms:List*",
                                "kms:ReEncryptFrom",
                                "kms:Encrypt",
                                "kms:ReEncryptTo",
                                "kms:Describe",
                                "kms:GenerateDataKey",
                            ],
                            resources=["*"],
                            effect=iam.Effect.ALLOW,
                        ),
                    ]
                ),
                "LoggingPermissionsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "cloudwatch:Put*",
                                "cloudwatch:Get*",
                                "cloudwatch:List*",
                                "cloudwatch:DescribeAlarms",
                                "logs:Put*",
                                "logs:Get*",
                                "logs:List*",
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:ListLogDeliveries",
                                "logs:Describe*",
                                "logs:CreateLogDelivery",
                                "logs:PutResourcePolicy",
                                "logs:UpdateLogDelivery",
                            ],
                            resources=["*"],
                        ),
                    ]
                ),
                "SageMakerPermissionsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "sagemaker:Describe*",
                                "sagemaker:GetSearchSuggestions",
                                "sagemaker:List*",
                                "sagemaker:*App",
                                "sagemaker:Search",
                                "sagemaker:RenderUiTemplate",
                                "sagemaker:BatchGetMetrics",
                                "sagemaker:CreateSpace",
                                "sagemaker:UpdateSpace",
                                "sagemaker:DeleteSpace",
                                "ec2:DescribeDhcpOptions",
                                "ec2:DescribeNetworkInterfaces",
                                "ec2:DescribeRouteTables",
                                "ec2:DescribeSecurityGroups",
                                "ec2:DescribeSubnets",
                                "ec2:DescribeVpcEndpoints",
                                "ec2:DescribeVpcs",
                                "iam:ListRoles",
                            ],
                            resources=["*"],
                        ),
                    ]
                ),
                "LakeFormationPermissionsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "lakeformation:GetEffectivePermissionsForPath",
                                "lakeformation:ListPermissions",
                                "lakeformation:ListDataCellsFilter",
                                "lakeformation:GetDataCellsFilter",
                                "lakeformation:SearchDatabasesByLFTags",
                                "lakeformation:SearchTablesByLFTags",
                                "lakeformation:GetLFTag",
                                "lakeformation:ListLFTags",
                                "lakeformation:GetResourceLFTags",
                                "lakeformation:ListLakeFormationOptins",
                                "glue:GetDatabase",
                                "glue:GetDatabases",
                                "glue:GetConnections",
                                "glue:SearchTables",
                                "glue:GetTable",
                                "glue:GetTableVersions",
                                "glue:GetPartitions",
                                "glue:GetTables",
                                "glue:GetWorkflow",
                                "glue:ListWorkflows",
                                "glue:BatchGetWorkflows",
                                "glue:GetWorkflowRuns",
                                "glue:GetWorkflow",
                            ],
                            resources=["*"],
                        ),
                    ]
                ),
                "CodeWhispererPermissionsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "codewhisperer:GenerateRecommendations*",
                            ],
                            resources=["*"],
                        ),
                    ]
                ),
            },
        )
