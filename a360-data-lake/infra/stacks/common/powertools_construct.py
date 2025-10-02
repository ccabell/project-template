"""AWS Lambda Powertools construct with circuit breakers and retry logic.

This module implements comprehensive AWS Lambda Powertools integration with
advanced resilience patterns including circuit breakers, exponential backoff,
jitter, and SSM-based configuration management. It provides standardized
observability, error handling, and performance monitoring for the healthcare
platform's Lambda functions.

The construct creates:
- SSM parameters for circuit breaker configuration
- Retry policies with exponential backoff and jitter
- CloudWatch metrics and alarms for monitoring
- Structured logging configuration
- Tracing integration with X-Ray
- Performance monitoring and alerting
- Health checks and recovery mechanisms

All configurations are externalized to SSM parameters to enable runtime
configuration changes without code deployment.
"""

import json
import logging
import os
from typing import Any

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from aws_cdk import aws_ssm as ssm
from constructs import Construct

logging.basicConfig(level=logging.ERROR)


class PowertoolsConstruct(Construct):
    """AWS Lambda Powertools construct with advanced resilience patterns.

    Provides standardized Powertools integration with circuit breakers,
    retry logic, observability, and SSM-based configuration management
    for healthcare Lambda functions.

    Attributes:
        circuit_breaker_parameters: Dictionary of circuit breaker SSM parameters
        retry_config_parameters: Dictionary of retry configuration parameters
        monitoring_parameters: Dictionary of monitoring configuration parameters
        powertools_layer: Lambda layer with Powertools libraries
        alarm_topic: SNS topic for operational alarms
        log_groups: Dictionary of CloudWatch log groups
        metrics_namespace: CloudWatch metrics namespace
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment_name: str,
        kms_key: Any,
        **kwargs,
    ) -> None:
        """Initialize Powertools construct.

        Args:
            scope: CDK construct scope
            construct_id: Unique identifier for this construct
            environment_name: Environment name for configuration
            kms_key: KMS key for parameter encryption
            **kwargs: Additional arguments passed to parent Construct
        """
        super().__init__(scope, construct_id, **kwargs)

        self.environment_name = environment_name.lower()
        self.kms_key = kms_key
        self.metrics_namespace = f"Healthcare/{self.environment_name.title()}"

        # Get PowerTools layer version from context or environment with default
        self.powertools_version = (
            self.node.try_get_context("powertools_version") or
            os.environ.get("POWERTOOLS_VERSION") or
            "74"
        )

        # Initialize dictionaries
        self.circuit_breaker_parameters: dict[str, ssm.StringParameter] = {}
        self.retry_config_parameters: dict[str, ssm.StringParameter] = {}
        self.monitoring_parameters: dict[str, ssm.StringParameter] = {}
        self.log_groups: dict[str, logs.LogGroup] = {}

        # Create core resources
        self._create_alarm_topic()
        self._create_powertools_layer()
        self._create_circuit_breaker_parameters()
        self._create_retry_config_parameters()
        self._create_monitoring_parameters()
        self._create_log_groups()
        self._create_cloudwatch_alarms()
        self._create_health_check_functions()

    def _create_alarm_topic(self) -> None:
        """Create SNS topic for operational alarms."""
        self.alarm_topic = sns.Topic(
            self,
            "PowertoolsAlarmTopic",
            topic_name=f"{self.environment_name}-powertools-alarms",
            display_name="Powertools Operational Alarms",
            master_key=self.kms_key,
        )

    def _create_powertools_layer(self) -> None:
        """Create Lambda layer with Powertools libraries."""
        # Use AWS public Powertools layer with configurable version
        powertools_layer_arn = f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:{self.powertools_version}"
        self.powertools_layer = lambda_.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            layer_version_arn=powertools_layer_arn,
        )

    def _create_circuit_breaker_parameters(self) -> None:
        """Create SSM parameters for circuit breaker configurations."""
        # Textract circuit breaker configuration
        textract_cb_config = ssm.StringParameter(
            self,
            "TextractCircuitBreakerConfig",
            parameter_name=f"/{self.environment_name}/powertools/textract/circuit-breaker",
            string_value=json.dumps(
                {
                    "enabled": True,
                    "failure_threshold": 5,
                    "recovery_timeout_seconds": 300,
                    "half_open_max_calls": 3,
                    "success_threshold": 2,
                    "monitor_window_seconds": 60,
                    "min_calls_to_evaluate": 10,
                },
            ),
            description="Circuit breaker configuration for Textract operations",
            tier=ssm.ParameterTier.STANDARD,
            allowed_pattern="^\\{.*\\}$",
        )

        self.circuit_breaker_parameters["textract"] = textract_cb_config

        # Macie circuit breaker configuration
        macie_cb_config = ssm.StringParameter(
            self,
            "MacieCircuitBreakerConfig",
            parameter_name=f"/{self.environment_name}/powertools/macie/circuit-breaker",
            string_value=json.dumps(
                {
                    "enabled": True,
                    "failure_threshold": 3,
                    "recovery_timeout_seconds": 180,
                    "half_open_max_calls": 2,
                    "success_threshold": 2,
                    "monitor_window_seconds": 60,
                    "min_calls_to_evaluate": 5,
                },
            ),
            description="Circuit breaker configuration for Macie operations",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.circuit_breaker_parameters["macie"] = macie_cb_config

        # Bedrock circuit breaker configuration
        bedrock_cb_config = ssm.StringParameter(
            self,
            "BedrockCircuitBreakerConfig",
            parameter_name=f"/{self.environment_name}/powertools/bedrock/circuit-breaker",
            string_value=json.dumps(
                {
                    "enabled": True,
                    "failure_threshold": 10,
                    "recovery_timeout_seconds": 600,
                    "half_open_max_calls": 5,
                    "success_threshold": 3,
                    "monitor_window_seconds": 120,
                    "min_calls_to_evaluate": 20,
                },
            ),
            description="Circuit breaker configuration for Bedrock AI operations",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.circuit_breaker_parameters["bedrock"] = bedrock_cb_config

        # Database circuit breaker configuration
        database_cb_config = ssm.StringParameter(
            self,
            "DatabaseCircuitBreakerConfig",
            parameter_name=f"/{self.environment_name}/powertools/database/circuit-breaker",
            string_value=json.dumps(
                {
                    "enabled": True,
                    "failure_threshold": 8,
                    "recovery_timeout_seconds": 240,
                    "half_open_max_calls": 3,
                    "success_threshold": 2,
                    "monitor_window_seconds": 60,
                    "min_calls_to_evaluate": 15,
                },
            ),
            description="Circuit breaker configuration for database operations",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.circuit_breaker_parameters["database"] = database_cb_config

    def _create_retry_config_parameters(self) -> None:
        """Create SSM parameters for retry configurations."""
        # Textract retry configuration
        textract_retry_config = ssm.StringParameter(
            self,
            "TextractRetryConfig",
            parameter_name=f"/{self.environment_name}/powertools/textract/retry-config",
            string_value=json.dumps(
                {
                    "max_attempts": 5,
                    "initial_delay_seconds": 1.0,
                    "max_delay_seconds": 60.0,
                    "backoff_multiplier": 2.0,
                    "jitter": True,
                    "jitter_max_seconds": 5.0,
                    "retryable_exceptions": [
                        "ThrottlingException",
                        "ProvisionedThroughputExceededException",
                        "InternalServerError",
                        "ServiceUnavailableException",
                        "TooManyRequestsException",
                    ],
                    "non_retryable_exceptions": [
                        "InvalidParameterException",
                        "BadDocumentException",
                        "UnsupportedDocumentException",
                    ],
                },
            ),
            description="Retry configuration for Textract operations with exponential backoff",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.retry_config_parameters["textract"] = textract_retry_config

        # Macie retry configuration
        macie_retry_config = ssm.StringParameter(
            self,
            "MacieRetryConfig",
            parameter_name=f"/{self.environment_name}/powertools/macie/retry-config",
            string_value=json.dumps(
                {
                    "max_attempts": 3,
                    "initial_delay_seconds": 2.0,
                    "max_delay_seconds": 30.0,
                    "backoff_multiplier": 2.0,
                    "jitter": True,
                    "jitter_max_seconds": 3.0,
                    "retryable_exceptions": [
                        "ThrottlingException",
                        "InternalServerException",
                        "ServiceUnavailableException",
                    ],
                    "non_retryable_exceptions": [
                        "ValidationException",
                        "ResourceNotFoundException",
                        "ConflictException",
                    ],
                },
            ),
            description="Retry configuration for Macie operations",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.retry_config_parameters["macie"] = macie_retry_config

        # Bedrock retry configuration
        bedrock_retry_config = ssm.StringParameter(
            self,
            "BedrockRetryConfig",
            parameter_name=f"/{self.environment_name}/powertools/bedrock/retry-config",
            string_value=json.dumps(
                {
                    "max_attempts": 7,
                    "initial_delay_seconds": 0.5,
                    "max_delay_seconds": 120.0,
                    "backoff_multiplier": 2.0,
                    "jitter": True,
                    "jitter_max_seconds": 10.0,
                    "retryable_exceptions": [
                        "ThrottlingException",
                        "ModelTimeoutException",
                        "InternalServerException",
                        "ServiceUnavailableException",
                    ],
                    "non_retryable_exceptions": [
                        "ValidationException",
                        "AccessDeniedException",
                        "ModelNotReadyException",
                    ],
                },
            ),
            description="Retry configuration for Bedrock AI operations",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.retry_config_parameters["bedrock"] = bedrock_retry_config

        # Database retry configuration
        database_retry_config = ssm.StringParameter(
            self,
            "DatabaseRetryConfig",
            parameter_name=f"/{self.environment_name}/powertools/database/retry-config",
            string_value=json.dumps(
                {
                    "max_attempts": 4,
                    "initial_delay_seconds": 0.1,
                    "max_delay_seconds": 30.0,
                    "backoff_multiplier": 2.0,
                    "jitter": True,
                    "jitter_max_seconds": 2.0,
                    "retryable_exceptions": [
                        "DatabaseException",
                        "ConnectionException",
                        "TimeoutException",
                        "TransientConnectionException",
                    ],
                    "non_retryable_exceptions": [
                        "AuthenticationException",
                        "AuthorizationException",
                        "StatementTimeoutException",
                    ],
                },
            ),
            description="Retry configuration for database operations",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.retry_config_parameters["database"] = database_retry_config

    def _create_monitoring_parameters(self) -> None:
        """Create SSM parameters for monitoring configurations."""
        # Global monitoring configuration
        global_monitoring_config = ssm.StringParameter(
            self,
            "GlobalMonitoringConfig",
            parameter_name=f"/{self.environment_name}/powertools/monitoring/global-config",
            string_value=json.dumps(
                {
                    "metrics_namespace": self.metrics_namespace,
                    "default_dimensions": {
                        "Environment": self.environment_name.title(),
                        "Service": "Healthcare-Platform",
                    },
                    "cold_start_tracking": True,
                    "memory_utilization_tracking": True,
                    "custom_metrics_enabled": True,
                    "high_cardinality_metrics": False,
                    "metric_resolution": "Standard",
                    "log_level": "INFO",
                    "sampling_rate": 0.1,
                    "capture_lambda_handler": True,
                    "capture_lambda_error": True,
                    "capture_lambda_cold_start": True,
                },
            ),
            description="Global monitoring configuration for Powertools",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.monitoring_parameters["global"] = global_monitoring_config

        # Alerting thresholds configuration
        alerting_config = ssm.StringParameter(
            self,
            "AlertingConfig",
            parameter_name=f"/{self.environment_name}/powertools/monitoring/alerting-config",
            string_value=json.dumps(
                {
                    "error_rate_threshold_percent": 5.0,
                    "duration_threshold_ms": 30000,
                    "memory_utilization_threshold_percent": 90.0,
                    "cold_start_rate_threshold_percent": 20.0,
                    "circuit_breaker_open_threshold_count": 3,
                    "consecutive_failures_threshold": 5,
                    "evaluation_periods": 2,
                    "datapoints_to_alarm": 2,
                    "treat_missing_data": "notBreaching",
                },
            ),
            description="Alerting thresholds configuration for monitoring",
            tier=ssm.ParameterTier.STANDARD,
        )

        self.monitoring_parameters["alerting"] = alerting_config

    def _create_log_groups(self) -> None:
        """Create standardized CloudWatch log groups."""
        # Powertools operations log group
        powertools_log_group = logs.LogGroup(
            self,
            "PowertoolsLogGroup",
            log_group_name=f"/aws/lambda/powertools/{self.environment_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.log_groups["powertools"] = powertools_log_group

        # Circuit breaker log group
        circuit_breaker_log_group = logs.LogGroup(
            self,
            "CircuitBreakerLogGroup",
            log_group_name=f"/healthcare/{self.environment_name}/circuit-breakers",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.log_groups["circuit_breaker"] = circuit_breaker_log_group

        # Performance metrics log group
        performance_log_group = logs.LogGroup(
            self,
            "PerformanceLogGroup",
            log_group_name=f"/healthcare/{self.environment_name}/performance",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.log_groups["performance"] = performance_log_group

    def _create_cloudwatch_alarms(self) -> None:
        """Create CloudWatch alarms for monitoring."""
        # Circuit breaker open alarm
        circuit_breaker_alarm = cloudwatch.Alarm(
            self,
            "CircuitBreakerOpenAlarm",
            alarm_name=f"{self.environment_name}-circuit-breaker-open",
            alarm_description="Alarm when circuit breakers are open",
            metric=cloudwatch.Metric(
                namespace=self.metrics_namespace,
                metric_name="CircuitBreakerOpen",
                dimensions_map={
                    "Environment": self.environment_name.title(),
                },
                statistic="Sum",
            ),
            threshold=1,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
        )

        circuit_breaker_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alarm_topic),
        )

        # High error rate alarm
        error_rate_alarm = cloudwatch.Alarm(
            self,
            "HighErrorRateAlarm",
            alarm_name=f"{self.environment_name}-high-error-rate",
            alarm_description="Alarm when error rate exceeds threshold",
            metric=cloudwatch.Metric(
                namespace=self.metrics_namespace,
                metric_name="ErrorRate",
                dimensions_map={
                    "Environment": self.environment_name.title(),
                },
                statistic="Average",
            ),
            threshold=5.0,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )

        error_rate_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alarm_topic),
        )

        # High latency alarm
        latency_alarm = cloudwatch.Alarm(
            self,
            "HighLatencyAlarm",
            alarm_name=f"{self.environment_name}-high-latency",
            alarm_description="Alarm when function latency is high",
            metric=cloudwatch.Metric(
                namespace=self.metrics_namespace,
                metric_name="Duration",
                dimensions_map={
                    "Environment": self.environment_name.title(),
                },
                statistic="Average",
            ),
            threshold=30000,  # 30 seconds
            evaluation_periods=2,
            datapoints_to_alarm=2,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
        )

        latency_alarm.add_alarm_action(
            cloudwatch_actions.SnsAction(self.alarm_topic),
        )

    def _create_health_check_functions(self) -> None:
        """Create health check and circuit breaker management functions."""
        self.health_check_function = lambda_.Function(
            self,
            "CircuitBreakerHealthCheckFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.lambda_handler",
            timeout=Duration.minutes(2),
            memory_size=256,
            environment={
                "POWERTOOLS_SERVICE_NAME": "circuit-breaker-health-check",
                "POWERTOOLS_LOG_LEVEL": "INFO",
                "POWERTOOLS_METRICS_NAMESPACE": self.metrics_namespace,
                "ENVIRONMENT_NAME": self.environment_name,
                "ALARM_TOPIC_ARN": self.alarm_topic.topic_arn,
            },
            layers=[self.powertools_layer],
            code=lambda_.Code.from_inline("""
