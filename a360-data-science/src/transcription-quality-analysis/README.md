# Multilingual Transcript Analysis Framework with Backend Comparison
A comprehensive quality assurance system for aesthetic medicine consultation transcripts supporting both English and Spanish language processing.
## Overview
This framework provides a testing infrastructure for medical transcription accuracy across multiple languages and backend implementations. It compares three transcript types for each consultation: manually verified ground truth transcript, original Deepgram STT output, and LLM-corrected version with brand name fixes. The framework persists all processing results to S3, enabling further analysis or visualization.
### Core Features
- **Comprehensive Quality Metrics**: Character Error Rate (CER) and Word Error Rate (WER) calculations before and after LLM correction. False positive/negative analysis for correction assessment. Speaker diarization accuracy
- **Flexible Organization**: Language-specific directory structure supporting independent processing pipelines. Consultation ID mapping system to enable comparison of multiple backend implementations and eliminate file duplication. Configurable analysis targeting specific consultation subsets
- **AWS Integration**: Transcripts are downloaded from an S3 bucket. Computed metrics are also persisted to S3 as partitioned `.parquet` files to enable further processing and analysis with, for example, AWS Athena
## Directory Structure
```
.
├── consultation_mapping.json      <- Consultation ID mappings
├── consultation-scripts           <- Ground truth transcripts
│   ├── english
│   │   ├── consultation_01.txt
│   │   ├── ...
│   │   └── consultation_05.txt
│   └── spanish
│       ├── consultation_01.txt
│       ├── ...
│       └── consultation_05.txt
├── Makefile                       <- Automation commands
├── README.md                      <- This documentation
└── transcript_analysis.py         <- Analysis and metrics calculation
```
## Configuration
### AWS Profile
Make sure to configure the correct AWS profile with `aws configure` command
### Consultation Mapping System
The `consultation_mapping.json` file manages the relationship between ground truth and generated transcripts:
```json
{
  "consultation_mappings": {
    "english": {
      "consultation_01": [
        {
          "consultation_id": "e50128cc-369b-46fb-a603-7bfc1037bcc8",
          "speech_to_text_model": "nova-3-medical",
          "spellcheck_model": "claude-3-haiku"
        },
        {
          "consultation_id": "d1bb6674-cdc9-4f71-aece-9bd40822f838",
          "speech_to_text_model": "nova-3-general",
          "spellcheck_model": "claude-3-haiku"
        }
      ]
    },
    "spanish": {
      "consultation_01": [
        {
          "consultation_id": "09aef3df-8802-4021-9505-400a53a8e45f",
          "speech_to_text_model": "nova-3-medical",
          "spellcheck_model": "claude-3-haiku"
        }
      ]
    }
  }
}
```
Each ground truth transcript is mapped to a list of variations, enabling assignment of multiple consultations to a single ground truth script.
### S3 Bucket Configuration
The framework expects transcript files in S3 with the following structure:
```
a360-development-transcription-analysis
└── consultations
    └── {consultation_id}
        ├── original.json
        └── corrected.json
```
## Usage
To analyze the transcripts for a specific language and upload metrics to S3 run:
```sh
make AWS_PROFILE=<your AWS profile> analyze-{language}
```
Alternatively, to analyze the transcripts for all available languages, run:
```sh
make AWS_PROFILE=<your AWS profile> analyze
```
Inspect the `Makefile` for additional options available for customizations
## Analysis Metrics
### Error Rate Calculations
- **Character Error Rate (CER)**: Measures character-level accuracy by calculating the Levenshtein distance between transcript and ground truth at the character level. Lower values indicate higher accuracy
- **Word Error Rate (WER)**: Evaluates word-level accuracy by calculating the Levenshtein distance between tokenized transcript and ground truth. Lower values indicate higher accuracy
### Correction Quality Assessment
- **False Positives**: Count of incorrect corrections introduced by LLM processing. These represent unnecessary changes that reduce transcript quality
- **False Negatives**: Count of required corrections missed by LLM processing. These indicate opportunities for improvement in correction algorithms
### Speaker Diarization Analysis
- **Diarization Accuracy**: Percentage of correctly identified speaker segments compared to ground truth annotations. Critical for maintaining conversation context in medical consultations
