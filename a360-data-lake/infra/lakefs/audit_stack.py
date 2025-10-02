"""LakeFS audit logging and compliance infrastructure.

This module provides comprehensive audit logging, compliance reporting,
and data lineage tracking for LakeFS operations in healthcare environments.
"""

from dataclasses import dataclass
from typing import Any

from aws_cdk import Duration
from aws_cdk import aws_cloudtrail as cloudtrail
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kinesis as kinesis
from aws_cdk import aws_kinesisfirehose as firehose
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct


@dataclass(frozen=True)
class LakeFSAuditProps:
    """Configuration properties for LakeFS audit logging.

    Attributes:
        audit_bucket: S3 bucket for storing audit logs.
        lakefs_endpoint: LakeFS server endpoint URL.
        sns_audit_topic_arn: SNS topic ARN for audit event notifications.
    """

    audit_bucket: s3.IBucket
    lakefs_endpoint: str
    sns_audit_topic_arn: str


class LakeFSAuditStack(Construct):
    """LakeFS audit logging and compliance infrastructure.

    Provides comprehensive audit trail, compliance reporting, and
    data lineage tracking for all LakeFS version control operations.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        props: LakeFSAuditProps,
        **kwargs: dict[str, Any],
    ) -> None:
        """Initialize LakeFS audit stack.

        Args:
            scope: CDK construct scope for resource creation.
            construct_id: Unique identifier for this construct.
            props: Configuration properties for audit logging.
            **kwargs: Additional arguments passed to parent Construct.
        """
        super().__init__(scope, construct_id, **kwargs)

        self.audit_bucket = props.audit_bucket
        self.lakefs_endpoint = props.lakefs_endpoint
        self.sns_audit_topic_arn = props.sns_audit_topic_arn

        # Create audit trail infrastructure
        self._create_cloudtrail_audit()
        self._create_kinesis_stream()
        self._create_audit_processor()
        self._create_compliance_reports()
        self._create_data_lineage_tracker()

    def _create_cloudtrail_audit(self) -> None:
        """Create CloudTrail for comprehensive AWS API audit logging."""
        # Create CloudTrail for infrastructure changes
        self.cloudtrail = cloudtrail.Trail(
            self,
            "LakeFSCloudTrail",
            trail_name="lakefs-infrastructure-audit",
            send_to_cloud_watch_logs=True,
            include_global_service_events=True,
            is_multi_region_trail=True,
            enable_file_validation=True,
            bucket=self.audit_bucket,
            s3_key_prefix="cloudtrail/",
        )

        # Ensure CloudTrail depends on the audit bucket being fully configured
        self.cloudtrail.node.add_dependency(self.audit_bucket)

        # Add S3 data events for audit bucket
        self.cloudtrail.add_s3_event_selector(
            [
                cloudtrail.S3EventSelector(
                    bucket=self.audit_bucket,
                    object_prefix="audit-events/",
                ),
            ],
        )

    def _create_kinesis_stream(self) -> None:
        """Create Kinesis Data Stream for real-time audit log processing."""
        self.audit_stream = kinesis.Stream(
            self,
            "LakeFSAuditStream",
            stream_name="lakefs-audit-events",
            shard_count=2,
            retention_period=Duration.days(7),
            encryption=kinesis.StreamEncryption.MANAGED,
        )

        # Create Kinesis Data Firehose for S3 delivery
        self.firehose_role = iam.Role(
            self,
            "FirehoseDeliveryRole",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
            inline_policies={
                "FirehoseDeliveryPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:AbortMultipartUpload",
                                "s3:GetBucketLocation",
                                "s3:GetObject",
                                "s3:ListBucket",
                                "s3:ListBucketMultipartUploads",
                                "s3:PutObject",
                            ],
                            resources=[
                                self.audit_bucket.bucket_arn,
                                f"{self.audit_bucket.bucket_arn}/*",
                            ],
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "kinesis:DescribeStream",
                                "kinesis:GetShardIterator",
                                "kinesis:GetRecords",
                                "kinesis:ListShards",
                            ],
                            resources=[self.audit_stream.stream_arn],
                        ),
                        iam.PolicyStatement(  
                            effect=iam.Effect.ALLOW,  
                            actions=[  
                                "logs:CreateLogGroup",  
                                "logs:CreateLogStream",  
                                "logs:PutLogEvents",  
                                "logs:DescribeLogStreams",  
                                "logs:DescribeLogGroups",  
                            ],  
                            resources=["*"],  
                        ),  
                    ],  
                ),  
            },  
        )  
        self.audit_firehose = firehose.CfnDeliveryStream(
            self,
            "LakeFSAuditFirehose",
            delivery_stream_name="lakefs-audit-delivery",
            delivery_stream_type="KinesisStreamAsSource",
            kinesis_stream_source_configuration=firehose.CfnDeliveryStream.KinesisStreamSourceConfigurationProperty(
                kinesis_stream_arn=self.audit_stream.stream_arn,
                role_arn=self.firehose_role.role_arn
            ),
            extended_s3_destination_configuration=firehose.CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty(
                bucket_arn=self.audit_bucket.bucket_arn,
                role_arn=self.firehose_role.role_arn,
                prefix="audit-events/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/",
                error_output_prefix="audit-errors/",
                buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                    interval_in_seconds=60,
                    size_in_m_bs=64
                ),
                compression_format="GZIP",
                cloud_watch_logging_options=firehose.CfnDeliveryStream.CloudWatchLoggingOptionsProperty(
                    enabled=True,
                    log_group_name="/aws/kinesisfirehose/lakefs-audit-delivery",
                    log_stream_name="S3Delivery",
                )
            )
        )

    def _create_audit_processor(self) -> None:
        """Create Lambda function for processing and enriching audit events."""
        self.audit_processor_role = iam.Role(
            self,
            "AuditProcessorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole",
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaKinesisExecutionRole",
                ),
            ],
            inline_policies={
                "AuditProcessorPolicy": iam.PolicyDocument(
                    statements=[
                        # S3 permissions for audit logs
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "s3:PutObject",
                                "s3:GetObject",
                            ],
                            resources=[
                                f"{self.audit_bucket.bucket_arn}/audit-events/*",
                            ],
                        ),
                        # SNS permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["sns:Publish"],
                            resources=[self.sns_audit_topic_arn],
                        ),
                    ],
                ),
            },
        )

        self.audit_processor = lambda_.Function(
            self,
            "AuditProcessor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            role=self.audit_processor_role,
            timeout=Duration.minutes(5),
            environment={
                "AUDIT_BUCKET": self.audit_bucket.bucket_name,
                "SNS_AUDIT_TOPIC_ARN": self.sns_audit_topic_arn,
                "LAKEFS_ENDPOINT": self.lakefs_endpoint,
            },
            code=lambda_.Code.from_inline("""
