"""Ground truth generation routes with Cognito authentication.

This module provides authenticated endpoints for ground truth script generation
using AWS Cognito and Verified Permissions for authorization.
"""

import logging
import uuid
from typing import Any, Dict, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..aws.authorizers import CognitoUser, require_cognito_auth, require_admin_access, require_evaluation_access
from ..config.settings import get_settings
from ..core.storage import create_storage_backend
from ..core.generation import EnhancedGroundTruthGenerator, SeedTerminologyManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generation"])


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
    selected_brands: List[str] = Field(default_factory=list, description="User-selected brand names")
    selected_terms: List[str] = Field(default_factory=list, description="User-selected medical terms")


class GroundTruthResponse(BaseModel):
    """Response model for ground truth generation."""
    
    success: bool = Field(..., description="Whether generation succeeded")
    script_id: str = Field(..., description="Generated script identifier")
    content: str = Field(..., description="Generated script content")
    word_count: int = Field(..., description="Actual word count")
    storage_path: str = Field(..., description="Storage path for script")
    metadata: Dict[str, Any] = Field(..., description="Generation metadata")
    message: str = Field(..., description="Status message")


class VerticalsResponse(BaseModel):
    """Response model for available verticals."""
    
    available_verticals: List[str] = Field(..., description="List of available medical verticals")
    description: str = Field(..., description="Description of verticals")


@router.get("/verticals", response_model=VerticalsResponse)
async def get_available_verticals(
    current_user: CognitoUser = Depends(require_cognito_auth),
    evaluation_access: bool = Depends(require_evaluation_access)
) -> VerticalsResponse:
    """Get list of available medical verticals for ground truth generation.
    
    Requires evaluation access (admin, evaluator, or reviewer groups).
    
    Args:
        current_user: Authenticated Cognito user
        evaluation_access: Evaluation access verification
    
    Returns:
        VerticalsResponse with available medical verticals
        
    Raises:
        HTTPException: If retrieval fails or user lacks permissions
    """
    try:
        manager = SeedTerminologyManager()
        verticals = manager.get_available_verticals()
        
        logger.info(f"Retrieved {len(verticals)} available verticals for user {current_user.email}")
        
        return VerticalsResponse(
            available_verticals=verticals,
            description="Medical verticals available for ground truth generation"
        )
        
    except Exception as e:
        logger.error(f"Error retrieving available verticals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve verticals: {str(e)}"
        )


@router.post("/ground-truth", response_model=GroundTruthResponse)
async def generate_ground_truth_script(
    request: GroundTruthGenerationRequest,
    current_user: CognitoUser = Depends(require_cognito_auth),
    admin_access: bool = Depends(require_admin_access)
) -> GroundTruthResponse:
    """Generate a ground truth consultation script for testing.
    
    Requires admin access to generate ground truth scripts.
    
    Args:
        request: Ground truth generation parameters
        current_user: Authenticated Cognito user
        admin_access: Admin access verification
        
    Returns:
        GroundTruthResponse with generated script
        
    Raises:
        HTTPException: If generation fails or user lacks permissions
    """
    try:
        settings = get_settings()
        storage_config = settings.get_storage_config()
        storage = create_storage_backend(**storage_config)
        
        generator = EnhancedGroundTruthGenerator(storage_backend=storage)
        generation_id = str(uuid.uuid4())
        
        logger.info(f"Starting ground truth generation for user {current_user.email}: {request.medical_vertical}")
        
        # Generate script
        script = generator.generate_script(
            medical_vertical=request.medical_vertical,
            language=request.language,
            target_word_count=request.target_word_count,
            challenge_level=request.challenge_level,
            seed_term_density=request.seed_term_density,
            include_product_names=request.include_product_names,
            selected_terms=request.selected_terms,
            selected_brands=request.selected_brands
        )
        
        # Save script to storage
        script_url, metadata_url = generator.save_script(script)
        
        logger.info(f"Ground truth generation completed by {current_user.email}: {generation_id}")
        
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
                "generated_by": current_user.email,
                "generated_at": datetime.now().isoformat(),
                "seed_terms_used": script.seed_terms_used,
                "brand_names_used": script.brand_names_used,
                "difficulty_score": script.difficulty_score,
                "transcription_challenge_score": script.transcription_challenge_score,
                "voice_actor_challenge_score": script.voice_actor_challenge_score
            },
            message=f"Successfully generated {request.medical_vertical} script ({script.word_count} words)"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating ground truth script for user {current_user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}"
        )