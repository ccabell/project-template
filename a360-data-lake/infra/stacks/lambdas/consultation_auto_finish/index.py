"""Lambda function to auto-finish idle and ongoing consultations after 12 hours.

This function runs daily at 12 AM EST to check consultations that have been
in IDLE (2) or ONGOING (1) status for more than 12 hours from their started_at time.
All times are converted to EST for calculation.
"""

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import ClientError

# Try to import Powertools, fall back to basic logging if not available
try:
    from aws_lambda_powertools import Logger, Metrics, Tracer
    from aws_lambda_powertools.metrics import MetricUnit

    # Initialize Powertools
    logger = Logger(service="consultation_auto_finish")
    tracer = Tracer(service="consultation_auto_finish")
    metrics = Metrics(namespace="ConsultationService")

    POWERTOOLS_AVAILABLE = True
except ImportError:
    # Fallback to basic logging
    import logging

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Create dummy classes for when Powertools is not available
    class DummyTracer:
        def capture_lambda_handler(self, func):
            return func

        def capture_method(self, func):
            return func

    class DummyMetrics:
        def log_metrics(self, **kwargs):
            def decorator(func):
                return func

            return decorator

        def add_metric(self, **kwargs):
            pass

    tracer = DummyTracer()
    metrics = DummyMetrics()

    POWERTOOLS_AVAILABLE = False

# Constants
IDLE_STATUS = 2
ONGOING_STATUS = 1
FINISHED_STATUS = 3
DEFAULT_TIMEOUT_MINUTES = 720  # 12 hours
EST_TIMEZONE = ZoneInfo("America/New_York")
MAX_TIMEOUT_MINUTES = 24 * 60  # 24 hours maximum
MIN_TIMEOUT_MINUTES = 1  # 1 minute minimum


class ConsultationAutoFinishError(Exception):
    """Custom exception for consultation auto-finish errors."""


class ConfigurationError(ConsultationAutoFinishError):
    """Raised when there are configuration issues."""


class ValidationError(ConsultationAutoFinishError):
    """Raised when input validation fails."""


class DatabaseError(ConsultationAutoFinishError):
    """Raised when database operations fail."""


@dataclass
class DatabaseConfig:
    """Database configuration from environment variables."""

    cluster_arn: str
    secret_arn: str
    database_name: str
    region: str

    @classmethod
    def from_environment(cls) -> "DatabaseConfig":
        """Create database config from environment variables."""
        required_vars = {
            "DB_CLUSTER_ARN": "cluster_arn",
            "DB_SECRET_ARN": "secret_arn",
            "DB_NAME": "database_name",
        }

        config_values = {}
        for env_var, field_name in required_vars.items():
            value = os.environ.get(env_var)
            if not value:
                msg = f"Missing required environment variable: {env_var}"
                raise ConfigurationError(
                    msg,
                )
            config_values[field_name] = value

        # Get region with fallback
        config_values["region"] = os.environ.get("AWS_REGION", "us-east-1")

        return cls(**config_values)


@dataclass
class TimeInfo:
    """Time calculation information for consultation timeout."""

    cutoff_time_est: str
    cutoff_time_utc: str
    finished_at_utc: str
    timeout_minutes: int


@dataclass
class AutoFinishResult:
    """Result of the auto-finish operation."""

    updated_count: int
    time_info: TimeInfo
    success: bool
    error_message: str | None = None


class TimeCalculator:
    """Handles time calculations for consultation auto-finish operations."""

    @staticmethod
    def calculate_time_info(timeout_minutes: int) -> TimeInfo:
        """Calculate cutoff time in both EST and UTC.

        Args:
            timeout_minutes: Timeout in minutes for idle consultations

        Returns:
            TimeInfo object containing all time-related information
        """
        # Get current time in EST
        now_est = datetime.now(EST_TIMEZONE)
        cutoff_est = now_est - timedelta(minutes=timeout_minutes)

        # Convert to UTC for database query (keep timezone info for proper handling)
        cutoff_utc = cutoff_est.astimezone(UTC)
        finished_at_utc = now_est.astimezone(UTC)

        return TimeInfo(
            cutoff_time_est=cutoff_est.isoformat(),
            cutoff_time_utc=cutoff_utc.isoformat(),
            finished_at_utc=finished_at_utc.isoformat(),
            timeout_minutes=timeout_minutes,
        )


