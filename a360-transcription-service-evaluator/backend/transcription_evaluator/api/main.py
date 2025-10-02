"""FastAPI application for transcription evaluation service.

This module provides HTTP endpoints for analyzing transcript quality
by comparing raw Deepgram ASR output, LLM-corrected versions, and
ground truth transcripts.

The service provides comprehensive analysis including:
    • Character and word error rate calculations
    • False positive and false negative analysis
    • Speaker diarization accuracy metrics
    • Visualization generation
    • Results storage in S3

Endpoints:
    • POST /analyze/single - Analyze a single consultation
    • POST /analyze/batch - Analyze multiple consultations  
    • GET /analyze/report/{report_id} - Retrieve analysis report
    • GET /health - Health check endpoint
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..config.settings import get_settings
from ..core.storage import StorageBackend, create_storage_backend
from ..core.generation import EnhancedGroundTruthGenerator, GeneratedScript
from ..services.transcript_analysis import TranscriptAnalyzer

logger = logging.getLogger(__name__)

app = FastAPI(
    title="A360 Transcription Evaluator",
    description="Service for evaluating transcript quality and accuracy",
    version="0.1.0",
    openapi_tags=[
        {
            "name": "analysis",
            "description": "Transcript analysis endpoints",
        },
        {
            "name": "health",
            "description": "Health check endpoints",
        },
        {
            "name": "generation",
            "description": "Ground truth generation endpoints",
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConsultationAnalysisRequest(BaseModel):
    """Request model for single consultation analysis."""
    
    consultation_key: str = Field(
        ..., description="Consultation key identifier (e.g., 'consultation_01')"
    )
    consultation_uuid: str = Field(
        ..., description="Consultation UUID for storage lookup"
    )
    ground_truth_path: str = Field(
        ..., description="Path to ground truth file in storage"
    )
    language: str = Field(
        default="english", description="Language for processing"
    )


class BatchAnalysisRequest(BaseModel):
    """Request model for batch consultation analysis."""
    
    consultation_mapping: Dict[str, Any] = Field(
        ..., description="Full consultation mapping data"
    )
    language: str = Field(
        default="english", description="Language to analyze"
    )
    consultation_keys: Optional[List[str]] = Field(
        default=None, description="Optional list of specific consultation keys"
    )
    include_plots: bool = Field(
        default=True, description="Whether to generate visualization plots"
    )


class AnalysisResponse(BaseModel):
    """Response model for analysis operations."""
    
    success: bool = Field(..., description="Whether analysis succeeded")
    analysis_id: str = Field(..., description="Unique analysis identifier")
    report_path: Optional[str] = Field(
        default=None, description="Path to saved analysis report"
    )
    summary_statistics: Optional[Dict[str, Any]] = Field(
        default=None, description="Summary statistics from analysis"
    )
    message: str = Field(..., description="Status message")


class HealthResponse(BaseModel):
    """Response model for health check."""
    
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="Current timestamp")
    version: str = Field(..., description="Service version")


class SingleAnalysisRequest(BaseModel):
    """Request model for direct single transcript analysis."""
    
    consultation_id: str = Field(..., description="Consultation identifier")
    original_text: str = Field(..., description="Original transcript text")
    corrected_text: str = Field(..., description="Corrected transcript text")
    ground_truth_text: str = Field(..., description="Ground truth transcript text")
    backend: str = Field(..., description="Backend system used for transcription")
    confidence_threshold: float = Field(default=0.7, description="Confidence threshold for analysis")


class GroundTruthGenerationRequest(BaseModel):
    """Request model for ground truth generation."""
    
    medical_vertical: str = Field(
        default="aesthetic_medicine", 
        description="Medical vertical (aesthetic_medicine, dermatology, venous_care, plastic_surgery)"
    )
    language: str = Field(default="english", description="Language for generation")
    target_word_count: int = Field(default=600, description="Target word count for script")
    challenge_level: str = Field(default="both", description="Challenge level (voice_actor, transcription, both)")
    seed_term_density: float = Field(default=0.15, description="Density of seed terms (0.1-0.5)")
    include_product_names: bool = Field(default=True, description="Include brand/product names")


class GroundTruthResponse(BaseModel):
    """Response model for ground truth generation."""
    
    success: bool = Field(..., description="Whether generation succeeded")
    script_id: str = Field(..., description="Generated script identifier")
    content: str = Field(..., description="Generated script content")
    word_count: int = Field(..., description="Actual word count")
    storage_path: str = Field(..., description="Storage path for script")
    metadata: Dict[str, Any] = Field(..., description="Generation metadata")
    message: str = Field(..., description="Status message")


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Health check endpoint for service monitoring.
    
    Returns:
        HealthResponse with current service status
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="0.1.0"
    )


@app.post("/analyze/single", response_model=AnalysisResponse, tags=["analysis"])
async def analyze_single_consultation(
    request: ConsultationAnalysisRequest
) -> AnalysisResponse:
    """Analyze a single consultation for transcript quality.
    
    Args:
        request: Single consultation analysis request
        
    Returns:
        AnalysisResponse with analysis results
        
    Raises:
        HTTPException: If analysis fails or consultation not found
    """
    try:
        settings = get_settings()
        storage_config = settings.get_storage_config()
        storage = create_storage_backend(**storage_config)
        
        analyzer = TranscriptAnalyzer(storage_backend=storage)
        analysis_id = str(uuid.uuid4())
        
        logger.info(f"Starting single consultation analysis: {request.consultation_key}")
        
        result = analyzer.process_consultation(
            consultation_key=request.consultation_key,
            consultation_uuid=request.consultation_uuid,
            ground_truth_path=request.ground_truth_path,
            language=request.language
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not process consultation {request.consultation_key}"
            )
        
        # Generate analysis report
        report = analyzer.generate_analysis_report([result], request.language)
        
        # Save analysis results
        report_path = analyzer.save_analysis_results(
            report=report,
            language=request.language,
            include_plots=True
        )
        
        logger.info(f"Single consultation analysis completed: {analysis_id}")
        
        return AnalysisResponse(
            success=True,
            analysis_id=analysis_id,
            report_path=report_path,
            summary_statistics=report.get("summary_statistics"),
            message=f"Successfully analyzed consultation {request.consultation_key}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing single consultation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@app.post("/analyze/batch", response_model=AnalysisResponse, tags=["analysis"])
async def analyze_batch_consultations(
    request: BatchAnalysisRequest
) -> AnalysisResponse:
    """Analyze multiple consultations for transcript quality.
    
    Args:
        request: Batch consultation analysis request
        
    Returns:
        AnalysisResponse with batch analysis results
        
    Raises:
        HTTPException: If analysis fails or no consultations found
    """
    try:
        settings = get_settings()
        storage_config = settings.get_storage_config()
        storage = create_storage_backend(**storage_config)
        
        analyzer = TranscriptAnalyzer(storage_backend=storage)
        analysis_id = str(uuid.uuid4())
        
        logger.info(
            f"Starting batch consultation analysis for language: {request.language}"
        )
        
        results = analyzer.analyze_consultations_from_mapping(
            consultation_mapping=request.consultation_mapping,
            language=request.language,
            consultation_keys=request.consultation_keys
        )
        
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No consultations found for language {request.language}"
            )
        
        # Generate comprehensive analysis report
        report = analyzer.generate_analysis_report(results, request.language)
        
        # Save analysis results with optional plots
        report_path = analyzer.save_analysis_results(
            report=report,
            language=request.language,
            include_plots=request.include_plots
        )
        
        logger.info(
            f"Batch analysis completed: {analysis_id} ({len(results)} consultations)"
        )
        
        return AnalysisResponse(
            success=True,
            analysis_id=analysis_id,
            report_path=report_path,
            summary_statistics=report.get("summary_statistics"),
            message=f"Successfully analyzed {len(results)} consultations"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch analysis failed: {str(e)}"
        )


@app.get("/analyze/report/{report_path:path}", tags=["analysis"])
async def get_analysis_report(report_path: str) -> Dict[str, Any]:
    """Retrieve a stored analysis report.
    
    Args:
        report_path: Path to the analysis report in storage
        
    Returns:
        Dictionary containing the analysis report data
        
    Raises:
        HTTPException: If report not found or cannot be retrieved
    """
    try:
        settings = get_settings()
        storage_config = settings.get_storage_config()
        storage = create_storage_backend(**storage_config)
        
        logger.info(f"Retrieving analysis report: {report_path}")
        
        if not storage.exists(report_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis report not found: {report_path}"
            )
        
        report_data = storage.load_json(report_path)
        
        return report_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving report {report_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve report: {str(e)}"
        )


@app.post("/analyze/single", response_model=AnalysisResponse, tags=["analysis"])
async def analyze_single_transcript(
    request: SingleAnalysisRequest
) -> AnalysisResponse:
    """Analyze a single transcript directly with provided text data.
    
    Args:
        request: Single transcript analysis request with text data
        
    Returns:
        AnalysisResponse with analysis results
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        from ..core.analysis import FPFNAnalyzer, calculate_accuracy
        
        settings = get_settings()
        storage_config = settings.get_storage_config()
        storage = create_storage_backend(**storage_config)
        
        analyzer = FPFNAnalyzer(storage_backend=storage)
        analysis_id = str(uuid.uuid4())
        
        logger.info(f"Starting direct transcript analysis: {request.consultation_id}")
        
        # Perform FP/FN analysis
        false_positives, false_negatives = analyzer.analyze_consultation(
            consultation_id=request.consultation_id,
            backend=request.backend,
            original_text=request.original_text,
            corrected_text=request.corrected_text,
            ground_truth_text=request.ground_truth_text,
            confidence_threshold=request.confidence_threshold
        )
        
        # Calculate accuracy metrics
        accuracy_metrics = calculate_accuracy(
            request.original_text,
            request.corrected_text, 
            request.ground_truth_text
        )
        
        # Save analysis results
        report_path = analyzer.save_analysis_results(
            consultation_id=request.consultation_id,
            false_positives=false_positives,
            false_negatives=false_negatives,
            accuracy_metrics=accuracy_metrics
        )
        
        logger.info(f"Direct transcript analysis completed: {analysis_id}")
        
        return AnalysisResponse(
            success=True,
            analysis_id=analysis_id,
            report_path=report_path,
            summary_statistics={
                "false_positive_count": len(false_positives),
                "false_negative_count": len(false_negatives),
                "accuracy": accuracy_metrics.get("accuracy", 0.0),
                "character_error_rate": accuracy_metrics.get("character_error_rate", 1.0)
            },
            message=f"Successfully analyzed consultation {request.consultation_id}"
        )
        
    except Exception as e:
        logger.error(f"Error in direct transcript analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@app.post("/generate/ground-truth", response_model=GroundTruthResponse, tags=["generation"])
async def generate_ground_truth_script(
    request: GroundTruthGenerationRequest
) -> GroundTruthResponse:
    """Generate a ground truth consultation script for testing.
    
    Args:
        request: Ground truth generation parameters
        
    Returns:
        GroundTruthResponse with generated script
        
    Raises:
        HTTPException: If generation fails
    """
    try:
        settings = get_settings()
        storage_config = settings.get_storage_config()
        storage = create_storage_backend(**storage_config)
        
        generator = EnhancedGroundTruthGenerator(storage_backend=storage)
        generation_id = str(uuid.uuid4())
        
        logger.info(f"Starting ground truth generation: {request.medical_vertical}")
        
        # Generate script
        script = generator.generate_script(
            medical_vertical=request.medical_vertical,
            language=request.language,
            target_word_count=request.target_word_count,
            challenge_level=request.challenge_level,
            seed_term_density=request.seed_term_density,
            include_product_names=request.include_product_names
        )
        
        # Save script to storage
        script_url, metadata_url = generator.save_script(script)
        
        logger.info(f"Ground truth generation completed: {generation_id}")
        
        return GroundTruthResponse(
            success=True,
            script_id=script.script_id,
            content=script.content,
            word_count=script.word_count,
            storage_path=script.storage_path,
            metadata={
                "script_url": script_url,
                "metadata_url": metadata_url,
                "generation_id": generation_id,
                "seed_terms_used": script.seed_terms_used,
                "brand_names_used": script.brand_names_used,
                "difficulty_score": script.difficulty_score,
                "transcription_challenge_score": script.transcription_challenge_score,
                "voice_actor_challenge_score": script.voice_actor_challenge_score
            },
            message=f"Successfully generated {request.medical_vertical} script ({script.word_count} words)"
        )
        
    except Exception as e:
        logger.error(f"Error generating ground truth script: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}"
        )


@app.get("/generate/verticals", tags=["generation"])
async def get_available_verticals() -> Dict[str, List[str]]:
    """Get list of available medical verticals for ground truth generation.
    
    Returns:
        Dictionary with available medical verticals
    """
    try:
        from ..core.generation import SeedTerminologyManager
        
        manager = SeedTerminologyManager()
        verticals = manager.get_available_verticals()
        
        return {
            "available_verticals": verticals,
            "description": "Medical verticals available for ground truth generation"
        }
        
    except Exception as e:
        logger.error(f"Error retrieving available verticals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve verticals: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors.
    
    Args:
        request: HTTP request object
        exc: Exception that was raised
        
    Returns:
        JSONResponse with error details
    """
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error occurred",
            "detail": str(exc) if logger.isEnabledFor(logging.DEBUG) else None
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "transcription_evaluator.api.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )