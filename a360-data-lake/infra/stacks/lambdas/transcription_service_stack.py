from aws_cdk import Duration, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from config.common import Config
from constructs import Construct

from stacks.common.eventbridge_s3_rule_construct import EventBridgeS3RuleWithTransformer
from stacks.common.utils import get_transcription_kms_key


class TranscriptionServiceStack(Stack):
    """Stack for transcription processing services.

    Defines Lambda functions and supporting resources for processing
    audio transcriptions and storing metadata in PostgreSQL.
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

        transcription_kms_key = get_transcription_kms_key(self, config.stage_prefix)

        powertools_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:38",
        )

        handler_role = iam.Role(
            self,
            "TranscriptionHandlerRole",
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

        handler_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:DescribeKey",
                ],
                resources=[transcription_kms_key.key_arn],
            ),
        )

        handler_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket",
                ],
                resources=[
                    f"arn:aws:s3:::{config.upload_s3_bucket_name}",
                    f"arn:aws:s3:::{config.upload_s3_bucket_name}/*",
                    f"arn:aws:s3:::{config.transcription_s3_bucket_name}",
                    f"arn:aws:s3:::{config.transcription_s3_bucket_name}/*",
                ],
            ),
        )

        # Add Secrets Manager permissions
        handler_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[
                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:{config.db_secret_name}*",
                ],
            ),
        )

        handler_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "rds-data:ExecuteStatement",
                    "rds-data:BatchExecuteStatement",
                ],
                resources=["*"],
            ),
        )

        transcription_handler = lambda_.Function(
            self,
            "TranscriptionHandler",
            function_name=f"{config.stage_prefix}TranscriptionHandler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            code=lambda_.Code.from_asset("stacks/lambdas/transcription_handler"),
            handler="index.handler",
            environment={
                "DB_CLUSTER_ARN": aurora_cluster_arn,
                "DB_SECRET_ARN": aurora_cluster_secret_arn,
                "DB_NAME": config.aurora_serverless.database_name,
                "REGION": self.region,
            },
            timeout=Duration.seconds(30),
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

        EventBridgeS3RuleWithTransformer(
            self,
            "TranscriptSavingRule",
            bucket_name=config.transcription_s3_bucket_name,
            prefix="",
            suffix="-final.json",
            target=transcription_handler,
            description="Rule for loading transcripts from S3 to TranscriptionHandler lambda",
        )
