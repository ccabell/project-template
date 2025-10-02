"""
SageMaker Pipeline Stack for ML Operations.

This module defines the SagemakerPipelineStack class which combines
the build and deploy constructs to create the complete infrastructure
for SageMaker ML Operations, including model building and deployment pipelines.
"""

import json
from typing import Any, Dict, cast

from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_iam as iam
from cdk_nag import NagSuppressions
from constructs import Construct

from infrastructure.sagemaker_pipeline.constructs.build_pipeline import (
    BuildPipelineConstruct,
)
from infrastructure.sagemaker_pipeline.constructs.deploy_pipeline import (
    DeployPipelineConstruct,
)


class SagemakerPipelineStack(Stack):
    """
    Stack for SageMaker MLOps pipeline infrastructure.

    This stack orchestrates the creation of multiple constructs to establish
    the complete SageMaker MLOps pipeline, including:
    - Model build pipeline
    - Model deployment pipeline
    - Access logging
    - IAM roles and policies

    The stack outputs key resource ARNs for cross-stack references.
    """

    @staticmethod
    def from_lookup(
        scope: Construct, id: str, stack_name: str
    ) -> "SagemakerPipelineStack":
        """
        References an existing SagemakerPipelineStack by name without recreating it.

        Args:
            scope: Parent construct
            id: Unique identifier for the reference
            stack_name: Name of the existing stack to reference

        Returns:
            Reference to the existing SagemakerPipelineStack
        """
        existing_stack_ref = Stack.of(scope).stack_name
        return cast(SagemakerPipelineStack, existing_stack_ref)

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        studio_resources: Dict[str, Any] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize SagemakerPipelineStack.

        Args:
            scope: Parent construct
            construct_id: Unique identifier for this stack
            studio_resources: Dictionary containing references to existing Studio resources
            **kwargs: Additional arguments to pass to the parent stack
        """
        super().__init__(scope, construct_id, **kwargs)

        with open("./examples/model_train_deploy_pipeline/project_config.json") as file:
            variables = json.load(file)

        sm_pipeline_name = variables["SageMakerPipelineName"]
        use_amt = variables["USE_AMT"]

        # Import existing roles from Studio setup if provided
        if studio_resources:
            default_role = iam.Role.from_role_name(
                self,
                "ImportedDefaultRole",
                role_name=studio_resources.get("default_role_name", ""),
            )

            data_scientist_role = iam.Role.from_role_name(
                self,
                "ImportedDataScientistRole",
                role_name=studio_resources.get("data_scientist_role_name", ""),
            )

        deploy_pipeline = DeployPipelineConstruct(self, "DeployPipeline")

        build_pipeline = BuildPipelineConstruct(
            self,
            "BuildPipeline",
            sm_pipeline_name=sm_pipeline_name,
            use_amt=use_amt,
            access_logs_bucket=deploy_pipeline.access_logs_bucket,
            sm_model_deploy_lambda_arn=deploy_pipeline.model_deploy_lambda.function_arn,
        )

        self._add_outputs(
            deploy_pipeline.access_logs_bucket.bucket_arn,
            build_pipeline.project_role.role_arn,
        )

        self._apply_nag_suppressions()

    def _add_outputs(
        self, access_logs_bucket_arn: str, pipeline_project_role_arn: str
    ) -> None:
        """
        Add CloudFormation outputs for cross-stack references.

        Args:
            access_logs_bucket_arn: ARN of the access logs bucket
            pipeline_project_role_arn: ARN of the pipeline project role
        """
        CfnOutput(
            self,
            "access_log_bucket_arn",
            export_name="accesslogbucketarn",
            value=access_logs_bucket_arn,
        )

        CfnOutput(
            self,
            "pipeline_project_role_arn",
            export_name="pipelineprojectrolearn",
            value=pipeline_project_role_arn,
        )

    def _apply_nag_suppressions(self) -> None:
        """
        Apply CDK Nag suppressions at stack level.
        """
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Lambda execution policy for custom resources created by higher level CDK constructs",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                    ],
                }
            ],
        )
