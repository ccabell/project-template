#!/usr/bin/env python3
"""Enhanced false positive and false negative identification with fuzzy matching.

This module provides improved analysis of spellcheck layer errors using advanced
alignment algorithms and fuzzy matching techniques. It handles complex transcription
scenarios including word boundary issues, punctuation variations, and frameshift
mutations where multiple words become one or vice versa.

Key enhancements:
    • Fuzzy matching for robust term identification
    • Advanced sequence alignment algorithms
    • Punctuation and formatting normalization
    • Frameshift mutation detection
    • Context-aware error classification
    • Phonetic similarity analysis
    • Storage abstraction integration for S3/local analysis
    • Enhanced statistical confidence reporting
"""

from __future__ import annotations

import json
import logging
import re
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein
import difflib
import boto3
from botocore.exceptions import ClientError

from ..config.settings import get_settings
from .storage import StorageBackend, create_storage_backend

logger = logging.getLogger(__name__)


class DiffVisualizer:
    """Creates human-readable diff output for transcription comparisons."""
    
    def __init__(self):
        self.deleted_marker = "[-"
        self.deleted_end = "-]"
        self.inserted_marker = "{+"
        self.inserted_end = "+}"
        self.unchanged_marker = ""
    
    def create_unified_diff(
        self, 
        original: str, 
        corrected: str, 
        ground_truth: str,
        context_lines: int = 3
    ) -> Dict[str, str]:
        """Create unified diff visualization for three-way comparison.
        
        Args:
            original: Original transcript text
            corrected: Corrected transcript text  
            ground_truth: Ground truth transcript text
            context_lines: Number of context lines to show around changes
            
        Returns:
            Dict containing formatted diff strings for each comparison
        """
        return {
            "original_vs_ground_truth": self._create_two_way_diff(
                original, ground_truth, "Original", "Ground Truth", context_lines
            ),
            "corrected_vs_ground_truth": self._create_two_way_diff(
                corrected, ground_truth, "Corrected", "Ground Truth", context_lines  
            ),
            "original_vs_corrected": self._create_two_way_diff(
                original, corrected, "Original", "Corrected", context_lines
            )
        }
    
    def _create_two_way_diff(
        self,
        text1: str,
        text2: str, 
        label1: str,
        label2: str,
        context_lines: int = 3
    ) -> str:
        """Create a two-way unified diff."""
        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)
        
        diff = list(difflib.unified_diff(
            lines1, lines2,
            fromfile=label1,
            tofile=label2,
            n=context_lines
        ))
        
        return ''.join(diff) if diff else f"No differences between {label1} and {label2}"
    
    def create_inline_diff(self, original: str, corrected: str, ground_truth: str) -> str:
        """Create inline diff showing changes with markup.
        
        Args:
            original: Original text
            corrected: Corrected text
            ground_truth: Ground truth text
            
        Returns:
            Inline diff with visual markers for changes
        """
        words_corrected = corrected.split()
        words_ground_truth = ground_truth.split()
        
        matcher = difflib.SequenceMatcher(None, words_corrected, words_ground_truth)
        
        result = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                result.extend(words_corrected[i1:i2])
            elif tag == 'delete':
                result.append(f"{self.deleted_marker} {' '.join(words_corrected[i1:i2])} {self.deleted_end}")
            elif tag == 'insert':
                result.append(f"{self.inserted_marker} {' '.join(words_ground_truth[j1:j2])} {self.inserted_end}")
            elif tag == 'replace':
                if i1 < i2:
                    result.append(f"{self.deleted_marker} {' '.join(words_corrected[i1:i2])} {self.deleted_end}")
                if j1 < j2:
                    result.append(f"{self.inserted_marker} {' '.join(words_ground_truth[j1:j2])} {self.inserted_end}")
        
        return ' '.join(result)


class StatisticalConfidence:
    """Calculates statistical confidence intervals for FP/FN analysis."""
    
    @staticmethod
    def calculate_95th_percentile_confidence(
        error_count: int, 
        total_samples: int, 
        confidence_scores: List[float]
    ) -> Dict[str, float]:
        """Calculate 95th percentile confidence band for error analysis.
        
        Args:
            error_count: Number of errors detected
            total_samples: Total number of samples analyzed
            confidence_scores: List of individual confidence scores
            
        Returns:
            Dict containing confidence statistics
        """
        if not confidence_scores or total_samples == 0:
            return {
                "mean_confidence": 0.0,
                "confidence_95th_percentile": 0.0,
                "confidence_lower_bound": 0.0,
                "confidence_upper_bound": 0.0,
                "error_rate": 0.0,
                "error_rate_95th_ci_lower": 0.0,
                "error_rate_95th_ci_upper": 0.0,
                "sample_size": total_samples,
                "margin_of_error": 0.0
            }
        
        mean_confidence = statistics.mean(confidence_scores)
        
        confidence_95th = (
            statistics.quantiles(confidence_scores, n=100)[94] 
            if len(confidence_scores) >= 2
            else confidence_scores[0]
        )
        
        if len(confidence_scores) >= 2:
            std_dev = statistics.stdev(confidence_scores)
            margin = 1.96 * (std_dev / (len(confidence_scores) ** 0.5))
            confidence_lower = max(0.0, mean_confidence - margin)
            confidence_upper = min(1.0, mean_confidence + margin)
        else:
            confidence_lower = confidence_upper = mean_confidence
            margin = 0.0
        
        error_rate = error_count / total_samples
        
        z_score = 1.96
        n = total_samples
        p = error_rate
        
        if n > 0:
            denominator = 1 + (z_score ** 2) / n
            center = (p + (z_score ** 2) / (2 * n)) / denominator
            margin_prop = z_score * ((p * (1 - p) / n + (z_score ** 2) / (4 * n ** 2)) ** 0.5) / denominator
            
            error_rate_lower = max(0.0, center - margin_prop)
            error_rate_upper = min(1.0, center + margin_prop)
        else:
            error_rate_lower = error_rate_upper = 0.0
        
        return {
            "mean_confidence": round(mean_confidence, 4),
            "confidence_95th_percentile": round(confidence_95th, 4),
            "confidence_lower_bound": round(confidence_lower, 4),
            "confidence_upper_bound": round(confidence_upper, 4),
            "error_rate": round(error_rate, 4),
            "error_rate_95th_ci_lower": round(error_rate_lower, 4),
            "error_rate_95th_ci_upper": round(error_rate_upper, 4),
            "error_rate_confidence_band": f"{round(error_rate * 100, 2)}% (95% CI: {round(error_rate_lower * 100, 2)}% - {round(error_rate_upper * 100, 2)}%)",
            "sample_size": total_samples,
            "margin_of_error": round(margin, 4),
            "statistical_significance": "statistically_significant" if error_rate_lower > 0.01 else "not_statistically_significant"
        }


