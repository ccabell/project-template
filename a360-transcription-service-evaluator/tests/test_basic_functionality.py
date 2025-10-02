"""Basic functionality tests to validate test setup.

This module contains simple tests to ensure the test environment
is working correctly before running the full test suite.
"""

import pytest
from unittest.mock import Mock
from transcription_evaluator.config.settings import TranscriptionEvaluatorSettings


class TestBasicFunctionality:
    """Basic functionality tests."""
    
    def test_settings_loading(self):
        """Test that settings can be loaded successfully."""
        settings = TranscriptionEvaluatorSettings()
        assert settings.storage_backend == "s3"
        assert settings.aws_region == "us-east-1"
        assert settings.default_language == "english"
    
    def test_settings_with_overrides(self):
        """Test settings with custom values."""
        settings = TranscriptionEvaluatorSettings(
            storage_backend="local",
            debug=True
        )
        assert settings.storage_backend == "local"
        assert settings.debug is True
    
    def test_settings_validation(self):
        """Test settings field validation."""
        # Valid settings should work
        settings = TranscriptionEvaluatorSettings(
            fuzzy_matching_threshold=0.8,
            default_word_count=500
        )
        assert settings.fuzzy_matching_threshold == 0.8
        assert settings.default_word_count == 500
        
        # Invalid values should raise errors
        with pytest.raises(ValueError):
            TranscriptionEvaluatorSettings(fuzzy_matching_threshold=1.5)
    
    def test_storage_config_generation(self):
        """Test storage configuration generation."""
        # S3 config
        s3_settings = TranscriptionEvaluatorSettings(
            storage_backend="s3",
            s3_bucket="test-bucket"
        )
        s3_config = s3_settings.get_storage_config()
        assert s3_config["backend_type"] == "s3"
        assert s3_config["bucket_name"] == "test-bucket"
        
        # Local config
        local_settings = TranscriptionEvaluatorSettings(
            storage_backend="local",
            local_storage_path="/tmp/test"
        )
        local_config = local_settings.get_storage_config()
        assert local_config["backend_type"] == "local"
        assert local_config["base_path"] == "/tmp/test"
    
    def test_mock_functionality(self):
        """Test that mocking works correctly."""
        mock_service = Mock()
        mock_service.authenticate_user.return_value = {"user_id": "123"}
        
        result = mock_service.authenticate_user("test@example.com", "password")
        assert result["user_id"] == "123"
        mock_service.authenticate_user.assert_called_once_with("test@example.com", "password")


@pytest.mark.asyncio
class TestAsyncFunctionality:
    """Test async functionality."""
    
    async def test_async_mock(self):
        """Test async mocking works correctly."""
        from unittest.mock import AsyncMock
        
        mock_service = Mock()
        mock_service.async_method = AsyncMock(return_value="async_result")
        
        result = await mock_service.async_method("test_param")
        assert result == "async_result"
        mock_service.async_method.assert_called_once_with("test_param")