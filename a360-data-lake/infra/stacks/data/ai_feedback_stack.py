from aws_cdk import Duration, Stack, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from config.common import Config
from constructs import Construct

from stacks.common.bedrock_models import CLAUDE_3_5_HAIKU_INF_PROFILE_ARN
from stacks.common.eventbridge_pipe_construct import create_sqs_to_lambda_pipe
from stacks.common.lambda_construct import LambdaConstruct
from stacks.common.queue_factory import QueueFactory
from stacks.common.utils import (
    get_lambda_insights_layer,
    get_powertools_layer,
    get_xray_policy,
)


class AIFeedbackProcessingStack(Stack):
    """Stack for processing AI feedback.

    AI feedback with user comments is loaded to the SQS queue polled by the EventBridge
    Pipe that invokes the processing Lambda. The function categorizes feedback comments
    with Bedrock and stores the results in the DB.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.IVpc,
        aurora_cluster_arn: str,
        aurora_cluster_secret_arn: str,
        config: Config,
        **kwargs,
    ):
        """Initialize the stack.

        Args:
            scope: The scope in which this resource is defined.
            construct_id: The identifier of this resource.
            vpc: VPC for deployment of network-aware resources.
            aurora_cluster_arn: ARN of the Aurora Cluster.
            aurora_cluster_secret_arn: ARN of the Secrets Manager secret containing
                Aurora Cluster credentials.
            config: Configuration object containing stage information.
            **kwargs: Additional parameters passed to the underlying Stack.
        """
        super().__init__(scope, construct_id, **kwargs)

        Tags.of(self).add("GitHubRepo", "a360-service-patients")
        Tags.of(self).add("Service", "AIFeedbackProcessingService")
        Tags.of(self).add("Environment", config.stage_prefix)
        Tags.of(self).add("ManagedBy", "CDK")

        self.feedback_queue = QueueFactory.create_queue(
            self,
            "AIFeedbackQueue",
            f"{config.stage_prefix}-ai-feedback-queue",
            visibility_timeout=Duration.minutes(5),
        )
        QueueFactory.setup_queue_monitoring(self, self.feedback_queue)

        feedback_categorizer_lambda = self._create_feedback_categorizer_lambda(
            aurora_cluster_arn,
            aurora_cluster_secret_arn,
            vpc,
            config,
        )

        pipe_id = "SqsToFeedbackCategorizerLambdaPipe"
        if config.stage_prefix.startswith("Sandbox-"):
            pipe_id = f"{config.stage_prefix}SqsToFeedbackCategorizerLambdaPipe"[:48]

        sqs_to_feedback_categorizer_lambda_pipe = create_sqs_to_lambda_pipe(
            scope=self,
            source_queue=self.feedback_queue,
            target_lambda=feedback_categorizer_lambda.function,
            pipe_id=pipe_id,
            enable_logging=True,
            log_level="TRACE",
        )
        sqs_to_feedback_categorizer_lambda_pipe.node.add_dependency(self.feedback_queue)
        sqs_to_feedback_categorizer_lambda_pipe.node.add_dependency(
            feedback_categorizer_lambda,
        )

    def _create_feedback_categorizer_lambda(
        self,
        aurora_cluster_arn: str,
        aurora_cluster_secret_arn: str,
        vpc: ec2.IVpc,
        config: Config,
    ) -> LambdaConstruct:
        """Create feedback categorizer Lambda function.

        Args:
            aurora_cluster_arn: ARN of the Aurora Cluster.
            aurora_cluster_secret_arn: ARN of the Secrets Manager secret containing
                Aurora Cluster credentials.
            vpc: VPC for deployment of network-aware resources.
            config: Configuration object containing stage information.

        Returns:
            An instance of `LambdaConstruct`
        """
        subnet_selection = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
        )

        inf_profile_arn = CLAUDE_3_5_HAIKU_INF_PROFILE_ARN.format(
            account_id=self.account,
            region=self.region,
        )

        policy_statements = [
            iam.PolicyStatement(
                actions=["rds-data:ExecuteStatement"],
                resources=[aurora_cluster_arn],
            ),
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[aurora_cluster_secret_arn],
            ),
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[inf_profile_arn],
            ),
            get_xray_policy(),
        ]

        func_name = "AIFeedbackCategorizer"
        func = LambdaConstruct(
            scope=self,
            id_=f"{func_name}Lambda",
            code_path="stacks/lambdas/ai_feedback_categorizer",
            handler="index.handler",
            vpc=vpc,
            vpc_subnets=subnet_selection,
            environment={
                "DB_CLUSTER_ARN": aurora_cluster_arn,
                "DB_SECRET_ARN": aurora_cluster_secret_arn,
                "DB_NAME": config.aurora_serverless.database_name,
                "MODEL_ARN": inf_profile_arn,
                "POWERTOOLS_TRACER_CAPTURE_RESPONSE": "true",
                "POWERTOOLS_TRACER_CAPTURE_ERROR": "true",
                "AWS_XRAY_SDK_ENABLED": "true",
            },
            layers=[
                get_powertools_layer(self, self.region),
                get_lambda_insights_layer(self, self.region),
            ],
            additional_policy_statements=policy_statements,
            function_name=config.stage_prefix + func_name,
        )
        func.function.node.default_child.add_property_override(
            "TracingConfig",
            {"Mode": "Active"},
        )
        return func
