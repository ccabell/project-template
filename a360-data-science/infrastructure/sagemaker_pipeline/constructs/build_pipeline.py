"""
Build Pipeline Construct for SageMaker ML Operations workflow.

This module defines the BuildPipelineConstruct class which establishes the infrastructure
for the model building pipeline including CodeCommit repository, CodeBuild project,
and CodePipeline for orchestration of the SageMaker model building process.
"""

from typing import Any

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_codebuild as cb
from aws_cdk import aws_codecommit as cc
from aws_cdk import aws_codepipeline as cp
from aws_cdk import aws_codepipeline_actions as cpactions
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from cdk_nag import NagSuppressions
from constructs import Construct


class BuildPipelineConstruct(Construct):
    """
    Construct for SageMaker model building pipeline infrastructure.

    This construct creates the necessary AWS resources for the model building
    pipeline, including:
    - CodeCommit repository for source code
    - S3 bucket for pipeline artifacts
    - CodeBuild project to execute pipeline code
    - CodePipeline to orchestrate the build process

    Attributes:
        project_role: IAM role for the pipeline project
        artifact_bucket: S3 bucket for storing pipeline artifacts
        repository: CodeCommit repository containing pipeline code
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        sm_pipeline_name: str,
        use_amt: str,
        access_logs_bucket: s3.Bucket,
        sm_model_deploy_lambda_arn: str,
        **kwargs: Any,
    ) -> None:
        """
        Initialize BuildPipelineConstruct.

        Args:
            scope: Parent construct
            construct_id: Unique identifier for this construct
            sm_pipeline_name: Name of the SageMaker pipeline
            use_amt: Flag indicating whether to use AMT (Asynchronous Inference)
            access_logs_bucket: S3 bucket for access logs
            sm_model_deploy_lambda_arn: ARN of the model deployment Lambda function
            **kwargs: Additional arguments to pass to the parent construct
        """
        super().__init__(scope, construct_id, **kwargs)

        stack_name = Stack.of(self).stack_name.lower()

        self.project_role = self._create_pipeline_role()
        self.repository = self._create_repository()
        pipeline_bucket = self._create_pipeline_bucket(access_logs_bucket)

        pipeline_encryption_key = self._create_pipeline_encryption_key()

        code_build_project = self._create_codebuild_project(
            sm_pipeline_name,
            pipeline_bucket,
            pipeline_encryption_key,
            use_amt,
            sm_model_deploy_lambda_arn,
        )

        artifact_bucket = self._create_artifact_bucket(access_logs_bucket)
        self.artifact_bucket = artifact_bucket

        self._create_pipeline(sm_pipeline_name, artifact_bucket, code_build_project)

        self._apply_nag_suppressions()

    def _create_pipeline_role(self) -> iam.Role:
        """
        Create IAM role for pipeline project.

        Returns:
            IAM Role with necessary permissions for pipeline execution
        """
        role = iam.Role(
            self,
            "ProjectRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("codebuild.amazonaws.com"),
                iam.ServicePrincipal("sagemaker.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSageMakerFullAccess"
                ),
            ],
        )
        return role

    def _create_repository(self) -> cc.Repository:
        """
        Create CodeCommit repository for pipeline code.

        Returns:
            CodeCommit repository containing pipeline code
        """
        repository = cc.Repository(
            self,
            "RegressionPipelineCode",
            repository_name="sm-pipeline-regression-code",
            description="SageMaker Model building workflow infrastructure as code for the Project",
            code=cc.Code.from_directory(
                "sagemaker_pipeline_deploy_manage_n_models_cdk/sm_pipeline_code/"
            ),
        )
        repository.grant_read(self.project_role)
        return repository

    def _create_pipeline_bucket(self, access_logs_bucket: s3.Bucket) -> s3.Bucket:
        """
        Create S3 bucket for pipeline artifacts.

        Args:
            access_logs_bucket: Bucket for storing access logs

        Returns:
            S3 bucket for pipeline artifacts
        """
        bucket = s3.Bucket(
            self,
            "PipelineBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            enforce_ssl=True,
            auto_delete_objects=True,
        )
        bucket.grant_read_write(self.project_role)
        return bucket

    def _create_pipeline_encryption_key(self) -> kms.Key:
        """
        Create KMS key for pipeline artifact encryption.

        Returns:
            KMS key for encryption
        """
        key = kms.Key(
            self,
            "PipelineEncryptionKey",
            alias="codepipeline/workload",
            description="Encryption key for workload codepipeline artifact_bucket",
            enabled=True,
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
        )
        return key

    def _create_codebuild_project(
        self,
        sm_pipeline_name: str,
        pipeline_bucket: s3.Bucket,
        pipeline_encryption_key: kms.Key,
        use_amt: str,
        sm_model_deploy_lambda_arn: str,
    ) -> cb.PipelineProject:
        """
        Create CodeBuild project for pipeline execution.

        Args:
            sm_pipeline_name: Name of the SageMaker pipeline
            pipeline_bucket: S3 bucket for pipeline artifacts
            pipeline_encryption_key: KMS key for encryption
            use_amt: Flag indicating whether to use AMT
            sm_model_deploy_lambda_arn: ARN of the model deployment Lambda function

        Returns:
            CodeBuild project for pipeline execution
        """
        project = cb.PipelineProject(
            self,
            "CBPipelineProject",
            project_name=f"{sm_pipeline_name}-modelbuild",
            description="Builds the model building workflow code repository, creates the SageMaker Pipeline",
            encryption_key=pipeline_encryption_key,
            role=self.project_role,
            environment_variables={
                "SM_PIPELINE_NAME": cb.BuildEnvironmentVariable(value=sm_pipeline_name),
                "ARTIFACT_BUCKET": cb.BuildEnvironmentVariable(
                    value=pipeline_bucket.bucket_name
                ),
                "SAGEMAKER_PIPELINE_ROLE_ARN": cb.BuildEnvironmentVariable(
                    value=self.project_role.role_arn
                ),
                "USE_AMT": cb.BuildEnvironmentVariable(value=use_amt),
                "SM_MODEL_DEPLOY_LAMBDA_ARN": cb.BuildEnvironmentVariable(
                    value=sm_model_deploy_lambda_arn
                ),
            },
            environment=cb.BuildEnvironment(
                build_image=cb.LinuxBuildImage.STANDARD_7_0,
                compute_type=cb.ComputeType.LARGE,
            ),
            build_spec=cb.BuildSpec.from_source_filename("buildspec.yml"),
            timeout=Duration.minutes(480),
        )
        return project

    def _create_artifact_bucket(self, access_logs_bucket: s3.Bucket) -> s3.Bucket:
        """
        Create S3 bucket for ML Ops artifacts.

        Args:
            access_logs_bucket: Bucket for storing access logs

        Returns:
            S3 bucket for ML Ops artifacts
        """
        bucket = s3.Bucket(
            self,
            "MlOpsArtifactsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            enforce_ssl=True,
            auto_delete_objects=True,
        )
        return bucket

    def _create_pipeline(
        self,
        sm_pipeline_name: str,
        artifact_bucket: s3.Bucket,
        code_build_project: cb.PipelineProject,
    ) -> cp.Pipeline:
        """
        Create CodePipeline for orchestration.

        Args:
            sm_pipeline_name: Name of the SageMaker pipeline
            artifact_bucket: S3 bucket for pipeline artifacts
            code_build_project: CodeBuild project for pipeline execution

        Returns:
            CodePipeline for orchestration
        """
        source_artifact = cp.Artifact()

        pipeline = cp.Pipeline(
            self,
            "Pipeline",
            artifact_bucket=artifact_bucket,
            pipeline_name=f"{sm_pipeline_name}-modelbuild",
            restart_execution_on_update=True,
            stages=[
                cp.StageProps(
                    stage_name="Source",
                    actions=[
                        cpactions.CodeCommitSourceAction(
                            action_name="WorkflowCode",
                            repository=self.repository,
                            output=source_artifact,
                            branch="main",
                        )
                    ],
                ),
                cp.StageProps(
                    stage_name="Build",
                    actions=[
                        cpactions.CodeBuildAction(
                            action_name="BuildAndCreateSageMakerPipeline",
                            input=source_artifact,
                            project=code_build_project,
                        )
                    ],
                ),
            ],
        )

        return pipeline

    def _apply_nag_suppressions(self) -> None:
        """
        Apply CDK Nag suppressions to resources.
        """
        NagSuppressions.add_resource_suppressions(
            self.project_role,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "SageMaker Project provider requires access to all indicies",
                }
            ],
            apply_to_children=True,
        )

        NagSuppressions.add_resource_suppressions(
            self.project_role,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Allowing AmazonSageMakerFullAccess as it is sample code, for production usecase scope down the permission",
                }
            ],
            apply_to_children=True,
        )
