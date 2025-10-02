"""Database initialization Lambda for A360 Transcription Service Evaluator.

This Lambda function initializes the Aurora PostgreSQL database with the required
schema for the Cognito-integrated RBAC system using RDS Data API. It supports
CloudFormation custom resource lifecycle events and provides proper signaling
back to CloudFormation.

The function creates all necessary tables and indexes for user management,
role-based access control, transcription processing, and audit logging.

Example:
    Lambda is triggered by CloudFormation custom resource during stack deployment:

    >>> # CloudFormation triggers this Lambda
    >>> response = handler(cfn_event, context)
    >>> response['Status']  # 'SUCCESS' or 'FAILED'
"""

import json
import os
from typing import Any, Dict, List

import boto3
import urllib3
from aws_lambda_powertools import Logger, Metrics, Tracer

# Removed correlation_paths import - not needed for basic logging
from aws_lambda_powertools.metrics import MetricUnit

tracer = Tracer(service="database-init")
logger = Logger(service="database-init")
metrics = Metrics(namespace="TranscriptionService", service="database-init")

http = urllib3.PoolManager()
rds_data = boto3.client("rds-data")


@tracer.capture_lambda_handler
@logger.inject_lambda_context
@metrics.log_metrics
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for database initialization.

    Handles CloudFormation custom resource lifecycle events (Create, Update, Delete)
    and initializes the Aurora PostgreSQL database with the complete schema using RDS Data API.

    Args:
        event (Dict[str, Any]): CloudFormation custom resource event containing
            RequestType, ResponseURL, StackId, RequestId, and ResourceProperties
        context (Any): Lambda runtime context object

    Returns:
        Dict[str, Any]: Response containing StatusCode, Status, and Data

    Raises:
        Exception: Re-raises any unhandled exceptions after logging
    """
    logger.info("Database initialization Lambda started", extra={"event": event})

    # Extract CloudFormation event data
    request_type = event.get("RequestType")
    response_url = event.get("ResponseURL")
    stack_id = event.get("StackId")
    request_id = event.get("RequestId")
    logical_resource_id = event.get("LogicalResourceId")
    properties = event.get("ResourceProperties", {})

    status = "SUCCESS"
    reason = "Database operation completed successfully"
    response_data = {"Timestamp": context.aws_request_id}

    # Fast path for DELETE requests to speed up development iteration
    if request_type == "Delete":
        logger.info("DELETE request detected - taking fast path")
        response_data["Message"] = "Database deletion acknowledged (no action taken)"
        _send_cfn_response(
            response_url,
            stack_id,
            request_id,
            logical_resource_id,
            status,
            response_data,
            "DELETE operation completed quickly",
        )
        return {"StatusCode": 200, "Status": status, "Data": response_data}

    try:
        if request_type == "Create":
            logger.info("Processing Create request")
            metrics.add_metric(
                name="DatabaseCreateRequests", unit=MetricUnit.Count, value=1
            )
            _initialize_database(properties)
            response_data["Message"] = "Database schema created successfully"

        elif request_type == "Update":
            logger.info("Processing Update request")
            metrics.add_metric(
                name="DatabaseUpdateRequests", unit=MetricUnit.Count, value=1
            )
            _initialize_database(properties)
            response_data["Message"] = "Database schema updated successfully"

        else:
            raise ValueError(f"Unknown RequestType: {request_type}")

    except Exception as e:
        logger.error("Database operation failed", extra={"error": str(e)})
        metrics.add_metric(name="DatabaseInitErrors", unit=MetricUnit.Count, value=1)
        status = "FAILED"
        reason = f"Database operation failed: {str(e)}"
        response_data["Error"] = str(e)

    finally:
        # Send response to CloudFormation
        _send_cfn_response(
            response_url,
            stack_id,
            request_id,
            logical_resource_id,
            status,
            response_data,
            reason,
        )

    return {
        "StatusCode": 200 if status == "SUCCESS" else 500,
        "Status": status,
        "Data": response_data,
    }


@tracer.capture_method
def _initialize_database(properties: Dict[str, Any]) -> None:
    """Initialize database with complete schema using RDS Data API.

    Creates all tables, indexes, and initial data for the Cognito-integrated
    RBAC system including users, roles, permissions, and audit tables.

    Args:
        properties (Dict[str, Any]): CloudFormation resource properties containing
            SecretArn, DatabaseArn, and DatabaseName

    Raises:
        ValueError: If required properties are missing
        Exception: If database operations fail
    """
    secret_arn = properties.get("SecretArn")
    database_arn = properties.get("DatabaseArn")
    database_name = properties.get("DatabaseName", "transcription_evaluator")

    if not secret_arn:
        raise ValueError("SecretArn is required in ResourceProperties")
    if not database_arn:
        raise ValueError("DatabaseArn is required in ResourceProperties")

    logger.info(
        "Initializing database schema",
        extra={"database_arn": database_arn, "database_name": database_name},
    )

    try:
        _execute_sql("SELECT version()", secret_arn, database_arn, database_name)
        logger.info("Database connection successful")

        _create_extensions(secret_arn, database_arn, database_name)
        _create_enums(secret_arn, database_arn, database_name)
        _create_tables(secret_arn, database_arn, database_name)
        _create_indexes(secret_arn, database_arn, database_name)
        _create_functions(secret_arn, database_arn, database_name)
        _insert_initial_data(secret_arn, database_arn, database_name)

        logger.info("Database schema initialization completed successfully")

    except Exception as e:
        logger.error("Database initialization failed", extra={"error": str(e)})
        raise


def _execute_sql(
    sql: str,
    secret_arn: str,
    database_arn: str,
    database_name: str,
    parameters: List[Dict] = None,
) -> Dict:
    """Execute SQL statement using RDS Data API.

    Args:
        sql (str): SQL statement to execute
        secret_arn (str): ARN of the secret containing database credentials
        database_arn (str): ARN of the database cluster
        database_name (str): Name of the database
        parameters (List[Dict], optional): SQL parameters

    Returns:
        Dict: Response from RDS Data API
    """
    try:
        params = {
            "secretArn": secret_arn,
            "resourceArn": database_arn,
            "database": database_name,
            "sql": sql,
        }

        if parameters:
            params["parameters"] = parameters

        response = rds_data.execute_statement(**params)
        return response

    except Exception as e:
        logger.error("SQL execution failed", extra={"sql": sql, "error": str(e)})
        raise


def _create_extensions(secret_arn: str, database_arn: str, database_name: str) -> None:
    """Create required PostgreSQL extensions.

    Args:
        secret_arn (str): ARN of the secret containing database credentials
        database_arn (str): ARN of the database cluster
        database_name (str): Name of the database
    """
    logger.info("Creating database extensions")

    extensions = [
        'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";',
        'CREATE EXTENSION IF NOT EXISTS "pgcrypto";',
        'CREATE EXTENSION IF NOT EXISTS "pg_trgm";',
    ]

    for extension in extensions:
        _execute_sql(extension, secret_arn, database_arn, database_name)


def _create_enums(secret_arn: str, database_arn: str, database_name: str) -> None:
    """Create enumeration types for the application.

    Args:
        secret_arn (str): ARN of the secret containing database credentials
        database_arn (str): ARN of the database cluster
        database_name (str): Name of the database
    """
    logger.info("Creating enumeration types")

    enums = [
        "DO $$ BEGIN CREATE TYPE user_status AS ENUM ('active', 'inactive', 'suspended', 'pending'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
        "DO $$ BEGIN CREATE TYPE permission_type AS ENUM ('read', 'write', 'admin', 'owner'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
        "DO $$ BEGIN CREATE TYPE analysis_status AS ENUM ('pending', 'processing', 'completed', 'failed'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
        "DO $$ BEGIN CREATE TYPE transcription_backend AS ENUM ('deepgram', 'whisper', 'assembly', 'google', 'azure'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
        "DO $$ BEGIN CREATE TYPE evaluation_type AS ENUM ('accuracy', 'quality', 'speaker_diarization', 'sentiment'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
        "DO $$ BEGIN CREATE TYPE job_status AS ENUM ('draft', 'ready_to_assign', 'assigned_to_reader', 'audio_submitted', 'completed', 'failed'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
        "DO $$ BEGIN CREATE TYPE assignment_status AS ENUM ('assigned', 'in_progress', 'audio_submitted', 'completed', 'skipped'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
        "DO $$ BEGIN CREATE TYPE assignment_type AS ENUM ('record', 'evaluate', 'review'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
        "DO $$ BEGIN CREATE TYPE priority_level AS ENUM ('high', 'medium', 'low'); EXCEPTION WHEN duplicate_object THEN null; END $$;",
    ]

    for enum_sql in enums:
        _execute_sql(enum_sql, secret_arn, database_arn, database_name)


def _create_tables(secret_arn: str, database_arn: str, database_name: str) -> None:
    """Create all database tables.

    Args:
        secret_arn (str): ARN of the secret containing database credentials
        database_arn (str): ARN of the database cluster
        database_name (str): Name of the database
    """
    logger.info("Creating database tables")

    # Users table (Cognito integration)
    _execute_sql(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            cognito_user_id VARCHAR(128) UNIQUE NOT NULL,
            email VARCHAR(255) NOT NULL,
            username VARCHAR(100) UNIQUE NOT NULL,
            full_name VARCHAR(255),
            status user_status DEFAULT 'active',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP WITH TIME ZONE,
            metadata JSONB DEFAULT '{}'::jsonb
        )
    """,
        secret_arn,
        database_arn,
        database_name,
    )

    # Roles table
    _execute_sql(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(100) UNIQUE NOT NULL,
            description TEXT,
            is_system_role BOOLEAN DEFAULT false,
            permissions JSONB DEFAULT '[]'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """,
        secret_arn,
        database_arn,
        database_name,
    )

    # User roles junction table
    _execute_sql(
        """
        CREATE TABLE IF NOT EXISTS user_roles (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            assigned_by UUID REFERENCES users(id),
            UNIQUE(user_id, role_id)
        )
    """,
        secret_arn,
        database_arn,
        database_name,
    )

    # Transcription evaluations table
    _execute_sql(
        """
        CREATE TABLE IF NOT EXISTS transcription_evaluations (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            consultation_id VARCHAR(255) NOT NULL,
            consultation_uuid UUID,
            backend transcription_backend NOT NULL,
            original_text TEXT,
            corrected_text TEXT,
            ground_truth_text TEXT,
            evaluation_results JSONB DEFAULT '{}'::jsonb,
            accuracy_score DECIMAL(5,4),
            error_rate DECIMAL(5,4),
            status analysis_status DEFAULT 'pending',
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP WITH TIME ZONE,
            metadata JSONB DEFAULT '{}'::jsonb
        )
    """,
        secret_arn,
        database_arn,
        database_name,
    )

    # Analysis reports table
    _execute_sql(
        """
        CREATE TABLE IF NOT EXISTS analysis_reports (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            title VARCHAR(255) NOT NULL,
            description TEXT,
            report_type evaluation_type NOT NULL,
            consultation_ids TEXT[] DEFAULT '{}',
            report_data JSONB NOT NULL DEFAULT '{}'::jsonb,
            storage_path VARCHAR(500),
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """,
        secret_arn,
        database_arn,
        database_name,
    )

    # Audit log table
    _execute_sql(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID REFERENCES users(id),
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(100),
            resource_id VARCHAR(255),
            details JSONB DEFAULT '{}'::jsonb,
            ip_address INET,
            user_agent TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """,
        secret_arn,
        database_arn,
        database_name,
    )

    # Jobs table for script generation and management
    _execute_sql(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            job_id VARCHAR(100) UNIQUE NOT NULL,
            title VARCHAR(255),
            script_content TEXT,
            word_count INTEGER,
            terms_used JSONB DEFAULT '[]'::jsonb,
            pronunciation_guide JSONB DEFAULT '{}'::jsonb,
            brands JSONB DEFAULT '[]'::jsonb,
            vertical VARCHAR(100),
            difficulty_level INTEGER DEFAULT 1,
            status job_status DEFAULT 'draft',
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB DEFAULT '{}'::jsonb
        )
    """,
        secret_arn,
        database_arn,
        database_name,
    )

    # Job assignments table
    _execute_sql(
        """
        CREATE TABLE IF NOT EXISTS job_assignments (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            assignment_id VARCHAR(100) UNIQUE NOT NULL,
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            assigned_to_cognito_id VARCHAR(128) NOT NULL,
            assigned_by_cognito_id VARCHAR(128) NOT NULL,
            assignment_type assignment_type NOT NULL,
            priority priority_level DEFAULT 'medium',
            status assignment_status DEFAULT 'assigned',
            notes TEXT,
            due_date TIMESTAMP WITH TIME ZONE,
            audio_file_s3_key VARCHAR(500),
            audio_submitted_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB DEFAULT '{}'::jsonb
        )
    """,
        secret_arn,
        database_arn,
        database_name,
    )


def _create_indexes(secret_arn: str, database_arn: str, database_name: str) -> None:
    """Create database indexes for performance optimization.

    Args:
        secret_arn (str): ARN of the secret containing database credentials
        database_arn (str): ARN of the database cluster
        database_name (str): Name of the database
    """
    logger.info("Creating database indexes")

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_users_cognito_user_id ON users(cognito_user_id);",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
        "CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);",
        "CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id);",
        "CREATE INDEX IF NOT EXISTS idx_transcription_evaluations_consultation_id ON transcription_evaluations(consultation_id);",
        "CREATE INDEX IF NOT EXISTS idx_transcription_evaluations_backend ON transcription_evaluations(backend);",
        "CREATE INDEX IF NOT EXISTS idx_transcription_evaluations_status ON transcription_evaluations(status);",
        "CREATE INDEX IF NOT EXISTS idx_transcription_evaluations_created_by ON transcription_evaluations(created_by);",
        "CREATE INDEX IF NOT EXISTS idx_analysis_reports_type ON analysis_reports(report_type);",
        "CREATE INDEX IF NOT EXISTS idx_analysis_reports_created_by ON analysis_reports(created_by);",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_job_id ON jobs(job_id);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_created_by ON jobs(created_by);",
        "CREATE INDEX IF NOT EXISTS idx_jobs_vertical ON jobs(vertical);",
        "CREATE INDEX IF NOT EXISTS idx_job_assignments_assignment_id ON job_assignments(assignment_id);",
        "CREATE INDEX IF NOT EXISTS idx_job_assignments_job_id ON job_assignments(job_id);",
        "CREATE INDEX IF NOT EXISTS idx_job_assignments_assigned_to ON job_assignments(assigned_to_cognito_id);",
        "CREATE INDEX IF NOT EXISTS idx_job_assignments_assigned_by ON job_assignments(assigned_by_cognito_id);",
        "CREATE INDEX IF NOT EXISTS idx_job_assignments_status ON job_assignments(status);",
        "CREATE INDEX IF NOT EXISTS idx_job_assignments_priority ON job_assignments(priority);",
        "CREATE INDEX IF NOT EXISTS idx_job_assignments_type ON job_assignments(assignment_type);",
        "CREATE INDEX IF NOT EXISTS idx_job_assignments_assigned_at ON job_assignments(assigned_at);",
    ]

    for index_sql in indexes:
        try:
            _execute_sql(index_sql, secret_arn, database_arn, database_name)
        except Exception as e:
            # Index creation might fail if already exists, log but continue
            logger.warning(
                "Index creation warning", extra={"sql": index_sql, "error": str(e)}
            )


def _create_functions(secret_arn: str, database_arn: str, database_name: str) -> None:
    """Create database functions and triggers.

    Args:
        secret_arn (str): ARN of the secret containing database credentials
        database_arn (str): ARN of the database cluster
        database_name (str): Name of the database
    """
    logger.info("Creating database functions")

    # Updated timestamp trigger function
    _execute_sql(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """,
        secret_arn,
        database_arn,
        database_name,
    )

    # Create triggers for updated_at columns
    tables_with_updated_at = ["users", "roles", "analysis_reports", "jobs", "job_assignments"]
    for table in tables_with_updated_at:
        # Drop existing trigger first (separate statement for RDS Data API)
        _execute_sql(
            f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table}",
            secret_arn,
            database_arn,
            database_name,
        )
        
        # Create new trigger (separate statement for RDS Data API)
        _execute_sql(
            f"""CREATE TRIGGER update_{table}_updated_at 
                BEFORE UPDATE ON {table} 
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()""",
            secret_arn,
            database_arn,
            database_name,
        )