class InputValidator:
    """Handles input validation for the Lambda function."""

    @staticmethod
    def validate_timeout(timeout_minutes: Any) -> int:
        """Validate and convert timeout to integer within acceptable range.

        Args:
            timeout_minutes: Timeout value to validate

        Returns:
            Validated timeout in minutes

        Raises:
            ValidationError: If timeout is invalid
        """
        try:
            timeout = int(timeout_minutes)
        except (TypeError, ValueError) as e:
            msg = f"Invalid timeout value: {timeout_minutes}. Must be an integer."
            raise ValidationError(
                msg,
            ) from e

        if timeout < MIN_TIMEOUT_MINUTES:
            msg = (
                f"Timeout too small: {timeout} minutes. "
                f"Minimum is {MIN_TIMEOUT_MINUTES} minute(s)."
            )
            raise ValidationError(
                msg,
            )

        if timeout > MAX_TIMEOUT_MINUTES:
            msg = (
                f"Timeout too large: {timeout} minutes. "
                f"Maximum is {MAX_TIMEOUT_MINUTES} minutes."
            )
            raise ValidationError(
                msg,
            )

        return timeout


class SQLQueryBuilder:
    """Builds SQL queries for consultation auto-finish operations."""

    @staticmethod
    def build_update_query() -> str:
        """Build the SQL update query for auto-finishing consultations."""
        return """
            UPDATE consultations
            SET
                consultation_status = :finished_status,
                finished_at = (:finished_at)::timestamptz,
                updated_at = (:updated_at)::timestamptz
            WHERE
                consultation_status IN (:idle_status, :ongoing_status)
                AND started_at < (:cutoff_time)::timestamptz
                AND finished_at IS NULL
        """

    @staticmethod
    def build_parameters(time_info: TimeInfo) -> list[dict[str, Any]]:
        """Build parameters for the SQL query."""
        return [
            {"name": "finished_status", "value": {"longValue": FINISHED_STATUS}},
            {"name": "idle_status", "value": {"longValue": IDLE_STATUS}},
            {"name": "ongoing_status", "value": {"longValue": ONGOING_STATUS}},
            {
                "name": "finished_at",
                "value": {"stringValue": time_info.finished_at_utc},
            },
            {
                "name": "updated_at",
                "value": {"stringValue": time_info.finished_at_utc},
            },
            {
                "name": "cutoff_time",
                "value": {"stringValue": time_info.cutoff_time_utc},
            },
        ]


