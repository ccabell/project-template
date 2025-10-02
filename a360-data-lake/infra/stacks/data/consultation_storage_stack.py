"""ConsultationStorageStack
------------------------

Provisioning:

• S3 bucket (raw audio + converted WAV/MP3)
• Kinesis “audio” stream  → Firehose → S3
• Kinesis “transcript” stream (sentence JSON)
• Firehose transform Lambda  (wrap raw bytes → JSON envelope)
• Post-process Lambda (JSON  → WAV / MP3)
• DynamoDB tables
    – audio-metadata  (chunks, completion marker)
    – transcript-segments (one item per utterance)
• Cleanup Lambda (purge temporary audio items after status#completed)
"""

from __future__ import annotations

from typing import Any

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_secretsmanager,
)
from aws_cdk import (
    aws_dynamodb as dynamodb,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_kinesis as kinesis,
)
from aws_cdk import (
    aws_kinesisfirehose as firehose,
)
from aws_cdk import (
    aws_lambda as _lambda,
)
from aws_cdk import (
    aws_lambda_event_sources as evt,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk.aws_kinesis import StreamConsumer
from aws_cdk.aws_s3_notifications import LambdaDestination as S3LambdaDestination
from config.common import Config
from constructs import Construct

from stacks.common.utils import get_lambda_insights_layer, get_powertools_layer


class ConsultationStorageStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: Config,
        environment_name: str,
        s3_consultation_transcriptions: s3.Bucket,
        aurora_cluster_arn: str,
        aurora_cluster_secret_arn: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Set different S3 removal policies if production
        is_prod = config.stage_prefix.lower() == "prod"

        # 1. S3 bucket (raw audio + derived files)

        self.audio_bucket = s3.Bucket(
            self,
            "RawAudioBucket",
            bucket_name=f"a360-{environment_name}-raw-audio",
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY,
            auto_delete_objects=not is_prod,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="expire-audio-after-30-days",
                    expiration=Duration.days(30),
                ),
            ],
        )

        # Layers shared by all Python Lambdas
        powertools_layer = get_powertools_layer(self, self.region)
        insights_layer = get_lambda_insights_layer(self, self.region)

        # 2. Firehose transform Lambda (wrap raw bytes in JSON + set partitionKeys)
        self.firehose_processor_fn = _lambda.Function(
            self,
            "FirehoseTransformFn",
            function_name=f"{environment_name}-firehose-transform",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            code=_lambda.Code.from_asset("stacks/lambdas/firehose_processor"),
            handler="index.lambda_handler",
            timeout=Duration.seconds(15),
            memory_size=256,
            layers=[powertools_layer, insights_layer],
        )
        self.firehose_processor_fn.add_permission(
            "InvokeByFirehose",
            principal=iam.ServicePrincipal("firehose.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_account=self.account,
        )

        # 3. Kinesis streams
        self.audio_stream = kinesis.Stream(
            self,
            "AudioStream",
            stream_name=f"{environment_name}-audio-stream",
            shard_count=2,
            retention_period=Duration.hours(24),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.transcript_stream = kinesis.Stream(
            self,
            "TranscriptStream",
            stream_name=f"{environment_name}-transcript-stream",
            shard_count=2,
            retention_period=Duration.hours(24),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.transcript_consumer = StreamConsumer(
            self,
            "TranscriptEfoConsumer",
            stream=self.transcript_stream,
            stream_consumer_name=f"{environment_name}-transcript-efo",
        )
        self.ingestor_consumer = StreamConsumer(
            self,
            "IngestorEfoConsumer",
            stream=self.transcript_stream,
            stream_consumer_name=f"{environment_name}-ingestor-efo",
        )

        # 4. Firehose → S3 delivery
        firehose_role = self._create_firehose_role(environment_name)

        self.audio_delivery_stream = firehose.CfnDeliveryStream(
            self,
            "AudioFirehose",
            delivery_stream_name=f"{environment_name}-audio-delivery",
            delivery_stream_type="KinesisStreamAsSource",
            kinesis_stream_source_configuration=firehose.CfnDeliveryStream.KinesisStreamSourceConfigurationProperty(
                kinesis_stream_arn=self.audio_stream.stream_arn,
                role_arn=firehose_role.role_arn,
            ),
            extended_s3_destination_configuration=firehose.CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty(
                bucket_arn=self.audio_bucket.bucket_arn,
                role_arn=firehose_role.role_arn,
                buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                    interval_in_seconds=60,
                    size_in_m_bs=64,
                ),
                dynamic_partitioning_configuration=firehose.CfnDeliveryStream.DynamicPartitioningConfigurationProperty(
                    enabled=True,
                ),
                prefix=(
                    "!{partitionKeyFromLambda:consultation_id}/"
                    "!{timestamp:MM}-!{timestamp:dd}-!{timestamp:yyyy}-!{timestamp:HHmm}/"
                ),
                error_output_prefix="audio/errors/!{firehose:error-output-type}/",
                file_extension=".json",
                processing_configuration=firehose.CfnDeliveryStream.ProcessingConfigurationProperty(
                    enabled=True,
                    processors=[
                        firehose.CfnDeliveryStream.ProcessorProperty(
                            type="Lambda",
                            parameters=[
                                firehose.CfnDeliveryStream.ProcessorParameterProperty(
                                    parameter_name="LambdaArn",
                                    parameter_value=self.firehose_processor_fn.function_arn,
                                ),
                            ],
                        ),
                        firehose.CfnDeliveryStream.ProcessorProperty(
                            type="AppendDelimiterToRecord",
                            parameters=[
                                firehose.CfnDeliveryStream.ProcessorParameterProperty(
                                    parameter_name="Delimiter",
                                    parameter_value="\\n",
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        )

        # 5. DynamoDB tables
        self.audio_meta_table = dynamodb.Table(
            self,
            "AudioMetaTable",
            table_name=f"{environment_name}-consultation-sessions",
            partition_key=dynamodb.Attribute(
                name="consultation_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="metadata",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expiry_time",
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            removal_policy=(
                RemovalPolicy.RETAIN
                if environment_name == "prod"
                else RemovalPolicy.DESTROY
            ),
        )

        self.transcript_table = dynamodb.Table(
            self,
            "TranscriptSegmentsTable",
            table_name=f"{environment_name}-transcript-segments",
            partition_key=dynamodb.Attribute(
                name="consultation_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="segment_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expiry_time",
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            removal_policy=(
                RemovalPolicy.RETAIN
                if environment_name == "prod"
                else RemovalPolicy.DESTROY
            ),
        )

        self.active_connections_table = dynamodb.Table(
            self,
            "ActiveConnectionsTable",
            table_name=f"{environment_name}-active-connections",
            partition_key=dynamodb.Attribute(
                name="consultation_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="connection_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            removal_policy=(
                RemovalPolicy.RETAIN
                if environment_name == "prod"
                else RemovalPolicy.DESTROY
            ),
        )

        self.active_connections_table.add_global_secondary_index(
            index_name="ContainerIndex",
            partition_key=dynamodb.Attribute(
                name="container_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="consultation_id",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        CfnOutput(
            self,
            "TranscriptTableArn",
            value=self.transcript_table.table_arn,
            export_name=f"{environment_name}-transcript-table-arn",
        )
        CfnOutput(
            self,
            "TranscriptTableStreamArn",
            value=self.transcript_table.table_stream_arn,
            export_name=f"{environment_name}-transcript-table-stream-arn",
        )

        # 6. Post-process Lambda (JSON → WAV / MP3)

        self.ffmpeg_layer = _lambda.LayerVersion(
            self,
            "AudioConversionFnFfmpegLayer",
            code=_lambda.Code.from_asset("stacks/lambdas/layers/ffmpeg-layer.zip"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            compatible_architectures=[_lambda.Architecture.ARM_64],
            description="FFmpeg static binary layer",
        )
        self.audio_conversion_fn = _lambda.Function(
            self,
            "AudioConversionFn",
            function_name=f"{environment_name}-audio-transform",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            code=_lambda.Code.from_asset("stacks/lambdas/audio_transformation"),
            handler="index.handler",
            timeout=Duration.minutes(15),
            memory_size=2048,
            layers=[self.ffmpeg_layer, powertools_layer, insights_layer],
            environment={
                "RAW_BUCKET_NAME": self.audio_bucket.bucket_name,
                "MP3_BUCKET_NAME": s3_consultation_transcriptions.bucket_name,
                "AWS_DYNAMODB_SESSION_TABLE": self.audio_meta_table.table_name,
                "DB_CLUSTER_ARN": aurora_cluster_arn,
                "DB_SECRET_ARN": aurora_cluster_secret_arn,
                "DB_NAME": config.aurora_serverless.database_name,
                "REGION": self.region,
            },
        )
        self.audio_bucket.grant_read_write(self.audio_conversion_fn)
        self.audio_meta_table.grant_read_write_data(self.audio_conversion_fn)
        s3_consultation_transcriptions.grant_read_write(self.audio_conversion_fn)
        self.audio_conversion_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["rds-data:ExecuteStatement"],
                resources=[aurora_cluster_arn],
            ),
        )
        self.audio_conversion_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[aurora_cluster_secret_arn],
            ),
        )
        if s3_consultation_transcriptions.encryption_key:
            s3_consultation_transcriptions.encryption_key.grant_encrypt_decrypt(
                self.audio_conversion_fn,
            )

        self.audio_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            S3LambdaDestination(self.audio_conversion_fn),
            s3.NotificationKeyFilter(suffix=".json"),
        )

        # 7. Cleanup Lambda  (purge audio-metadata)
        self.cleanup_lambda = _lambda.Function(
            self,
            "ConsultationCleanupFn",
            function_name=f"{environment_name}-consultation-cleanup",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            code=_lambda.Code.from_asset("stacks/lambdas/consultation_cleanup"),
            handler="index.handler",
            timeout=Duration.minutes(5),
            environment={
                "TABLE_NAME": self.audio_meta_table.table_name,
                "POWERTOOLS_SERVICE_NAME": "consultation_cleanup",
            },
            layers=[powertools_layer, insights_layer],
        )
        self.audio_meta_table.grant_read_write_data(self.cleanup_lambda)
        self.cleanup_lambda.add_event_source(
            evt.DynamoEventSource(
                self.audio_meta_table,
                starting_position=_lambda.StartingPosition.LATEST,
                batch_size=25,
                filters=[
                    _lambda.FilterCriteria.filter(
                        {
                            "dynamodb": {
                                "NewImage": {
                                    "metadata": {"S": [{"prefix": "status#completed"}]},
                                },
                            },
                        },
                    ),
                ],
            ),
        )
        # 8. Segment Ingestor Lambda (process Kinesis transcript stream)

        dg_secret = aws_secretsmanager.Secret.from_secret_name_v2(
            self,
            "DeepgramApiKey",
            "deepgram/api-key",
        )

        self.segment_ingestor_fn = _lambda.Function(
            self,
            "SegmentIngestorFn",
            function_name=f"{environment_name}-segment-ingestor",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            code=_lambda.Code.from_asset("stacks/lambdas/kinesis_transcript_processor"),
            handler="index.handler",
            timeout=Duration.seconds(90),
            memory_size=2048,
            environment={
                "TRANSCRIPT_TABLE": self.transcript_table.table_name,
                "TRANSCRIPTION_BUCKET": s3_consultation_transcriptions.bucket_name,
                "BEDROCK_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0",
                "DG_API_KEY": dg_secret.secret_value_from_json(
                    "DEEPGRAM_API_KEY",
                ).unsafe_unwrap(),
            },
            layers=[powertools_layer, insights_layer],
        )

        self.transcript_table.grant_read_write_data(self.segment_ingestor_fn)
        dg_secret.grant_read(self.segment_ingestor_fn)

        self.segment_ingestor_fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kinesis:DescribeStreamSummary",
                    "kinesis:DescribeStreamConsumer",
                    "kinesis:ListShards",
                    "kinesis:GetShardIterator",
                    "kinesis:GetRecords",
                    "kinesis:SubscribeToShard",
                ],
                resources=[
                    self.transcript_stream.stream_arn,
                    self.ingestor_consumer.stream_consumer_arn,
                ],
            ),
        )

        self.segment_ingestor_fn.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess"),
        )

        ingestor_esm = _lambda.EventSourceMapping(
            self,
            "IngestorESM",
            target=self.segment_ingestor_fn,
            event_source_arn=self.ingestor_consumer.stream_consumer_arn,
            starting_position=_lambda.StartingPosition.LATEST,
            batch_size=25,
            max_batching_window=Duration.seconds(1),
            parallelization_factor=2,
            report_batch_item_failures=True,
            filters=[
                _lambda.FilterCriteria.filter(
                    {"data": {"event_type": ["transcript_segment"]}},
                ),
            ],
        )
        ingestor_esm.node.add_dependency(self.ingestor_consumer)

        # 8-2. Consultation-enrichment Lambda  (triggered by on-success destination)
        self.enrichment_fn = _lambda.Function(
            self,
            "ConsultationEnrichmentFn",
            function_name=f"{environment_name}-consultation-enrichment",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            code=_lambda.Code.from_asset("stacks/lambdas/consultation_enrichment"),
            handler="index.handler",
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "TRANSCRIPT_TABLE": self.transcript_table.table_name,
            },
            layers=[powertools_layer, insights_layer],
        )

        self.enrichment_fn.add_event_source(
            evt.DynamoEventSource(
                self.transcript_table,
                starting_position=_lambda.StartingPosition.LATEST,
                batch_size=25,
                retry_attempts=2,
            ),
        )

        self.transcript_table.grant(
            self.enrichment_fn,
            "dynamodb:GetItem",
            "dynamodb:UpdateItem",
        )

        self.transcript_table.grant_stream_read(self.enrichment_fn)
        self.enrichment_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["comprehendmedical:DetectEntitiesV2"],
                resources=["*"],
            ),
        )

        # 9. Segment Processor Lambda (aggregate on consultation_end)
        self.segment_processor_fn = _lambda.Function(
            self,
            "SegmentProcessorFn",
            function_name=f"{environment_name}-segment-processor",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.ARM_64,
            code=_lambda.Code.from_asset(
                "stacks/lambdas/transcription_segment_processor",
            ),
            handler="index.handler",
            timeout=Duration.seconds(60),
            memory_size=1024,
            environment={
                "TRANSCRIPT_TABLE": self.transcript_table.table_name,
                "TRANSCRIPTION_BUCKET": s3_consultation_transcriptions.bucket_name,
                "DB_CLUSTER_ARN": aurora_cluster_arn,
                "DB_SECRET_ARN": aurora_cluster_secret_arn,
                "BEDROCK_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0",
                "DB_NAME": config.aurora_serverless.database_name,
            },
            layers=[powertools_layer, insights_layer],
        )

        self.transcript_table.grant_read_write_data(self.segment_processor_fn)
        s3_consultation_transcriptions.grant_put(self.segment_processor_fn)

        proc_esm = _lambda.EventSourceMapping(
            self,
            "TranscriptAggregatorESM",
            target=self.segment_processor_fn,
            event_source_arn=self.transcript_consumer.stream_consumer_arn,
            starting_position=_lambda.StartingPosition.TRIM_HORIZON,
            batch_size=25,
            max_batching_window=Duration.seconds(1),
            filters=[
                _lambda.FilterCriteria.filter(
                    {
                        "data": {
                            "event_type": ["consultation_end"],
                        },
                    },
                ),
            ],
        )

        proc_esm.node.add_dependency(self.transcript_consumer)

        self.segment_processor_fn.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kinesis:DescribeStreamSummary",
                    "kinesis:DescribeStreamConsumer",
                    "kinesis:ListShards",
                    "kinesis:GetShardIterator",
                    "kinesis:GetRecords",
                    "kinesis:SubscribeToShard",
                ],
                resources=[
                    self.transcript_stream.stream_arn,
                    self.transcript_consumer.stream_consumer_arn,
                ],
            ),
        )
        self.segment_processor_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["rds-data:ExecuteStatement"],
                resources=[aurora_cluster_arn],
            ),
        )
        self.segment_processor_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[aurora_cluster_secret_arn],
            ),
        )
        self.segment_processor_fn.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess"),
        )

    def _create_firehose_role(self, env_name: str) -> iam.Role:
        role = iam.Role(
            self,
            "FirehoseRole",
            role_name=f"{env_name}-firehose-role",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
        )
        self.audio_bucket.grant_write(role)
        self.audio_stream.grant_read(role)
        self.firehose_processor_fn.grant_invoke(role)
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "AmazonKinesisReadOnlyAccess",
            ),
        )
        return role
