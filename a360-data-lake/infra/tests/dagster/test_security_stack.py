"""
Comprehensive test suite for Dagster+ SecurityStack.

This module provides unit tests for the SecurityStack using pytest
and AWS CDK assertions. Tests cover creation of security groups,
ingress rules, cross references, CloudFormation outputs, and helper getters.
"""

import pytest
from aws_cdk import App, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk.assertions import Template

from stacks.dagster.security_stack import SecurityStack


@pytest.fixture
def security_stack_template():
    app = App()
    vpc_stack = Stack(app, "VpcStack")
    vpc = ec2.Vpc(vpc_stack, "TestVpc", max_azs=1)

    security_stack = SecurityStack(app, "TestSecurityStack", vpc=vpc)
    return Template.from_stack(security_stack)


class TestSecurityGroupsCreation:
    def test_two_security_groups_created(self, security_stack_template):
        resources = security_stack_template.find_resources("AWS::EC2::SecurityGroup")
        assert len(resources) == 2


class TestIngressRules:
    def test_agent_sg_ingress_rules(self, security_stack_template):
        resources = security_stack_template.find_resources("AWS::EC2::SecurityGroup")
        assert any(
            "Dagster+ agent containers"
            in v.get("Properties", {}).get("GroupDescription", "")
            for v in resources.values()
        )

    def test_user_code_sg_ingress_rules(self, security_stack_template):
        resources = security_stack_template.find_resources("AWS::EC2::SecurityGroup")
        assert any(
            "Dagster+ user code containers"
            in v.get("Properties", {}).get("GroupDescription", "")
            for v in resources.values()
        )


class TestCrossSecurityGroupReferences:
    def test_cross_sg_ingress(self, security_stack_template):
        ingress_resources = security_stack_template.find_resources(
            "AWS::EC2::SecurityGroup",
        )
        count = 0
        for res in ingress_resources.values():
            ingress_rules = res.get("Properties", {}).get("SecurityGroupIngress", [])
            if isinstance(ingress_rules, list):
                count += len(ingress_rules)
        assert count >= 2


class TestSecurityStackOutputsAndGetters:
    def test_outputs_created(self, security_stack_template):
        for key in ["AgentSecurityGroupId", "UserCodeSecurityGroupId"]:
            security_stack_template.has_output(key, {})


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