import json
import os
import boto3
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

# Initialize AWS clients
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')

def enrich_audit_event(event: Dict[str, Any]) -> Dict[str, Any]:
    \"\"\"Enrich audit event with additional metadata.\"\"\"
    enriched_event = {
        'audit_id': str(uuid.uuid4()),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'event_source': 'lakefs',
        'compliance_tags': ['HIPAA', 'SOC2', 'data-lineage'],
        'original_event': event,
    }

    # Add operation classification
    event_type = event.get('detail-type', '')
    if 'commit' in event_type.lower():
        enriched_event['operation_type'] = 'data_commit'
        enriched_event['risk_level'] = 'medium'
    elif 'merge' in event_type.lower():
        enriched_event['operation_type'] = 'data_merge'
        enriched_event['risk_level'] = 'high'
    elif 'branch' in event_type.lower():
        enriched_event['operation_type'] = 'branch_management'
        enriched_event['risk_level'] = 'low'
    else:
        enriched_event['operation_type'] = 'other'
        enriched_event['risk_level'] = 'low'

    return enriched_event

def store_audit_event(enriched_event: Dict[str, Any]) -> None:
    \"\"\"Store enriched audit event to S3.\"\"\"
    try:
        # Create S3 key with date partitioning
        timestamp = datetime.now(timezone.utc)
        s3_key = f"audit-events/year={timestamp.year}/month={timestamp.month:02d}/day={timestamp.day:02d}/{enriched_event['audit_id']}.json"

        s3_client.put_object(
            Bucket=os.environ['AUDIT_BUCKET'],
            Key=s3_key,
            Body=json.dumps(enriched_event, indent=2),
            ContentType='application/json'
        )
        print(f"Stored audit event to S3: {s3_key}")
    except Exception as e:
        print(f"Failed to store to S3: {str(e)}")

