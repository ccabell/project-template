"""
SageMaker Studio Stack for ML Operations.

This module defines a complete SageMaker Studio environment including domain
configuration, user profiles, lifecycle configurations, and security controls.
The stack provides a production-quality implementation that follows AWS best
practices while meeting organizational requirements for ML operations.
"""

import json
from typing import Any, Dict, List, Optional

import aws_cdk as cdk
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_lambda_python_alpha as _alambda
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sagemaker as sagemaker
from aws_cdk.custom_resources import Provider
from cdk_nag import NagPackSuppression, NagSuppressions
from constructs import Construct

from infrastructure.sagemaker_studio.constructs.custom_resources import (
    EfsCleanupResource,
    IdleShutdownLifecycleConfig,
    PackageInstallerLifecycleConfig,
    StudioAppCleanupResource,
)
from infrastructure.sagemaker_studio.constructs.networking.import_vpc import (
    VpcImportConstruct,
)
from infrastructure.sagemaker_studio.constructs.roles import (
    StudioDefaultRole,
    StudioUserRole,
)


class SagemakerStudioStack(Stack):
    """
    Creates a comprehensive SageMaker Studio environment for ML operations.

    This stack implements a production-ready SageMaker Studio environment with:
    - Domain configuration with VPC integration
    - User profile management with IAM roles
    - Package installation lifecycle configurations
    - Idle app shutdown automation
    - Resource cleanup mechanisms
    - Security controls and monitoring

    The implementation follows AWS best practices while maintaining required
    permissions for SageMaker Studio functionality. It handles CDK Nag
    suppressions for needed permissions with proper justification.

    Attributes:
        domain_id: ID of the created SageMaker Studio domain
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        domain_name: str,
        workspace_id: str,
        vpc_id: str,
        subnet_ids: Optional[List[str]] = None,
        subnet_group_name: Optional[str] = None,
        security_group_id: Optional[str] = None,
        config_file_path: str = "user_config.json",
        **kwargs: Any,
    ) -> None:
        """
        Initialize the SageMaker Studio stack.

        Creates a complete SageMaker Studio environment with necessary IAM roles,
        VPC configuration, and lifecycle management capabilities. Implements
        required security controls while maintaining SageMaker functionality.

        Args:
            scope: CDK app construct providing the scope for resource creation
            construct_id: Unique identifier for the stack within the CDK app
            domain_name: Name to assign to the SageMaker Studio domain
            workspace_id: Identifier for the workspace environment
            vpc_id: ID of VPC to use for Studio domain networking
            subnet_ids: Optional list of subnet IDs for domain networking. If not
                provided, will use private subnets from VPC construct.
            subnet_group_name: Optional subnet group name for VPC selection
            security_group_id: Optional ID of security group for user profiles. If not
                provided, will use security group from VPC construct.
            config_file_path: Path to JSON configuration file with user profiles
            **kwargs: Additional arguments passed to parent Stack constructor
        """
        super().__init__(scope, construct_id, **kwargs)

        self.config = self._load_configuration(config_file_path)

        vpc_construct = self._import_vpc(
            vpc_id=vpc_id, subnet_group_name=subnet_group_name
        )

        default_role = self._create_default_role(domain_name)
        user_role = self._create_user_role(domain_name)

        used_subnet_ids = subnet_ids if subnet_ids else vpc_construct.private_subnet_ids
        used_security_group_id = (
            security_group_id if security_group_id else vpc_construct.security_group_id
        )

        domain = self._create_studio_domain(
            domain_name=domain_name,
            role=default_role,
            vpc=vpc_construct.vpc,
            subnet_ids=used_subnet_ids,
        )

        self._create_user_profiles(
            self.config,
            domain=domain,
            workspace_id=workspace_id,
            security_group_id=used_security_group_id,
            role=user_role,
        )

        self._enable_sagemaker_projects(user_role)

        self._setup_lifecycle_configurations(domain.attr_domain_id)

        self._configure_resource_cleanup(
            domain_id=domain.attr_domain_id, efs_id=domain.attr_home_efs_file_system_id
        )

        self._add_stack_outputs(domain.attr_domain_id)

        self._apply_resource_tags(workspace_id)

        self._apply_security_suppressions()

        self._apply_resource_policies()

        self.domain_id = domain.attr_domain_id

    def _load_configuration(self, config_file_path: str) -> Dict[str, Any]:
        """
        Load configuration settings from JSON file.

        Reads the project configuration file containing user profiles and
        other settings needed for SageMaker Studio setup.

        Args:
            config_file_path: Path to configuration JSON file

        Returns:
            Dictionary containing configuration settings

        Raises:
            FileNotFoundError: If configuration file doesn't exist
            json.JSONDecodeError: If configuration file contains invalid JSON
        """
        with open(config_file_path) as file:
            return json.load(file)

    def _import_vpc(
        self, vpc_id: str, subnet_group_name: Optional[str] = None
    ) -> VpcImportConstruct:
        """
        Import an existing VPC for SageMaker Studio networking.

        Creates a VPC import construct with proper security group configuration
        and flow log setup for SageMaker Studio.

        Args:
            vpc_id: ID of the existing VPC to import
            subnet_group_name: Optional subnet group name for selection

        Returns:
            Configured VPC import construct ready for SageMaker Studio
        """
        return VpcImportConstruct(
            self,
            "VpcImport",
            vpc_id=vpc_id,
            subnet_group_name=subnet_group_name,
        )

    def _configure_vpc(self, vpc_id: str) -> ec2.IVpc:
        """
        Configure VPC for SageMaker Studio networking.

        Retrieves and configures an existing VPC for use with SageMaker Studio,
        ensuring proper network isolation and access control. This method imports
        an existing VPC rather than creating a new one, to integrate with existing
        infrastructure.

        Args:
            vpc_id: ID of existing VPC to use for configuration

        Returns:
            Configured VPC ready for SageMaker Studio deployment
        """
        return ec2.Vpc.from_lookup(self, "ExistingVPC", vpc_id=vpc_id)

    def _setup_vpc_flow_logs(self, vpc: ec2.IVpc) -> None:
        """
        Set up VPC flow logs with CloudWatch integration.

        Configures comprehensive network traffic logging for security
        monitoring and compliance:
        - Creates CloudWatch log group for flow logs
        - Sets up IAM role for flow log delivery
        - Enables flow logging for the VPC

        Args:
            vpc: VPC instance to configure flow logs for
        """
        flow_log_group = logs.LogGroup(self, "VpcFlowLogGroup")
        flow_log_role = iam.Role(
            self,
            "VpcFlowLogRole",
            assumed_by=iam.ServicePrincipal("vpc-flow-logs.amazonaws.com"),
        )

        ec2.FlowLog(
            self,
            "FlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(
                flow_log_group, flow_log_role
            ),
        )

    def _create_default_role(self, domain_name: str) -> StudioDefaultRole:
        """
        Create IAM role for SageMaker Studio with required permissions.

        Configures an IAM role for SageMaker Studio domain execution with:
        - SageMaker managed policy for core functionality
        - Bedrock access for AI model capabilities
        - S3 access for data storage
        - LakeFormation and CodeWhisperer permissions

        Args:
            domain_name: Name of the SageMaker Studio domain

        Returns:
            Configured IAM role for SageMaker Studio domain
        """
        return StudioDefaultRole(self, "StudioDefaultRole", domain_name=domain_name)

    def _create_user_role(self, domain_name: str) -> StudioUserRole:
        """
        Create IAM role for SageMaker Studio users with required permissions.

        Configures an IAM role for data scientists using SageMaker Studio with:
        - SageMaker resource creation capabilities
        - Bedrock access for AI model usage
        - S3 access for data storage
        - EC2 networking permissions

        Args:
            domain_name: Name of the SageMaker Studio domain

        Returns:
            Configured IAM role for SageMaker Studio users
        """
        return StudioUserRole(self, "StudioUserRole", domain_name=domain_name)

    def _create_studio_domain(
        self, domain_name: str, role: iam.Role, vpc: ec2.IVpc, subnet_ids: List[str]
    ) -> sagemaker.CfnDomain:
        """
        Create and configure a SageMaker Studio domain with enhanced features.

        Implements a production-ready SageMaker Studio environment with automatic
        resource management, Docker support, and optimized defaults. Configures
        idle instance shutdown, resource specifications, and security settings
        for cost-effective operation.

        Args:
            domain_name: Name to assign to the Studio domain
            role: IAM role providing execution permissions for the domain
            vpc: VPC for domain networking
            subnet_ids: List of subnet IDs for domain networking

        Returns:
            Configured SageMaker Studio domain resource
        """
        idle_settings = sagemaker.CfnDomain.IdleSettingsProperty(
            idle_timeout_in_minutes=120,
            lifecycle_management="ENABLED",
            max_idle_timeout_in_minutes=180,
            min_idle_timeout_in_minutes=60,
        )

        app_lifecycle_config = sagemaker.CfnDomain.AppLifecycleManagementProperty(
            idle_settings=idle_settings,
        )

        jupyter_lab_settings = sagemaker.CfnDomain.JupyterLabAppSettingsProperty(
            app_lifecycle_management=app_lifecycle_config,
            default_resource_spec=sagemaker.CfnDomain.ResourceSpecProperty(
                instance_type="ml.t3.medium"
            ),
        )

        kernel_gateway_settings = sagemaker.CfnDomain.KernelGatewayAppSettingsProperty(
            default_resource_spec=sagemaker.CfnDomain.ResourceSpecProperty(
                instance_type="ml.t3.medium"
            )
        )

        code_editor_settings = sagemaker.CfnDomain.CodeEditorAppSettingsProperty(
            app_lifecycle_management=app_lifecycle_config,
            default_resource_spec=sagemaker.CfnDomain.ResourceSpecProperty(
                instance_type="ml.t3.medium"
            ),
        )

        domain_settings = sagemaker.CfnDomain.DomainSettingsProperty(
            docker_settings=sagemaker.CfnDomain.DockerSettingsProperty(
                enable_docker_access="ENABLED"
            ),
        )

        sharing_settings = sagemaker.CfnDomain.SharingSettingsProperty(
            notebook_output_option="Allowed",
            s3_output_path=f"s3://{cdk.Fn.sub('sagemaker-${AWS::Region}-${AWS::AccountId}')}/notebooks/",
        )

        space_storage_settings = sagemaker.CfnDomain.DefaultSpaceStorageSettingsProperty(
            default_ebs_storage_settings=sagemaker.CfnDomain.DefaultEbsStorageSettingsProperty(
                default_ebs_volume_size_in_gb=100,
                maximum_ebs_volume_size_in_gb=200,
            )
        )

        user_settings = sagemaker.CfnDomain.UserSettingsProperty(
            execution_role=role.role_arn,
            jupyter_lab_app_settings=jupyter_lab_settings,
            kernel_gateway_app_settings=kernel_gateway_settings,
            code_editor_app_settings=code_editor_settings,
            studio_web_portal="ENABLED",
            default_landing_uri="studio::",
            sharing_settings=sharing_settings,
            space_storage_settings=space_storage_settings,
        )

        default_space_settings = sagemaker.CfnDomain.DefaultSpaceSettingsProperty(
            execution_role=role.role_arn,
            space_storage_settings=space_storage_settings,
        )

        return sagemaker.CfnDomain(
            self,
            "SageMakerDomain",
            auth_mode="IAM",
            domain_name=domain_name,
            domain_settings=domain_settings,
            default_user_settings=user_settings,
            default_space_settings=default_space_settings,
            subnet_ids=subnet_ids,
            vpc_id=vpc.vpc_id,
            app_network_access_type="PublicInternetOnly",
            tag_propagation="ENABLED",
        )

    def _create_user_profiles(
        self,
        variables: Dict[str, Any],
        domain: sagemaker.CfnDomain,
        workspace_id: str,
        security_group_id: str,
        role: iam.Role,
    ) -> None:
        """
        Create SageMaker user profiles from configuration.

        Sets up user profiles in the SageMaker Studio domain with:
        - Profile name configuration
        - Execution role assignment
        - Security group assignment
        - Private space creation for each user
        - Resource cleanup configuration
        - Dedicated team user with shared space for collaboration

        Args:
            variables: Configuration dictionary containing user profiles
            domain: SageMaker Studio domain to create profiles in
            workspace_id: Identifier for the workspace environment
            security_group_id: ID of security group for user profiles
            role: IAM role to assign to user profiles
        """
        user_ids = variables.get("SageMakerUserProfiles", [])

        team_profile_name = "a360-shared-user"
        team_profile = sagemaker.CfnUserProfile(
            self,
            "TeamProfile",
            domain_id=domain.attr_domain_id,
            user_profile_name=team_profile_name,
            user_settings=sagemaker.CfnUserProfile.UserSettingsProperty(
                execution_role=role.role_arn,
            ),
            tags=[
                cdk.CfnTag(key="workspace_id", value=workspace_id),
            ],
        )

        team_jupyterlab_space_name = "a360-shared-jupyterlab-space"
        team_jupyterlab_space = sagemaker.CfnSpace(
            self,
            "TeamJupyterLabSpace",
            domain_id=domain.attr_domain_id,
            space_name=team_jupyterlab_space_name,
            ownership_settings=sagemaker.CfnSpace.OwnershipSettingsProperty(
                owner_user_profile_name=team_profile.user_profile_name
            ),
            space_settings=sagemaker.CfnSpace.SpaceSettingsProperty(
                app_type="JupyterLab",
                jupyter_lab_app_settings=sagemaker.CfnSpace.SpaceJupyterLabAppSettingsProperty(
                    default_resource_spec=sagemaker.CfnSpace.ResourceSpecProperty(
                        instance_type="ml.t3.medium"
                    ),
                ),
            ),
            space_sharing_settings=sagemaker.CfnSpace.SpaceSharingSettingsProperty(
                sharing_type="Shared"
            ),
            tags=[
                cdk.CfnTag(key="user_id", value="a360-shared-user"),
                cdk.CfnTag(key="purpose", value="collaborative-development"),
                cdk.CfnTag(key="workspace_id", value=workspace_id),
            ],
        )

        team_jupyterlab_space.node.add_dependency(team_profile)

        team_jupyterlab_app_cleanup = StudioAppCleanupResource(
            self,
            "TeamJupyterLabAppCleanup",
            domain_id=domain.attr_domain_id,
            user_profile_name=team_profile_name,
            space_name=team_jupyterlab_space_name,
        )

        team_jupyterlab_app_cleanup.node.add_dependency(team_profile)

        for user_id in user_ids:
            user_profile_name = f"{user_id.lower()}"

            profile = sagemaker.CfnUserProfile(
                self,
                f"UserProfile{user_id}",  # Unique construct ID for each user
                domain_id=domain.attr_domain_id,
                user_profile_name=user_profile_name,
                user_settings=sagemaker.CfnUserProfile.UserSettingsProperty(
                    security_groups=[security_group_id],
                    execution_role=role.role_arn,
                ),
                tags=[
                    cdk.CfnTag(key="user_id", value=user_id),
                    cdk.CfnTag(key="workspace_id", value=workspace_id),
                ],
            )

    def _enable_sagemaker_projects(self, role: iam.Role) -> None:
        """
        Enable SageMaker Projects feature with custom resource.

        Configures SageMaker Projects support including:
        - Lambda function for setup
        - Service Catalog portfolio access
        - Custom resource provider

        Args:
            role: IAM role to associate with projects
        """
        enable_projects_lambda = _alambda.PythonFunction(
            self,
            "EnableProjectsFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            layers=[
                _lambda.LayerVersion.from_layer_version_arn(
                    self,
                    "PowertoolsLayerIsComplete",
                    cdk.Fn.sub(
                        "arn:aws:lambda:${AWS::Region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-arm64:7"
                    ),
                )
            ],
            entry="./infrastructure/sagemaker_studio/lambda/enable_sagemaker_projects/",
            handler="on_event_handler",
            timeout=cdk.Duration.seconds(120),
            current_version_options=_lambda.VersionOptions(
                removal_policy=cdk.RemovalPolicy.DESTROY,
                retry_attempts=0,
                description="Fixed version to avoid versioning issues",
                provisioned_concurrent_executions=0,
            ),
        )

        enable_projects_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sagemaker:EnableSagemakerServicecatalogPortfolio",
                    "servicecatalog:ListAcceptedPortfolioShares",
                    "servicecatalog:AssociatePrincipalWithPortfolio",
                    "servicecatalog:AcceptPortfolioShare",
                    "iam:GetRole",
                ],
                resources=["*"],
            )
        )

        provider = Provider(
            self,
            "ProjectsProvider",
            on_event_handler=enable_projects_lambda,
            log_retention=logs.RetentionDays.ONE_WEEK,
            provider_function_name=cdk.PhysicalName.GENERATE_IF_NEEDED,
        )

        cdk.CustomResource(
            self,
            "SageMakerProjects",
            service_token=provider.service_token,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            resource_type="Custom::EnableSageMakerProjects",
            properties={"iteration": "1", "ExecutionRoles": [role.role_arn]},
        )

    def _setup_lifecycle_configurations(self, domain_id: str) -> None:
        """
        Set up lifecycle configurations for the SageMaker Studio domain.

        Creates and attaches lifecycle configurations for:
        - Package installation in Studio environments
        - Automatic shutdown of idle applications

        Args:
            domain_id: ID of the SageMaker Studio domain
        """
        package_installer = PackageInstallerLifecycleConfig(
            self,
            "PackageInstaller",
            domain_id=domain_id,
        )

        idle_shutdown = IdleShutdownLifecycleConfig(
            self,
            "IdleShutdown",
            domain_id=domain_id,
        )

        idle_shutdown.node.add_dependency(package_installer)

    def _configure_resource_cleanup(self, domain_id: str, efs_id: str) -> None:
        """
        Configure resource cleanup for Studio domain termination.

        Sets up custom resources to handle proper cleanup of:
        - EFS filesystems and mount targets
        - Studio applications and spaces

        Args:
            domain_id: ID of the SageMaker Studio domain
            efs_id: ID of the EFS filesystem to clean up
        """
        EfsCleanupResource(
            self,
            "EfsCleanup",
            file_system_id=efs_id,
        )

    def _add_stack_outputs(self, domain_id: str) -> None:
        """
        Add CloudFormation outputs for cross-stack references.

        Creates outputs for:
        - SageMaker domain ID for reference by other stacks

        Args:
            domain_id: ID of the SageMaker Studio domain
        """
        CfnOutput(
            self,
            "DomainId",
            value=domain_id,
            description="SageMaker Studio Domain ID",
            export_name=f"{self.stack_name}-DomainId",
        )

    def _apply_resource_tags(self, workspace_id: str) -> None:
        """
        Apply tags to all resources in the stack.

        Args:
            workspace_id: Identifier for the workspace environment
        """
        cdk.Tags.of(self).add(key="workspace_id", value=workspace_id)

    def _apply_security_suppressions(self) -> None:
        """
        Apply CDK Nag suppressions for known policy exceptions.

        Suppresses security warnings for:
        - Managed AWS policies required for SageMaker
        - Lambda execution roles
        - Wildcards in IAM policies needed for SageMaker operation
        """
        NagSuppressions.add_stack_suppressions(
            stack=self,
            suppressions=[
                NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Managed AWS policies allowed for SageMaker Studio functionality",
                ),
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="Wildcards permission allowed for SageMaker resource operations",
                ),
                NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="CDK provisioned Lambda functions with latest Python runtime",
                ),
                NagPackSuppression(
                    id="AwsSolutions-SF1",
                    reason="CDK provisioned Step Functions for custom resources",
                ),
                NagPackSuppression(
                    id="AwsSolutions-SF2",
                    reason="X-Ray tracing not required for infrastructure management Step Functions",
                ),
            ],
        )

    def _apply_resource_policies(self) -> None:
        """
        Apply policies to resources to handle deployment and updates gracefully.

        Sets removal policies and update behaviors for Lambda resources
        to prevent version-related deployment issues.
        """

        for node in self.node.find_all():
            if isinstance(node, _lambda.Function):
                node.apply_removal_policy(cdk.RemovalPolicy.DESTROY)

                if hasattr(node, "current_version") and node.current_version:
                    node.current_version.apply_removal_policy(cdk.RemovalPolicy.DESTROY)

            if node.__class__.__name__ == "Provider":
                for child in node.node.children:
                    if isinstance(child, _lambda.Function):
                        child.apply_removal_policy(cdk.RemovalPolicy.DESTROY)
                        if hasattr(child, "current_version") and child.current_version:
                            child.current_version.apply_removal_policy(
                                cdk.RemovalPolicy.DESTROY
                            )
