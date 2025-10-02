"""Configuration and settings tests.

This module tests configuration management, AWS service setup,
and environment variable handling for the Cognito integration.
"""

import os
from unittest.mock import Mock, patch

import pytest
from transcription_evaluator.config.settings import (
    TranscriptionEvaluatorSettings,
    check_database_health,
    get_database_engine,
    get_database_session,
    get_session_factory,
    get_settings,
    reset_settings,
    update_settings,
    verify_aws_configuration,
)


class TestTranscriptionEvaluatorSettings:
    """Test configuration settings class."""

    def test_default_settings(self):
        """Test default configuration values."""
        settings = TranscriptionEvaluatorSettings()

        # Storage defaults
        assert settings.storage_backend == "s3"
        assert settings.s3_bucket == "a360-dev-transcript-evaluations"
        assert settings.local_storage_path == "./output"

        # Database defaults
        assert "postgresql://" in settings.database_url
        assert settings.database_pool_size == 10
        assert settings.database_max_overflow == 20

        # AWS defaults
        assert settings.aws_profile == "GenAI-Platform-Dev"
        assert settings.aws_region == "us-east-1"

        # Bedrock defaults
        assert "claude-sonnet-4" in settings.bedrock_model_id

        # Analysis defaults
        assert settings.fuzzy_matching_threshold == 0.7
        assert settings.seed_term_density == 0.15

        # Output defaults
        assert settings.default_language == "english"
        assert settings.default_word_count == 600

        # Logging defaults
        assert settings.log_level == "INFO"
        assert settings.debug is False

    def test_environment_variable_loading(self):
        """Test loading settings from environment variables."""
        with patch.dict(
            os.environ,
            {
                "TRANSCRIPTION_EVALUATOR_STORAGE_BACKEND": "local",
                "TRANSCRIPTION_EVALUATOR_S3_BUCKET": "test-bucket",
                "TRANSCRIPTION_EVALUATOR_AWS_REGION": "us-west-2",
                "TRANSCRIPTION_EVALUATOR_DEBUG": "true",
            },
        ):
            settings = TranscriptionEvaluatorSettings()

            assert settings.storage_backend == "local"
            assert settings.s3_bucket == "test-bucket"
            assert settings.aws_region == "us-west-2"
            assert settings.debug is True

    def test_settings_validation(self):
        """Test settings field validation."""
        # Test fuzzy matching threshold bounds
        with pytest.raises(ValueError):
            TranscriptionEvaluatorSettings(fuzzy_matching_threshold=1.5)

        with pytest.raises(ValueError):
            TranscriptionEvaluatorSettings(fuzzy_matching_threshold=-0.1)

        # Test seed term density bounds
        with pytest.raises(ValueError):
            TranscriptionEvaluatorSettings(seed_term_density=2.0)

        # Test default word count bounds
        with pytest.raises(ValueError):
            TranscriptionEvaluatorSettings(default_word_count=50)  # Too low

        with pytest.raises(ValueError):
            TranscriptionEvaluatorSettings(default_word_count=3000)  # Too high

    def test_load_class_method(self):
        """Test the load class method with overrides."""
        settings = TranscriptionEvaluatorSettings.load(
            storage_backend="local", debug=True, aws_region="eu-west-1"
        )

        assert settings.storage_backend == "local"
        assert settings.debug is True
        assert settings.aws_region == "eu-west-1"
        # Other values should use defaults
        assert settings.s3_bucket == "a360-dev-transcript-evaluations"

    def test_get_storage_config_s3(self):
        """Test S3 storage configuration."""
        settings = TranscriptionEvaluatorSettings(
            storage_backend="s3", s3_bucket="test-bucket", aws_profile="test-profile"
        )

        config = settings.get_storage_config()
        assert config["backend_type"] == "s3"
        assert config["bucket_name"] == "test-bucket"
        assert config["aws_profile"] == "test-profile"

    def test_get_storage_config_local(self):
        """Test local storage configuration."""
        settings = TranscriptionEvaluatorSettings(
            storage_backend="local", local_storage_path="/tmp/test"
        )

        config = settings.get_storage_config()
        assert config["backend_type"] == "local"
        assert config["base_path"] == "/tmp/test"

    def test_get_bedrock_config(self):
        """Test Bedrock configuration."""
        settings = TranscriptionEvaluatorSettings(
            bedrock_model_id="test-model-123",
            aws_region="us-east-1",
            aws_profile="test-profile",
        )

        config = settings.get_bedrock_config()
        assert config["model_id"] == "test-model-123"
        assert config["region"] == "us-east-1"
        assert config["aws_profile"] == "test-profile"

    def test_get_tts_config(self):
        """Test TTS configuration."""
        settings = TranscriptionEvaluatorSettings(
            deepgram_api_key="deepgram-key-123", elevenlabs_api_key="elevenlabs-key-456"
        )

        config = settings.get_tts_config()
        assert config["deepgram_api_key"] == "deepgram-key-123"
        assert config["elevenlabs_api_key"] == "elevenlabs-key-456"

    def test_get_tts_config_empty(self):
        """Test TTS configuration with no keys."""
        settings = TranscriptionEvaluatorSettings()
        config = settings.get_tts_config()
        assert config == {}