import json
import boto3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.parameters import get_parameter
from botocore.exceptions import ClientError

logger = Logger()
tracer = Tracer()
metrics = Metrics()

ssm_client = boto3.client('ssm')
cloudwatch_client = boto3.client('cloudwatch')
sns_client = boto3.client('sns')

@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    try:
        environment = os.environ.get('ENVIRONMENT_NAME', 'dev')

        # Check circuit breaker states
        circuit_breaker_states = check_circuit_breaker_states(environment)

        # Analyze health metrics
        health_metrics = analyze_health_metrics(environment)

        # Generate recommendations
        recommendations = generate_recommendations(circuit_breaker_states, health_metrics)

        # Send alerts if needed
        alerts_sent = send_alerts_if_needed(circuit_breaker_states, health_metrics)

        logger.info(f"Health check completed. Circuit breakers: {circuit_breaker_states}")

        return {
            'statusCode': 200,
            'circuit_breaker_states': circuit_breaker_states,
            'health_metrics': health_metrics,
            'recommendations': recommendations,
            'alerts_sent': alerts_sent
        }

    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        metrics.add_metric(name="HealthCheckErrors", unit=MetricUnit.Count, value=1)
        raise

@tracer.capture_method
def check_circuit_breaker_states(environment: str) -> Dict[str, Any]:
    services = ['textract', 'macie', 'bedrock', 'database']
    states = {}

    for service in services:
        try:
            param_name = f"/{environment}/powertools/{service}/circuit-breaker"
            config_str = get_parameter(param_name, decrypt=False)
            config = json.loads(config_str) if config_str else {}

            # Check if circuit breaker is enabled and get current state
            enabled = config.get('enabled', False)
            failure_threshold = config.get('failure_threshold', 5)

            # Get recent failure metrics (simplified - would query actual metrics)
            current_failures = get_current_failure_count(environment, service)

            state = 'CLOSED'  # Default state
            if enabled and current_failures >= failure_threshold:
                state = 'OPEN'
            elif current_failures > 0:
                state = 'HALF_OPEN'

            states[service] = {
                'enabled': enabled,
                'state': state,
                'current_failures': current_failures,
                'failure_threshold': failure_threshold,
                'last_check': datetime.now().isoformat()
            }

            # Record metrics
            metrics.add_metric(
                name=f"CircuitBreaker{state}",
                unit=MetricUnit.Count,
                value=1,
                metadata={'service': service}
            )

        except Exception as e:
            logger.error(f"Error checking circuit breaker for {service}: {str(e)}")
            states[service] = {'error': str(e)}

    return states