def find_consultation_objects(storage: StorageBackend, consultation_id: str) -> tuple[str | None, str | None]:
    """Find original and corrected transcript objects for a consultation.
    
    Args:
        storage: Storage backend instance
        consultation_id: Consultation identifier
        
    Returns:
        Tuple of (original_path, corrected_path) or (None, None) if not found
    """
    try:
        prefix = f"{consultation_id}/transcript/"
        files = storage.list_files(prefix)
        
        orig_key = corr_key = None
        
        for file_path in files:
            if file_path.endswith("final.json"):
                orig_key = file_path
            elif file_path.endswith("corrected.json"):
                corr_key = file_path
        
        return orig_key, corr_key
    except Exception as e:
        logger.error(f"Failed to list objects for consultation {consultation_id}: {e}")
        return None, None


def load_json_transcript(storage: StorageBackend, path: str) -> dict:
    """Load JSON content from storage.
    
    Args:
        storage: Storage backend instance
        path: Path to JSON file
        
    Returns:
        Loaded JSON data
    """
    try:
        return storage.load_json(path)
    except Exception as e:
        logger.error(f"Failed to load transcript from {path}: {e}")
        raise


def flatten_json_transcript(json_data: dict) -> tuple[str, list[int]]:
    """Flatten JSON transcript to text and speaker labels.
    
    Args:
        json_data: JSON transcript data
        
    Returns:
        Tuple of (flattened_text, speaker_labels)
    """
    if "channel" not in json_data:
        return "", []
    
    channel = json_data["channel"]
    if "alternatives" not in channel or not channel["alternatives"]:
        return "", []
    
    text_parts = []
    speakers = []
    
    for alternative in channel["alternatives"]:
        if "transcript" in alternative:
            text_parts.append(alternative["transcript"])
            speaker = alternative.get("speaker", 0)
            speakers.append(speaker)
    
    return " ".join(text_parts), speakers


def calculate_accuracy(original_text: str, corrected_text: str, ground_truth_text: str) -> Dict[str, float]:
    """Calculate accuracy with confidence intervals based on character-level Levenshtein distance.
    
    Args:
        original_text: Original transcript text
        corrected_text: Corrected transcript text
        ground_truth_text: Ground truth transcript text
        
    Returns:
        Dict containing accuracy metrics and confidence statistics
    """
    if not ground_truth_text:
        return {
            "accuracy": 0.0,
            "accuracy_confidence_band": "0.0% (95% CI: 0.0% - 0.0%)",
            "character_error_rate": 1.0,
            "improvement_over_original": 0.0,
            "statistical_significance": "not_applicable"
        }
    
    original_distance = Levenshtein.distance(original_text, ground_truth_text)
    corrected_distance = Levenshtein.distance(corrected_text, ground_truth_text)
    
    original_accuracy = max(0.0, 1.0 - (original_distance / len(ground_truth_text)))
    corrected_accuracy = max(0.0, 1.0 - (corrected_distance / len(ground_truth_text)))
    
    cer = corrected_distance / len(ground_truth_text)
    improvement = corrected_accuracy - original_accuracy
    
    n_chars = len(ground_truth_text)
    n_correct = n_chars - corrected_distance
    
    z_score = 1.96
    p = corrected_accuracy
    n = n_chars
    
    if n > 0 and p > 0:
        denominator = 1 + (z_score ** 2) / n
        center = (p + (z_score ** 2) / (2 * n)) / denominator
        margin = z_score * ((p * (1 - p) / n + (z_score ** 2) / (4 * n ** 2)) ** 0.5) / denominator
        
        accuracy_lower = max(0.0, center - margin)
        accuracy_upper = min(1.0, center + margin)
    else:
        accuracy_lower = accuracy_upper = corrected_accuracy
    
    significance = "statistically_significant" if accuracy_lower > 0.5 else "not_statistically_significant"
    
    return {
        "accuracy": round(corrected_accuracy, 4),
        "accuracy_confidence_band": f"{round(corrected_accuracy * 100, 2)}% (95% CI: {round(accuracy_lower * 100, 2)}% - {round(accuracy_upper * 100, 2)}%)",
        "character_error_rate": round(cer, 4),
        "improvement_over_original": round(improvement, 4),
        "statistical_significance": significance,
        "sample_size_chars": n_chars,
        "original_accuracy": round(original_accuracy, 4)
    }