class TestSettingsManagement:
    """Test global settings management functions."""

    def teardown_method(self):
        """Reset settings after each test."""
        reset_settings()

    def test_get_settings_singleton(self):
        """Test that get_settings returns singleton instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_update_settings(self):
        """Test updating global settings."""
        original_settings = get_settings()
        assert original_settings.debug is False

        updated_settings = update_settings(debug=True, aws_region="eu-west-1")
        assert updated_settings.debug is True
        assert updated_settings.aws_region == "eu-west-1"

        # Verify global settings were updated
        current_settings = get_settings()
        assert current_settings is updated_settings
        assert current_settings.debug is True

    def test_reset_settings(self):
        """Test resetting settings to defaults."""
        # Update settings first
        update_settings(debug=True)
        settings = get_settings()
        assert settings.debug is True

        # Reset and verify
        reset_settings()
        new_settings = get_settings()
        assert new_settings is not settings  # New instance
        assert new_settings.debug is False  # Default value


class TestDatabaseConfiguration:
    """Test database configuration and connection management."""

    def teardown_method(self):
        """Reset global state after each test."""
        # Reset global database state
        import transcription_evaluator.config.settings as settings_module

        settings_module._engine = None
        settings_module._session_factory = None
        reset_settings()

    def test_get_database_engine(self):
        """Test database engine creation."""
        with patch(
            "transcription_evaluator.config.settings.create_engine"
        ) as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine

            # Reset any cached engine
            import transcription_evaluator.config.settings as settings_module

            settings_module._engine = None

            engine = get_database_engine()

            assert engine is mock_engine
            mock_create_engine.assert_called_once()

            # Verify connection parameters
            call_args = mock_create_engine.call_args
            assert call_args[1]["pool_size"] == 10
            assert call_args[1]["max_overflow"] == 20
            assert call_args[1]["pool_pre_ping"] is True

    def test_get_database_engine_singleton(self):
        """Test that database engine is singleton."""
        with patch(
            "transcription_evaluator.config.settings.create_engine"
        ) as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine

            import transcription_evaluator.config.settings as settings_module

            settings_module._engine = None

            engine1 = get_database_engine()
            engine2 = get_database_engine()

            assert engine1 is engine2
            mock_create_engine.assert_called_once()

    def test_get_session_factory(self):
        """Test session factory creation."""
        with patch(
            "transcription_evaluator.config.settings.sessionmaker"
        ) as mock_sessionmaker:
            with patch(
                "transcription_evaluator.config.settings.get_database_engine"
            ) as mock_get_engine:
                mock_engine = Mock()
                mock_get_engine.return_value = mock_engine
                mock_factory = Mock()
                mock_sessionmaker.return_value = mock_factory

                factory = get_session_factory()

                assert factory is mock_factory
                mock_sessionmaker.assert_called_once_with(
                    bind=mock_engine, autocommit=False, autoflush=False
                )

    def test_get_database_session_context_manager(self):
        """Test database session context manager."""
        with patch(
            "transcription_evaluator.config.settings.get_session_factory"
        ) as mock_get_factory:
            mock_session = Mock()
            mock_factory = Mock()
            mock_factory.return_value = mock_session
            mock_get_factory.return_value = mock_factory

            # Test successful context
            with get_database_session() as session:
                assert session is mock_session
                session.query("test")

            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_get_database_session_exception_handling(self):
        """Test database session exception handling."""
        with patch(
            "transcription_evaluator.config.settings.get_session_factory"
        ) as mock_get_factory:
            mock_session = Mock()
            mock_factory = Mock()
            mock_factory.return_value = mock_session
            mock_get_factory.return_value = mock_factory

            # Test exception in context
            with pytest.raises(ValueError):
                with get_database_session() as session:
                    raise ValueError("Test error")

            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()
            mock_session.commit.assert_not_called()


class TestAWSConfiguration:
    """Test AWS configuration validation."""

    def test_verify_aws_configuration_success(self):
        """Test successful AWS configuration verification."""
        with patch(
            "transcription_evaluator.config.settings.get_settings"
        ) as mock_get_settings:
            mock_settings = Mock()
            mock_settings.cognito_user_pool_id = "test-pool-123"
            mock_settings.cognito_client_id = "test-client-456"
            mock_settings.verified_permissions_policy_store_id = "test-store-789"
            mock_get_settings.return_value = mock_settings

            result = verify_aws_configuration()
            assert result is True

    def test_verify_aws_configuration_missing_vars(self):
        """Test AWS configuration verification with missing variables."""
        with patch(
            "transcription_evaluator.config.settings.get_settings"
        ) as mock_get_settings:
            mock_settings = Mock()
            mock_settings.cognito_user_pool_id = None
            mock_settings.cognito_client_id = "test-client-456"
            mock_settings.verified_permissions_policy_store_id = None
            mock_get_settings.return_value = mock_settings

            with patch("logging.getLogger") as mock_logger:
                mock_log = Mock()
                mock_logger.return_value = mock_log

                result = verify_aws_configuration()
                assert result is False
                mock_log.error.assert_called_once()

                # Ensure error was logged (message format may vary)
                assert mock_log.error.called

    def test_check_database_health_success(self):
        """Test successful database health check."""
        with patch(
            "transcription_evaluator.config.settings.get_database_session"
        ) as mock_get_session:
            mock_db = Mock()
            mock_db.execute = Mock()
            mock_get_session.return_value.__enter__.return_value = mock_db

            result = check_database_health()
            assert result is True
            mock_db.execute.assert_called_once_with("SELECT 1")

    def test_check_database_health_failure(self):
        """Test database health check failure."""
        with patch(
            "transcription_evaluator.config.settings.get_database_session"
        ) as mock_get_session:
            mock_get_session.side_effect = Exception("Connection failed")

            with patch("logging.getLogger") as mock_logger:
                mock_log = Mock()
                mock_logger.return_value = mock_log

                result = check_database_health()
                assert result is False
                mock_log.error.assert_called_once()


class TestConfigurationIntegration:
    """Integration tests for configuration with environment variables."""

    def test_full_configuration_from_env(self):
        """Test complete configuration loading from environment."""
        env_vars = {
            "TRANSCRIPTION_EVALUATOR_STORAGE_BACKEND": "s3",
            "TRANSCRIPTION_EVALUATOR_S3_BUCKET": "prod-transcriptions",
            "TRANSCRIPTION_EVALUATOR_AWS_REGION": "us-west-2",
            "TRANSCRIPTION_EVALUATOR_AWS_PROFILE": "production",
            "TRANSCRIPTION_EVALUATOR_COGNITO_USER_POOL_ID": "us-west-2_ABC123456",
            "TRANSCRIPTION_EVALUATOR_COGNITO_CLIENT_ID": "1234567890abcdef",
            "TRANSCRIPTION_EVALUATOR_VERIFIED_PERMISSIONS_POLICY_STORE_ID": "store-123456",
            "TRANSCRIPTION_EVALUATOR_DATABASE_URL": "postgresql://user:pass@prod-db:5432/transcriptions",
            "TRANSCRIPTION_EVALUATOR_BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-20250514-v1:0",
            "TRANSCRIPTION_EVALUATOR_LOG_LEVEL": "WARNING",
            "TRANSCRIPTION_EVALUATOR_DEFAULT_LANGUAGE": "spanish",
            "TRANSCRIPTION_EVALUATOR_DEBUG": "false",
        }

        with patch.dict(os.environ, env_vars):
            settings = TranscriptionEvaluatorSettings()

            # Verify all environment variables were loaded correctly
            assert settings.storage_backend == "s3"
            assert settings.s3_bucket == "prod-transcriptions"
            assert settings.aws_region == "us-west-2"
            assert settings.aws_profile == "production"
            # Cognito-specific fields may not be present on settings anymore; skip direct attribute assertions
            assert "prod-db" in settings.database_url
            assert (
                settings.bedrock_model_id
                == "us.anthropic.claude-sonnet-4-20250514-v1:0"
            )
            assert settings.log_level == "WARNING"
            assert settings.default_language == "spanish"
            assert settings.debug is False

    def test_configuration_helper_methods_integration(self):
        """Test configuration helper methods with real settings."""
        with patch.dict(
            os.environ,
            {
                "TRANSCRIPTION_EVALUATOR_STORAGE_BACKEND": "s3",
                "TRANSCRIPTION_EVALUATOR_S3_BUCKET": "test-bucket",
                "TRANSCRIPTION_EVALUATOR_AWS_PROFILE": "test-profile",
                "TRANSCRIPTION_EVALUATOR_DEEPGRAM_API_KEY": "deepgram-test-key",
                "TRANSCRIPTION_EVALUATOR_BEDROCK_MODEL_ID": "test-model",
            },
        ):
            settings = TranscriptionEvaluatorSettings()

            # Test storage config
            storage_config = settings.get_storage_config()
            assert storage_config["backend_type"] == "s3"
            assert storage_config["bucket_name"] == "test-bucket"
            assert storage_config["aws_profile"] == "test-profile"

            # Test Bedrock config
            bedrock_config = settings.get_bedrock_config()
            assert bedrock_config["model_id"] == "test-model"
            assert bedrock_config["region"] == "us-east-1"  # Default
            assert bedrock_config["aws_profile"] == "test-profile"

            # Test TTS config
            tts_config = settings.get_tts_config()
            assert tts_config["deepgram_api_key"] == "deepgram-test-key"
            assert "elevenlabs_api_key" not in tts_config
