#!/usr/bin/env python3
"""Multilingual text-to-speech engine supporting Deepgram and ElevenLabs APIs.

This module provides a unified interface for generating consultation audio files
using appropriate TTS providers based on language detection. English consultations
use Deepgram's Aura-2 voices for optimal medical terminology handling, while
Spanish consultations leverage ElevenLabs' multilingual capabilities.

The system automatically detects consultation language from directory structure,
applies speaker-aware voice selection, and generates high-quality MP3 outputs
for transcript analysis and quality assurance testing.

Key enhancements:
    • Storage abstraction integration for flexible input/output
    • Unified configuration management
    • Enhanced error handling and logging
    • Support for both local and S3-based workflows

Environment Variables:
    DEEPGRAM_API_KEY: Authentication token for Deepgram TTS services.
    ELEVENLABS_API_KEY: Authentication token for ElevenLabs TTS services.

Dependencies:
    deepgram-sdk: Deepgram TTS client library
    elevenlabs: ElevenLabs TTS client library
    pydub: Audio processing and concatenation
    python-dotenv: Environment variable management
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Protocol, Optional, List, Tuple, Dict, Any

from deepgram import DeepgramClient, SpeakOptions
from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from pydub import AudioSegment

from ..config.settings import get_settings
from ..core.storage import StorageBackend, create_storage_backend

logger = logging.getLogger(__name__)

DEEPGRAM_VOICES: List[str] = [
    "aura-2-thalia-en",
    "aura-2-andromeda-en",
    "aura-2-helena-en",
    "aura-2-apollo-en",
    "aura-2-arcas-en",
    "aura-2-aries-en",
    "aura-2-asteria-en",
    "aura-2-athena-en",
    "aura-2-atlas-en",
    "aura-2-callista-en",
    "aura-2-draco-en",
    "aura-2-hera-en",
    "aura-2-hyperion-en",
    "aura-2-luna-en",
    "aura-2-odysseus-en",
    "aura-2-zeus-en",
]

ELEVENLABS_VOICES: List[str] = [
    "1SM7GgM6IMuvQlz2BwM3",  # Mark: Non-chalant chats
    "vBKc2FfBKJfcZNyEt1n6",  # Finn: Tenor, podcasts and chats
]

SPEAKER_PATTERN = re.compile(r"^(Doctor|Patient):\s*(.+)$", re.IGNORECASE)


class TTSProvider(Protocol):
    """Protocol defining text-to-speech provider interface requirements.

    Establishes contract for TTS implementations ensuring consistent behavior
    across different service providers while maintaining type safety and
    comprehensive error handling capabilities.
    """

    def synthesize_text(self, text: str, voice: str) -> AudioSegment:
        """Synthesizes text to audio using specified voice configuration.

        Args:
            text: Input text content to synthesize.
            voice: Voice identifier for synthesis.

        Returns:
            AudioSegment containing synthesized audio data.

        Raises:
            APIError: If synthesis request fails.
            ValueError: If parameters are invalid.
        """
        ...


class DeepgramProvider:
    """Deepgram TTS provider for English language synthesis.

    Implements high-quality neural text-to-speech using Deepgram's Aura-2
    voice models optimized for medical terminology and professional dialogue.
    Provides superior accuracy for aesthetic medicine consultations.

    Attributes:
        client: Authenticated Deepgram client instance.

    Raises:
        RuntimeError: If DEEPGRAM_API_KEY environment variable is missing.
    """

    def __init__(self) -> None:
        """Initializes Deepgram provider with authenticated client.

        Raises:
            RuntimeError: If API key is not configured.
        """
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPGRAM_API_KEY environment variable required")

        self.client = DeepgramClient(api_key=api_key)

    def synthesize_text(self, text: str, voice: str) -> AudioSegment:
        """Synthesizes text using Deepgram Aura-2 voice models.

        Creates temporary file for audio generation, processes through Deepgram
        TTS service, and returns AudioSegment for further processing.

        Args:
            text: Text content to synthesize.
            voice: Deepgram voice model identifier.

        Returns:
            AudioSegment containing synthesized audio.

        Raises:
            ValueError: If text is empty or voice is invalid.
            RuntimeError: If synthesis fails.
        """
        if not text.strip():
            raise ValueError("Text content cannot be empty")

        if voice not in DEEPGRAM_VOICES:
            raise ValueError(f"Invalid Deepgram voice: {voice}")

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            try:
                payload = {"text": text}
                response = self.client.speak.rest.v("1").save(
                    tmp.name, payload, SpeakOptions(model=voice)
                )

                request_id = self._extract_request_id(response)
                logger.debug(
                    f"Deepgram synthesis completed: voice={voice}, request_id={request_id}, text_length={len(text)}"
                )

                segment = AudioSegment.from_file(tmp.name, format="mp3")
                return segment

            except Exception as e:
                logger.error(f"Deepgram synthesis failed: {e}, voice={voice}, text_length={len(text)}")
                raise RuntimeError(f"Deepgram synthesis failed: {e}") from e
            finally:
                Path(tmp.name).unlink(missing_ok=True)

    def _extract_request_id(self, response: object) -> Optional[str]:
        """Extracts request ID from Deepgram API response for logging.

        Args:
            response: Deepgram API response object.

        Returns:
            Request ID string if available, None otherwise.
        """
        if hasattr(response, "metadata"):
            return getattr(response.metadata, "request_id", None)

        if hasattr(response, "to_json"):
            try:
                data = json.loads(response.to_json())
                return data.get("metadata", {}).get("request_id")
            except Exception:
                return None

        return None


class ElevenLabsProvider:
    """ElevenLabs TTS provider for multilingual synthesis.

    Implements advanced neural text-to-speech using ElevenLabs' multilingual
    models with support for Spanish and other languages. Provides natural
    voice synthesis with configurable voice settings for optimal output quality.

    Attributes:
        client: Authenticated ElevenLabs client instance.

    Raises:
        RuntimeError: If ELEVENLABS_API_KEY environment variable is missing.
    """

    def __init__(self) -> None:
        """Initializes ElevenLabs provider with authenticated client.

        Raises:
            RuntimeError: If API key is not configured.
        """
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError("ELEVENLABS_API_KEY environment variable required")

        self.client = ElevenLabs(api_key=api_key)

    def synthesize_text(self, text: str, voice: str) -> AudioSegment:
        """Synthesizes text using ElevenLabs multilingual models.

        Generates audio using specified voice with optimized settings for
        medical consultation dialogue. Uses the client text_to_speech.convert
        method with proper error handling and temporary file management.

        Args:
            text: Text content to synthesize.
            voice: ElevenLabs voice name identifier.

        Returns:
            AudioSegment containing synthesized audio.

        Raises:
            ValueError: If text is empty or voice is invalid.
            RuntimeError: If synthesis fails.
        """
        if not text.strip():
            raise ValueError("Text content cannot be empty")

        if voice not in ELEVENLABS_VOICES:
            raise ValueError(f"Invalid ElevenLabs voice: {voice}")

        try:
            audio_generator = self.client.text_to_speech.convert(
                voice_id=voice,
                text=text,
                model_id="eleven_multilingual_v2",
                voice_settings={
                    "stability": 0.4,
                    "similarity_boost": 0.9,
                    "style": 0.2,
                    "use_speaker_boost": True,
                },
            )

            audio_bytes = b"".join(chunk for chunk in audio_generator)

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()

                segment = AudioSegment.from_file(tmp.name, format="mp3")

            Path(tmp.name).unlink(missing_ok=True)

            logger.debug(
                f"ElevenLabs synthesis completed: voice={voice}, text_length={len(text)}, audio_duration={len(segment)}ms"
            )

            return segment

        except Exception as e:
            logger.error(f"ElevenLabs synthesis failed: {e}, voice={voice}, text_length={len(text)}")
            raise RuntimeError(f"ElevenLabs synthesis failed: {e}") from e


def detect_language_from_path(file_path: str) -> str:
    """Detects consultation language from file path structure.

    Analyzes directory structure to determine appropriate TTS provider
    based on language-specific directory organization.

    Args:
        file_path: Path to consultation text file.

    Returns:
        Language code ('english' or 'spanish').

    Raises:
        ValueError: If language cannot be determined from path.
    """
    if "english" in file_path.lower():
        return "english"
    elif "spanish" in file_path.lower():
        return "spanish"
    else:
        raise ValueError(f"Cannot determine language from path: {file_path}")


def create_provider(language: str) -> TTSProvider:
    """Creates appropriate TTS provider based on language requirements.

    Factory function for instantiating language-specific TTS providers
    with proper authentication and configuration.

    Args:
        language: Target language for synthesis ('english' or 'spanish').

    Returns:
        Configured TTS provider instance.

    Raises:
        ValueError: If language is not supported.
        RuntimeError: If provider initialization fails.
    """
    match language:
        case "english":
            return DeepgramProvider()
        case "spanish":
            return ElevenLabsProvider()
        case _:
            raise ValueError(f"Unsupported language: {language}")


def select_voices(language: str) -> Tuple[str, str]:
    """Selects appropriate voice pair for doctor and patient speakers.

    Randomly selects complementary voices for doctor and patient roles
    from language-appropriate voice pools to ensure natural dialogue.

    Args:
        language: Target language for voice selection.

    Returns:
        Tuple of (doctor_voice, patient_voice) identifiers.

    Raises:
        ValueError: If language is not supported.
    """
    match language:
        case "english":
            return tuple(random.sample(DEEPGRAM_VOICES, k=2))
        case "spanish":
            return tuple(random.sample(ELEVENLABS_VOICES, k=2))
        case _:
            raise ValueError(f"Unsupported language: {language}")


def parse_consultation_line(line: str) -> Tuple[str, str]:
    """Parses consultation line to extract speaker and utterance.

    Validates line format and extracts speaker role and dialogue content
    for processing by appropriate TTS provider.

    Args:
        line: Consultation line in format "Speaker: utterance".

    Returns:
        Tuple of (speaker_role, utterance_text).

    Raises:
        ValueError: If line format is invalid.
    """
    match = SPEAKER_PATTERN.match(line)
    if not match:
        raise ValueError(f"Invalid line format: {line}")

    speaker, utterance = match.groups()
    return speaker.lower(), utterance.strip()


class TextToSpeechService:
    """Enhanced text-to-speech service with storage abstraction integration."""

    def __init__(
        self,
        storage_backend: Optional[StorageBackend] = None,
        aws_profile: Optional[str] = None,
        load_env: bool = True
    ):
        """Initialize TTS service with storage backend.

        Args:
            storage_backend: Storage backend instance
            aws_profile: AWS profile for authentication
            load_env: Whether to load environment variables
        """
        if load_env:
            load_dotenv()

        self.settings = get_settings()

        if storage_backend:
            self.storage = storage_backend
        else:
            storage_config = self.settings.get_storage_config()
            if aws_profile:
                storage_config["aws_profile"] = aws_profile
            self.storage = create_storage_backend(**storage_config)

        logger.info(f"Initialized TextToSpeechService with storage: {type(self.storage).__name__}")

    def synthesize_consultation_from_storage(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        language: Optional[str] = None
    ) -> str:
        """Synthesizes consultation audio from text stored in storage backend.

        Args:
            input_path: Path to consultation text in storage
            output_path: Optional custom output path for audio
            language: Optional language override

        Returns:
            Storage path of generated audio file

        Raises:
            FileNotFoundError: If input text doesn't exist
            ValueError: If consultation format is invalid
            RuntimeError: If synthesis fails
        """
        # Load text content from storage
        text_content = self.storage.load_text(input_path)

        if not text_content.strip():
            raise ValueError(f"Empty consultation file: {input_path}")

        # Detect language if not provided
        if not language:
            language = detect_language_from_path(input_path)

        # Generate output path if not provided
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = Path(input_path).stem
            output_path = f"tts-audio/{language}/{filename}_{timestamp}.mp3"

        # Synthesize audio
        audio_data = self.synthesize_consultation_text(text_content, language)

        # Save audio to storage
        audio_url = self.storage.save_binary(output_path, audio_data)

        logger.info(f"Consultation synthesized and saved to: {audio_url}")
        return output_path

    def synthesize_consultation_text(self, text_content: str, language: str) -> bytes:
        """Synthesizes consultation text into MP3 audio data.

        Args:
            text_content: Full consultation text content
            language: Language for synthesis

        Returns:
            MP3 audio data as bytes

        Raises:
            ValueError: If consultation format is invalid
            RuntimeError: If synthesis fails
        """
        provider = create_provider(language)

        lines = [
            line.strip()
            for line in text_content.splitlines()
            if line.strip()
        ]

        if not lines:
            raise ValueError("Empty consultation content")

        doctor_voice, patient_voice = select_voices(language)
        consultation_audio = AudioSegment.empty()

        for line in lines:
            try:
                speaker, utterance = parse_consultation_line(line)
                voice = doctor_voice if speaker == "doctor" else patient_voice

                segment = provider.synthesize_text(utterance, voice)
                consultation_audio += segment

            except Exception as e:
                logger.error(f"Line synthesis failed: {line}, error: {e}")
                raise RuntimeError(f"Failed to synthesize line: {line}") from e

        # Export to bytes
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            consultation_audio.export(tmp.name, format="mp3")
            tmp.seek(0)
            audio_bytes = tmp.read()

        Path(tmp.name).unlink(missing_ok=True)

        logger.info(
            f"Consultation synthesized: language={language}, doctor_voice={doctor_voice}, "
            f"patient_voice={patient_voice}, duration_seconds={len(consultation_audio) / 1000:.1f}, "
            f"line_count={len(lines)}"
        )

        return audio_bytes

    def process_batch_synthesis(
        self,
        input_prefix: str = "ground-truth",
        output_prefix: str = "tts-audio",
        language_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process batch synthesis of consultation files from storage.

        Args:
            input_prefix: Storage prefix for input text files
            output_prefix: Storage prefix for output audio files
            language_filter: Optional language filter

        Returns:
            Dict containing processing results and statistics
        """
        try:
            # List available text files
            text_files = self.storage.list_files(input_prefix)

            if language_filter:
                text_files = [f for f in text_files if language_filter in f]

            logger.info(f"Found {len(text_files)} text files for synthesis")

            successful = 0
            failed = 0
            results = []

            for text_file in text_files:
                try:
                    language = detect_language_from_path(text_file)

                    # Generate output path
                    filename = Path(text_file).stem
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = f"{output_prefix}/{language}/{filename}_{timestamp}.mp3"

                    # Synthesize
                    result_path = self.synthesize_consultation_from_storage(
                        input_path=text_file,
                        output_path=output_path,
                        language=language
                    )

                    results.append({
                        "input_path": text_file,
                        "output_path": result_path,
                        "language": language,
                        "status": "success"
                    })

                    successful += 1
                    logger.info(f"Successfully synthesized: {text_file}")

                except Exception as e:
                    logger.error(f"Failed to synthesize {text_file}: {e}")
                    results.append({
                        "input_path": text_file,
                        "error": str(e),
                        "status": "failed"
                    })
                    failed += 1

            return {
                "total_files": len(text_files),
                "successful": successful,
                "failed": failed,
                "results": results,
                "language_filter": language_filter
            }

        except Exception as e:
            logger.error(f"Batch synthesis failed: {e}")
            raise RuntimeError(f"Batch synthesis failed: {e}") from e

    def save_synthesis_report(
        self,
        results: Dict[str, Any],
        language: str = "all"
    ) -> str:
        """Save synthesis processing report to storage.

        Args:
            results: Processing results from batch_synthesis
            language: Language identifier for organization

        Returns:
            Storage path of saved report
        """
        timestamp = datetime.now().isoformat()
        report = {
            "synthesis_report": True,
            "timestamp": timestamp,
            "summary": {
                "total_files": results["total_files"],
                "successful": results["successful"],
                "failed": results["failed"],
                "success_rate": results["successful"] / results["total_files"] if results["total_files"] > 0 else 0
            },
            "language_filter": results.get("language_filter"),
            "results": results["results"]
        }

        report_path = f"tts-reports/{language}/synthesis_report_{timestamp}.json"
        url = self.storage.save_json(report_path, report)

        logger.info(f"Synthesis report saved to: {url}")
        return report_path


