# A360 Transcription Evaluator

[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Typing: strict](https://img.shields.io/badge/typing-strict-blue)](https://docs.python.org/3/library/typing.html)
[![Ruff](https://img.shields.io/badge/lint-ruff-46AADC)](https://docs.astral.sh/ruff/)
[![mypy](https://img.shields.io/badge/typecheck-mypy-2A6DB2)](https://mypy.readthedocs.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![AWS CDK](https://img.shields.io/badge/AWS-CDK-FF9900?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/cdk/)
[![License: A360 Proprietary](https://img.shields.io/badge/license-A360%20Proprietary-red)](#license)

Comprehensive transcription QA toolkit for aesthetic medicine and related verticals. Provides ground truth generation, FP/FN analysis, text-to-speech synthesis, and transcript-quality evaluation with unified S3/local storage.

### Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [CLI Usage](#cli-usage)
- [API Service](#api-service)
- [Programmatic Examples](#programmatic-examples)
- [Storage Layout](#storage-layout)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

### Overview
This repository contains the core Python package, API service, Lambda handlers, CDK stacks, and a lightweight frontend used to evaluate and visualize transcription quality across consultations.

### Features
- Ground truth script generation with medical seed terminology and brand names
- False-positive/false-negative detection with fuzzy matching and advanced alignment
- Text-to-speech synthesis (Deepgram for English, ElevenLabs for Spanish)
- Transcript-quality analysis: CER/WER, FP/FN, diarization accuracy, plots and reports
- Unified storage abstraction with S3 and local backends
- CLI and HTTP API interfaces

### Project Structure
```
a360-transcription-service-evaluator/
  backend/
    transcription_evaluator/
      api/                 FastAPI app (service endpoints)
      cli/                 Command-line interface
      config/              Pydantic settings and environment
      core/                Core logic (generation, analysis, storage)
      services/            TTS and transcript analysis services
      py.typed             Typing marker
    lambda_functions/      Lambda handlers (API, WebSocket, large jobs)
  cdk/                     AWS CDK stacks for infra & Lambdas
  frontend/                Lightweight web UI
  scripts/                 Utility scripts (deploy, init DB, packaging)
  pyproject.toml           Project metadata and script entrypoint
  Dockerfile               Container for local/dev usage
```

### Installation
Prerequisites:
- Python 3.12
- UV package manager
- AWS CLI configured (for S3 storage)

Recommended setup:
```bash
# Install project dependencies
uv sync

# Ensure backend package is importable during development
export PYTHONPATH="$(pwd)/backend:${PYTHONPATH}"

# Verify CLI entrypoint is available
uv run transcription-evaluator --help
```

Notes:
- The CLI entrypoint is `transcription-evaluator` (defined in `pyproject.toml`). If your environment does not pick it up, use `uv run python -m transcription_evaluator.cli.main` after setting `PYTHONPATH` as above.

### Configuration
Create a `.env` file at the repository root:
```bash
# Text-to-Speech API keys (required for TTS)
DEEPGRAM_API_KEY=your_deepgram_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key

# Storage configuration (defaults shown)
TRANSCRIPTION_EVALUATOR_STORAGE_BACKEND=s3
TRANSCRIPTION_EVALUATOR_S3_BUCKET=a360-dev-transcript-evaluations
TRANSCRIPTION_EVALUATOR_LOCAL_STORAGE_PATH=./output
TRANSCRIPTION_EVALUATOR_AWS_PROFILE=GenAI-Platform-Dev
TRANSCRIPTION_EVALUATOR_AWS_REGION=us-east-1
```

Environment variables summary:
- TRANSCRIPTION_EVALUATOR_STORAGE_BACKEND: s3 or local
- TRANSCRIPTION_EVALUATOR_S3_BUCKET: S3 bucket for outputs
- TRANSCRIPTION_EVALUATOR_LOCAL_STORAGE_PATH: base path for local storage
- TRANSCRIPTION_EVALUATOR_AWS_PROFILE: AWS named profile
- DEEPGRAM_API_KEY: required for English TTS
- ELEVENLABS_API_KEY: required for Spanish TTS

### CLI Usage
Global options (apply to all commands):
```bash
--log-level [DEBUG|INFO|WARNING|ERROR|CRITICAL]
--storage-backend [s3|local]
--local-path PATH
--s3-bucket TEXT
--aws-profile TEXT
```

Generate ground truth scripts:
```bash
transcription-evaluator generate-ground-truth \
  --vertical [aesthetic_medicine|dermatology|venous_care|plastic_surgery] \
  --language [english|spanish] \
  --word-count 600 \
  --challenge-level [voice_actor|transcription|both] \
  --seed-term-density 0.15 \
  --difficulty-level [basic|intermediate|advanced]
```

Analyze false positives/negatives:
```bash
transcription-evaluator analyze-fp-fn \
  --consultation-data path/to/consultation_mapping.json \
  --language [english|spanish] \
  [--consultation-ids id1,id2,...] \
  [--confidence-threshold 0.7] \
  [--save-individual]
```

Synthesize text-to-speech:
```bash
transcription-evaluator synthesize-tts \
  [--input-file ground-truth/english/consultation_01.txt] \
  [--output-file tts-audio/english/consultation_01_YYYYmmdd_HHMMSS.mp3] \
  [--input-prefix ground-truth] \
  [--output-prefix tts-audio] \
  [--language english|spanish] \
  [--save-report]
```

### API Service
The FastAPI app is located at `backend/transcription_evaluator/api/main.py`.

Run locally:
```bash
export PYTHONPATH="$(pwd)/backend:${PYTHONPATH}"
uv run uvicorn transcription_evaluator.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints:
- POST /analyze/single
- POST /analyze/batch
- GET  /analyze/report/{report_path}
- POST /analyze/single  (direct text-based FP/FN)
- POST /generate/ground-truth
- GET  /generate/verticals
- GET  /health

### Programmatic Examples
```python
from transcription_evaluator.core.generation import EnhancedGroundTruthGenerator
from transcription_evaluator.core.analysis import FPFNAnalyzer
from transcription_evaluator.services.text_to_speech import TextToSpeechService
from transcription_evaluator.services.transcript_analysis import TranscriptAnalyzer

generator = EnhancedGroundTruthGenerator()
script = generator.generate_script(
    medical_vertical="aesthetic_medicine", language="english", target_word_count=600
)
script_url, metadata_url = generator.save_script(script)

analyzer = FPFNAnalyzer()
fp, fn, metrics = analyzer.analyze_from_storage(
    consultation_id="consultation_01",
    consultation_uuid="uuid-here",
    backend="anthropic",
    ground_truth_text="Doctor: Hello...",
    confidence_threshold=0.7,
)

tts = TextToSpeechService()
audio_path = tts.synthesize_consultation_from_storage(
    input_path="ground-truth/english/consultation_01.txt"
)
```

### Storage Layout
```
ground-truth/
  english/|spanish/            # generated scripts (.txt) and metadata (_metadata.json)
fp-fn-analysis/
  english/|spanish/            # FP/FN per-consultation and summary JSON
tts-audio/
  english/|spanish/            # synthesized MP3
transcript-analysis/
  english/|spanish/            # analysis_report.json, metrics.csv, plots
tts-reports/
  all/|english/|spanish/       # synthesis batch reports
```

### Development
Testing:
```bash
uv sync --dev
uv run pytest
uv run pytest --cov=transcription_evaluator
```

Linting/typing (if configured in your environment):
```bash
uv run ruff .
uv run mypy backend/transcription_evaluator
```

### Troubleshooting
- Authentication: `aws configure --profile GenAI-Platform-Dev`
- Verify S3 access: `aws s3 ls s3://a360-dev-transcript-evaluations --profile GenAI-Platform-Dev`
- Ensure `PYTHONPATH` includes `backend` when running from source
- Debug logging: add `--log-level DEBUG` to any CLI command

### License
Proprietary — Aesthetics360 (A360). All rights reserved. Use of this software is restricted to authorized A360 personnel and approved partners. Redistribution or modification outside the A360 organization is prohibited without prior written consent.