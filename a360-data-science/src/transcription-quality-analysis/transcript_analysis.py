import json
import re
import sys
from argparse import ArgumentParser
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime
from io import BytesIO
from itertools import zip_longest
from pathlib import Path
from typing import Any

import boto3
import jiwer
import pandas as pd
from rapidfuzz.distance import Levenshtein

SPEAKER_TO_ID = {"doctor": 0, "patient": 1}


def _print(*args, indent: int = 0, prefix: str = "-> ", **kwargs):
    """Prints a formatted message with optional indentation and prefix

    Args:
        *args: Values to print
        indent: Number of spaces to indent the prefix. Defaults to 0
        prefix: Prefix string to prepend before message. Defaults to "-> "
        **kwargs: Additional keyword arguments passed to `print()`
    """
    if len(args) == 0:
        return print(*args, **kwargs)
    sep: str = kwargs.pop("sep", " ")
    raw = sep.join([str(arg) for arg in args])
    if raw.isspace():
        return print(raw, **kwargs)
    decorator = " " * indent + prefix
    insert_pos = len(raw) - len(raw.lstrip())
    decorated = raw[:insert_pos] + decorator + raw[insert_pos:]
    print(decorated, **kwargs)


def create_parser() -> ArgumentParser:
    """Creates a parser of command-line arguments

    Returns:
        A configured instance of `argparse.ArgumentParser` class
    """
    parser = ArgumentParser()
    parser.add_argument("bucket", help="S3 bucket name")
    parser.add_argument(
        "language",
        choices=("english", "spanish"),
        help="Language for consultation processing",
    )
    parser.add_argument("consultation_keys", nargs="+", help="Consultation keys")
    parser.add_argument(
        "-m",
        "--consultation_mapping_path",
        type=Path,
        default=Path("consultation_mapping.json"),
        help="Path to a JSON file with the consultation mapping",
    )
    parser.add_argument(
        "-g",
        "--gt_dir",
        type=Path,
        default=Path("consultation-scripts"),
        help="Path to a directory with ground truth consultation scripts",
    )
    return parser


def load_consultation_mapping(filepath: Path) -> dict[str, dict[str, Any]]:
    """Loads a consultation mapping from a JSON file

    Args:
        filepath: Path to the JSON mapping file

    Returns:
        Dictionary of consultation mappings

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the JSON is invalid or missing the required structure
    """
    if not filepath.is_file():
        msg = f"Consultation mapping file '{filepath}' does not exist"
        raise FileNotFoundError(msg)
    try:
        with filepath.open() as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        msg = f"File '{filepath}' is not a valid JSON"
        raise ValueError(msg) from e
    try:
        consultation_mapping = data["consultation_mappings"]
    except Exception as e:
        msg = (
            f"Invalid JSON structure in file '{filepath}'. Expected top-level key "
            "'consultation_mappings'"
        )
        raise ValueError(msg) from e
    if not isinstance(consultation_mapping, dict):
        msg = (
            f"Invalid JSON structure in file '{filepath}'. The value of the "
            "'consultation_mappings' key must be a dictionary"
        )
        raise ValueError(msg)
    return consultation_mapping


def load_s3_json(resource, bucket: str, key: str) -> Any:
    """Loads a JSON object from an S3 bucket

    Args:
        resource: `boto3` S3 resource
        bucket: Name of the S3 bucket
        key: Object key in the S3 bucket

    Returns:
        Parsed JSON object.
    """
    obj = resource.Object(bucket, key)
    buf = BytesIO()
    obj.download_fileobj(buf)
    buf.seek(0)
    return json.load(buf)


def parse_ground_truth_script(script_path: Path) -> tuple[str, list[int]]:
    """Parses the ground truth script from file

    Args:
        script_path: Path to the ground truth transcript file

    Returns:
        Tuple of (concatenated text, list of speaker labels)
    """
    utterances = []
    speaker_ids = []

    with script_path.open() as f:
        for line in f:
            if ":" not in line:
                continue
            speaker, utterance = line.split(":", 1)
            speaker_id = SPEAKER_TO_ID.get(speaker.strip().lower())
            utterance = utterance.strip()
            if speaker_id is not None and utterance:
                utterances.append(utterance)
                speaker_ids.append(speaker_id)
    return " ".join(utterances), speaker_ids


