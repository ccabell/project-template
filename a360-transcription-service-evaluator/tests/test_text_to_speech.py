"""Tests for the text-to-speech service."""

from unittest.mock import Mock, patch

import pytest


class TestTTSService:
    """Tests for TTS service module loading."""

    @pytest.mark.skip(reason="pydub has Python 3.12 compatibility issues with regex syntax")
    def test_tts_module_import(self):
        """Test that TTS module can be imported with mocked dependencies."""
        with patch("transcription_evaluator.services.text_to_speech.DeepgramClient"), \
             patch("transcription_evaluator.services.text_to_speech.ElevenLabs"), \
             patch("transcription_evaluator.services.text_to_speech.AudioSegment"):
            
            # This should succeed with mocked dependencies
            from transcription_evaluator.services.text_to_speech import TextToSpeechService
            assert TextToSpeechService is not None


class TestTTSServiceConfiguration:
    """Tests for TTS service configuration and basic functionality."""

    @pytest.mark.skip(reason="pydub has Python 3.12 compatibility issues with regex syntax")
    def test_tts_service_init(self):
        """Test TTS service initialization with mocked dependencies."""
        with patch("transcription_evaluator.services.text_to_speech.DeepgramClient"), \
             patch("transcription_evaluator.services.text_to_speech.ElevenLabs"), \
             patch("transcription_evaluator.services.text_to_speech.AudioSegment"), \
             patch("transcription_evaluator.services.text_to_speech.get_settings") as mock_settings:
            
            # Mock settings
            mock_settings.return_value = Mock(
                deepgram_api_key="test-key",
                elevenlabs_api_key="test-key",
                stage="test"
            )
            
            from transcription_evaluator.services.text_to_speech import TextToSpeechService
            
            # Mock storage backend
            mock_storage = Mock()
            
            # This should succeed with proper mocking
            service = TextToSpeechService(mock_storage)
            assert service is not None

    @pytest.mark.skip(reason="pydub has Python 3.12 compatibility issues with regex syntax")
    def test_voice_mapping_constants(self):
        """Test that voice mapping constants exist."""
        with patch("transcription_evaluator.services.text_to_speech.DeepgramClient"), \
             patch("transcription_evaluator.services.text_to_speech.ElevenLabs"), \
             patch("transcription_evaluator.services.text_to_speech.AudioSegment"):
            
            from transcription_evaluator.services.text_to_speech import (
                DEEPGRAM_VOICES, ELEVENLABS_VOICES
            )
            
            assert isinstance(DEEPGRAM_VOICES, dict)
            assert isinstance(ELEVENLABS_VOICES, dict)

    @pytest.mark.skip(reason="pydub has Python 3.12 compatibility issues with regex syntax")
    def test_language_detection_patterns(self):
        """Test language detection helper functions."""
        with patch("transcription_evaluator.services.text_to_speech.DeepgramClient"), \
             patch("transcription_evaluator.services.text_to_speech.ElevenLabs"), \
             patch("transcription_evaluator.services.text_to_speech.AudioSegment"):
            
            from transcription_evaluator.services.text_to_speech import detect_language_from_path
            
            # Test English detection
            result = detect_language_from_path("consultation_data/english/session1/transcript.txt")
            assert result == "en"
            
            # Test Spanish detection
            result = detect_language_from_path("consultation_data/spanish/session1/transcript.txt")
            assert result == "es"
            
            # Test default fallback
            result = detect_language_from_path("consultation_data/unknown/session1/transcript.txt")
            assert result == "en"  # Default to English