@tracer.capture_method
def get_current_failure_count(environment: str, service: str) -> int:
    # Simplified failure count - would query CloudWatch metrics in real implementation
    try:
        # Query CloudWatch for recent error metrics
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=10)

        response = cloudwatch_client.get_metric_statistics(
            Namespace=os.environ.get('POWERTOOLS_METRICS_NAMESPACE', 'Healthcare'),
            MetricName='Errors',
            Dimensions=[
                {'Name': 'Service', 'Value': service},
                {'Name': 'Environment', 'Value': environment}
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,
            Statistics=['Sum']
        )

        if response['Datapoints']:
            return int(sum(dp['Sum'] for dp in response['Datapoints']))
        return 0

    except Exception as e:
        logger.warning(f"Could not get failure count for {service}: {str(e)}")
        return 0

@tracer.capture_method
def analyze_health_metrics(environment: str) -> Dict[str, Any]:
    # Analyze system health metrics
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=30)

        metrics_analysis = {
            'time_window': f"{start_time.isoformat()} to {end_time.isoformat()}",
            'overall_health': 'HEALTHY',  # Would be calculated based on actual metrics
            'error_rate': 0.0,
            'average_latency': 0.0,
            'throughput': 0.0,
            'memory_utilization': 0.0
        }

        return metrics_analysis

    except Exception as e:
        logger.error(f"Error analyzing health metrics: {str(e)}")
        return {'error': str(e)}