class MedicalTermClassifier:
    """Basic medical term classifier for vertical classification."""
    
    def __init__(self):
        self.medical_verticals = {
            "dermatology": ["skin", "dermatology", "acne", "eczema", "psoriasis", "melanoma"],
            "venous_care": ["vein", "venous", "varicose", "thrombosis", "compression"],
            "plastic_surgery": ["plastic", "surgery", "implant", "reconstruction", "augmentation"],
            "aesthetic_medicine": ["aesthetic", "botox", "filler", "cosmetic", "rejuvenation"]
        }
    
    def classify_term(self, term: str) -> str:
        """Classify a medical term into a vertical.
        
        Args:
            term: Medical term to classify
            
        Returns:
            Medical vertical classification
        """
        term_lower = term.lower()
        
        for vertical, keywords in self.medical_verticals.items():
            if any(keyword in term_lower for keyword in keywords):
                return vertical
        
        return "general"
    
    def get_medical_vertical(self, text: str) -> str:
        """Determine the medical vertical from text content.
        
        Args:
            text: Text content to analyze
            
        Returns:
            Dominant medical vertical
        """
        text_lower = text.lower()
        vertical_counts = {}
        
        for vertical, keywords in self.medical_verticals.items():
            count = sum(1 for keyword in keywords if keyword in text_lower)
            if count > 0:
                vertical_counts[vertical] = count
        
        if vertical_counts:
            return max(vertical_counts.items(), key=lambda x: x[1])[0]
        
        return "general"


@dataclass
class AlignedSegment:
    """Represents an aligned segment between two sequences."""
    
    original_text: str
    corrected_text: str
    ground_truth_text: str
    original_start: int
    original_end: int
    corrected_start: int
    corrected_end: int
    ground_truth_start: int
    ground_truth_end: int
    alignment_score: float
    segment_type: str


@dataclass
class TermAnalysis:
    """Enhanced analysis result for a specific term causing FP/FN errors."""
    
    term: str
    error_type: str
    original_context: str
    corrected_context: str
    ground_truth_context: str
    confidence: float
    medical_vertical: str
    position: int
    consultation_id: str
    backend: str
    fuzzy_score: float
    alignment_type: str
    suggested_correction: str
    error_pattern: str
    diff_visualization: Dict[str, str]
    inline_diff: str
    confidence_statistics: Dict[str, float]


