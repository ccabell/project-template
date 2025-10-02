"""Output Manager for AWS CDK stacks.

This module provides a class that consistently handles AWS CDK stack outputs
for the Dagter+ hybrid agent deployment stack.
"""

from aws_cdk import CfnOutput
from aws_cdk import aws_ssm as ssm
from constructs import Construct


class OutputManager:
    """Consistent management of CloudFormation outputs and SSM Parameters for
    Dagster+ hybrid agent cross-stack references.


    Attributes:
        scope: The construct for which outputs are being managed.
        stack_name: The name of the Dagster+ hybrid agent stack.
    """

    def __init__(self, scope: Construct, stack_name: str) -> None:
        self.scope = scope
        self.stack_name = stack_name

    def add_output_with_ssm(
        self,
        id_: str,
        value: str,
        description: str,
        export_name: str,
    ) -> None:
        """Creates CloudFormation output and SSM Parameter for Dagster+ hybrid agent stack.

        Args:
            id_: Unique identifier for the output/parameter.
            value: The value of the property returned by the aws cloudformation describe-stacks command.
            export_name: The name used to export the value of this output across stacks.
            description: A String type that describes the output value.
        """
        # Export CloudFormation Output
        CfnOutput(
            self.scope,
            id_,
            value=value,
            export_name=export_name,
            description=description,
        )
        # Create SSM Param
        ssm.StringParameter(
            self.scope,
            f"{id_}Parameter",
            parameter_name=f"/infrastructure/{self.stack_name}/{export_name}".lower(),
            string_value=value,
            description=description,
        )