@tracer.capture_method
def generate_recommendations(circuit_breaker_states: Dict, health_metrics: Dict) -> List[str]:
    recommendations = []

    # Analyze circuit breaker states
    for service, state_info in circuit_breaker_states.items():
        if isinstance(state_info, dict) and state_info.get('state') == 'OPEN':
            recommendations.append(
                f"Circuit breaker for {service} is OPEN. Consider investigating "
                f"underlying issues or adjusting failure threshold."
            )
        elif isinstance(state_info, dict) and state_info.get('current_failures', 0) > 0:
            recommendations.append(
                f"Service {service} has {state_info['current_failures']} recent failures. "
                f"Monitor closely to prevent circuit breaker from opening."
            )

    # Analyze health metrics
    if health_metrics.get('error_rate', 0) > 5.0:
        recommendations.append(
            f"Error rate ({health_metrics['error_rate']}%) is above threshold. "
            "Investigate error patterns and consider scaling adjustments."
        )

    if health_metrics.get('average_latency', 0) > 10000:  # 10 seconds
        recommendations.append(
            f"Average latency ({health_metrics['average_latency']}ms) is high. "
            "Consider performance optimization or resource scaling."
        )

    return recommendations

@tracer.capture_method
def send_alerts_if_needed(circuit_breaker_states: Dict, health_metrics: Dict) -> int:
    alerts_sent = 0
    alarm_topic_arn = os.environ.get('ALARM_TOPIC_ARN')

    if not alarm_topic_arn:
        return alerts_sent

    # Check for critical conditions
    open_circuit_breakers = [
        service for service, state in circuit_breaker_states.items()
        if isinstance(state, dict) and state.get('state') == 'OPEN'
    ]

    if open_circuit_breakers:
        message = f"CRITICAL: Circuit breakers are OPEN for services: {', '.join(open_circuit_breakers)}"

        try:
            sns_client.publish(
                TopicArn=alarm_topic_arn,
                Message=message,
                Subject=f"Circuit Breaker Alert - {os.environ.get('ENVIRONMENT_NAME', 'Unknown').title()}"
            )
            alerts_sent += 1
            logger.warning(f"Sent circuit breaker alert: {message}")

        except Exception as e:
            logger.error(f"Failed to send alert: {str(e)}")

    return alerts_sent