class TextNormalizer:
    """Handles text normalization for better alignment."""
    
    def __init__(self):
        self.punctuation_mapping = {
            '/': ' / ',
            '-': ' - ',
            ':': ' : ',
            '(': ' ( ',
            ')': ' ) ',
            ',': ' , ',
            '.': ' . ',
            '!': ' ! ',
            '?': ' ? ',
            ';': ' ; ',
            '"': ' " ',
            "'": " ' ",
            '[': ' [ ',
            ']': ' ] ',
            '&': ' & ',
        }
        
        self.medical_abbreviations = {
            'ml': 'milliliters',
            'cc': 'cubic centimeters',
            'mg': 'milligrams',
            'g': 'grams',
            'kg': 'kilograms',
            'cm': 'centimeters',
            'mm': 'millimeters',
            'hrs': 'hours',
            'min': 'minutes',
            'sec': 'seconds',
        }
        
        self.ordinal_equivalencies = {
            'first': '1st',
            '1st': 'first',
            'second': '2nd',
            '2nd': 'second',
            'third': '3rd',
            '3rd': 'third',
        }
        
        self.unit_spacing_patterns = [
            (r'(\d+)\s*(ml|cc|mg|g|kg|cm|mm|units?|iu|mcg|μg)', r'\1\2'),
            (r'(\d+)([a-z]+)', r'\1 \2'),
        ]
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for better alignment with equivalency handling.
        
        Args:
            text: Input text to normalize
            
        Returns:
            Normalized text with equivalencies resolved
        """
        text = text.lower()
        
        for word, equivalent in self.ordinal_equivalencies.items():
            text = re.sub(rf'\b{word}\b', equivalent.lower(), text)
        
        for pattern, replacement in self.unit_spacing_patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        for abbr, full in self.medical_abbreviations.items():
            text = re.sub(rf'\b{abbr}\b', full, text)
        
        for punct, spaced in self.punctuation_mapping.items():
            text = text.replace(punct, spaced)
        
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def create_word_tokens(self, text: str) -> List[str]:
        """Create word tokens with position information.
        
        Args:
            text: Input text
            
        Returns:
            List of word tokens
        """
        normalized = self.normalize_text(text)
        tokens = normalized.split()
        
        filtered_tokens = []
        for token in tokens:
            if token and not re.match(r'^[^\w\s]+$', token):
                filtered_tokens.append(token)
        
        return filtered_tokens


class AdvancedSequenceAligner:
    """Advanced sequence alignment for transcription comparison."""
    
    def __init__(self):
        self.normalizer = TextNormalizer()
        self.min_fuzzy_score = 70
        self.frameshift_threshold = 0.8
    
    def align_sequences(
        self,
        original: str,
        corrected: str,
        ground_truth: str
    ) -> List[AlignedSegment]:
        """Align three sequences using advanced algorithms.
        
        Args:
            original: Original transcript
            corrected: Corrected transcript
            ground_truth: Ground truth transcript
            
        Returns:
            List of aligned segments
        """
        norm_original = self.normalizer.normalize_text(original)
        norm_corrected = self.normalizer.normalize_text(corrected)
        norm_ground_truth = self.normalizer.normalize_text(ground_truth)
        
        orig_tokens = self.normalizer.create_word_tokens(norm_original)
        corr_tokens = self.normalizer.create_word_tokens(norm_corrected)
        gt_tokens = self.normalizer.create_word_tokens(norm_ground_truth)
        
        orig_vs_gt = list(difflib.unified_diff(orig_tokens, gt_tokens, lineterm=''))
        corr_vs_gt = list(difflib.unified_diff(corr_tokens, gt_tokens, lineterm=''))
        
        segments = self._create_alignment_segments(
            orig_tokens, corr_tokens, gt_tokens,
            orig_vs_gt, corr_vs_gt
        )
        
        return segments
    
    def _create_alignment_segments(
        self,
        orig_tokens: List[str],
        corr_tokens: List[str],
        gt_tokens: List[str],
        orig_diff: List[str],
        corr_diff: List[str]
    ) -> List[AlignedSegment]:
        """Create aligned segments from tokens and diffs."""
        segments = []
        
        matcher = difflib.SequenceMatcher(None, orig_tokens, gt_tokens)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            corr_segment = self._find_corrected_segment(
                corr_tokens, gt_tokens, j1, j2
            )
            
            if corr_segment:
                corr_start, corr_end = corr_segment
                
                segment = AlignedSegment(
                    original_text=' '.join(orig_tokens[i1:i2]),
                    corrected_text=' '.join(corr_tokens[corr_start:corr_end]),
                    ground_truth_text=' '.join(gt_tokens[j1:j2]),
                    original_start=i1,
                    original_end=i2,
                    corrected_start=corr_start,
                    corrected_end=corr_end,
                    ground_truth_start=j1,
                    ground_truth_end=j2,
                    alignment_score=self._calculate_alignment_score(
                        orig_tokens[i1:i2], corr_tokens[corr_start:corr_end], gt_tokens[j1:j2]
                    ),
                    segment_type=tag
                )
                
                segments.append(segment)
        
        return segments
    
    def _find_corrected_segment(
        self,
        corr_tokens: List[str],
        gt_tokens: List[str],
        gt_start: int,
        gt_end: int
    ) -> Optional[Tuple[int, int]]:
        """Find corresponding segment in corrected tokens."""
        if gt_start >= len(gt_tokens):
            return None
        
        target_text = ' '.join(gt_tokens[gt_start:gt_end])
        
        best_match = None
        best_score = 0
        
        for i in range(len(corr_tokens)):
            for j in range(i + 1, min(len(corr_tokens) + 1, i + (gt_end - gt_start) + 2)):
                candidate_text = ' '.join(corr_tokens[i:j])
                score = fuzz.ratio(target_text, candidate_text)
                
                if score > best_score:
                    best_score = score
                    best_match = (i, j)
        
        return best_match if best_score > self.min_fuzzy_score else None
    
    def _calculate_alignment_score(
        self,
        orig_segment: List[str],
        corr_segment: List[str],
        gt_segment: List[str]
    ) -> float:
        """Calculate alignment quality score."""
        if not orig_segment and not corr_segment and not gt_segment:
            return 1.0
        
        orig_text = ' '.join(orig_segment)
        corr_text = ' '.join(corr_segment)
        gt_text = ' '.join(gt_segment)
        
        orig_vs_gt = fuzz.ratio(orig_text, gt_text) / 100.0
        corr_vs_gt = fuzz.ratio(corr_text, gt_text) / 100.0
        
        len_weight = 1.0 - abs(len(orig_segment) - len(gt_segment)) / max(len(orig_segment), len(gt_segment), 1)
        
        return (orig_vs_gt + corr_vs_gt + len_weight) / 3.0


class FPFNAnalyzer:
    """Enhanced false positive/negative analyzer with storage abstraction integration."""
    
    def __init__(
        self,
        storage_backend: Optional[StorageBackend] = None,
        aws_profile: Optional[str] = None
    ):
        self.normalizer = TextNormalizer()
        self.aligner = AdvancedSequenceAligner()
        self.classifier = MedicalTermClassifier()
        self.diff_visualizer = DiffVisualizer()
        self.min_confidence = 0.6
        self.fuzzy_threshold = 75
        
        self.settings = get_settings()
        
        if storage_backend:
            self.storage = storage_backend
        else:
            storage_config = self.settings.get_storage_config()
            if aws_profile:
                storage_config["aws_profile"] = aws_profile
            self.storage = create_storage_backend(**storage_config)
        
        self.error_patterns = {
            'punctuation': r'[^\w\s]',
            'medical_unit': r'\b\d+\s*(ml|cc|mg|g|kg|cm|mm|hrs|min|sec)\b',
            'brand_name': r'\b[A-Z]{2,}(?:\s[A-Z]{2,})*\b',
            'dosage': r'\b\d+(?:\.\d+)?\s*(?:ml|cc|mg|g|kg|units?)\b',
            'procedure_code': r'\b[A-Z]\d{4,5}\b',
            'percentage': r'\b\d+(?:\.\d+)?%\b',
        }
        
        logger.info(f"Initialized FPFNAnalyzer with storage: {type(self.storage).__name__}")
    
    def analyze_consultation(
        self,
        consultation_id: str,
        backend: str,
        original_text: str,
        corrected_text: str,
        ground_truth_text: str,
        confidence_threshold: float = 0.7
    ) -> Tuple[List[TermAnalysis], List[TermAnalysis]]:
        """Enhanced analysis using fuzzy matching and advanced alignment.
        
        Args:
            consultation_id: Consultation identifier
            backend: Backend implementation used
            original_text: Original transcript
            corrected_text: Corrected transcript
            ground_truth_text: Ground truth transcript
            confidence_threshold: Minimum confidence for inclusion
            
        Returns:
            Tuple of (false_positives, false_negatives) analysis
        """
        segments = self.aligner.align_sequences(
            original_text, corrected_text, ground_truth_text
        )
        
        false_positives = []
        false_negatives = []
        
        for segment in segments:
            fp_analysis = self._analyze_false_positive(
                segment, consultation_id, backend, confidence_threshold
            )
            if fp_analysis:
                false_positives.extend(fp_analysis)
            
            fn_analysis = self._analyze_false_negative(
                segment, consultation_id, backend, confidence_threshold
            )
            if fn_analysis:
                false_negatives.extend(fn_analysis)
        
        return false_positives, false_negatives
    
    def analyze_from_storage(
        self,
        consultation_id: str,
        consultation_uuid: str,
        backend: str,
        ground_truth_text: str,
        confidence_threshold: float = 0.7
    ) -> Tuple[List[TermAnalysis], List[TermAnalysis], Dict[str, float]]:
        """Analyze consultation directly from storage.
        
        Args:
            consultation_id: Consultation identifier
            consultation_uuid: UUID for transcript lookup
            backend: Backend implementation used
            ground_truth_text: Ground truth text
            confidence_threshold: Minimum confidence for inclusion
            
        Returns:
            Tuple of (false_positives, false_negatives, accuracy_metrics)
        """
        orig_key, corr_key = find_consultation_objects(self.storage, consultation_uuid)
        
        if not orig_key or not corr_key:
            logger.warning(f"Missing transcript files for consultation {consultation_uuid}")
            return [], [], {}
        
        orig_json = load_json_transcript(self.storage, orig_key)
        corr_json = load_json_transcript(self.storage, corr_key)
        
        orig_text, _ = flatten_json_transcript(orig_json)
        corr_text, _ = flatten_json_transcript(corr_json)
        
        false_positives, false_negatives = self.analyze_consultation(
            consultation_id=consultation_id,
            backend=backend,
            original_text=orig_text,
            corrected_text=corr_text,
            ground_truth_text=ground_truth_text,
            confidence_threshold=confidence_threshold
        )
        
        accuracy_metrics = calculate_accuracy(orig_text, corr_text, ground_truth_text)
        
        return false_positives, false_negatives, accuracy_metrics
    
    def _analyze_false_positive(
        self,
        segment: AlignedSegment,
        consultation_id: str,
        backend: str,
        confidence_threshold: float
    ) -> List[TermAnalysis]:
        """Analyze segment for false positive errors."""
        if segment.segment_type == 'equal':
            return []
        
        orig_vs_gt_score = fuzz.ratio(segment.original_text, segment.ground_truth_text)
        corr_vs_gt_score = fuzz.ratio(segment.corrected_text, segment.ground_truth_text)
        
        if orig_vs_gt_score > corr_vs_gt_score and orig_vs_gt_score > self.fuzzy_threshold:
            orig_words = segment.original_text.split()
            corr_words = segment.corrected_text.split()
            gt_words = segment.ground_truth_text.split()
            
            problematic_terms = self._identify_problematic_terms(
                orig_words, corr_words, gt_words, "false_positive"
            )
            
            analyses = []
            for term_info in problematic_terms:
                error_pattern = self._classify_error_pattern(term_info['term'])
                alignment_type = self._determine_alignment_type(
                    term_info['term'], orig_words, corr_words
                )
                
                diff_viz = self.diff_visualizer.create_unified_diff(
                    segment.original_text,
                    segment.corrected_text, 
                    segment.ground_truth_text
                )
                inline_diff = self.diff_visualizer.create_inline_diff(
                    segment.original_text,
                    segment.corrected_text,
                    segment.ground_truth_text
                )
                
                confidence_stats = StatisticalConfidence.calculate_95th_percentile_confidence(
                    error_count=1,
                    total_samples=1, 
                    confidence_scores=[min(segment.alignment_score, confidence_threshold + 0.1)]
                )
                
                analysis = TermAnalysis(
                    term=term_info['term'],
                    error_type="false_positive",
                    original_context=segment.original_text,
                    corrected_context=segment.corrected_text,
                    ground_truth_context=segment.ground_truth_text,
                    confidence=min(segment.alignment_score, confidence_threshold + 0.1),
                    medical_vertical=self.classifier.classify_term(term_info['term']),
                    position=segment.original_start,
                    consultation_id=consultation_id,
                    backend=backend,
                    fuzzy_score=corr_vs_gt_score,
                    alignment_type=alignment_type,
                    suggested_correction=term_info['suggestion'],
                    error_pattern=error_pattern,
                    diff_visualization=diff_viz,
                    inline_diff=inline_diff,
                    confidence_statistics=confidence_stats
                )
                analyses.append(analysis)
            
            return analyses
        
        return []
    
    def _analyze_false_negative(
        self,
        segment: AlignedSegment,
        consultation_id: str,
        backend: str,
        confidence_threshold: float
    ) -> List[TermAnalysis]:
        """Analyze segment for false negative errors."""
        if segment.segment_type == 'equal':
            return []
        
        orig_vs_gt_score = fuzz.ratio(segment.original_text, segment.ground_truth_text)
        corr_vs_gt_score = fuzz.ratio(segment.corrected_text, segment.ground_truth_text)
        
        if orig_vs_gt_score < self.fuzzy_threshold and corr_vs_gt_score <= orig_vs_gt_score:
            orig_words = segment.original_text.split()
            corr_words = segment.corrected_text.split()
            gt_words = segment.ground_truth_text.split()
            
            problematic_terms = self._identify_problematic_terms(
                orig_words, corr_words, gt_words, "false_negative"
            )
            
            analyses = []
            for term_info in problematic_terms:
                error_pattern = self._classify_error_pattern(term_info['term'])
                alignment_type = self._determine_alignment_type(
                    term_info['term'], orig_words, gt_words
                )
                
                diff_viz = self.diff_visualizer.create_unified_diff(
                    segment.original_text,
                    segment.corrected_text,
                    segment.ground_truth_text
                )
                inline_diff = self.diff_visualizer.create_inline_diff(
                    segment.original_text,
                    segment.corrected_text,
                    segment.ground_truth_text
                )
                
                confidence_stats = StatisticalConfidence.calculate_95th_percentile_confidence(
                    error_count=1,
                    total_samples=1,
                    confidence_scores=[min(segment.alignment_score, confidence_threshold + 0.1)]
                )
                
                analysis = TermAnalysis(
                    term=term_info['term'],
                    error_type="false_negative",
                    original_context=segment.original_text,
                    corrected_context=segment.corrected_text,
                    ground_truth_context=segment.ground_truth_text,
                    confidence=min(segment.alignment_score, confidence_threshold + 0.1),
                    medical_vertical=self.classifier.classify_term(term_info['term']),
                    position=segment.original_start,
                    consultation_id=consultation_id,
                    backend=backend,
                    fuzzy_score=orig_vs_gt_score,
                    alignment_type=alignment_type,
                    suggested_correction=term_info['suggestion'],
                    error_pattern=error_pattern,
                    diff_visualization=diff_viz,
                    inline_diff=inline_diff,
                    confidence_statistics=confidence_stats
                )
                analyses.append(analysis)
            
            return analyses
        
        return []
    
    def _identify_problematic_terms(
        self,
        orig_words: List[str],
        corr_words: List[str],
        gt_words: List[str],
        error_type: str
    ) -> List[Dict[str, str]]:
        """Identify specific terms causing problems with sophisticated split-word handling."""
        problematic_terms = []
        
        if error_type == "false_positive":
            problematic_terms.extend(self._find_false_positive_terms(orig_words, corr_words, gt_words))
        elif error_type == "false_negative":
            problematic_terms.extend(self._find_false_negative_terms(orig_words, corr_words, gt_words))
        
        return problematic_terms
    
    def _find_false_positive_terms(
        self,
        orig_words: List[str],
        corr_words: List[str],
        gt_words: List[str]
    ) -> List[Dict[str, str]]:
        """Find false positive terms with sophisticated sequence-aware detection."""
        problematic_terms = []
        
        if self._is_sequence_level_mismatch(orig_words, corr_words, gt_words):
            orig_phrase = ' '.join(orig_words)
            corr_phrase = ' '.join(corr_words)
            gt_phrase = ' '.join(gt_words)
            
            orig_gt_score = fuzz.ratio(self.normalizer.normalize_text(orig_phrase),
                                      self.normalizer.normalize_text(gt_phrase))
            corr_gt_score = fuzz.ratio(self.normalizer.normalize_text(corr_phrase),
                                      self.normalizer.normalize_text(gt_phrase))
            
            if orig_gt_score > self.fuzzy_threshold and corr_gt_score < orig_gt_score - 15:
                problematic_terms.append({
                    'term': corr_phrase,
                    'suggestion': orig_phrase,
                    'type': 'sequence_level_incorrect_change',
                    'confidence': (orig_gt_score - corr_gt_score) / 100.0,
                    'pattern': 'sequence_degradation'
                })
        else:
            processed_indices = set()
            
            for i, orig_word in enumerate(orig_words):
                if i in processed_indices or i >= len(corr_words) or i >= len(gt_words):
                    continue
                    
                if self._are_terms_equivalent(corr_words[i], gt_words[i]):
                    continue
                
                orig_word_norm = self.normalizer.normalize_text(orig_word)
                corr_word_norm = self.normalizer.normalize_text(corr_words[i])
                gt_word_norm = self.normalizer.normalize_text(gt_words[i])
                
                orig_gt_score = fuzz.ratio(orig_word_norm, gt_word_norm)
                corr_gt_score = fuzz.ratio(corr_word_norm, gt_word_norm)
                
                if orig_gt_score > self.fuzzy_threshold and corr_gt_score < orig_gt_score - 10:
                    problematic_terms.append({
                        'term': corr_words[i],
                        'suggestion': orig_words[i],
                        'type': 'incorrect_change',
                        'confidence': (orig_gt_score - corr_gt_score) / 100.0
                    })
                    processed_indices.add(i)
        
        return problematic_terms
    
    def _find_false_negative_terms(
        self,
        orig_words: List[str],
        corr_words: List[str],
        gt_words: List[str]
    ) -> List[Dict[str, str]]:
        """Find false negative terms with sophisticated sequence-aware detection."""
        problematic_terms = []
        
        if self._is_sequence_level_mismatch(orig_words, corr_words, gt_words):
            orig_phrase = ' '.join(orig_words)
            corr_phrase = ' '.join(corr_words)
            gt_phrase = ' '.join(gt_words)
            
            orig_gt_score = fuzz.ratio(self.normalizer.normalize_text(orig_phrase), 
                                      self.normalizer.normalize_text(gt_phrase))
            corr_gt_score = fuzz.ratio(self.normalizer.normalize_text(corr_phrase),
                                      self.normalizer.normalize_text(gt_phrase))
            
            if orig_gt_score < self.fuzzy_threshold and corr_gt_score <= orig_gt_score + 10:
                problematic_terms.append({
                    'term': gt_phrase,
                    'suggestion': gt_phrase,
                    'type': 'sequence_level_missed_correction',
                    'confidence': (self.fuzzy_threshold - corr_gt_score) / 100.0,
                    'pattern': 'sequence_mismatch'
                })
        else:
            processed_indices = set()
            
            for i, orig_word in enumerate(orig_words):
                if i in processed_indices or i >= len(gt_words):
                    continue
                
                if self._are_terms_equivalent(orig_words[i], gt_words[i]):
                    continue
                    
                if i < len(corr_words) and self._are_terms_equivalent(corr_words[i], gt_words[i]):
                    continue
                    
                orig_word_norm = self.normalizer.normalize_text(orig_word)
                gt_word_norm = self.normalizer.normalize_text(gt_words[i])
                
                orig_gt_score = fuzz.ratio(orig_word_norm, gt_word_norm)
                
                if orig_gt_score < self.fuzzy_threshold:
                    if i < len(corr_words):
                        corr_word_norm = self.normalizer.normalize_text(corr_words[i])
                        corr_gt_score = fuzz.ratio(corr_word_norm, gt_word_norm)
                        
                        if corr_gt_score <= orig_gt_score + 5:
                            problematic_terms.append({
                                'term': gt_words[i],
                                'suggestion': gt_words[i],
                                'type': 'missed_correction',
                                'confidence': (self.fuzzy_threshold - orig_gt_score) / 100.0
                            })
                            processed_indices.add(i)
        
        return problematic_terms
    
    def _is_sequence_level_mismatch(
        self,
        orig_words: List[str],
        corr_words: List[str], 
        gt_words: List[str]
    ) -> bool:
        """Determine if this is a sequence-level mismatch that should be treated as a single issue."""
        max_len = max(len(orig_words), len(gt_words))
        min_len = min(len(orig_words), len(gt_words))
        length_ratio = min_len / max_len if max_len > 0 else 1.0
        
        if length_ratio < 0.7:
            return True
            
        orig_phrase = ' '.join(orig_words)
        gt_phrase = ' '.join(gt_words)
        
        overall_similarity = fuzz.ratio(
            self.normalizer.normalize_text(orig_phrase),
            self.normalizer.normalize_text(gt_phrase)
        )
        
        if overall_similarity < 40:
            return True
            
        matching_words = 0
        for i in range(min(len(orig_words), len(gt_words))):
            if self._are_terms_equivalent(orig_words[i], gt_words[i]):
                matching_words += 1
            else:
                word_similarity = fuzz.ratio(
                    self.normalizer.normalize_text(orig_words[i]),
                    self.normalizer.normalize_text(gt_words[i])
                )
                if word_similarity > self.fuzzy_threshold:
                    matching_words += 1
        
        match_ratio = matching_words / max(len(orig_words), len(gt_words))
        
        return match_ratio < 0.3
    
    def _are_terms_equivalent(self, term1: str, term2: str) -> bool:
        """Check if two terms are semantically equivalent."""
        norm1 = self.normalizer.normalize_text(term1)
        norm2 = self.normalizer.normalize_text(term2)
        
        if norm1 == norm2:
            return True
        
        similarity = fuzz.ratio(norm1, norm2)
        if similarity >= 95:
            return True
        
        unit_pattern1 = re.sub(r'(\d+)\s*([a-z]+)', r'\1\2', norm1)
        unit_pattern2 = re.sub(r'(\d+)\s*([a-z]+)', r'\1\2', norm2)
        if unit_pattern1 == unit_pattern2:
            return True
            
        return False
    
    def _classify_error_pattern(self, term: str) -> str:
        """Classify the error pattern for a term."""
        for pattern_name, pattern_regex in self.error_patterns.items():
            if re.search(pattern_regex, term, re.IGNORECASE):
                return pattern_name
        return "general"
    
    def _determine_alignment_type(
        self,
        term: str,
        seq1: List[str],
        seq2: List[str]
    ) -> str:
        """Determine the type of alignment issue."""
        if len(seq1) != len(seq2):
            return "frameshift"
        
        if any(char in term for char in '.,!?;:/-()[]{}'):
            return "punctuation"
        
        if any(' ' in word for word in seq1 + seq2):
            return "word_boundary"
        
        for word1 in seq1:
            for word2 in seq2:
                if fuzz.ratio(word1, word2) > 60:
                    return "phonetic"
        
        return "general"
    
    def save_analysis_results(
        self,
        consultation_id: str,
        false_positives: List[TermAnalysis],
        false_negatives: List[TermAnalysis],
        accuracy_metrics: Dict[str, float],
        language: str = "english"
    ) -> str:
        """Save analysis results to storage.
        
        Args:
            consultation_id: Consultation identifier
            false_positives: False positive analyses
            false_negatives: False negative analyses
            accuracy_metrics: Accuracy calculation results
            language: Language for organization
            
        Returns:
            Storage path of saved results
        """
        timestamp = datetime.now().isoformat()
        
        results = {
            "consultation_id": consultation_id,
            "timestamp": timestamp,
            "false_positive_count": len(false_positives),
            "false_negative_count": len(false_negatives),
            "false_positives": [asdict(fp) for fp in false_positives],
            "false_negatives": [asdict(fn) for fn in false_negatives],
            "accuracy_metrics": accuracy_metrics,
            "summary": {
                "total_errors": len(false_positives) + len(false_negatives),
                "accuracy": accuracy_metrics.get("accuracy", 0.0),
                "character_error_rate": accuracy_metrics.get("character_error_rate", 1.0),
                "improvement_over_original": accuracy_metrics.get("improvement_over_original", 0.0)
            }
        }
        
        storage_path = f"fp-fn-analysis/{language}/{consultation_id}_{timestamp}.json"
        url = self.storage.save_json(storage_path, results)
        
        logger.info(f"Analysis results saved to: {url}")
        return storage_path


@dataclass
class FPFNReport:
    """Enhanced false positive/negative analysis report."""
    
    false_positives: List[TermAnalysis]
    false_negatives: List[TermAnalysis]
    medical_verticals: Dict[str, List[str]]
    summary_stats: Dict[str, Any]
    consultation_analysis: Dict[str, Any]
    error_patterns: Dict[str, List[str]]
    alignment_statistics: Dict[str, Any]


def create_modifiable_terminology_config(
    report: FPFNReport,
    storage: StorageBackend,
    language: str = "english"
) -> str:
    """Create enhanced modifiable terminology configuration.
    
    Args:
        report: FP/FN analysis report
        storage: Storage backend for saving config
        language: Language for organization
        
    Returns:
        Storage path of saved configuration
    """
    config = {
        "enhanced_terminology_config": {
            "version": "2.0",
            "description": "Enhanced modifiable terminology configuration with fuzzy matching and error patterns",
            "medical_verticals": {},
            "error_patterns": {
                "false_positive_patterns": [],
                "false_negative_patterns": [],
                "alignment_types": {
                    "frameshift": [],
                    "punctuation": [],
                    "word_boundary": [],
                    "phonetic": []
                }
            },
            "fuzzy_matching_settings": {
                "min_fuzzy_score": 75,
                "confidence_threshold": 0.7,
                "alignment_score_threshold": 0.6
            },
            "generation_settings": {
                "include_false_positives": True,
                "include_false_negatives": True,
                "include_error_patterns": True,
                "prioritize_by_alignment_type": True,
                "use_fuzzy_matching": True
            }
        }
    }
    
    for vertical in ["dermatology", "venous_care", "plastic_surgery", "aesthetic_medicine"]:
        fp_terms = [
            fp.term for fp in report.false_positives
            if fp.medical_vertical == vertical
        ]
        fn_terms = [
            fn.term for fn in report.false_negatives
            if fn.medical_vertical == vertical
        ]
        
        config["enhanced_terminology_config"]["medical_verticals"][vertical] = {
            "enabled": True,
            "priority": "high",
            "false_positive_terms": list(set(fp_terms[:10])),
            "false_negative_terms": list(set(fn_terms[:10])),
            "exclusions": [],
            "custom_terms": [],
            "error_patterns": list(set(
                fp.error_pattern for fp in report.false_positives
                if fp.medical_vertical == vertical
            ))
        }
    
    for fp in report.false_positives[:20]:
        config["enhanced_terminology_config"]["error_patterns"]["false_positive_patterns"].append({
            "term": fp.term,
            "pattern": fp.error_pattern,
            "alignment_type": fp.alignment_type,
            "fuzzy_score": fp.fuzzy_score,
            "frequency": 1,
            "context": fp.original_context,
            "enabled": True
        })
    
    for fn in report.false_negatives[:20]:
        config["enhanced_terminology_config"]["error_patterns"]["false_negative_patterns"].append({
            "term": fn.term,
            "pattern": fn.error_pattern,
            "alignment_type": fn.alignment_type,
            "fuzzy_score": fn.fuzzy_score,
            "frequency": 1,
            "context": fn.original_context,
            "enabled": True
        })
    
    for alignment_type in ["frameshift", "punctuation", "word_boundary", "phonetic"]:
        terms = [
            analysis.term for analysis in report.false_positives + report.false_negatives
            if analysis.alignment_type == alignment_type
        ]
        config["enhanced_terminology_config"]["error_patterns"]["alignment_types"][alignment_type] = list(set(terms))
    
    timestamp = datetime.now().isoformat()
    storage_path = f"terminology-config/{language}/enhanced_config_{timestamp}.json"
    url = storage.save_json(storage_path, config)
    
    logger.info(f"Enhanced modifiable terminology configuration created: {url}")
    return storage_path


# For backward compatibility
FPFNIdentifier = FPFNAnalyzer