def _insert_initial_data(
    secret_arn: str, database_arn: str, database_name: str
) -> None:
    """Insert initial system data.

    Args:
        secret_arn (str): ARN of the secret containing database credentials
        database_arn (str): ARN of the database cluster
        database_name (str): Name of the database
    """
    logger.info("Inserting initial system data")

    # Insert system roles
    roles = [
        (
            "System Administrator",
            "Full system access with all permissions",
            True,
            '["admin", "read", "write", "delete", "manage_users", "manage_roles"]',
        ),
        (
            "Data Analyst",
            "Access to view and analyze transcription data",
            True,
            '["read", "analyze", "export"]',
        ),
        (
            "Transcription Manager",
            "Manage transcription evaluations and reports",
            True,
            '["read", "write", "manage_evaluations"]',
        ),
        ("Viewer", "Read-only access to transcription data", True, '["read"]'),
    ]

    for name, description, is_system, permissions in roles:
        _execute_sql(
            """
            INSERT INTO roles (name, description, is_system_role, permissions)
            VALUES (:name, :description, :is_system_role, :permissions::jsonb)
            ON CONFLICT (name) DO UPDATE SET
                description = EXCLUDED.description,
                permissions = EXCLUDED.permissions,
                updated_at = CURRENT_TIMESTAMP
        """,
            secret_arn,
            database_arn,
            database_name,
            [
                {"name": "name", "value": {"stringValue": name}},
                {"name": "description", "value": {"stringValue": description}},
                {"name": "is_system_role", "value": {"booleanValue": is_system}},
                {"name": "permissions", "value": {"stringValue": permissions}},
            ],
        )


