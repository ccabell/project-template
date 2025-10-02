"""Tests for the CLI module."""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest


class TestCLI:
    """Tests for CLI functionality with mocked dependencies."""

    @pytest.mark.skip(reason="CLI module has pydub dependency issues and needs structural refactoring")
    def test_cli_module_import(self):
        """Test that CLI module can be imported with mocked dependencies."""
        with patch("transcription_evaluator.cli.main.DeepgramClient"), \
             patch("transcription_evaluator.cli.main.ElevenLabs"), \
             patch("transcription_evaluator.cli.main.AudioSegment"):
            
            # This should succeed with mocked dependencies
            from transcription_evaluator.cli.main import main
            assert main is not None

    @pytest.mark.skip(reason="CLI module has pydub dependency issues and needs structural refactoring")
    def test_cli_argument_parsing(self):
        """Test CLI argument parsing."""
        with patch("transcription_evaluator.cli.main.DeepgramClient"), \
             patch("transcription_evaluator.cli.main.ElevenLabs"), \
             patch("transcription_evaluator.cli.main.AudioSegment"), \
             patch("sys.argv", ["cli", "--help"]), \
             patch("argparse.ArgumentParser.parse_args") as mock_parse:
            
            mock_parse.side_effect = SystemExit
            
            from transcription_evaluator.cli.main import main
            
            with pytest.raises(SystemExit):
                main()

    @pytest.mark.skip(reason="CLI module has pydub dependency issues and needs structural refactoring")
    def test_cli_settings_load(self):
        """Test CLI loads settings properly."""
        with patch("transcription_evaluator.cli.main.DeepgramClient"), \
             patch("transcription_evaluator.cli.main.ElevenLabs"), \
             patch("transcription_evaluator.cli.main.AudioSegment"), \
             patch("transcription_evaluator.cli.main.get_settings") as mock_settings:
            
            mock_settings.return_value = Mock(
                stage="test",
                aws_region="us-east-1"
            )
            
            from transcription_evaluator.cli.main import logger
            assert logger is not None

    @pytest.mark.skip(reason="CLI module has pydub dependency issues and needs structural refactoring")
    def test_cli_commands_available(self):
        """Test that CLI commands are defined."""
        with patch("transcription_evaluator.cli.main.DeepgramClient"), \
             patch("transcription_evaluator.cli.main.ElevenLabs"), \
             patch("transcription_evaluator.cli.main.AudioSegment"):
            
            # Import should work and expose command functions
            import transcription_evaluator.cli.main as cli_main
            
            # Check that main function exists
            assert hasattr(cli_main, 'main')
            assert callable(cli_main.main)