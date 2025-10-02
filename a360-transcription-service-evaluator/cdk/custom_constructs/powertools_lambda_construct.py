"""Reusable Lambda construct with PowerTools and ARM64 architecture.

This construct provides a standardized Lambda function configuration with
ARM64 architecture, PowerTools layers, and production-grade settings.
"""

from typing import Dict, List, Optional
from constructs import Construct
from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_lambda as lambda_,
    aws_ec2 as ec2,
    aws_iam as aws_iam,
    aws_logs as logs
)


class PowertoolsLambdaConstruct(Construct):
    """Standardized Lambda function with PowerTools and ARM64 architecture."""
    
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        handler: str,
        code: lambda_.Code,
        service_name: str,
        namespace: str = "TranscriptionService",
        description: str = "",
        timeout: Duration = Duration.minutes(5),
        memory_size: int = 512,
        environment: Optional[Dict[str, str]] = None,
        vpc: Optional[ec2.Vpc] = None,
        vpc_subnets: Optional[ec2.SubnetSelection] = None,
        security_groups: Optional[List[ec2.SecurityGroup]] = None,
        additional_layers: Optional[List[lambda_.LayerVersion]] = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.service_name = service_name
        self.namespace = namespace
        
        env_vars = {
            "POWERTOOLS_SERVICE_NAME": service_name,
            "POWERTOOLS_METRICS_NAMESPACE": namespace,
            "POWERTOOLS_LOG_LEVEL": "INFO",
            "POWERTOOLS_METRICS_NAMESPACE": namespace
        }
        if environment:
            env_vars.update(environment)
        
        log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=f"/aws/lambda/{service_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        layers = [
            lambda_.LayerVersion.from_layer_version_arn(
                self,
                "PowerToolsLayer",
                layer_version_arn=f"arn:aws:lambda:{Stack.of(self).region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-arm64:18"
            ),
            lambda_.LayerVersion.from_layer_version_arn(
                self,
                "LambdaInsightsLayer", 
                layer_version_arn=f"arn:aws:lambda:{Stack.of(self).region}:580247275435:layer:LambdaInsightsExtension-Arm64:5"
            )
        ]
        
        if additional_layers:
            layers.extend(additional_layers)
        
        self.function = lambda_.Function(
            self,
            "Function",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler=handler,
            code=code,
            description=description,
            timeout=timeout,
            memory_size=memory_size,
            environment=env_vars,
            layers=layers,
            vpc=vpc,
            vpc_subnets=vpc_subnets,
            security_groups=security_groups,
            dead_letter_queue_enabled=True,
            retry_attempts=2,
            log_group=log_group
        )
        
        self.function.add_to_role_policy(
            aws_iam.PolicyStatement(
                effect=aws_iam.Effect.ALLOW,
                actions=[
                    "cloudwatch:PutMetricData",
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream", 
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )
    
    @property
    def function_arn(self) -> str:
        """Return the Lambda function ARN."""
        return self.function.function_arn
    
    @property
    def function_name(self) -> str:
        """Return the Lambda function name."""
        return self.function.function_name
    
    def add_to_role_policy(self, statement: aws_iam.PolicyStatement) -> None:
        """Add IAM policy statement to the Lambda execution role."""
        self.function.add_to_role_policy(statement)
    
    def grant_invoke(self, grantee: aws_iam.IGrantable) -> aws_iam.Grant:
        """Grant invoke permissions to the specified principal."""
        return self.function.grant_invoke(grantee)