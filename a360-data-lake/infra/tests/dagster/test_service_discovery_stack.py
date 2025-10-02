"""
Comprehensive test suite for Dagster+ ServiceDiscoveryStack.

This module provides unit tests for the ServiceDiscoveryStack using pytest
and AWS CDK assertions. Tests cover private DNS namespace creation,
Cloud Map configuration, CloudFormation outputs, and helper getters.
"""

import pytest
from aws_cdk import App, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk.assertions import Template

from stacks.dagster.constants import DAGSTER_STACK_PREFIX
from stacks.dagster.service_discovery import ServiceDiscoveryStack


@pytest.fixture
def sd_stack_template():
    app = App()
    vpc_stack = Stack(app, "VpcStack")
    vpc = ec2.Vpc(vpc_stack, "TestVpc", max_azs=1)

    sd_stack = ServiceDiscoveryStack(app, "TestSD", vpc=vpc)
    # skip validation to avoid token-based properties
    return Template.from_stack(sd_stack)


class TestServiceDiscoveryNamespace:
    def test_namespace_created(self, sd_stack_template):
        sd_stack_template.has_resource_properties(
            "AWS::ServiceDiscovery::PrivateDnsNamespace",
            {
                "Name": f"{DAGSTER_STACK_PREFIX.lower()}.local",
                "Description": "Private DNS namespace for Dagster+ code server discovery",
            },
        )

    def test_namespace_vpc_association(self, sd_stack_template):
        resources = sd_stack_template.find_resources(
            "AWS::ServiceDiscovery::PrivateDnsNamespace",
        )
        assert len(resources) == 1
        for res in resources.values():
            props = res.get("Properties", {})
            assert props.get("Vpc") is not None


class TestServiceDiscoveryOutputs:
    def test_outputs_created(self, sd_stack_template):
        keys = ["NamespaceId", "NamespaceName", "NamespaceArn"]
        for key in keys:
            sd_stack_template.has_output(key, {})


class TestServiceDiscoveryGetters:
    def test_getters_return_values(self):
        app = App()
        vpc_stack = Stack(app, "Vpc2")
        vpc = ec2.Vpc(vpc_stack, "Vpc2", max_azs=1)
        sd_stack = ServiceDiscoveryStack(app, "MinimalSD", vpc=vpc)

        ns_id = sd_stack.get_namespace_id()
        ns_name = sd_stack.get_namespace_name()
        ns_arn = sd_stack.get_namespace_arn()

        assert isinstance(ns_id, str)
        assert len(ns_id) > 0
        assert isinstance(ns_name, str)
        assert ns_name.endswith(".local")
        # ARN may be represented as a Token, so just ensure non-empty
        assert isinstance(ns_arn, str)
        assert len(ns_arn) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