class DatabaseClient:
    """Handles database operations for consultation auto-finish."""

    def __init__(self, config: DatabaseConfig):
        """Initialize the database client."""
        self.config = config
        self._client = None

    @property
    def client(self):
        """Lazy initialization of RDS Data API client."""
        if self._client is None:
            self._client = boto3.client("rds-data", region_name=self.config.region)
        return self._client

    def execute_auto_finish_query(
        self,
        query: str,
        parameters: list[dict[str, Any]],
        max_retries: int = 3,
    ) -> int:
        """Execute the auto-finish SQL query with retry logic for transient errors.

        Args:
            query: SQL query to execute
            parameters: Query parameters
            max_retries: Maximum number of retry attempts for transient failures

        Returns:
            Number of records updated

        Raises:
            DatabaseError: If the database operation fails after all retries
        """
        retry_count = 0
        last_exception = None
        base_delay = 1  # Base delay in seconds for exponential backoff

        while retry_count < max_retries:
            try:
                LoggingService.log_info(
                    "Executing auto-finish query",
                    {
                        "query": query.strip(),
                        "parameters": {p["name"]: p["value"] for p in parameters},
                        "retry_count": retry_count,
                    },
                )

                result = self.client.execute_statement(
                    resourceArn=self.config.cluster_arn,
                    secretArn=self.config.secret_arn,
                    database=self.config.database_name,
                    sql=query,
                    parameters=parameters,
                )

                updated_count = result.get("numberOfRecordsUpdated", 0)
                LoggingService.log_info(
                    f"Database query completed, updated {updated_count} records",
                )

                return updated_count

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")

                # Determine if error is retryable
                retryable_errors = [
                    "ServiceUnavailable",
                    "ThrottlingException",
                    "InternalServerError",
                ]

                if error_code in retryable_errors and retry_count < max_retries - 1:
                    # Calculate exponential backoff with jitter
                    delay = (2**retry_count) * base_delay
                    jitter = 0.1 * delay  # 10% jitter
                    sleep_time = delay + (jitter * (0.5 - (time.time() % 1)))

                    LoggingService.log_error(
                        f"Transient error executing auto-finish query, retrying in {sleep_time:.2f}s",
                        exception=e,
                        extra={
                            "error_code": error_code,
                            "retry_count": retry_count + 1,
                            "max_retries": max_retries,
                            "error_message": str(e),
                        },
                    )
                    time.sleep(sleep_time)
                    retry_count += 1
                    last_exception = e
                else:
                    LoggingService.log_error(
                        "Error executing auto-finish query",
                        exception=e,
                        extra={
                            "error_code": error_code,
                            "error_message": str(e),
                        },
                    )
                    msg = f"Database operation failed: {e!s}"
                    raise DatabaseError(msg) from e

            except Exception as e:
                LoggingService.log_error(
                    "Unexpected error executing auto-finish query",
                    exception=e,
                    extra={"error_message": str(e)},
                )
                msg = f"Database operation failed: {e!s}"
                raise DatabaseError(msg) from e

        # If we've exhausted retries
        if last_exception:
            LoggingService.log_error(
                "Exhausted retries for auto-finish database operation",
                exception=last_exception,
                extra={"error": str(last_exception)},
            )
            msg = f"Database operation failed after {max_retries} retries: {last_exception!s}"
            raise DatabaseError(
                msg,
            ) from last_exception

        # This should never happen, but just in case
        msg = "Unknown error in database operation"
        raise DatabaseError(msg)