def parse_transcript(transcript: dict) -> tuple[str, list[int]]:
    """Parses transcript text and speaker labels from a dictionary

    Args:
        transcript: Transcript dictionary

    Returns:
        Tuple of (concatenated text, list of speaker labels)
    """
    utterances = []
    speaker_ids = []
    known_ids = SPEAKER_TO_ID.values()

    for alt in transcript.get("channel", {}).get("alternatives", []):
        utterance = alt.get("transcript", "").strip()
        speaker_id = alt.get("speaker")
        if speaker_id in known_ids and utterance:
            utterances.append(utterance)
            speaker_ids.append(speaker_id)
    return " ".join(utterances), speaker_ids


def calculate_fp_fn(
    gt_text: str, orig_text: str, corrected_text: str
) -> tuple[int, int]:
    """Calculates false positives and false negatives for correction.

    FN = edits(corrected, ground_truth)
    FP = max(0, edits(orig, corrected) - improvements)

    Args:
        gt_text: Ground truth transcript
        orig_text: Original generated transcript
        corrected_text: Corrected transcript

    Returns:
        Tuple of (false_positives, false_negatives)
    """
    gt_words = gt_text.strip().split()
    orig_words = orig_text.strip().split()
    corrected_words = corrected_text.strip().split()
    dist_orig_gt = Levenshtein.distance(gt_words, orig_words)
    dist_corr_gt = Levenshtein.distance(gt_words, corrected_words)
    dist_orig_corr = Levenshtein.distance(corrected_words, orig_words)
    improvements = max(dist_orig_gt - dist_corr_gt, 0)
    false_positives = max(dist_orig_corr - improvements, 0)
    return false_positives, dist_corr_gt


def calculate_diarization_accuracy(
    gt_speakers: Sequence[int], pred_speakers: Sequence[int]
) -> float:
    """Calculates diarization accuracy between ground truth and predicted speaker labels

    If sequences differ in length, shorter sequence will be padded and matches will be
    averaged by the length of a longer sequence

    Args:
        gt_speakers: Ground truth speaker labels
        pred_speakers: Predicted speaker labels

    Returns:
        Accuracy between 0 and 1
    """
    matches = sum(
        x == y for x, y in zip_longest(gt_speakers, pred_speakers, fillvalue=object())
    )
    return matches / max(len(gt_speakers), len(pred_speakers), 1)


def sanitize_str(value: str, repl: str = "-") -> str:
    """Replaces all unsafe URL characters in `value` with `repl`

    Safe values are: alphanumeric, dot, underscore, tilde, and hyphen.

    Args:
        value: String to sanitize
        repl: Replacement string. Defaults to `"-"`

    Returns:
        Sanitized version of `value`
    """
    return re.sub(r"[^A-Za-z0-9._~-]", repl, value)


