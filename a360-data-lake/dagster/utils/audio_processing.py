"""Audio processing utilities using ffmpeg.
This module provides functions for preprocessing audio files to optimize
transcription performance and cost.
"""

import subprocess
import tempfile
import os
from typing import Tuple
import shutil


def process_audio_with_ffmpeg(
    audio_data: bytes,
    speed_factor: float = 3.0,
    sample_rate: int = 22050,
    bitrate: str = "64k",
) -> Tuple[bytes, float, float]:
    """Process audio with ffmpeg to speed up playback.

    Args:
        audio_data: Input audio data as bytes.
        speed_factor: Speed multiplication factor (must be > 0).
        sample_rate: Target sample rate (must be > 0).
        bitrate: Target bitrate string.

    Returns:
        Tuple of (processed audio bytes, original duration, processed duration).

    Raises:
        ValueError: If input parameters are invalid.
        RuntimeError: If ffmpeg/ffprobe are not available.
        subprocess.CalledProcessError: If ffmpeg processing fails.
    """
    if not audio_data:
        raise ValueError("Audio data cannot be empty")
    if speed_factor <= 0:
        raise ValueError("Speed factor must be greater than 0")
    if sample_rate <= 0:
        raise ValueError("Sample rate must be greater than 0")
    if not bitrate or not bitrate.strip():
        raise ValueError("Bitrate cannot be empty")

    # ... rest of the existing implementation ...
    """Process audio with ffmpeg to speed up playback.
    Args:
        audio_data: Input audio data as bytes.
        speed_factor: Speed multiplication factor.
        sample_rate: Target sample rate.
        bitrate: Target bitrate.
    Returns:
        Tuple of (processed audio bytes, original duration, processed duration).
    Raises:
        subprocess.CalledProcessError: If ffmpeg processing fails.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, "input.mp3")
        output_path = os.path.join(temp_dir, "output.mp3")

        with open(input_path, "wb") as f:
            f.write(audio_data)

        probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            input_path,
        ]

        if shutil.which("ffprobe") is None:
            raise RuntimeError("ffprobe is not installed or not in PATH")

        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg is not installed or not in PATH")

        original_duration = float(subprocess.check_output(probe_cmd).decode().strip())  # noqa: S603

        process_cmd = [
            "ffmpeg",
            "-i",
            input_path,
            "-filter:a",
            f"atempo={speed_factor}",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-b:a",
            bitrate,
            "-y",
            output_path,
        ]

        subprocess.run(process_cmd, check=True, capture_output=True)  # noqa: S603

        processed_duration = original_duration / speed_factor

        with open(output_path, "rb") as f:
            processed_data = f.read()

        return processed_data, original_duration, processed_duration
