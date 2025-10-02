"""ECS cluster and service infrastructure for Dagster+ agent deployment.

This module creates the core ECS infrastructure including cluster, task definitions,
and services for running the Dagster+ hybrid agent. Implements auto-scaling,
monitoring, and health checks for production reliability.
"""

from typing import Any, cast

import cdk_nag
from aws_cdk import Aspects, Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_servicediscovery as servicediscovery
from cdk_nag import NagSuppressions
from constructs import Construct

from .agent_config import AgentConfiguration
from .constants import (
    AGENT_COMMAND_TEMPLATE,
    AGENT_CPU,
    AGENT_MEMORY,
    DAGSTER_STACK_PREFIX,
    LOG_RETENTION_DAYS,
)
from .outputs import OutputManager


class EcsStack(Stack):
    """ECS infrastructure for Dagster+ agent deployment.

    Creates and manages ECS cluster, task definitions, and services required
    for running the Dagster+ agent. Includes health checks, auto-scaling,
    and monitoring configurations for production deployments.

    Attributes:
        vpc: VPC instance for resource deployment.
        cluster: ECS cluster for container orchestration.
        agent_log_group: CloudWatch log group for agent logs.
        agent_task_definition: Task definition for agent container.
        agent_service: ECS service running the agent.
        output_manager: Manager for consistent output creation.
    """

    vpc: ec2.IVpc
    cluster: ecs.Cluster
    agent_log_group: logs.LogGroup
    task_execution_role: iam.IRole
    agent_role: iam.IRole
    agent_task_definition: ecs.FargateTaskDefinition
    agent_service: ecs.FargateService
    output_manager: OutputManager

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        agent_security_group: ec2.ISecurityGroup,
        user_code_security_group: ec2.ISecurityGroup,
        namespace: servicediscovery.IPrivateDnsNamespace,
        agent_config: AgentConfiguration,
        **kwargs: Any,
    ) -> None:
        """Initialize ECS stack with required infrastructure components.

        Args:
            scope: CDK construct scope for resource creation.
            construct_id: Unique identifier for this stack.
            vpc: VPC instance for resource deployment.
            task_execution_role: IAM role for task execution.
            agent_role: IAM role for agent operations.
            user_code_role: IAM role for user code execution.
            agent_security_group: Security group for agent tasks.
            user_code_security_group: Security group for user code tasks.
            namespace: Service discovery namespace for code servers.
            agent_config: Agent configuration instance.
            **kwargs: Additional arguments passed to parent Stack.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.output_manager = OutputManager(self, self.stack_name)
        self.vpc = vpc
        self.agent_security_group = agent_security_group
        self.user_code_security_group = user_code_security_group
        self.namespace = namespace
        self.agent_config = agent_config

        self._create_cluster()
        self._create_log_group()
        self._create_task_execution_role()
        self._create_agent_role()
        self._create_agent_task_definition()
        self._create_agent_service()
        self._create_outputs()
        self._create_code_location_ecr_repo()
        self._configure_security_checks()

    def _configure_security_checks(self) -> None:
        """Configures security analysis and compliance rules for the infrastructure.

        Implements AWS Solutions security checks and necessary suppressions for the
        development environment. This includes:

        1. AWS Solutions security check aspects for comprehensive scanning
        2. IAM-related suppressions for Lake Formation integration
        3. Lambda validation suppressions for CloudFormation intrinsic functions
        """
        Aspects.of(self).add(cdk_nag.AwsSolutionsChecks())
        NagSuppressions.add_stack_suppressions(
            stack=self,
            suppressions=[
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lake Formation integration requires wildcard permissions",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS managed policies required for Lake Formation roles",
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Custom resource Lambda requires intrinsic functions",
                },
            ],
        )
        NagSuppressions.add_resource_suppressions(
            construct=self.agent_task_definition,
            suppressions=[
                {
                    "id": "AwsSolutions-ECS2",
                    "reason": "Dagster agent requires some pre-defined env vars for config/bootstrap.",
                },
            ],
        )
        NagSuppressions.add_resource_suppressions(
            construct=self.cluster,
            suppressions=[
                {
                    "id": "AwsSolutions-ECS4",
                    "reason": "ECS Cluster has to have `enhanced` Container Insights, not only enabled.",
                },
            ],
        )

    def _create_cluster(self) -> None:
        """Create ECS cluster with appropriate settings.

        Establishes cluster with container insights enabled for monitoring
        and configures default capacity provider strategy for Fargate.
        """
        self.cluster = ecs.Cluster(
            self,
            "Cluster",
            cluster_name=DAGSTER_STACK_PREFIX,
            vpc=self.vpc,
            container_insights_v2=ecs.ContainerInsights.ENHANCED,
            enable_fargate_capacity_providers=True,
        )

        self.cluster.add_default_capacity_provider_strategy(
            [ecs.CapacityProviderStrategy(capacity_provider="FARGATE", weight=1)],
        )

    def _create_log_group(self) -> None:
        """Create CloudWatch log group for agent and user code logs.

        Configures retention policy and removal behavior for cost
        optimization and compliance requirements.
        """
        self.agent_log_group = logs.LogGroup(
            self,
            "AgentLogGroup",
            log_group_name=f"/ecs/{DAGSTER_STACK_PREFIX}",
            retention=logs.RetentionDays(LOG_RETENTION_DAYS),
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _create_task_execution_role(self) -> None:
        """Create IAM role for ECS task execution.

        Configures basic task execution permissions including ECR access,
        CloudWatch logging, and Secrets Manager access for agent tokens.
        """
        self.task_execution_role = cast(
            "iam.IRole",
            iam.Role(
                self,
                "TaskExecutionRole",
                role_name=f"{DAGSTER_STACK_PREFIX}-task-execution-role",
                assumed_by=cast(
                    "iam.IPrincipal",
                    iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                ),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name(
                        "service-role/AmazonECSTaskExecutionRolePolicy",
                    ),
                ],
                inline_policies={
                    "SecretsManagerAccess": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=[
                                    "secretsmanager:GetSecretValue",
                                    "secretsmanager:DescribeSecret",
                                ],
                                resources=[
                                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:*",
                                ],
                            ),
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=[
                                    "secretsmanager:ListSecrets",
                                    "ecs:ListTagsForResource",
                                ],
                                resources=["*"],
                            ),
                        ],
                    ),
                },
            ),
        )

    def _create_agent_role(self) -> None:
        """Create IAM role for Dagster+ agent operations.

        Configures comprehensive permissions for ECS service management,
        data lake access, and VPC Lattice communication.
        """
        self.agent_role = cast(
            "iam.IRole",
            iam.Role(
                self,
                "AgentRole",
                role_name=f"{DAGSTER_STACK_PREFIX}-agent-role",
                assumed_by=cast(
                    "iam.IPrincipal",
                    iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                ),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name(
                        "AmazonS3ReadOnlyAccess",
                    ),
                    iam.ManagedPolicy.from_aws_managed_policy_name(
                        "AmazonAthenaFullAccess",
                    ),
                ],
                inline_policies={
                    "SecretsManagerAccess": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=[
                                    "secretsmanager:GetSecretValue",
                                    "secretsmanager:DescribeSecret",
                                ],
                                resources=[
                                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:*",
                                ],
                            ),
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=[
                                    "secretsmanager:ListSecrets",
                                    "ecs:ListTagsForResource",
                                ],
                                resources=["*"],
                            ),
                        ],
                    ),
                    "ECSServiceManagement": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=[
                                    "ecs:DescribeTaskDefinition",
                                ],
                                resources=["*"],
                            ),
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=[
                                    "ecs:RunTask",
                                    "ecs:StopTask",
                                    "ecs:DescribeTasks",
                                    "ecs:ListTasks",
                                    "ecs:RegisterTaskDefinition",
                                    "ecs:DeregisterTaskDefinition",
                                    "ecs:CreateService",
                                    "ecs:DeleteService",
                                    "ecs:DescribeServices",
                                    "ecs:ListServices",
                                    "ecs:UpdateService",
                                    "ecs:TagResource",
                                ],
                                resources=[
                                    self.cluster.cluster_arn,
                                    f"{self.cluster.cluster_arn}/*",
                                    f"arn:aws:ecs:{self.region}:{self.account}:task-definition/{DAGSTER_STACK_PREFIX}-*",
                                    f"arn:aws:ecs:{self.region}:{self.account}:service/{DAGSTER_STACK_PREFIX}/*",
                                    f"arn:aws:ecs:{self.region}:{self.account}:container-instance/{DAGSTER_STACK_PREFIX}/*",
                                    f"arn:aws:ecs:{self.region}:{self.account}:task/{DAGSTER_STACK_PREFIX}/*",
                                    # code location deployment prefixes
                                    f"arn:aws:ecs:{self.region}:{self.account}:task-definition/server_{self.agent_config.organization}_*",
                                    # launched run prefixes
                                    f"arn:aws:ecs:{self.region}:{self.account}:task-definition/dagsterrun_{self.agent_config.organization}_*",
                                ],
                            ),
                        ],
                    ),
                    "CloudWatchLogging": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=[
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents",
                                    "logs:GetLogEvents",
                                    "logs:DescribeLogGroups",
                                    "logs:DescribeLogStreams",
                                ],
                                resources=[
                                    self.agent_log_group.log_group_arn,
                                    f"{self.agent_log_group.log_group_arn}:*",
                                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/ecs/{DAGSTER_STACK_PREFIX}*",
                                ],
                            ),
                        ],
                    ),
                    "VPCLatticeAccess": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=[
                                    "vpc-lattice:GetService",
                                    "vpc-lattice:ListServices",
                                    "vpc-lattice:CreateTargetGroup",
                                    "vpc-lattice:GetTargetGroup",
                                    "vpc-lattice:ListTargetGroups",
                                    "vpc-lattice:RegisterTargets",
                                    "vpc-lattice:DeregisterTargets",
                                ],
                                resources=["*"],
                            ),
                        ],
                    ),
                    "EC2Access": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=[
                                    "ec2:DescribeRouteTables",
                                    "ec2:DescribeNetworkInterfaces",
                                    "ecs:ListAccountSettings",
                                    "tag:GetResources",
                                ],
                                resources=["*"],
                            ),
                        ],
                    ),
                    "BedrockAccess": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                effect=iam.Effect.ALLOW,
                                actions=[
                                    "bedrock:InvokeModel",
                                    "bedrock:InvokeModelWithResponseStream",
                                ],
                                resources=[
                                    f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0",
                                ]
                                +
                                # https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html
                                [
                                    f"arn:aws:bedrock:{region}::foundation-model/anthropic.claude-sonnet-4-20250514-v1:0"
                                    for region in (
                                        "us-west-2",
                                        "us-east-1",
                                        "us-east-2",
                                        "ap-northeast-1",
                                        "eu-west-1",
                                    )
                                ],
                            ),
                        ],
                    ),
                },
            ),
        )
        self.add_agent_service_discovery_permissions(self.namespace.namespace_arn)
        self.add_agent_datalake_permissions()
        self.grant_pass_role_for_user_code()

    def _create_code_location_ecr_repo(self) -> None:
        self.code_location_repo = ecr.Repository(
            self,
            "CodeLocationRepo",
            repository_name="dagster",
            image_scan_on_push=True,  # Optional: Enable vulnerability scans
            removal_policy=RemovalPolicy.DESTROY,  # Optional: Destroy on stack deletion
        )

        # Optional: Add lifecycle policy to clean up old images
        self.code_location_repo.add_lifecycle_rule(
            description="Expire untagged images after 30 days",
            tag_status=ecr.TagStatus.UNTAGGED,
            max_image_age=Duration.days(30),
        )

    def add_agent_datalake_permissions(self) -> None:
        """Create IAM role policy for user code execution.

        Configures permissions for data processing including S3 access,
        Athena queries, Glue operations, and Lake Formation governance.
        """
        user_code_policies = {
            "DataLakeAccess": iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:ListBucket",
                            "s3:GetBucketLocation",
                            "s3:GetBucketVersioning",
                        ],
                        resources=[
                            "arn:aws:s3:::a360-data-lake-*",
                            "arn:aws:s3:::a360-data-lake-*/*",
                        ],
                    ),
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "glue:GetDatabase",
                            "glue:GetDatabases",
                            "glue:GetTable",
                            "glue:GetTables",
                            "glue:GetPartition",
                            "glue:GetPartitions",
                            "glue:BatchCreatePartition",
                            "glue:BatchDeletePartition",
                            "glue:BatchUpdatePartition",
                        ],
                        resources=[
                            f"arn:aws:glue:{self.region}:{self.account}:catalog",
                            f"arn:aws:glue:{self.region}:{self.account}:database/a360_*",
                            f"arn:aws:glue:{self.region}:{self.account}:table/a360_*/*",
                        ],
                    ),
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "lakeformation:GetDataAccess",
                            "lakeformation:GrantPermissions",
                            "lakeformation:RevokePermissions",
                            "lakeformation:BatchGrantPermissions",
                            "lakeformation:BatchRevokePermissions",
                            "lakeformation:ListPermissions",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "kms:Decrypt",
                            "kms:DescribeKey",
                            "kms:GenerateDataKey",
                        ],
                        resources=[
                            f"arn:aws:kms:{self.region}:{self.account}:key/*",
                        ],
                        conditions={
                            "StringEquals": {
                                "kms:ViaService": [
                                    f"s3.{self.region}.amazonaws.com",
                                    f"glue.{self.region}.amazonaws.com",
                                ],
                            },
                        },
                    ),
                ],
            ),
            # needs improvement, align naming convention for easier scoping
            "PodcastMedallionStackAccess": iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:ListBucket",
                            "s3:GetBucketLocation",
                            "s3:GetBucketVersioning",
                        ],
                        resources=[
                            "arn:aws:s3:::a360-*-podcast-*",
                            "arn:aws:s3:::a360-*-podcast-*/*",
                        ],
                    ),
                ],
            ),
            "CloudWatchLogging": iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            "logs:DescribeLogGroups",
                            "logs:DescribeLogStreams",
                        ],
                        resources=[
                            f"arn:aws:logs:{self.region}:{self.account}:log-group:/ecs/{DAGSTER_STACK_PREFIX}*",
                        ],
                    ),
                ],
            ),
        }

        for policy_base_name, document in user_code_policies.items():
            self.agent_role.attach_inline_policy(
                iam.Policy(
                    self,
                    f"UserCode{policy_base_name}Policy",
                    document=document,
                ),
            )

    def add_agent_service_discovery_permissions(self, namespace_arn: str) -> None:
        """Add service discovery permissions to agent role.

        Args:
            namespace_arn: Service discovery namespace ARN.
        """
        service_discovery_policy = iam.Policy(
            self,
            "ServiceDiscoveryPolicy",
            policy_name=f"{DAGSTER_STACK_PREFIX}-service-discovery-policy",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "servicediscovery:CreateService",
                        "servicediscovery:DeleteService",
                        "servicediscovery:GetService",
                        "servicediscovery:ListServices",
                        "servicediscovery:RegisterInstance",
                        "servicediscovery:DeregisterInstance",
                        "servicediscovery:GetInstance",
                        "servicediscovery:ListInstances",
                        "servicediscovery:GetOperation",
                        "servicediscovery:GetNamespace",
                        "servicediscovery:TagResource",
                    ],
                    resources=[
                        namespace_arn,
                        f"{namespace_arn}/*",
                        f"arn:aws:servicediscovery:{self.region}:{self.account}:service/srv-*",
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "servicediscovery:ListTagsForResource",
                    ],
                    resources=[
                        f"arn:aws:servicediscovery:{self.region}:{self.account}:*/*",
                    ],
                ),
            ],
        )
        service_discovery_policy.attach_to_role(cast("iam.IRole", self.agent_role))

    def grant_pass_role_for_user_code(self) -> None:
        """Grant PassRole permission for user code execution."""
        pass_role_policy = iam.Policy(
            self,
            "PassRolePolicy",
            policy_name=f"{DAGSTER_STACK_PREFIX}-pass-role-policy",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["iam:PassRole"],
                    resources=[
                        self.get_agent_role_arn(),
                        self.get_task_execution_role_arn(),
                    ],
                    conditions={
                        "StringEquals": {
                            "iam:PassedToService": "ecs-tasks.amazonaws.com",
                        },
                    },
                ),
            ],
        )
        pass_role_policy.attach_to_role(cast("iam.IRole", self.agent_role))

    def _create_agent_task_definition(self) -> None:
        """Create task definition for Dagster+ agent container.

        Configures CPU, memory, environment variables, and health checks
        for the agent container. Includes secret management for tokens.
        """
        self.agent_task_definition = ecs.FargateTaskDefinition(
            self,
            "AgentTaskDefinition",
            family=f"{DAGSTER_STACK_PREFIX}-agent",
            cpu=int(AGENT_CPU),
            memory_limit_mib=int(AGENT_MEMORY),
            task_role=self.agent_role,
            execution_role=self.task_execution_role,
        )

        agent_secret = self.agent_config.get_agent_secret(self)

        subnet_ids = ",".join([subnet.subnet_id for subnet in self.vpc.private_subnets])

        environment_variables = self.agent_config.get_agent_environment_variables()

        self.agent_task_definition.add_container(
            "DagsterAgent",
            image=ecs.ContainerImage.from_registry(
                "docker.io/dagster/dagster-cloud-agent:latest",
            ),
            environment={env.name: env.value for env in environment_variables},
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="agent",
                log_group=self.agent_log_group,
            ),
            health_check=self.agent_config.get_health_check_config(),
            stop_timeout=Duration.seconds(120),
            entry_point=["/bin/sh", "-c"],
            command=[
                AGENT_COMMAND_TEMPLATE.format(
                    DagsterOrganization=self.agent_config.organization,
                    AgentToken=agent_secret.secret_value.to_string(),
                    DeploymentConfig=""
                    if self.agent_config.deployment != "prod"
                    else "deployment: prod",
                    EnableBranchDeployments=self.agent_config.enable_branch_deployments,
                    ConfigCluster=self.cluster.cluster_name,
                    ConfigSubnets=subnet_ids,
                    ConfigSecurityGroupIds=self.user_code_security_group.security_group_id,
                    ServiceDiscoveryNamespace=self.namespace.namespace_id,
                    TaskExecutionRoleArn=self.get_task_execution_role_arn(),
                    AgentRoleArn=self.get_agent_role_arn(),
                    AgentLogGroup=self.agent_log_group.log_group_name,
                    TaskLaunchType="FARGATE",
                    EnableZeroDowntimeDeploys=self.agent_config.enable_zero_downtime,
                    CodeServerMetricsEnabled=self.agent_config.user_code_metrics_enabled,
                    AgentMetricsEnabled=self.agent_config.metrics_enabled,
                ).strip(),
            ],
        )

    def _create_agent_service(self) -> None:
        """Create ECS service for running the Dagster+ agent.

        Configures service with appropriate deployment settings,
        health checks, and auto-scaling for reliability.
        """
        self.agent_service = ecs.FargateService(
            self,
            "AgentService",
            service_name=f"{DAGSTER_STACK_PREFIX}-agent",
            cluster=self.cluster,
            task_definition=self.agent_task_definition,
            desired_count=1,
            vpc_subnets=ec2.SubnetSelection(subnets=self.vpc.private_subnets),
            security_groups=[self.agent_security_group],
            max_healthy_percent=200 if self.agent_config.enable_zero_downtime else 100,
            min_healthy_percent=100 if self.agent_config.enable_zero_downtime else 0,
            circuit_breaker=ecs.DeploymentCircuitBreaker(enable=True, rollback=True),
        )

    def _create_outputs(self) -> None:
        """Create CloudFormation outputs for cross-stack references.

        Exports cluster, service, and configuration details for
        monitoring and integration with other stacks.
        """
        self.output_manager.add_output_with_ssm(
            "ClusterArn",
            self.cluster.cluster_arn,
            "ECS cluster ARN",
            "ECS-Cluster-ARN",
        )

        self.output_manager.add_output_with_ssm(
            "ClusterName",
            self.cluster.cluster_name,
            "ECS cluster name",
            "ECS-Cluster-Name",
        )

        self.output_manager.add_output_with_ssm(
            "ServiceArn",
            self.agent_service.service_arn,
            "Agent service ARN",
            "Agent-Service-ARN",
        )

        self.output_manager.add_output_with_ssm(
            "ServiceName",
            self.agent_service.service_name,
            "Agent service name",
            "Agent-Service-Name",
        )

        self.output_manager.add_output_with_ssm(
            "TaskDefinitionArn",
            self.agent_task_definition.task_definition_arn,
            "Agent task definition ARN",
            "Agent-Task-Definition-ARN",
        )

        self.output_manager.add_output_with_ssm(
            "LogGroupName",
            self.agent_log_group.log_group_name,
            "CloudWatch log group name",
            "Log-Group-Name",
        )

        self.output_manager.add_output_with_ssm(
            "TaskExecutionRoleArn",
            self.task_execution_role.role_arn,
            "Task execution role ARN",
            "Task-Execution-Role-ARN",
        )

        self.output_manager.add_output_with_ssm(
            "AgentRoleArn",
            self.agent_role.role_arn,
            "Agent role ARN",
            "Agent-Role-ARN",
        )

    def get_cluster_arn(self) -> str:
        """Get ECS cluster ARN for external references.

        Returns:
            ECS cluster ARN.
        """
        return self.cluster.cluster_arn

    def get_service_arn(self) -> str:
        """Get agent service ARN for monitoring.

        Returns:
            Agent service ARN.
        """
        return self.agent_service.service_arn

    def get_log_group_name(self) -> str:
        """Get CloudWatch log group name.

        Returns:
            Log group name for agent logs.
        """
        return self.agent_log_group.log_group_name

    def get_task_execution_role_arn(self) -> str:
        """Get task execution role ARN for ECS integration.

        Returns:
            Task execution role ARN.
        """
        return self.task_execution_role.role_arn

    def get_agent_role_arn(self) -> str:
        """Get agent role ARN for ECS integration.

        Returns:
            Agent role ARN.
        """
        return self.agent_role.role_arn