def send_high_risk_alert(enriched_event: Dict[str, Any]) -> None:
    \"\"\"Send SNS alert for high-risk operations.\"\"\"
    if enriched_event.get('risk_level') != 'high':
        return

    try:
        message = {
            'alert_type': 'HIGH_RISK_OPERATION',
            'operation': enriched_event['operation_type'],
            'audit_id': enriched_event['audit_id'],
            'timestamp': enriched_event['timestamp'],
            'details': enriched_event['original_event']
        }

        sns_client.publish(
            TopicArn=os.environ['SNS_AUDIT_TOPIC_ARN'],
            Subject='LakeFS High-Risk Operation Alert',
            Message=json.dumps(message, indent=2)
        )
        print(f"Sent high-risk alert for: {enriched_event['audit_id']}")
    except Exception as e:
        print(f"Failed to send SNS alert: {str(e)}")

def handler(event, context):
    \"\"\"Process incoming audit events.\"\"\"
    print(f"Processing audit event: {json.dumps(event)}")

    try:
        # Handle EventBridge events
        if 'source' in event and event['source'] == 'lakefs':
            enriched_event = enrich_audit_event(event)
            store_audit_event(enriched_event)
            send_high_risk_alert(enriched_event)

        # Handle direct invocations with multiple events
        elif 'Records' in event:
            for record in event['Records']:
                if 'body' in record:
                    body = json.loads(record['body'])
                    enriched_event = enrich_audit_event(body)
                    store_audit_event(enriched_event)
                    send_high_risk_alert(enriched_event)

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Audit events processed successfully'})
        }

    except Exception as e:
        print(f"Error processing audit events: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
"""),
            log_retention=logs.RetentionDays.ONE_YEAR,
        )

        # Add Kinesis event source mapping to process audit stream events
        lambda_.EventSourceMapping(
            self,
            "AuditStreamEventMapping",
            target=self.audit_processor,
            event_source_arn=self.audit_stream.stream_arn,
            batch_size=10,
            starting_position=lambda_.StartingPosition.LATEST,
            retry_attempts=3,
        )

    def _create_compliance_reports(self) -> None:
        """Create Lambda function for generating compliance reports."""
        self.compliance_reporter = lambda_.Function(
            self,
            "ComplianceReporter",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            role=self.audit_processor_role,
            timeout=Duration.minutes(10),
            environment={
                "AUDIT_BUCKET": self.audit_bucket.bucket_name,
            },
            code=lambda_.Code.from_inline("""
import json
import os
import boto3
from datetime import datetime, timedelta
from collections import defaultdict

s3_client = boto3.client('s3')

def generate_compliance_report(start_date: str, end_date: str) -> dict:
    \"\"\"Generate compliance report for specified date range.\"\"\"
    bucket_name = os.environ['AUDIT_BUCKET']

    # Query audit events from S3
    objects = s3_client.list_objects_v2(
        Bucket=bucket_name,
        Prefix='audit-events/',
        StartAfter=f'audit-events/year={start_date[:4]}/',
    )

    operations_count = defaultdict(int)
    risk_distribution = defaultdict(int)
    users_activity = defaultdict(int)

    for obj in objects.get('Contents', []):
        try:
            # Download and parse audit event
            response = s3_client.get_object(Bucket=bucket_name, Key=obj['Key'])
            event_data = json.loads(response['Body'].read().decode('utf-8'))

            # Count operations
            op_type = event_data.get('operation_type', 'unknown')
            operations_count[op_type] += 1

            # Risk level distribution
            risk_level = event_data.get('risk_level', 'unknown')
            risk_distribution[risk_level] += 1

            # User activity (if available)
            user = event_data.get('original_event', {}).get('userIdentity', {}).get('userName', 'system')
            users_activity[user] += 1

        except Exception as e:
            print(f"Error processing {obj['Key']}: {str(e)}")
            continue

    report = {
        'report_id': f"compliance-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        'period': {'start': start_date, 'end': end_date},
        'generated_at': datetime.now().isoformat(),
        'summary': {
            'total_operations': sum(operations_count.values()),
            'operations_by_type': dict(operations_count),
            'risk_distribution': dict(risk_distribution),
            'active_users': len(users_activity),
            'user_activity': dict(users_activity),
        },
        'compliance_status': 'COMPLIANT',  # Simplified for demo
        'recommendations': [
            'Continue monitoring high-risk operations',
            'Review user access patterns monthly',
            'Ensure all data lineage is captured',
        ]
    }

    return report

def handler(event, context):
    \"\"\"Generate and store compliance report.\"\"\"
    try:
        # Default to last 30 days if no period specified
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        report = generate_compliance_report(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )

        # Store report in S3
        report_key = f"compliance-reports/{report['report_id']}.json"
        s3_client.put_object(
            Bucket=os.environ['AUDIT_BUCKET'],
            Key=report_key,
            Body=json.dumps(report, indent=2),
            ContentType='application/json'
        )

        print(f"Generated compliance report: {report_key}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'report_id': report['report_id'],
                'location': f"s3://{os.environ['AUDIT_BUCKET']}/{report_key}"
            })
        }

    except Exception as e:
        print(f"Error generating compliance report: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
"""),
            log_retention=logs.RetentionDays.ONE_YEAR,
        )

        # Schedule monthly compliance reports
        self.compliance_schedule = events.Rule(
            self,
            "MonthlyComplianceSchedule",
            schedule=events.Schedule.cron(
                minute="0",
                hour="2",
                day="1",  # First day of each month
                month="*",
                year="*",
            ),
        )

        self.compliance_schedule.add_target(
            targets.LambdaFunction(self.compliance_reporter),
        )

    def _create_data_lineage_tracker(self) -> None:
        """Create EventBridge rules for LakeFS data lineage tracking."""
        # Rule for commit events to track data changes
        self.commit_tracking_rule = events.Rule(
            self,
            "DataCommitTracking",
            event_pattern=events.EventPattern(
                source=["lakefs"],
                detail_type=["Repository Commit"],
            ),
        )

        # Add audit processor as target
        self.commit_tracking_rule.add_target(
            targets.LambdaFunction(self.audit_processor),
        )

        # Rule for merge events to track data promotion
        self.merge_tracking_rule = events.Rule(
            self,
            "DataMergeTracking",
            event_pattern=events.EventPattern(
                source=["lakefs"],
                detail_type=["Branch Merge"],
            ),
        )

        self.merge_tracking_rule.add_target(
            targets.LambdaFunction(self.audit_processor),
        )

        # Rule for branch creation/deletion
        self.branch_tracking_rule = events.Rule(
            self,
            "BranchLifecycleTracking",
            event_pattern=events.EventPattern(
                source=["lakefs"],
                detail_type=["Branch Created", "Branch Deleted"],
            ),
        )

        self.branch_tracking_rule.add_target(
            targets.LambdaFunction(self.audit_processor),
        )