def _send_cfn_response(
    response_url: str,
    stack_id: str,
    request_id: str,
    logical_resource_id: str,
    status: str,
    response_data: Dict[str, Any],
    reason: str = None,
) -> None:
    """Send response back to CloudFormation.

    Args:
        response_url (str): CloudFormation response URL
        stack_id (str): CloudFormation stack ID
        request_id (str): CloudFormation request ID
        logical_resource_id (str): Logical resource ID
        status (str): Response status ('SUCCESS' or 'FAILED')
        response_data (Dict[str, Any]): Response data to send back
        reason (str, optional): Reason for the response status
    """
    if not response_url:
        logger.warning("No response URL provided, skipping CloudFormation response")
        return

    response_body = {
        "Status": status,
        "Reason": reason
        or f"See CloudWatch Log Stream: {os.environ.get('AWS_LOG_STREAM_NAME', 'unknown')}",
        "PhysicalResourceId": logical_resource_id,
        "StackId": stack_id,
        "RequestId": request_id,
        "LogicalResourceId": logical_resource_id,
        "Data": response_data,
    }

    json_response_body = json.dumps(response_body)

    try:
        headers = {"content-type": "", "content-length": str(len(json_response_body))}

        response = http.request(
            "PUT", response_url, body=json_response_body, headers=headers
        )

        logger.info(
            "CloudFormation response sent",
            extra={"status_code": response.status, "response_status": status},
        )

    except Exception as e:
        logger.error("Failed to send CloudFormation response", extra={"error": str(e)})
        # Must raise to ensure CloudFormation gets notified of failure
        raise
        raise