def process_consultation(
    gt_script_path: Path,
    variations: Iterable[dict[str, str]],
    language: str,
    s3_resource,
    bucket_name: str,
    indent: int = 0,
) -> list[dict[str, Any]] | None:
    """Processes a consultation and calculates transcription metrics

    Downloads original and corrected transcripts from S3, compares them to ground truth,
    and calculates various quality metrics

    Args:
        gt_script_path: Path to the ground truth script file
        variations: Iterable of consultation variation dicts
        language: Language of the consultation
        s3_resource: `boto3` S3 resource
        bucket_name: Name of the S3 bucket
        indent: Number of spaces to indent output logs

    Returns:
        List of metric dictionaries or None if all variations failed
    """
    rows = []
    var_indent = indent + 2
    for variation in variations:
        consultation_id = variation["consultation_id"]
        _print(f"Processing variation {consultation_id}...", indent=indent)
        try:
            orig_key = f"consultations/{consultation_id}/original.json"
            _print(
                f"Downloading original transcript '{orig_key}'...",
                indent=var_indent,
                end=" ",
                flush=True,
            )
            orig_transcript = load_s3_json(s3_resource, bucket_name, orig_key)
            print("Done")
            corr_key = f"consultations/{consultation_id}/corrected.json"
            _print(
                f"Downloading corrected transcript '{corr_key}'...",
                indent=var_indent,
                end=" ",
                flush=True,
            )
            corrected_transcript = load_s3_json(s3_resource, bucket_name, corr_key)
            print("Done")
        except Exception as e:
            _print(
                f"\nFailed to download transcript from S3: {e}. Skipping...",
                indent=var_indent + 2,
            )
            continue
        _print("Parsing transcripts...", indent=var_indent, end=" ", flush=True)
        gt_text, gt_speakers = parse_ground_truth_script(gt_script_path)
        orig_text, orig_speakers = parse_transcript(orig_transcript)
        corrected_text, corrected_speakers = parse_transcript(corrected_transcript)
        print("Done")

        _print("Calculating metrics...", indent=var_indent, end=" ", flush=True)
        cer_original = jiwer.cer(gt_text, orig_text)
        cer_corrected = jiwer.cer(gt_text, corrected_text)
        wer_original = jiwer.wer(gt_text, orig_text)
        wer_corrected = jiwer.wer(gt_text, corrected_text)

        fp, fn = calculate_fp_fn(gt_text, orig_text, corrected_text)
        diarization_acc = calculate_diarization_accuracy(gt_speakers, orig_speakers)

        car = max(0, 1 - cer_corrected)
        war = max(0, 1 - wer_corrected)
        overall_quality = car * 0.2 + war * 0.6 + diarization_acc * 0.2
        print("Done")

        today = date.today()  # noqa: DTZ011
        consultation_date: str | date = orig_transcript.get("start", today)
        if isinstance(consultation_date, str):
            try:
                consultation_date = datetime.fromisoformat(consultation_date).date()
            except Exception:
                consultation_date = today
        rows.append(
            {
                "year": consultation_date.year,
                "month": consultation_date.month,
                "speech_to_text_model": sanitize_str(variation["speech_to_text_model"]),
                "spellcheck_model": sanitize_str(variation["spellcheck_model"]),
                "language": language,
                "cer_original": cer_original,
                "cer_corrected": cer_corrected,
                "wer_original": wer_original,
                "wer_corrected": wer_corrected,
                "correction_fp": fp,
                "correction_fn": fn,
                "diarization_accuracy": diarization_acc,
                "overall_quality": overall_quality,
            }
        )
    if len(rows) == 0:
        return None
    return rows


def put_s3_obj(
    payload: bytes,
    resource,
    bucket: str,
    key: str,
    content_type: str = "binary/octet-stream",
) -> str:
    """Uploads a byte payload to an S3

    Args:
        payload: Bytes to upload
        resource: `boto3` S3 resource
        bucket: Name of the S3 bucket
        key: Object key in the S3 bucket
        content_type: MIME type of the payload. Defaults to `binary/octet-stream`

    Returns:
        S3 URI of the uploaded object.
    """
    obj = resource.Object(bucket, key)
    obj.put(Body=payload, ContentType=content_type)
    return f"s3://{bucket}/{key}"


def delete_s3_objects(
    resource, bucket_name: str, keys: Sequence[str]
) -> list[dict[str, str]]:
    """Deletes multiple objects from an S3 bucket

    Args:
        resource: `boto3` S3 resource
        bucket_name: Name of the S3 bucket
        keys: Object keys to delete

    Returns:
        List of deletion errors, if any
    """
    if len(keys) == 0:
        return []
    bucket = resource.Bucket(bucket_name)
    response = bucket.delete_objects(
        Delete={"Objects": [{"Key": key} for key in keys], "Quiet": True}
    )
    return response.get("Errors", [])


