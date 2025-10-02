"""Configuration constants for Dagster+ agent deployment.

This module defines constants that define some deployment parameters
in the Dagster+ hybrid agent deployment.
"""

from aws_cdk import aws_logs as logs

AGENT_CPU: str = "256"
AGENT_MEMORY: str = "1024"
AGENT_COMMAND_TEMPLATE: str = """/bin/bash -c "mkdir -p $DAGSTER_HOME && echo '
instance_class:
  module: dagster_cloud
  class: DagsterCloudAgentInstance

dagster_cloud_api:
  url: "https://{DagsterOrganization}.agent.dagster.cloud"
  agent_token: "{AgentToken}"
  {DeploymentConfig}
  branch_deployments: {EnableBranchDeployments}

user_code_launcher:
  module: dagster_cloud.workspace.ecs
  class: EcsUserCodeLauncher
  config:
    cluster: {ConfigCluster}
    subnets: [{ConfigSubnets}]
    security_group_ids: [{ConfigSecurityGroupIds}]
    service_discovery_namespace_id: {ServiceDiscoveryNamespace}
    execution_role_arn: {TaskExecutionRoleArn}
    task_role_arn: {AgentRoleArn}
    log_group: {AgentLogGroup}
    launch_type: {TaskLaunchType}
    requires_healthcheck: {EnableZeroDowntimeDeploys}
    code_server_metrics:
      enabled: {CodeServerMetricsEnabled}
    agent_metrics:
      enabled: {AgentMetricsEnabled}' > $DAGSTER_HOME/dagster.yaml && dagster-cloud agent run"
"""
DAGSTER_STACK_PREFIX: str = "Dagster-Cloud-Aesthetics360"
LOG_RETENTION_DAYS: logs.RetentionDays = logs.RetentionDays.ONE_WEEK
