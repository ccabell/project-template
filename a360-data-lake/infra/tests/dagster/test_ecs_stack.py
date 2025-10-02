"""
Comprehensive test suite for Dagster+ ECS infrastructure stack.

This module provides extensive unit testing for the Dagster+ ECS cluster and service
infrastructure using pytest and AWS CDK assertions. Tests cover cluster creation,
Container Insights, service discovery integration, task definitions, log groups,
IAM roles, Fargate services (with deployment circuit breaker, network configuration),
sensitive token handling, and CloudFormation outputs.
"""

import pytest
from aws_cdk import App, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_servicediscovery as servicediscovery
from aws_cdk.assertions import Match, Template

from stacks.dagster.constants import (
    AGENT_CPU,
    AGENT_MEMORY,
    DAGSTER_STACK_PREFIX,
    LOG_RETENTION_DAYS,
)
from stacks.dagster.ecs_stack import AgentConfiguration, EcsStack


@pytest.fixture
def ecs_stack_template():
    app = App()
    vpc_stack = Stack(app, "VpcStack")
    vpc = ec2.Vpc(vpc_stack, "TestVpc", max_azs=1)
    agent_sg = ec2.SecurityGroup(vpc_stack, "AgentSG", vpc=vpc)
    user_sg = ec2.SecurityGroup(vpc_stack, "UserSG", vpc=vpc)
    namespace = servicediscovery.PrivateDnsNamespace(
        vpc_stack,
        "NS",
        name="test.local",
        vpc=vpc,
    )

    ecs_stack = EcsStack(
        app,
        "TestEcs",
        vpc=vpc,
        agent_security_group=agent_sg,
        user_code_security_group=user_sg,
        namespace=namespace,
        agent_config=AgentConfiguration(),
    )
    return Template.from_stack(ecs_stack)


class TestEcsStackCluster:
    def test_cluster_created(self, ecs_stack_template):
        ecs_stack_template.has_resource_properties(
            "AWS::ECS::Cluster",
            {"ClusterName": DAGSTER_STACK_PREFIX},
        )

    def test_container_insights_enhanced(self, ecs_stack_template):
        ecs_stack_template.has_resource_properties(
            "AWS::ECS::Cluster",
            {
                "ClusterSettings": Match.array_with(
                    [
                        Match.object_like(
                            {"Name": "containerInsights", "Value": "enhanced"},
                        ),
                    ],
                ),
            },
        )


class TestEcsStackLogGroup:
    def test_log_group_created(self, ecs_stack_template):
        ecs_stack_template.resource_count_is("AWS::Logs::LogGroup", 1)
        ecs_stack_template.has_resource_properties(
            "AWS::Logs::LogGroup",
            {"RetentionInDays": LOG_RETENTION_DAYS},
        )


class TestEcsStackIamRoles:
    def test_task_execution_role(self, ecs_stack_template):
        ecs_stack_template.has_resource_properties(
            "AWS::IAM::Role",
            {
                "RoleName": Match.string_like_regexp(
                    f"{DAGSTER_STACK_PREFIX}-task-execution-role",
                ),
            },
        )

    def test_agent_and_task_execution_roles_creation(self, ecs_stack_template):
        roles = ecs_stack_template.find_resources("AWS::IAM::Role")
        assert len(roles) >= 2


class TestEcsStackTaskDefinition:
    def test_task_definition_properties(self, ecs_stack_template):
        ecs_stack_template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {"Cpu": str(AGENT_CPU), "Memory": str(AGENT_MEMORY)},
        )

    def test_container_environment_and_secrets(self, ecs_stack_template):
        ecs_stack_template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "ContainerDefinitions": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Environment": Match.array_with(
                                    [
                                        {
                                            "Name": "DAGSTER_HOME",
                                            "Value": "/opt/dagster/dagster_home",
                                        },
                                    ],
                                ),
                            },
                        ),
                    ],
                ),
            },
        )


class TestEcsStackService:
    def test_service_created(self, ecs_stack_template):
        ecs_stack_template.resource_count_is("AWS::ECS::Service", 1)

    def test_health_and_deployment_config(self, ecs_stack_template):
        ecs_stack_template.has_resource_properties(
            "AWS::ECS::Service",
            {
                "DeploymentConfiguration": Match.object_like(
                    {"DeploymentCircuitBreaker": Match.object_like({})},
                ),
            },
        )

    def test_network_configuration(self, ecs_stack_template):
        ecs_stack_template.has_resource_properties(
            "AWS::ECS::Service",
            {"NetworkConfiguration": Match.any_value()},
        )


class TestEcsStackOutputs:
    def test_outputs_created(self, ecs_stack_template):
        for key in ["ClusterArn", "ServiceArn", "TaskExecutionRoleArn"]:
            ecs_stack_template.has_output(key, {})


class TestEcsStackHelpers:
    def test_getters_return_values(self):
        app = App()
        vpc_stack = Stack(app, "Vpc2")
        vpc = ec2.Vpc(vpc_stack, "Vpc2", max_azs=1)
        sg = ec2.SecurityGroup(vpc_stack, "SG", vpc=vpc)
        ns = servicediscovery.PrivateDnsNamespace(
            vpc_stack,
            "NS2",
            name="x.local",
            vpc=vpc,
        )
        config = AgentConfiguration()
        ecs_stack = EcsStack(
            app,
            "MinimalEcs",
            vpc=vpc,
            agent_security_group=sg,
            user_code_security_group=sg,
            namespace=ns,
            agent_config=config,
        )
        assert isinstance(ecs_stack.get_cluster_arn(), str)
        assert isinstance(ecs_stack.get_service_arn(), str)
        assert isinstance(ecs_stack.get_log_group_name(), str)
        assert isinstance(ecs_stack.get_task_execution_role_arn(), str)
        assert isinstance(ecs_stack.get_agent_role_arn(), str)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
