#!/usr/bin/env python3
"""
Command-line interface for transcription evaluation toolkit.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from ..config.settings import get_settings, update_settings
from ..core.generation import EnhancedGroundTruthGenerator
from ..core.analysis import FPFNAnalyzer, calculate_accuracy, FPFNReport
from ..core.storage import create_storage_backend
from ..services.text_to_speech import TextToSpeechService


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def generate_ground_truth_command(args):
    """Generate ground truth scripts command."""
    try:
        # Update settings with CLI args
        settings_overrides = {}
        if args.storage_backend:
            settings_overrides["storage_backend"] = args.storage_backend
        if args.local_path:
            settings_overrides["local_storage_path"] = args.local_path
        if args.s3_bucket:
            settings_overrides["s3_bucket"] = args.s3_bucket
        
        if settings_overrides:
            update_settings(**settings_overrides)
        
        # Initialize generator
        generator = EnhancedGroundTruthGenerator(aws_profile=args.aws_profile)
        
        # Generate script
        script = generator.generate_script(
            medical_vertical=args.vertical,
            language=args.language,
            target_word_count=args.word_count,
            challenge_level=args.challenge_level,
            seed_term_density=args.seed_term_density,
            difficulty_level=args.difficulty_level
        )
        
        # Save script
        script_url, metadata_url = generator.save_script(script)
        
        print(f"Generated script: {script.script_id}")
        print(f"Word count: {script.word_count}")
        print(f"Difficulty score: {script.difficulty_score:.2f}")
        print(f"Seed terms used: {len(script.seed_terms_used)}")
        print(f"Brand names used: {len(script.brand_names_used)}")
        print(f"Script saved to: {script_url}")
        print(f"Metadata saved to: {metadata_url}")
        
    except Exception as e:
        print(f"Error generating ground truth: {e}")
        sys.exit(1)


def analyze_fp_fn_command(args):
    """Analyze false positives and false negatives command."""
    try:
        # Update settings with CLI args
        settings_overrides = {}
        if args.storage_backend:
            settings_overrides["storage_backend"] = args.storage_backend
        if args.local_path:
            settings_overrides["local_storage_path"] = args.local_path
        if args.s3_bucket:
            settings_overrides["s3_bucket"] = args.s3_bucket
        
        if settings_overrides:
            update_settings(**settings_overrides)
        
        # Initialize analyzer
        analyzer = FPFNAnalyzer(aws_profile=args.aws_profile)
        
        # Load consultation mapping
        with open(args.consultation_data, 'r', encoding='utf-8') as f:
            consultation_data = json.load(f)
        
        # Get consultations for language
        consultations = consultation_data.get("consultation_mappings", {}).get(args.language, {})
        
        # Filter by consultation IDs if specified
        if args.consultation_ids:
            selected_ids = args.consultation_ids.split(",")
            consultations = {k: v for k, v in consultations.items() if k in selected_ids}
        
        # Process each consultation
        all_results = []
        for consultation_id, consultation_info in consultations.items():
            ground_truth_file = f"speak_text_contents/{args.language}/{consultation_info['ground_truth_file']}"
            
            if Path(ground_truth_file).exists():
                try:
                    # Read ground truth content
                    with open(ground_truth_file, 'r', encoding='utf-8') as f:
                        ground_truth_text = f.read()
                    
                    # Process each variation (backend implementation)
                    for variation in consultation_info.get('variations', []):
                        consultation_uuid = variation['consultation_id']
                        backend = variation['backend']
                        
                        try:
                            # Perform enhanced FP/FN analysis using storage
                            false_positives, false_negatives, accuracy_metrics = analyzer.analyze_from_storage(
                                consultation_id=consultation_id,
                                consultation_uuid=consultation_uuid,
                                backend=backend,
                                ground_truth_text=ground_truth_text,
                                confidence_threshold=args.confidence_threshold
                            )
                            
                            # Create analysis result
                            result = {
                                "consultation_id": consultation_id,
                                "consultation_uuid": consultation_uuid,
                                "backend": backend,
                                "false_positive_count": len(false_positives),
                                "false_negative_count": len(false_negatives),
                                "false_positives": [fp.__dict__ for fp in false_positives],
                                "false_negatives": [fn.__dict__ for fn in false_negatives],
                                "accuracy_metrics": accuracy_metrics,
                                "accuracy": accuracy_metrics.get("accuracy", 0.0),
                            }
                            
                            all_results.append(result)
                            print(f"Analyzed {consultation_id} ({backend}): {len(false_positives)} FP, {len(false_negatives)} FN")
                            
                            # Save individual results if requested
                            if args.save_individual:
                                analyzer.save_analysis_results(
                                    consultation_id=consultation_id,
                                    false_positives=false_positives,
                                    false_negatives=false_negatives,
                                    accuracy_metrics=accuracy_metrics,
                                    language=args.language
                                )
                        
                        except Exception as e:
                            print(f"Error analyzing {consultation_id} ({backend}): {e}")
                            continue
                            
                except Exception as e:
                    print(f"Error processing {consultation_id}: {e}")
            else:
                print(f"Ground truth file not found: {ground_truth_file}")
        
        # Create summary report
        if all_results:
            total_consultations = len(all_results)
            total_fp = sum(r["false_positive_count"] for r in all_results)
            total_fn = sum(r["false_negative_count"] for r in all_results)
            
            summary = {
                "total_consultations": total_consultations,
                "total_false_positives": total_fp,
                "total_false_negatives": total_fn,
                "average_accuracy": sum(r["accuracy"] for r in all_results) / len(all_results),
                "consultations": all_results
            }
            
            # Save summary report using storage
            summary_path = f"fp-fn-analysis/{args.language}/summary_{args.language}.json"
            url = analyzer.storage.save_json(summary_path, summary)
            
            print(f"\nAnalysis completed. Summary saved to: {url}")
            print(f"Total: {total_fp} FP, {total_fn} FN")
            print(f"Average accuracy: {summary['average_accuracy']:.2%}")
        else:
            print("No consultations were successfully analyzed.")
            
    except Exception as e:
        print(f"Error in FP/FN analysis: {e}")
        sys.exit(1)


def synthesize_tts_command(args):
    """Text-to-speech synthesis command."""
    try:
        # Update settings with CLI args
        settings_overrides = {}
        if args.storage_backend:
            settings_overrides["storage_backend"] = args.storage_backend
        if args.local_path:
            settings_overrides["local_storage_path"] = args.local_path
        if args.s3_bucket:
            settings_overrides["s3_bucket"] = args.s3_bucket
        
        if settings_overrides:
            update_settings(**settings_overrides)
        
        # Initialize TTS service
        tts_service = TextToSpeechService(aws_profile=args.aws_profile)
        
        if args.input_file:
            # Single file synthesis
            output_path = tts_service.synthesize_consultation_from_storage(
                input_path=args.input_file,
                output_path=args.output_file,
                language=args.language
            )
            print(f"Synthesized audio saved to: {output_path}")
        else:
            # Batch synthesis
            results = tts_service.process_batch_synthesis(
                input_prefix=args.input_prefix,
                output_prefix=args.output_prefix,
                language_filter=args.language
            )
            
            print(f"Batch synthesis completed:")
            print(f"Total files: {results['total_files']}")
            print(f"Successful: {results['successful']}")
            print(f"Failed: {results['failed']}")
            
            if args.save_report:
                report_path = tts_service.save_synthesis_report(results, args.language or "all")
                print(f"Report saved to: {report_path}")
                
    except Exception as e:
        print(f"Error in TTS synthesis: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Transcription Evaluation Toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global options
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level"
    )
    
    parser.add_argument(
        "--storage-backend",
        choices=["s3", "local"],
        help="Storage backend to use (overrides config)"
    )
    
    parser.add_argument(
        "--local-path",
        help="Local storage path (when using local backend)"
    )
    
    parser.add_argument(
        "--s3-bucket",
        help="S3 bucket name (when using S3 backend)"
    )
    
    parser.add_argument(
        "--aws-profile",
        help="AWS profile to use"
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Generate ground truth command
    gen_parser = subparsers.add_parser(
        "generate-ground-truth",
        help="Generate ground truth consultation scripts"
    )
    gen_parser.add_argument(
        "--vertical",
        choices=["aesthetic_medicine", "dermatology", "venous_care", "plastic_surgery"],
        default="aesthetic_medicine",
        help="Medical vertical for script generation"
    )
    gen_parser.add_argument(
        "--language",
        choices=["english", "spanish"],
        default="english",
        help="Language for script generation"
    )
    gen_parser.add_argument(
        "--word-count",
        type=int,
        default=600,
        help="Target word count for generated script"
    )
    gen_parser.add_argument(
        "--challenge-level",
        choices=["voice_actor", "transcription", "both"],
        default="both",
        help="Challenge level for script generation"
    )
    gen_parser.add_argument(
        "--seed-term-density",
        type=float,
        default=0.15,
        help="Density of seed terms in generated script (0.0-1.0)"
    )
    gen_parser.add_argument(
        "--difficulty-level",
        choices=["basic", "intermediate", "advanced"],
        default="intermediate",
        help="Difficulty level for generated script"
    )
    
    # FP/FN analysis command
    fp_fn_parser = subparsers.add_parser(
        "analyze-fp-fn",
        help="Analyze false positives and false negatives"
    )
    fp_fn_parser.add_argument(
        "--consultation-data",
        required=True,
        help="Path to consultation mapping JSON file"
    )
    fp_fn_parser.add_argument(
        "--language",
        required=True,
        choices=["english", "spanish"],
        help="Language for analysis"
    )
    fp_fn_parser.add_argument(
        "--consultation-ids",
        help="Comma-separated list of consultation IDs to analyze"
    )
    fp_fn_parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Minimum confidence threshold for error detection"
    )
    fp_fn_parser.add_argument(
        "--save-individual",
        action="store_true",
        help="Save individual consultation analysis results"
    )
    
    # Text-to-speech synthesis command
    tts_parser = subparsers.add_parser(
        "synthesize-tts",
        help="Generate audio from consultation text using TTS"
    )
    tts_parser.add_argument(
        "--input-file",
        help="Single input text file path in storage"
    )
    tts_parser.add_argument(
        "--output-file", 
        help="Output audio file path (for single file mode)"
    )
    tts_parser.add_argument(
        "--input-prefix",
        default="ground-truth",
        help="Storage prefix for input text files (batch mode)"
    )
    tts_parser.add_argument(
        "--output-prefix",
        default="tts-audio", 
        help="Storage prefix for output audio files (batch mode)"
    )
    tts_parser.add_argument(
        "--language",
        choices=["english", "spanish"],
        help="Language filter for synthesis"
    )
    tts_parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save synthesis processing report"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Execute command
    if args.command == "generate-ground-truth":
        generate_ground_truth_command(args)
    elif args.command == "analyze-fp-fn":
        analyze_fp_fn_command(args)
    elif args.command == "synthesize-tts":
        synthesize_tts_command(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()