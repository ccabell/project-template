from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_athena as athena
from aws_cdk import aws_glue as glue
from aws_cdk import aws_s3 as s3
from constructs import Construct


class TranscriptionAnalysisStack(Stack):
    """Stack with resources required for the transcription quality analysis"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        analytics_db: glue.CfnDatabase,
        env_prefix: str = "",
        **kwargs,
    ):
        """Initializes the stack

        Args:
            scope: CDK construct providing the scope for resource creation
            construct_id: Unique identifier for the stack
            analytics_db: A Glue database inside of which to create a table with metrics
            env_prefix: Optional prefix for the deployment environment. Will be
                prepended to the names of some resources. Defaults to `""`
            **kwargs: Additional arguments passed to parent Stack constructor
        """
        super().__init__(scope, construct_id, **kwargs)

        bucket_name = f"{env_prefix}transcription-analysis".lower()
        self.transcript_analysis_bucket = s3.Bucket(
            self,
            "TranscriptionAnalysisBucket",
            bucket_name=bucket_name,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.transcript_analysis_workgroup = athena.CfnWorkGroup(
            self,
            "TranscriptionAnalysisWorkGroup",
            name="a360-transcription-quality-analysis",
            description="Workgroup for transcription quality analysis queries",
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                enforce_work_group_configuration=True,
                publish_cloud_watch_metrics_enabled=True,
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=self.transcript_analysis_bucket.s3_url_for_object(
                        "athena-results/"
                    )
                ),
            ),
        )

        self.transcript_metrics_table = glue.CfnTable(
            self,
            "TranscriptionMetricsTable",
            catalog_id=analytics_db.catalog_id,
            database_name=analytics_db.ref,
            table_input=glue.CfnTable.TableInputProperty(
                description="Transcription quality metrics with model version tracking",
                name="transcription_metrics",
                parameters={"classification": "parquet", "compressionType": "none"},
                partition_keys=[
                    glue.CfnTable.ColumnProperty(name="year", type="int"),
                    glue.CfnTable.ColumnProperty(name="month", type="int"),
                    glue.CfnTable.ColumnProperty(name="stt_model", type="string"),
                    glue.CfnTable.ColumnProperty(
                        name="spellcheck_model", type="string"
                    ),
                ],
                storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                    columns=[
                        glue.CfnTable.ColumnProperty(
                            name="language",
                            comment="Transcript Language",
                            type="string",
                        ),
                        glue.CfnTable.ColumnProperty(
                            name="cer_original",
                            comment="CER of the original transcript compared to GT",
                            type="double",
                        ),
                        glue.CfnTable.ColumnProperty(
                            name="cer_corrected",
                            comment="CER of the corrected transcript compared to GT",
                            type="double",
                        ),
                        glue.CfnTable.ColumnProperty(
                            name="wer_original",
                            comment="WER of the original transcript compared to GT",
                            type="double",
                        ),
                        glue.CfnTable.ColumnProperty(
                            name="wer_corrected",
                            comment="WER of the corrected transcript compared to GT",
                            type="double",
                        ),
                        glue.CfnTable.ColumnProperty(
                            name="correction_fp",
                            comment="Incorrect corrections made (false positives)",
                            type="int",
                        ),
                        glue.CfnTable.ColumnProperty(
                            name="correction_fn",
                            comment="Corrections missed (false negatives)",
                            type="int",
                        ),
                        glue.CfnTable.ColumnProperty(
                            name="diarization_accuracy",
                            comment="Diarization accuracy compared to GT",
                            type="double",
                        ),
                        glue.CfnTable.ColumnProperty(
                            name="overall_quality",
                            comment="Overall quality score calculated as combination of CAR, WAR, and diarization accuracy",
                            type="double",
                        ),
                    ],
                    compressed=False,
                    input_format="org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                    location=self.transcript_analysis_bucket.s3_url_for_object(
                        "metrics/processed/"
                    ),
                    output_format="org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                    serde_info=glue.CfnTable.SerdeInfoProperty(
                        parameters={"serialization.format": "1"},
                        serialization_library="org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe",
                    ),
                ),
                table_type="EXTERNAL_TABLE",
            ),
        )