# Legacy function compatibility
def synthesize_consultation(text_file: Path) -> None:
    """Legacy function for backward compatibility.

    Args:
        text_file: Path to consultation text file.

    Raises:
        FileNotFoundError: If text file doesn't exist.
        ValueError: If consultation format is invalid.
        RuntimeError: If synthesis fails.
    """
    if not text_file.exists():
        raise FileNotFoundError(f"Text file not found: {text_file}")

    language = detect_language_from_path(str(text_file))
    service = TextToSpeechService()

    with open(text_file, 'r', encoding='utf-8') as f:
        text_content = f.read()

    audio_data = service.synthesize_consultation_text(text_content, language)

    # Save to local file system for backward compatibility
    output_dir = Path(__file__).parent.parent.parent.parent / "text_to_speech_outputs" / language
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{text_file.stem}.mp3"

    with open(output_path, 'wb') as f:
        f.write(audio_data)

    logger.info(f"Legacy synthesis completed: {output_path}")


def discover_consultation_files(
    input_directory: Path, 
    target_language: Optional[str] = None
) -> List[Path]:
    """Discovers consultation text files for synthesis processing.

    Legacy function maintained for backward compatibility.

    Args:
        input_directory: Root directory containing language subdirectories.
        target_language: Optional language filter for file discovery.

    Returns:
        List of Path objects for consultation text files to process.

    Raises:
        FileNotFoundError: If input directory doesn't exist.
        ValueError: If target language directory is invalid.
    """
    if not input_directory.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_directory}")

    consultation_files = []

    if target_language:
        language_dir = input_directory / target_language
        if not language_dir.is_dir():
            raise ValueError(f"Language directory not found: {language_dir}")
        consultation_files.extend(language_dir.glob("*.txt"))
    else:
        for language_dir in input_directory.iterdir():
            if language_dir.is_dir():
                consultation_files.extend(language_dir.glob("*.txt"))

    return sorted(consultation_files)


def synthesize_all_consultations(language_filter: Optional[str] = None) -> None:
    """Legacy function for synthesizing all consultations.

    Args:
        language_filter: Optional language filter

    Raises:
        FileNotFoundError: If input directory structure doesn't exist.
        RuntimeError: If API keys are not configured.
        ValueError: If specified language is invalid.
    """
    load_dotenv()

    input_dir = Path(__file__).parent.parent.parent.parent / "speak_text_contents"

    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    consultation_files = discover_consultation_files(input_dir, language_filter)

    if not consultation_files:
        logger.warning(f"No consultation files found in {input_dir}")
        return

    logger.info(f"Starting synthesis of {len(consultation_files)} files")

    successful = 0
    failed = 0

    for text_file in consultation_files:
        try:
            synthesize_consultation(text_file)
            successful += 1
        except Exception as e:
            logger.error(f"Consultation synthesis failed for {text_file}: {e}")
            failed += 1

    logger.info(f"Synthesis completed: {successful} successful, {failed} failed")