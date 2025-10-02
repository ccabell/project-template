# cdk/stacks/common/lambda_construct.py

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct


class LambdaConstruct(Construct):
    """Reusable Lambda function construct with standard configurations.

    This construct creates a Lambda function with commonly used configurations like
    VPC access, IAM permissions, logging, and environment variables.

    Attributes:
        function: The Lambda function instance
        function_name: Name of the created Lambda function
        function_arn: ARN of the created Lambda function
        role: IAM role used by the Lambda function
    """

    def __init__(
        self,
        scope: Construct,
        id_: str,
        code_path: str,
        handler: str,
        vpc: ec2.IVpc | None = None,
        vpc_subnets: ec2.SubnetSelection | None = None,
        environment: dict[str, str] | None = None,
        timeout: Duration | None = None,
        memory_size: int = 512,
        runtime: lambda_.Runtime = lambda_.Runtime.PYTHON_3_12,
        architecture: lambda_.Architecture = lambda_.Architecture.ARM_64,
        layers: list[lambda_.ILayerVersion] | None = None,
        log_retention: logs.RetentionDays = logs.RetentionDays.ONE_WEEK,
        reserved_concurrent_executions: int | None = None,
        security_groups: list[ec2.ISecurityGroup] | None = None,
        additional_policy_statements: list[iam.PolicyStatement] | None = None,
        function_name: str | None = None,
        removal_policy: RemovalPolicy = RemovalPolicy.DESTROY,
    ) -> None:
        """Initialize Lambda function with standard configurations."""
        super().__init__(scope, id_)

        # Set defaults for mutable default arguments
        if timeout is None:
            timeout = Duration.minutes(5)

        self.role = iam.Role(
            self,
            "Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole",
                ),
            ],
        )

        if additional_policy_statements:
            policy = iam.Policy(
                self,
                "LambdaPolicy",
                statements=additional_policy_statements,
            )
            self.role.attach_inline_policy(policy)

        if vpc:
            self.role.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaVPCAccessExecutionRole",
                ),
            )

        function_props = {
            "runtime": runtime,
            "architecture": architecture,
            "code": lambda_.Code.from_asset(code_path),
            "handler": handler,
            "role": self.role,
            "timeout": timeout,
            "memory_size": memory_size,
            "environment": environment,
            "log_retention": log_retention,
            "reserved_concurrent_executions": reserved_concurrent_executions,
        }

        if function_name:
            function_props["function_name"] = function_name

        if vpc:
            function_props["vpc"] = vpc
            if vpc_subnets:
                function_props["vpc_subnets"] = vpc_subnets
            if security_groups:
                function_props["security_groups"] = security_groups

        if layers:
            function_props["layers"] = layers

        self.function = lambda_.Function(
            self,
            "Function",
            **function_props,
        )

        # Apply removal policy
        if self.function.node.default_child:
            self.function.node.default_child.apply_removal_policy(removal_policy)

        self.function_name = self.function.function_name
        self.function_arn = self.function.function_arn

    @classmethod
    def from_lambda(
        cls,
        scope: Construct,
        id_: str,
        function: lambda_.Function,
    ) -> "LambdaConstruct":
        """Create a LambdaConstruct instance from an existing Lambda function.

        This factory method wraps an existing Lambda function in a LambdaConstruct,
        allowing for consistent handling of functions created through different
        approaches while maintaining the LambdaConstruct interface.

        Args:
            scope: The construct scope.
            id_: The construct ID.
            function: Existing Lambda function to wrap.

        Returns:
            A new LambdaConstruct instance containing the provided function.
        """
        construct = cls.__new__(cls)
        Construct.__init__(construct, scope, id_)
        construct.function = function
        construct.function_name = function.function_name
        construct.function_arn = function.function_arn
        construct.role = function.role
        return construct
