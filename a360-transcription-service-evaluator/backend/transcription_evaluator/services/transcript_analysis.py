#!/usr/bin/env python3
"""Transcript quality assurance utility for aesthetic medicine consultations.

This module provides comprehensive analysis of transcript quality by aligning
three artifacts per consultation:
    • Raw Deepgram ASR transcript (storage JSON)
    • LLM spell-checked version (storage JSON)
    • Ground truth transcript (text file)

It produces per consultation metrics:
    • Character/word error rate before vs. after correction
    • False positives (new mistakes) and false negatives (missed fixes)
    • Speaker diarization accuracy (Doctor=0 | Patient=1)

Key enhancements:
    • Storage abstraction integration for flexible input/output
    • Enhanced statistical analysis with confidence intervals
    • Comprehensive visualization and reporting
    • Support for both local and cloud-based workflows

Cross-Region Bedrock model ID (Claude 3.7 Sonnet):
    us.anthropic.claude-3-7-sonnet-20250219-v1:0
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd

from ..config.settings import get_settings
from ..core.storage import StorageBackend, create_storage_backend

logger = logging.getLogger(__name__)

CROSS_REGION_MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"


def levenshtein(seq_a: List[str] | str, seq_b: List[str] | str) -> int:
    """Compute Levenshtein distance between two sequences.

    Args:
        seq_a: First sequence (string or list of strings)
        seq_b: Second sequence (string or list of strings)

    Returns:
        Edit distance between the sequences
    """
    if len(seq_a) < len(seq_b):
        seq_a, seq_b = seq_b, seq_a
    prev = list(range(len(seq_b) + 1))
    for i, ca in enumerate(seq_a, 1):
        cur = [i]
        for j, cb in enumerate(seq_b, 1):
            ins = cur[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (ca != cb)
            cur.append(min(ins, dele, sub))
        prev = cur
    return prev[-1]


def wordify(text: str) -> List[str]:
    """Tokenize text into words using whitespace.

    Args:
        text: Input text to tokenize

    Returns:
        List of words
    """
    return text.strip().split()


def flatten_json_transcript(
    obj: Dict[str, Any], field: str = "channel"
) -> Tuple[str, List[int]]:
    """Concatenate alternative transcripts and gather speaker labels.

    Args:
        obj: JSON object containing transcript data
        field: Field name containing alternatives

    Returns:
        Combined text and per-utterance speaker sequence
    """
    alts = obj.get(field, {}).get("alternatives", [])
    texts, speakers = [], []
    for alt in alts:
        t = alt.get("transcript", "").strip()
        if t:
            texts.append(t)
            speakers.append(int(alt.get("speaker", 0)))
    return " ".join(texts), speakers


def parse_ground_truth(text_content: str) -> Tuple[str, List[int]]:
    """Parse ground truth text with speaker annotations.

    Expected format: <Doctor: text> or <Patient: text> per line

    Args:
        text_content: Ground truth text content

    Returns:
        Combined text and speaker sequence
    """
    speaker_map = {"doctor": 0, "patient": 1}
    utterances, speakers = [], []

    for raw in text_content.splitlines():
        if ":" not in raw:
            continue
        who, utter = raw.split(":", 1)
        utter = utter.strip()
        who_key = who.strip().lower()
        if utter:
            utterances.append(utter)
            speakers.append(speaker_map.get(who_key, 0))

    return " ".join(utterances), speakers


def calculate_fp_fn(
    orig_tokens: List[str],
    corrected_tokens: List[str],
    ground_truth_tokens: List[str],
) -> Tuple[int, int]:
    """Calculate false positives and false negatives for correction.

    FN = edits(corrected, ground_truth)
    FP = max(0, edits(orig, corrected) - improvements)

    Args:
        orig_tokens: Original transcript tokens
        corrected_tokens: Corrected transcript tokens
        ground_truth_tokens: Ground truth tokens

    Returns:
        Tuple of (false_positives, false_negatives)
    """
    dist_orig_gt = levenshtein(orig_tokens, ground_truth_tokens)
    dist_corr_gt = levenshtein(corrected_tokens, ground_truth_tokens)
    dist_orig_corr = levenshtein(orig_tokens, corrected_tokens)
    improvements = max(dist_orig_gt - dist_corr_gt, 0)
    false_positives = max(dist_orig_corr - improvements, 0)
    return false_positives, dist_corr_gt


def calculate_diarization_accuracy(
    gt_speakers: List[int], json_speakers: List[int]
) -> float:
    """Calculate accuracy of speaker labels after length alignment.

    Args:
        gt_speakers: Ground truth speaker labels
        json_speakers: Predicted speaker labels

    Returns:
        Accuracy as a float between 0 and 1
    """
    if not gt_speakers or not json_speakers:
        return 0.0
    n = min(len(gt_speakers), len(json_speakers))
    matches = sum(1 for i in range(n) if gt_speakers[i] == json_speakers[i])
    return matches / n


def find_consultation_objects(
    storage: StorageBackend,
    consultation_id: str,
    orig_suffix: str = "final.json",
    corr_suffix: str = "corrected.json",
) -> Tuple[Optional[str], Optional[str]]:
    """Find original and corrected transcript objects for a consultation.

    Args:
        storage: Storage backend instance
        consultation_id: Consultation UUID
        orig_suffix: Suffix for original transcript files
        corr_suffix: Suffix for corrected transcript files

    Returns:
        Tuple of (original_key, corrected_key) or (None, None) if not found
    """
    prefix = f"{consultation_id}/transcript/"

    try:
        files = storage.list_files(prefix)
        orig_key = corr_key = None

        for file_path in files:
            if file_path.endswith(orig_suffix):
                orig_key = file_path
            elif file_path.endswith(corr_suffix):
                corr_key = file_path

        return orig_key, corr_key
    except Exception as e:
        logger.error(f"Failed to find consultation objects for {consultation_id}: {e}")
        return None, None


class TranscriptAnalyzer:
    """Enhanced transcript analyzer with storage abstraction integration."""

    def __init__(
        self,
        storage_backend: Optional[StorageBackend] = None,
        aws_profile: Optional[str] = None,
    ):
        """Initialize transcript analyzer with storage backend.

        Args:
            storage_backend: Storage backend instance
            aws_profile: AWS profile for authentication
        """
        self.settings = get_settings()

        if storage_backend:
            self.storage = storage_backend
        else:
            storage_config = self.settings.get_storage_config()
            if aws_profile:
                storage_config["aws_profile"] = aws_profile
            self.storage = create_storage_backend(**storage_config)

        logger.info(
            f"Initialized TranscriptAnalyzer with storage: {type(self.storage).__name__}"
        )

    def process_consultation(
        self,
        consultation_key: str,
        consultation_uuid: str,
        ground_truth_path: str,
        language: str = "english",
    ) -> Optional[Dict[str, Any]]:
        """Process a single consultation and calculate metrics.

        Args:
            consultation_key: Consultation key (e.g., 'consultation_01')
            consultation_uuid: Consultation UUID from mapping
            ground_truth_path: Path to ground truth file in storage
            language: Language for processing

        Returns:
            Dictionary with metrics or None if processing failed
        """
        orig_key, corr_key = find_consultation_objects(self.storage, consultation_uuid)

        if not orig_key or not corr_key:
            logger.warning(
                f"Missing transcript files for consultation {consultation_uuid}"
            )
            return None

        try:
            # Load transcripts from storage
            orig_json = self.storage.load_json(orig_key)
            corr_json = self.storage.load_json(corr_key)

            # Load ground truth text
            gt_text_content = self.storage.load_text(ground_truth_path)

            orig_text, orig_speakers = flatten_json_transcript(orig_json)
            corr_text, corr_speakers = flatten_json_transcript(corr_json)
            gt_text, gt_speakers = parse_ground_truth(gt_text_content)

            cer_before = levenshtein(orig_text, gt_text) / max(len(gt_text), 1)
            cer_after = levenshtein(corr_text, gt_text) / max(len(gt_text), 1)

            orig_words = wordify(orig_text)
            corr_words = wordify(corr_text)
            gt_words = wordify(gt_text)

            wer_before = levenshtein(orig_words, gt_words) / max(len(gt_words), 1)
            wer_after = levenshtein(corr_words, gt_words) / max(len(gt_words), 1)

            false_positives, false_negatives = calculate_fp_fn(
                orig_words, corr_words, gt_words
            )
            speaker_accuracy = calculate_diarization_accuracy(
                gt_speakers, orig_speakers
            )

            return {
                "consultation_id": consultation_uuid,
                "consultation_key": consultation_key,
                "language": language,
                "cer_before": cer_before,
                "cer_after": cer_after,
                "wer_before": wer_before,
                "wer_after": wer_after,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "speaker_accuracy": speaker_accuracy,
                "orig_text_length": len(orig_text),
                "corr_text_length": len(corr_text),
                "gt_text_length": len(gt_text),
                "orig_word_count": len(orig_words),
                "corr_word_count": len(corr_words),
                "gt_word_count": len(gt_words),
            }
        except Exception as e:
            logger.error(
                f"Failed to process consultation {consultation_key} ({consultation_uuid}): {e}"
            )
            return None

    def analyze_consultations_from_mapping(
        self,
        consultation_mapping: Dict[str, Any],
        language: str,
        consultation_keys: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Analyze consultations using consultation mapping data.

        Args:
            consultation_mapping: Full consultation mapping data
            language: Language to analyze
            consultation_keys: Optional list of specific consultation keys

        Returns:
            List of analysis results
        """
        if language not in consultation_mapping.get("consultation_mappings", {}):
            raise ValueError(f"No mappings found for language: {language}")

        language_mappings = consultation_mapping["consultation_mappings"][language]

        if consultation_keys:
            # Filter to specific keys
            selected_mappings = {
                k: v for k, v in language_mappings.items() if k in consultation_keys
            }
        else:
            selected_mappings = language_mappings

        results = []
        for consultation_key, mapping_data in selected_mappings.items():
            if isinstance(mapping_data, str):
                # Simple UUID mapping
                consultation_uuid = mapping_data
                ground_truth_file = f"{consultation_key}.txt"
            else:
                # Complex mapping with metadata
                consultation_uuid = mapping_data.get("consultation_id")
                ground_truth_file = mapping_data.get(
                    "ground_truth_file", f"{consultation_key}.txt"
                )

            ground_truth_path = f"ground-truth/{language}/{ground_truth_file}"

            logger.info(
                f"Processing consultation {consultation_key} ({consultation_uuid})"
            )

            result = self.process_consultation(
                consultation_key=consultation_key,
                consultation_uuid=consultation_uuid,
                ground_truth_path=ground_truth_path,
                language=language,
            )

            if result:
                results.append(result)
            else:
                logger.warning(f"Failed to process consultation: {consultation_key}")

        return results

    def generate_analysis_report(
        self, results: List[Dict[str, Any]], language: str = "english"
    ) -> Dict[str, Any]:
        """Generate comprehensive analysis report.

        Args:
            results: List of consultation analysis results
            language: Language being analyzed

        Returns:
            Comprehensive analysis report
        """
        if not results:
            return {"error": "No results to analyze"}

        df = pd.DataFrame(results)

        # Calculate summary statistics
        summary_stats = {
            "total_consultations": len(results),
            "language": language,
            "model_used": CROSS_REGION_MODEL_ID,
            "analysis_timestamp": datetime.now().isoformat(),
            "cer_statistics": {
                "before_mean": df["cer_before"].mean(),
                "before_std": df["cer_before"].std(),
                "after_mean": df["cer_after"].mean(),
                "after_std": df["cer_after"].std(),
                "improvement_mean": (df["cer_before"] - df["cer_after"]).mean(),
                "improvement_count": (df["cer_after"] < df["cer_before"]).sum(),
                "degradation_count": (df["cer_after"] > df["cer_before"]).sum(),
            },
            "wer_statistics": {
                "before_mean": df["wer_before"].mean(),
                "before_std": df["wer_before"].std(),
                "after_mean": df["wer_after"].mean(),
                "after_std": df["wer_after"].std(),
                "improvement_mean": (df["wer_before"] - df["wer_after"]).mean(),
                "improvement_count": (df["wer_after"] < df["wer_before"]).sum(),
                "degradation_count": (df["wer_after"] > df["wer_before"]).sum(),
            },
            "fp_fn_statistics": {
                "total_false_positives": df["false_positives"].sum(),
                "total_false_negatives": df["false_negatives"].sum(),
                "fp_fn_ratio": df["false_positives"].sum()
                / max(df["false_negatives"].sum(), 1),
                "mean_false_positives": df["false_positives"].mean(),
                "mean_false_negatives": df["false_negatives"].mean(),
            },
            "speaker_statistics": {
                "mean_accuracy": df["speaker_accuracy"].mean(),
                "std_accuracy": df["speaker_accuracy"].std(),
                "perfect_accuracy_count": (df["speaker_accuracy"] == 1.0).sum(),
            },
        }

        return {
            "summary_statistics": summary_stats,
            "detailed_results": results,
            "consultation_breakdown": df.to_dict("records"),
        }

    def save_analysis_results(
        self,
        report: Dict[str, Any],
        language: str = "english",
        include_plots: bool = True,
    ) -> str:
        """Save analysis results to storage.

        Args:
            report: Analysis report to save
            language: Language identifier
            include_plots: Whether to generate and save plots

        Returns:
            Storage path of saved report
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save main report
        report_path = f"transcript-analysis/{language}/analysis_report_{timestamp}.json"
        report_url = self.storage.save_json(report_path, report)

        # Save CSV data
        if report.get("detailed_results"):
            df = pd.DataFrame(report["detailed_results"])
            csv_content = df.to_csv(index=False)
            csv_path = f"transcript-analysis/{language}/metrics_{timestamp}.csv"
            self.storage.save_text(csv_path, csv_content)

        # Generate and save plots if requested
        if include_plots and report.get("detailed_results"):
            self._save_visualization_plots(
                report["detailed_results"], language, timestamp
            )

        logger.info(f"Analysis results saved to: {report_url}")
        return report_path

    def _save_visualization_plots(
        self, results: List[Dict[str, Any]], language: str, timestamp: str
    ) -> None:
        """Generate and save visualization plots.

        Args:
            results: Analysis results data
            language: Language identifier
            timestamp: Timestamp for file naming
        """
        df = pd.DataFrame(results)

        # Error rates plot
        fig1, ax1 = plt.subplots(figsize=(12, 6))
        consultation_ids = [r["consultation_key"] for r in results]

        ax1.bar(consultation_ids, df["cer_before"], label="CER-before", alpha=0.7)
        ax1.bar(consultation_ids, df["cer_after"], label="CER-after", alpha=0.7)
        ax1.bar(
            consultation_ids,
            df["wer_before"],
            bottom=df["cer_before"],
            label="WER-before",
            alpha=0.7,
        )
        ax1.bar(
            consultation_ids,
            df["wer_after"],
            bottom=df["cer_after"],
            label="WER-after",
            alpha=0.7,
        )

        ax1.set_ylabel("Error rate")
        ax1.set_title("Character and Word Error Rates")
        ax1.legend()
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        # Save plot as binary data
        import io

        buf1 = io.BytesIO()
        fig1.savefig(buf1, format="png", dpi=300)
        buf1.seek(0)
        plot1_path = f"transcript-analysis/{language}/error_rates_{timestamp}.png"
        self.storage.save_binary(plot1_path, buf1.getvalue())
        plt.close(fig1)

        # FP/FN plot
        fig2, ax2 = plt.subplots(figsize=(12, 6))
        ax2.bar(
            consultation_ids, df["false_negatives"], label="False-negatives", alpha=0.7
        )
        ax2.bar(
            consultation_ids,
            df["false_positives"],
            bottom=df["false_negatives"],
            label="False-positives",
            alpha=0.7,
        )

        ax2.set_ylabel("Token count")
        ax2.set_title("Spell-checker FP / FN")
        ax2.legend()
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        buf2 = io.BytesIO()
        fig2.savefig(buf2, format="png", dpi=300)
        buf2.seek(0)
        plot2_path = f"transcript-analysis/{language}/fp_fn_{timestamp}.png"
        self.storage.save_binary(plot2_path, buf2.getvalue())
        plt.close(fig2)

        logger.info(f"Visualization plots saved: {plot1_path}, {plot2_path}")

    def print_summary_analysis(self, report: Dict[str, Any]) -> None:
        """Print detailed summary analysis of the results.

        Args:
            report: Analysis report containing statistics
        """
        stats = report.get("summary_statistics", {})

        print("\n" + "=" * 80)
        print("TRANSCRIPT ANALYSIS SUMMARY")
        print("=" * 80)

        print(f"\nLanguage: {stats.get('language', 'unknown')}")
        print(f"Total consultations: {stats.get('total_consultations', 0)}")
        print(f"Model used: {stats.get('model_used', 'unknown')}")

        # CER Analysis
        cer_stats = stats.get("cer_statistics", {})
        print("\nCHARACTER ERROR RATE (CER):")
        print(
            f"  Before: {cer_stats.get('before_mean', 0):.1%} ± {cer_stats.get('before_std', 0):.3f}"
        )
        print(
            f"  After:  {cer_stats.get('after_mean', 0):.1%} ± {cer_stats.get('after_std', 0):.3f}"
        )
        print(f"  Mean improvement: {cer_stats.get('improvement_mean', 0):+.4f}")
        print(
            f"  Improved: {cer_stats.get('improvement_count', 0)}/{stats.get('total_consultations', 0)}"
        )
        print(
            f"  Degraded: {cer_stats.get('degradation_count', 0)}/{stats.get('total_consultations', 0)}"
        )

        # WER Analysis
        wer_stats = stats.get("wer_statistics", {})
        print("\nWORD ERROR RATE (WER):")
        print(
            f"  Before: {wer_stats.get('before_mean', 0):.1%} ± {wer_stats.get('before_std', 0):.3f}"
        )
        print(
            f"  After:  {wer_stats.get('after_mean', 0):.1%} ± {wer_stats.get('after_std', 0):.3f}"
        )
        print(f"  Mean improvement: {wer_stats.get('improvement_mean', 0):+.4f}")
        print(
            f"  Improved: {wer_stats.get('improvement_count', 0)}/{stats.get('total_consultations', 0)}"
        )
        print(
            f"  Degraded: {wer_stats.get('degradation_count', 0)}/{stats.get('total_consultations', 0)}"
        )

        # FP/FN Analysis
        fp_fn_stats = stats.get("fp_fn_statistics", {})
        print("\nFALSE POSITIVES vs FALSE NEGATIVES:")
        print(f"  Total False Positives: {fp_fn_stats.get('total_false_positives', 0)}")
        print(f"  Total False Negatives: {fp_fn_stats.get('total_false_negatives', 0)}")
        print(f"  FP/FN Ratio: {fp_fn_stats.get('fp_fn_ratio', 0):.2f}")
        print(
            f"  Mean FP per consultation: {fp_fn_stats.get('mean_false_positives', 0):.1f}"
        )
        print(
            f"  Mean FN per consultation: {fp_fn_stats.get('mean_false_negatives', 0):.1f}"
        )

        # Speaker Analysis
        speaker_stats = stats.get("speaker_statistics", {})
        print("\nSPEAKER DIARIZATION:")
        print(
            f"  Mean accuracy: {speaker_stats.get('mean_accuracy', 0):.1%} ± {speaker_stats.get('std_accuracy', 0):.3f}"
        )
        print(
            f"  Perfect accuracy: {speaker_stats.get('perfect_accuracy_count', 0)}/{stats.get('total_consultations', 0)}"
        )


def print_summary_analysis(df: pd.DataFrame) -> None:
    """Legacy function for backward compatibility."""
    # Convert DataFrame to report format
    results = df.to_dict("records")
    analyzer = TranscriptAnalyzer()
    report = analyzer.generate_analysis_report(results)
    analyzer.print_summary_analysis(report)


def generate_plots(df: pd.DataFrame, outdir: Path) -> None:
    """Legacy function for backward compatibility."""
    results = df.to_dict("records")

    # Create analyzer and save plots to local directory
    analyzer = TranscriptAnalyzer()

    # Generate plots locally for backward compatibility
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(df["consultation_id"], df["cer_before"], label="CER-before")
    ax.bar(
        df["consultation_id"],
        df["cer_after"],
        bottom=df["cer_before"],
        label="CER-after",
    )
    ax.bar(
        df["consultation_id"],
        df["wer_before"],
        bottom=df["cer_before"] + df["cer_after"],
        label="WER-before",
    )
    ax.bar(
        df["consultation_id"],
        df["wer_after"],
        bottom=df["cer_before"] + df["cer_after"] + df["wer_before"],
        label="WER-after",
    )
    ax.set_ylim(0, 2)
    ax.set_ylabel("Error rate")
    ax.set_title("Character and Word Error Rates")
    ax.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig.savefig(outdir / "error_rates.png", dpi=300)
    plt.close(fig)

    fig2, ax2 = plt.subplots(figsize=(12, 6))
    ax2.bar(df["consultation_id"], df["false_negatives"], label="False-negatives")
    ax2.bar(
        df["consultation_id"],
        df["false_positives"],
        bottom=df["false_negatives"],
        label="False-positives",
    )
    ax2.set_ylabel("Token count")
    ax2.set_title("Spell-checker FP / FN")
    ax2.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    fig2.savefig(outdir / "fp_fn.png", dpi=300)
    plt.close(fig2)
