"""CDK Stack for consultation auto-finish Lambda function.

Creates the Lambda function that automatically finishes idle consultations
after a configurable timeout, and sets up EventBridge scheduling to run daily at 12 AM EST.
"""

from aws_cdk import Duration, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from config.common import Config
from constructs import Construct


class ConsultationAutoFinishStack(Stack):
    """Stack for auto-finishing idle and ongoing consultations after 12 hours.

    Creates Lambda function and EventBridge rule to automatically update
    consultations that have been in IDLE (2) or ONGOING (1) status for more than 12 hours.
    Runs daily at 12 AM EST.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: Config,
        vpc: ec2.IVpc,
        aurora_cluster_arn: str,
        aurora_cluster_secret_arn: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # AWS Lambda Powertools layer
        powertools_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:38",
        )

        # Create IAM role for the Lambda function
        handler_role = iam.Role(
            self,
            "ConsultationAutoFinishRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole",
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaVPCAccessExecutionRole",
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AWSXrayWriteOnlyAccess",
                ),
            ],
        )

        # Add RDS Data API permissions
        handler_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "rds-data:ExecuteStatement",
                    "rds-data:BatchExecuteStatement",
                ],
                resources=[aurora_cluster_arn],
            ),
        )

        # Add Secrets Manager permissions
        handler_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[aurora_cluster_secret_arn],
            ),
        )

        auto_finish_lambda = lambda_.Function(
            self,
            "ConsultationAutoFinishLambda",
            function_name=f"{config.stage_prefix}ConsultationAutoFinish",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            code=lambda_.Code.from_asset(
                "infra/stacks/lambdas/consultation_auto_finish",
            ),
            handler="index.lambda_handler",
            environment={
                "DB_CLUSTER_ARN": aurora_cluster_arn,
                "DB_SECRET_ARN": aurora_cluster_secret_arn,
                "DB_NAME": config.aurora_serverless.database_name,
                "POWERTOOLS_SERVICE_NAME": "consultation_auto_finish",
                "POWERTOOLS_METRICS_NAMESPACE": "ConsultationService",
                "POWERTOOLS_LOG_LEVEL": "INFO",
            },
            timeout=Duration.minutes(5),
            memory_size=256,
            role=handler_role,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            layers=[powertools_layer],
            tracing=lambda_.Tracing.ACTIVE,
            log_retention=logs.RetentionDays.ONE_MONTH,
        )

        # Create EventBridge rule for daily execution at 12 AM EST/1 AM EDT
        # Note: EventBridge uses UTC time. EST is UTC-5, EDT is UTC-4.
        # Setting to 5 AM UTC ensures consistent 12 AM EST execution.
        # During EDT (Daylight Saving Time), this will run at 1 AM EDT.
        auto_finish_rule = events.Rule(
            self,
            "ConsultationAutoFinishRule",
            rule_name=f"{config.stage_prefix}ConsultationAutoFinishRule",
            description="Daily execution of consultation auto-finish at 12 AM EST/1 AM EDT",
            schedule=events.Schedule.cron(
                minute="0",
                hour="5",  # 5 AM UTC = 12 AM EST = 1 AM EDT
                day="*",
                month="*",
                year="*",
            ),
        )

        # Add Lambda function as target for the rule
        auto_finish_rule.add_target(
            targets.LambdaFunction(
                auto_finish_lambda,
                retry_attempts=2,
            ),
        )

        # Grant EventBridge permission to invoke the Lambda function
        auto_finish_lambda.add_permission(
            "AllowEventBridgeInvoke",
            principal=iam.ServicePrincipal("events.amazonaws.com"),
            source_arn=auto_finish_rule.rule_arn,
        )

        # Store references for potential use by other stacks
        self.auto_finish_lambda = auto_finish_lambda
        self.auto_finish_rule = auto_finish_rule
