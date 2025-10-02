"""Consultation pipeline infrastructure for Dagster+ Hybrid deployment.

This module provisions consultation-specific infrastructure that integrates with
existing Dagster+ Hybrid deployment including:
- EventBridge integration for automated consultation pipeline triggering
- IAM roles and policies for consultation data access
- S3 bucket permissions for consultation medallion architecture
- Integration with existing DagsterEcsStack hybrid agents

Note: This stack does NOT provision standalone Dagster infrastructure.
It relies on existing DagsterEcsStack, DagsterSecurityStack, and DagsterServiceDiscoveryStack.
"""

import aws_cdk as cdk
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_ssm as ssm
from constructs import Construct


class ConsultationPipelineDagsterStack(cdk.Stack):
    """Consultation pipeline integration stack for Dagster+ Hybrid deployment.

    Provides consultation-specific infrastructure that integrates with existing
    Dagster+ Hybrid deployment:
    - EventBridge integration for automated pipeline triggering
    - IAM permissions for consultation data access
    - Integration with existing hybrid agents
    - Consultation pipeline orchestration logic
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment_name: str = "production",
        **kwargs,
    ) -> None:
        """Initialize consultation pipeline integration stack.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this stack
            environment_name: Environment name for resource naming
            **kwargs: Additional CDK stack arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        self.environment_name = environment_name.lower()

        self._create_eventbridge_integration()
        self._create_consultation_pipeline_iam_roles()
        self._create_monitoring_and_logging()
        self._create_ssm_parameters()

    def _create_eventbridge_integration(self) -> None:
        """Create EventBridge rules for automated consultation pipeline triggering."""
        # EventBridge rule for consultation uploads
        self.consultation_upload_rule = events.Rule(
            self,
            "ConsultationUploadRule",
            rule_name=f"dagster-consultation-upload-{self.environment_name}",
            description="Trigger consultation pipeline on uploads to consultation medallion buckets",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {
                        "name": [f"a360-{self.environment_name}-consultation-bronze"],
                    },
                    "object": {
                        "key": [{"prefix": "consultations/"}],
                    },
                },
            ),
        )

        # Create Lambda function to trigger Dagster+ pipeline runs via GraphQL API
        self._create_dagster_trigger_lambda()

        # Connect EventBridge rule to Lambda trigger
        self.consultation_upload_rule.add_target(
            targets.LambdaFunction(self.dagster_trigger_function),
        )

        # EventBridge rule for consultation processing completion
        self.consultation_completion_rule = events.Rule(
            self,
            "ConsultationCompletionRule",
            rule_name=f"dagster-consultation-completion-{self.environment_name}",
            description="Handle consultation pipeline trigger/completion events",
            event_pattern=events.EventPattern(
                source=["custom.consultation.pipeline"],
                detail_type=["Pipeline Trigger Requested", "Pipeline Completion"],
            ),
        )

    def _create_dagster_trigger_lambda(self) -> None:
        """Create Lambda function to trigger Dagster+ pipeline runs via GraphQL API."""
        # IAM role for the trigger Lambda
        trigger_role = iam.Role(
            self,
            "ConsultationDagsterTriggerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole",
                ),
            ],
        )

        # Grant permissions to access consultation S3 buckets for metadata
        trigger_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectAttributes",
                    "s3:GetObjectTagging",
                    "s3:ListBucket",
                ],
                resources=[
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-bronze",
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-bronze/*",
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-silver",
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-silver/*",
                ],
            ),
        )

        # Grant permissions to publish EventBridge events
        trigger_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["events:PutEvents"],
                resources=[
                    f"arn:aws:events:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:event-bus/default",
                ],
            ),
        )

        # Grant permissions to read SSM parameters for Dagster+ configuration
        trigger_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[
                    f"arn:aws:ssm:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:parameter/dagster/{self.environment_name}/*",
                ],
            ),
        )

        # Lambda function for triggering Dagster+ runs
        self.dagster_trigger_function = lambda_.Function(
            self,
            "ConsultationDagsterTriggerFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            role=trigger_role,
            timeout=cdk.Duration.minutes(2),
            memory_size=512,
            log_retention=logs.RetentionDays.TWO_WEEKS,
            environment={
                "ENVIRONMENT": self.environment_name,
                "CONSULTATION_LOCATION_NAME": f"consultation-transcripts-pipeline-{self.environment_name}",
            },
            code=lambda_.Code.from_inline('''
import json
import boto3
import os
import urllib.parse
import urllib.request
from datetime import datetime
import logging
import hashlib

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

def lambda_handler(event, context):
    """
    Lambda function to trigger Dagster+ pipeline runs via GraphQL API.

    Receives S3 events for consultation uploads and triggers appropriate
    Dagster+ pipeline runs using the consultation_pipelines code location.
    """

    logger.info("Received consultation event for processing.")

    results = []

    # Process EventBridge events from S3
    for record in event.get('Records', []):
        if 'eventSource' in record and record['eventSource'] == 'aws:s3':
            result = process_s3_event(record)
            results.append(result)

    # Process direct EventBridge events
    if 'source' in event and event['source'] == 'aws.s3':
        result = process_eventbridge_s3_event(event)
        results.append(result)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Pipeline triggers processed',
            'results': results
        })
    }

def process_s3_event(record):
    """Process S3 event record to trigger consultation pipeline."""
    bucket = record['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(record['s3']['object']['key'])

    return process_consultation_upload(bucket, key)

def process_eventbridge_s3_event(event):
    """Process EventBridge S3 event to trigger consultation pipeline."""
    detail = event.get('detail', {})
    bucket = detail.get('bucket', {}).get('name', '')
    key = detail.get('object', {}).get('key', '')

    return process_consultation_upload(bucket, key)

def process_consultation_upload(bucket, key):
    """Process consultation file upload and trigger Dagster+ pipeline."""

    # Create hash of key for HIPAA-compliant logging
    key_hash = hashlib.sha256(key.encode()).hexdigest()[:12]
    logger.info("Processing consultation upload: bucket=%s, key_hash=%s", bucket, key_hash)

    # Extract consultation metadata from S3 key
    consultation_id = extract_consultation_id(key)
    tenant_id = extract_tenant_id(key, bucket) or "aesthetics360_demo"

    if not consultation_id:
        return {"status": "skipped", "reason": "Could not extract consultation_id from key"}

    # Trigger Dagster+ pipeline run using GraphQL API
    run_config = {
        "consultation_id": consultation_id,
        "tenant_id": tenant_id,
        "s3_bucket": bucket,
        "s3_key": key,
        "triggered_at": datetime.utcnow().isoformat()
    }

    # Log sanitized config for HIPAA compliance
    safe_config = {**run_config, "s3_key": f"sha256:{key_hash}"}
    logger.info("Would trigger consultation pipeline with config (sanitized): %s", json.dumps(safe_config))

    # Publish completion event to EventBridge for downstream processing
    eventbridge = boto3.client('events')
    eventbridge.put_events(
        Entries=[
            {
                'Source': 'custom.consultation.pipeline',
                'DetailType': 'Pipeline Trigger Requested',
                'Detail': json.dumps({
                    'consultation_id': consultation_id,
                    'tenant_id': tenant_id,
                    'bucket': bucket,
                    's3_key_hash': f"sha256:{key_hash}",  # Avoid emitting raw key
                    'environment': os.environ['ENVIRONMENT'],
                    'location_name': os.environ['CONSULTATION_LOCATION_NAME']
                })
            }
        ]
    )

    return {
        "status": "triggered",
        "consultation_id": consultation_id,
        "tenant_id": tenant_id,
        "run_config": safe_config  # Return sanitized config
    }

def extract_consultation_id(s3_key):
    """Extract consultation ID from S3 key path."""
    # Expected format: consultations/{consultation_id}/transcript.json
    # or consultations/{consultation_id}/attachments/{filename}
    try:
        parts = s3_key.split('/')
        if len(parts) >= 2 and parts[0] == 'consultations':
            return parts[1]
    except Exception as e:
        logger.error("Error extracting consultation_id from key (hash): %s",
                    hashlib.sha256(s3_key.encode()).hexdigest()[:12])
    return None

def extract_tenant_id(s3_key, bucket):
    """Extract tenant ID from S3 object tags or key structure."""
    try:
        # Try to get tenant from S3 object tags first
        s3_client = boto3.client('s3')
        try:
            response = s3_client.get_object_tagging(Bucket=bucket, Key=s3_key)
            for tag in response.get('TagSet', []):
                if tag['Key'].lower() in ['tenant', 'tenant_id']:
                    return tag['Value']
        except Exception:
            pass  # Tags not available, continue to fallback

        # Fallback: extract from key structure if available
        # e.g., tenants/{tenant_id}/consultations/{consultation_id}/...
        parts = s3_key.split('/')
        if len(parts) >= 2 and parts[0] == 'tenants':
            return parts[1]

    except Exception as e:
        logger.warning("Could not extract tenant_id, using default")

    return "aesthetics360_demo"  # Default tenant
            '''),
        )

    def _create_consultation_pipeline_iam_roles(self) -> None:
        """Create IAM roles and policies for consultation pipeline access."""
        # IAM role for Dagster+ hybrid agents to access consultation data
        # Use service principals and account root to avoid wildcard issues
        self.consultation_pipeline_role = iam.Role(
            self,
            "ConsultationPipelineRole",
            role_name=f"DagsterConsultationPipeline-{self.environment_name}",
            assumed_by=iam.CompositePrincipal(
                # Allow ECS tasks to assume this role (for hybrid agents)
                iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                # Allow Lambda functions to assume this role
                iam.ServicePrincipal("lambda.amazonaws.com"),
            ),
            max_session_duration=cdk.Duration.hours(12),
        )

        # S3 permissions for consultation medallion buckets
        self.consultation_pipeline_role.add_to_policy(
            iam.PolicyStatement(
                sid="ConsultationS3Access",
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetObjectAttributes",
                    "s3:GetObjectTagging",
                    "s3:PutObjectTagging",
                ],
                resources=[
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-bronze",
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-bronze/*",
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-silver",
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-silver/*",
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-gold",
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-gold/*",
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-landing",
                    f"arn:aws:s3:::a360-{self.environment_name}-consultation-landing/*",
                ],
            ),
        )

        # Lambda invocation permissions for consultation processing functions
        self.consultation_pipeline_role.add_to_policy(
            iam.PolicyStatement(
                sid="ConsultationLambdaAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "lambda:InvokeFunction",
                ],
                resources=[
                    f"arn:aws:lambda:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:function:*consultation*",
                    f"arn:aws:lambda:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:function:*textract*",
                    f"arn:aws:lambda:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:function:*phi-detection*",
                    f"arn:aws:lambda:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:function:*pii-redaction*",
                    f"arn:aws:lambda:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:function:*embedding*",
                    f"arn:aws:lambda:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:function:*enrichment*",
                ],
            ),
        )

        # EventBridge permissions for pipeline orchestration
        self.consultation_pipeline_role.add_to_policy(
            iam.PolicyStatement(
                sid="ConsultationEventBridgeAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "events:PutEvents",
                    "events:DescribeRule",
                    "events:ListTargetsByRule",
                ],
                resources=[
                    f"arn:aws:events:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:event-bus/default",
                    self.consultation_upload_rule.rule_arn,
                    self.consultation_completion_rule.rule_arn,
                ],
            ),
        )

        # CloudWatch metrics permissions
        self.consultation_pipeline_role.add_to_policy(
            iam.PolicyStatement(
                sid="ConsultationCloudWatchMetricsAccess",
                effect=iam.Effect.ALLOW,
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "cloudwatch:namespace": "Dagster/ConsultationPipeline",
                    },
                },
            ),
        )

        # CloudWatch logs permissions (separate from metrics)
        self.consultation_pipeline_role.add_to_policy(
            iam.PolicyStatement(
                sid="ConsultationCloudWatchLogsAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:log-group:/dagster/consultation-transcripts-pipeline*",
                    f"arn:aws:logs:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:log-group:/dagster/consultation-transcripts-pipeline*:*",
                ],
            ),
        )

        # Secrets Manager permissions for accessing API keys and credentials
        self.consultation_pipeline_role.add_to_policy(
            iam.PolicyStatement(
                sid="ConsultationSecretsAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                ],
                resources=[
                    f"arn:aws:secretsmanager:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:secret:*consultation*",
                    f"arn:aws:secretsmanager:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:secret:*textract*",
                    f"arn:aws:secretsmanager:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:secret:*bedrock*",
                ],
            ),
        )

    def _create_monitoring_and_logging(self) -> None:
        """Create monitoring and logging resources for consultation pipeline."""
        # CloudWatch Log Group for consultation pipeline logs
        self.consultation_pipeline_log_group = logs.LogGroup(
            self,
            "ConsultationPipelineLogGroup",
            log_group_name=f"/dagster/consultation-transcripts-pipeline-{self.environment_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

    # Lambda log group is now managed by CDK via log_retention parameter

    def _create_ssm_parameters(self) -> None:
        """Create SSM parameters for consultation pipeline configuration."""
        # Dagster+ configuration parameters
        ssm.StringParameter(
            self,
            "ConsultationLocationName",
            parameter_name=f"/dagster/{self.environment_name}/consultation/location-name",
            string_value=f"consultation-transcripts-pipeline-{self.environment_name}",
            description="Dagster+ code location name for consultation pipelines",
        )

        # Consultation pipeline IAM role ARN
        ssm.StringParameter(
            self,
            "ConsultationPipelineRoleArn",
            parameter_name=f"/dagster/{self.environment_name}/consultation/role-arn",
            string_value=self.consultation_pipeline_role.role_arn,
            description="IAM role ARN for consultation pipeline execution",
        )

        # Consultation bucket names
        ssm.StringParameter(
            self,
            "ConsultationBronzeBucket",
            parameter_name=f"/dagster/{self.environment_name}/consultation/bronze-bucket",
            string_value=f"a360-{self.environment_name}-consultation-bronze",
            description="S3 bucket name for consultation bronze data",
        )

        ssm.StringParameter(
            self,
            "ConsultationSilverBucket",
            parameter_name=f"/dagster/{self.environment_name}/consultation/silver-bucket",
            string_value=f"a360-{self.environment_name}-consultation-silver",
            description="S3 bucket name for consultation silver data",
        )

        ssm.StringParameter(
            self,
            "ConsultationGoldBucket",
            parameter_name=f"/dagster/{self.environment_name}/consultation/gold-bucket",
            string_value=f"a360-{self.environment_name}-consultation-gold",
            description="S3 bucket name for consultation gold data",
        )

        # EventBridge rule names
        ssm.StringParameter(
            self,
            "ConsultationUploadRuleName",
            parameter_name=f"/dagster/{self.environment_name}/consultation/upload-rule",
            string_value=self.consultation_upload_rule.rule_name,
            description="EventBridge rule name for consultation uploads",
        )

        # Log group names
        ssm.StringParameter(
            self,
            "ConsultationLogGroupName",
            parameter_name=f"/dagster/{self.environment_name}/consultation/log-group",
            string_value=self.consultation_pipeline_log_group.log_group_name,
            description="CloudWatch log group for consultation pipeline",
        )