class LoggingService:
    """Centralized logging service."""

    @staticmethod
    def log_info(message: str, extra: dict[str, Any] | None = None) -> None:
        """Log info message with optional extra data."""
        if POWERTOOLS_AVAILABLE:
            logger.info(message, extra=extra or {})
        else:
            if extra:
                message = f"{message} - {extra}"
            logger.info(message)

    @staticmethod
    def log_error(
        message: str,
        exception: Exception | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log error message with optional exception and extra data."""
        if POWERTOOLS_AVAILABLE:
            logger.error(message, exc_info=exception is not None, extra=extra or {})
        else:
            if extra:
                message = f"{message} - {extra}"
            logger.error(message, exc_info=exception is not None)

    @staticmethod
    def log_metric(name: str, value: int) -> None:
        """Log metric value."""
        if POWERTOOLS_AVAILABLE:
            metrics.add_metric(name=name, unit=MetricUnit.Count, value=value)
        else:
            # Fallback logging for metrics
            logger.info(f"METRIC: {name}={value}")


class ConsultationAutoFinishService:
    """Main service class for auto-finishing consultations."""

    def __init__(self):
        """Initialize the service."""
        self.validator = InputValidator()
        self.time_calculator = TimeCalculator()
        self.query_builder = SQLQueryBuilder()

    def process_auto_finish(
        self,
        timeout_minutes: int | None = None,
    ) -> AutoFinishResult:
        """Process auto-finish operation for consultations.

        Args:
            timeout_minutes: Optional custom timeout in minutes

        Returns:
            AutoFinishResult containing operation results
        """
        # Validate timeout
        validated_timeout = self.validator.validate_timeout(
            timeout_minutes if timeout_minutes is not None else DEFAULT_TIMEOUT_MINUTES,
        )
        LoggingService.log_info(f"Using timeout of {validated_timeout} minutes")

        # Get database configuration
        db_config = DatabaseConfig.from_environment()
        db_client = DatabaseClient(db_config)

        # Calculate time information
        time_info = self.time_calculator.calculate_time_info(validated_timeout)
        LoggingService.log_info(
            "Calculated cutoff times",
            {
                "timeout_minutes": validated_timeout,
                "cutoff_time_est": time_info.cutoff_time_est,
                "cutoff_time_utc": time_info.cutoff_time_utc,
            },
        )

        # Build query and parameters
        query = self.query_builder.build_update_query()
        parameters = self.query_builder.build_parameters(time_info)

        try:
            # Execute the database operation
            updated_count = db_client.execute_auto_finish_query(query, parameters)

            # Log success metrics
            LoggingService.log_metric("ConsultationsAutoFinished", updated_count)
            LoggingService.log_metric("TimeoutMinutes", validated_timeout)

            LoggingService.log_info(
                f"Successfully auto-finished {updated_count} consultations",
            )

            return AutoFinishResult(
                updated_count=updated_count,
                time_info=time_info,
                success=True,
            )

        except DatabaseError as e:
            return AutoFinishResult(
                updated_count=0,
                time_info=time_info,
                success=False,
                error_message=str(e),
            )


class ResponseBuilder:
    """Builds Lambda function responses."""

    @staticmethod
    def build_success_response(result: AutoFinishResult) -> dict[str, Any]:
        """Build a successful response."""
        response_body = {
            "message": f"Successfully auto-finished {result.updated_count} consultations",
            "updated_count": result.updated_count,
            "timeout_minutes": result.time_info.timeout_minutes,
            "cutoff_time_est": result.time_info.cutoff_time_est,
            "cutoff_time_utc": result.time_info.cutoff_time_utc,
            "finished_at_utc": result.time_info.finished_at_utc,
        }
        return {"statusCode": 200, "body": json.dumps(response_body)}

    @staticmethod
    def build_error_response(error_message: str) -> dict[str, Any]:
        """Build an error response."""
        return {"statusCode": 500, "body": json.dumps({"error": error_message})}


@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Auto-finish idle and ongoing consultations after specified timeout.

    Args:
        event: Lambda event data (can contain custom timeout_minutes)
        _context: Lambda context object (unused)

    Returns:
        Dictionary with statusCode and result message
    """
    try:
        service = ConsultationAutoFinishService()
        result = service.process_auto_finish(event.get("timeout_minutes"))

        if result.success:
            return ResponseBuilder.build_success_response(result)
        raise ConsultationAutoFinishError(result.error_message)

    except (ValidationError, ConfigurationError) as e:
        # Preserve specific validation and configuration errors
        error_message = str(e)
        LoggingService.log_error(error_message, exception=e)
        LoggingService.log_metric("AutoFinishErrors", 1)
        return ResponseBuilder.build_error_response(error_message)
    except Exception as e:
        error_message = f"Error auto-finishing consultations: {e!s}"
        LoggingService.log_error(error_message, exception=e)

        # Log error metrics
        LoggingService.log_metric("AutoFinishErrors", 1)

        return ResponseBuilder.build_error_response(error_message)


# Legacy function references for backward compatibility
_validate_timeout = InputValidator.validate_timeout
_calculate_time_info = TimeCalculator.calculate_time_info
_log_info = LoggingService.log_info
_log_error = LoggingService.log_error
_log_metric = LoggingService.log_metric