def upload_metrics_to_s3(
    metrics: pd.DataFrame, s3_resource, bucket_name: str, indent: int = 0
) -> list[str]:
    """Uploads metrics DataFrame to S3 as partitioned parquet files

    Groups metrics by year, month, STT model, and spellcheck model.
    If any upload fails, previously uploaded partitions are deleted.

    Args:
        metrics: `pd.DataFrame` of metrics
        s3_resource: `boto3` S3 resource
        bucket_name: Name of the S3 bucket
        indent: Number of spaces to indent output logs

    Returns:
        List of uploaded S3 keys
    """
    group_cols = ["year", "month", "speech_to_text_model", "spellcheck_model"]
    other_cols = metrics.columns.drop(group_cols)
    partitions = metrics.groupby(group_cols)[other_cols]
    s3_key_template = (
        "metrics/processed/year={}/month={:02d}/stt_model={}/spellcheck_model={}/{}"
    )
    uploaded_keys = []
    print(f"Uploading {len(partitions)} metric partition(s) to S3...")
    for (year, month, stt_model, spellcheck_model), partition in partitions:
        filename = f"metrics-{datetime.now(UTC).strftime('%Y-%m-%d-%H-%M-%S')}.parquet"
        key = s3_key_template.format(year, month, stt_model, spellcheck_model, filename)
        msg = (
            f"Uploading partition (year={year}, month={month}, stt_model={stt_model}, "
            f"spellcheck_model={spellcheck_model}) to {key}..."
        )
        _print(msg, indent=indent, end=" ", flush=True)
        data = partition.to_parquet(engine="pyarrow", index=False)
        try:
            put_s3_obj(
                data, s3_resource, bucket_name, key, "application/vnd.apache.parquet"
            )
            print("Done")
        except Exception as e:
            msg = f"\nFailed to upload partition to S3: {e}. Aborting..."
            _print(msg, indent=indent + 2)
            num_uploaded = len(uploaded_keys)
            if num_uploaded == 0:
                return []
            msg = f"Deleting {num_uploaded} previously uploaded partition(s) from S3..."
            _print(msg, indent=indent, end=" ", flush=True)
            try:
                errors = delete_s3_objects(s3_resource, bucket_name, uploaded_keys)
            except Exception as e:
                msg = (
                    f"\nFailed to delete previously uploaded partition(s) from S3: {e}"
                )
                _print(msg, indent=indent + 2)
            else:
                if (num_errors := len(errors)) > 0:
                    msg = f"\nFailed to delete {num_errors} previously uploaded partition(s) from S3"
                    _print(msg, indent=indent + 2)
                else:
                    print("Done")
            return []
        uploaded_keys.append(key)
    return uploaded_keys


def main() -> int:
    """Main script entry point

    Parses arguments, loads mapping, processes consultations, and uploads computed
    metrics to S3

    Returns:
        Exit code: 0 if successful, 1 otherwise
    """
    parser = create_parser()
    args = parser.parse_args()

    gt_dir: Path = args.gt_dir / args.language
    if not gt_dir.is_dir():
        print(f"Ground truth directory '{gt_dir}' does not exist")
        return 1

    try:
        consultation_mapping = load_consultation_mapping(args.consultation_mapping_path)
    except Exception as e:
        print("Failed to load consultation mapping:", e)
        return 1

    language_mapping = consultation_mapping.get(args.language)
    if not isinstance(language_mapping, dict) or len(language_mapping) == 0:
        print(f"No consultation mappings found for language '{args.language}'")
        return 1

    s3 = boto3.resource("s3")
    processing_results = []
    processed_count = 0
    print(f"Processing {len(args.consultation_keys)} consultation(s)...")
    for consultation_key in args.consultation_keys:
        _print(f"Processing consultation {consultation_key} ({args.language})...")
        gt_script_path = gt_dir / f"{consultation_key}.txt"
        if not gt_script_path.is_file():
            _print(
                f"Ground truth script '{gt_script_path}' does not exist. Skipping...",
                indent=2,
            )
            continue

        variations = language_mapping.get(consultation_key)
        if not isinstance(variations, list) or len(variations) == 0:
            _print("No variations found. Skipping...", indent=2)
            continue

        rows = process_consultation(
            gt_script_path, variations, args.language, s3, args.bucket, 2
        )
        if rows is None:
            _print("No variations were processed. Skipping...", indent=2)
            continue
        processing_results.extend(rows)
        _print(f"Successfully processed {len(rows)} variation(s)", indent=2)
        processed_count += 1
    if len(processing_results) == 0:
        print("No consultations were processed successfully")
        return 1
    df = pd.DataFrame(processing_results)
    print(f"Successfully processed {processed_count} consultation(s)")
    uploaded_keys = upload_metrics_to_s3(df, s3, args.bucket)
    if len(uploaded_keys) == 0:
        print("No metric partitions were uploaded successfully")
        return 1
    print(f"Successfully uploaded {len(uploaded_keys)} metric partition(s) to S3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