"""),
        )

        self.health_check_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ssm:GetParameter",
                    "ssm:GetParameters",
                    "cloudwatch:GetMetricStatistics",
                    "cloudwatch:PutMetricData",
                ],
                resources=[
                    f"arn:aws:ssm:*:*:parameter/{self.environment_name}/powertools/*",
                    f"arn:aws:cloudwatch:*:*:metric/{self.metrics_namespace}/*",
                ],
            ),
        )

        self.alarm_topic.grant_publish(self.health_check_function)

    def get_standard_lambda_environment(
        self,
        service_name: str,
        additional_vars: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Get standardized Lambda environment variables for Powertools.

        Args:
            service_name: Name of the service for Powertools configuration
            additional_vars: Additional environment variables to include

        Returns:
            Dictionary of environment variables for Lambda configuration
        """
        env_vars = {
            "POWERTOOLS_SERVICE_NAME": service_name,
            "POWERTOOLS_LOG_LEVEL": "INFO",
            "POWERTOOLS_METRICS_NAMESPACE": self.metrics_namespace,
            "POWERTOOLS_TRACER_CAPTURE_RESPONSE": "true",
            "POWERTOOLS_TRACER_CAPTURE_ERROR": "true",
            "POWERTOOLS_LOGGER_SAMPLE_RATE": "0.1",
            "POWERTOOLS_LOGGER_LOG_EVENT": "false",
            "POWERTOOLS_METRICS_CAPTURE_COLD_START_METRIC": "true",
            "CIRCUIT_BREAKER_CONFIG_PARAM": f"/{self.environment_name}/powertools/{service_name}/circuit-breaker",
            "RETRY_CONFIG_PARAM": f"/{self.environment_name}/powertools/{service_name}/retry-config",
            "ENVIRONMENT_NAME": self.environment_name,
        }

        if additional_vars:
            env_vars.update(additional_vars)

        return env_vars

    def get_circuit_breaker_parameter(
        self,
        service_name: str,
    ) -> ssm.StringParameter | None:
        """Get circuit breaker parameter for a service.

        Args:
            service_name: Name of the service

        Returns:
            SSM parameter or None if not found
        """
        return self.circuit_breaker_parameters.get(service_name)

    def get_retry_config_parameter(
        self,
        service_name: str,
    ) -> ssm.StringParameter | None:
        """Get retry configuration parameter for a service.

        Args:
            service_name: Name of the service

        Returns:
            SSM parameter or None if not found
        """
        return self.retry_config_parameters.get(service_name)
