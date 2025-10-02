#!/usr/bin/env python3
"""Configuration management for transcription evaluation toolkit.

This module provides centralized configuration management using Pydantic settings
with support for environment variables and defaults. It also provides helpers for
database connections and AWS-related configuration validation.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


class TranscriptionEvaluatorSettings(BaseSettings):
    """Main configuration class for the transcription evaluator.

    Args:
        aws_region: AWS region for services
        cognito_user_pool_id: AWS Cognito User Pool ID
        cognito_client_id: AWS Cognito App Client ID
        verified_permissions_policy_store_id: AWS Verified Permissions Policy Store ID
        storage_backend: Storage backend identifier.
        s3_bucket: S3 bucket for evaluation artifacts.
        local_storage_path: Local path when using the local backend.
        database_url: Direct database URL; if set, other database fields are ignored.
        database_host: Database host name.
        database_port: Database port number.
        database_name: Database name.
        database_user: Database user name.
        database_password: Database user password.
        database_pool_size: SQLAlchemy connection pool size.
        database_max_overflow: SQLAlchemy max overflow connections.
        aws_profile: AWS named profile.
        aws_region: AWS region name.
        transcription_bucket: S3 bucket for source transcriptions.
        bedrock_model_id: Bedrock model identifier to use.
        deepgram_api_key: Deepgram API key.
        elevenlabs_api_key: ElevenLabs API key.
        fuzzy_matching_threshold: Threshold for fuzzy matching.
        seed_term_density: Density of seed terms in generated scripts.
        default_language: Default language for processing.
        default_word_count: Target word count for generated scripts.
        log_level: Application log level.
        log_format: Logging format string.
        debug: Debug mode flag.

    Returns:
        A validated settings object sourced from environment variables and defaults.
    """

    aws_region: str = Field(default="us-east-1", description="AWS region for services")

    cognito_user_pool_id: Optional[str] = Field(
        default=None, description="AWS Cognito User Pool ID"
    )
    cognito_client_id: Optional[str] = Field(
        default=None, description="AWS Cognito App Client ID"
    )
    verified_permissions_policy_store_id: Optional[str] = Field(
        default=None, description="AWS Verified Permissions Policy Store ID"
    )

    model_config = SettingsConfigDict(
        env_prefix="TRANSCRIPTION_EVALUATOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Storage Configuration
    storage_backend: Literal["s3", "local"] = Field(
        default="s3", description="Storage backend to use: 's3' or 'local'"
    )

    s3_bucket: str = Field(
        description="S3 bucket name for storage (from environment variable)",
    )

    local_storage_path: str = Field(
        default="./output",
        description="Local storage base path when using local backend",
    )

    # Database Configuration
    database_url: Optional[str] = Field(
        default="postgresql://localhost:5432/transcription_evaluator",
        description="Database connection URL (PostgreSQL)",
    )

    database_host: str = Field(default="localhost", description="Database host")

    database_port: int = Field(default=5432, description="Database port")

    database_name: str = Field(
        default="transcription_evaluator", description="Database name"
    )

    database_user: Optional[str] = Field(default=None, description="Database username")

    database_password: Optional[str] = Field(
        default=None, description="Database password"
    )

    database_pool_size: int = Field(
        default=10, description="SQLAlchemy connection pool size"
    )

    database_max_overflow: int = Field(
        default=20, description="SQLAlchemy max overflow connections"
    )

    # AWS Configuration
    aws_profile: Optional[str] = Field(
        default=None,
        description="AWS profile to use for S3 access (None uses IAM role in ECS)",
    )

    aws_region: str = Field(default="us-east-1", description="AWS region for services")

    transcription_bucket: str = Field(
        default="a360-dev-consultation-transcriptions-2",
        description="S3 bucket for source transcription data",
    )

    # Bedrock Configuration
    bedrock_model_id: str = Field(
        default="us.anthropic.claude-sonnet-4-20250514-v1:0",
        description="Bedrock model ID for Claude Sonnet 4",
    )

    # TTS Configuration
    deepgram_api_key: Optional[str] = Field(
        default=None, description="Deepgram API key for text-to-speech"
    )

    elevenlabs_api_key: Optional[str] = Field(
        default=None, description="ElevenLabs API key for text-to-speech"
    )

    # Analysis Configuration
    fuzzy_matching_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Fuzzy matching confidence threshold"
    )

    seed_term_density: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Default seed term density for generated scripts",
    )

    # Output Configuration
    default_language: Literal["english", "spanish"] = Field(
        default="english", description="Default language for processing"
    )

    default_word_count: int = Field(
        default=600,
        ge=100,
        le=2000,
        description="Default word count for generated scripts",
    )

    # Logging Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Logging format string",
    )

    # Development Configuration
    debug: bool = Field(default=False, description="Enable debug mode")

    @classmethod
    def load(cls, **kwargs) -> "TranscriptionEvaluatorSettings":
        """
        Load settings with optional overrides.

        Args:
            **kwargs: Override values for settings

        Returns:
            TranscriptionEvaluatorSettings instance
        """
        return cls(**kwargs)

    def get_storage_config(self) -> dict:
        """Get configuration for storage backend."""
        if self.storage_backend == "s3":
            return {
                "backend_type": "s3",
                "bucket_name": self.s3_bucket,
                "aws_profile": self.aws_profile,
            }
        else:
            return {"backend_type": "local", "base_path": self.local_storage_path}

    def get_bedrock_config(self) -> dict:
        """Get configuration for Bedrock."""
        return {
            "model_id": self.bedrock_model_id,
            "region": self.aws_region,
            "aws_profile": self.aws_profile,
        }

    def get_tts_config(self) -> dict:
        """Get configuration for text-to-speech."""
        config = {}
        if self.deepgram_api_key:
            config["deepgram_api_key"] = self.deepgram_api_key
        if self.elevenlabs_api_key:
            config["elevenlabs_api_key"] = self.elevenlabs_api_key
        return config


# Global settings instance
_settings: Optional[TranscriptionEvaluatorSettings] = None


def get_settings() -> TranscriptionEvaluatorSettings:
    """Get global settings instance.

    Returns:
        TranscriptionEvaluatorSettings: Singleton settings instance.
    """
    global _settings
    if _settings is None:
        _settings = TranscriptionEvaluatorSettings()
    return _settings


def update_settings(**kwargs) -> TranscriptionEvaluatorSettings:
    """Update global settings with new values.

    Args:
        **kwargs: Fields to override when constructing new settings.

    Returns:
        TranscriptionEvaluatorSettings: Newly created settings instance.
    """
    global _settings
    _settings = TranscriptionEvaluatorSettings(**kwargs)
    return _settings


def reset_settings():
    """Reset settings to default values.

    This clears the cached singleton so the next call to get_settings will
    construct a fresh instance using current environment variables.
    """
    global _settings
    _settings = None


# Database session management
_engine: Optional[object] = None
_session_factory: Optional[sessionmaker] = None


def get_database_url() -> str:
    """Get database connection URL.

    Returns:
        str: Database URL derived from settings.

    Raises:
        ValueError: If required credentials are missing when building the URL.
    """
    settings = get_settings()

    if settings.database_url:
        return settings.database_url

    # Build URL from components
    if not settings.database_user or not settings.database_password:
        raise ValueError("Database credentials not configured")

    return (
        f"postgresql://{settings.database_user}:{settings.database_password}"
        f"@{settings.database_host}:{settings.database_port}/{settings.database_name}"
    )


def get_database_engine():
    """Get SQLAlchemy database engine.

    Returns:
        Engine: SQLAlchemy engine instance created once per process.
    """
    global _engine
    if _engine is None:
        database_url = get_database_url()
        settings = get_settings()
        _engine = create_engine(
            database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
            echo=settings.debug,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    """Get SQLAlchemy session factory.

    Returns:
        sessionmaker: Configured sessionmaker bound to the engine.
    """
    global _session_factory
    if _session_factory is None:
        engine = get_database_engine()
        _session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return _session_factory


@contextmanager
def get_database_session() -> Generator[Session, None, None]:
    """Context manager for database sessions.

    Yields:
        Session: Active SQLAlchemy session bound to the engine.

    Raises:
        Exception: Propagates exceptions after rolling back the session.
    """
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def verify_aws_configuration() -> bool:
    """Verify required AWS configuration values are present.

    Returns:
        bool: True when all required values are set; otherwise False.
    """
    settings = get_settings()
    missing: list[str] = []

    required_map: dict[str, Optional[str]] = {
        "COGNITO_USER_POOL_ID": settings.cognito_user_pool_id
        if hasattr(settings, "cognito_user_pool_id")
        else None,
        "COGNITO_CLIENT_ID": settings.cognito_client_id
        if hasattr(settings, "cognito_client_id")
        else None,
        "VERIFIED_PERMISSIONS_POLICY_STORE_ID": settings.verified_permissions_policy_store_id
        if hasattr(settings, "verified_permissions_policy_store_id")
        else None,
    }

    for env_name, value in required_map.items():
        if value in (None, ""):
            missing.append(env_name)

    if missing:
        logger = logging.getLogger(__name__)
        logger.error("Missing required AWS configuration: %s", ", ".join(missing))
        return False

    return True


def check_database_health() -> bool:
    """Check database connectivity and basic query health.

    Returns:
        bool: True if the database responds to a simple query; otherwise False.
    """
    try:
        with get_database_session() as session:
            session.execute("SELECT 1")
            return True
    except Exception:
        logger = logging.getLogger(__name__)
        logger.error("Database health check failed")
        return False
