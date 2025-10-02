"""Enhanced ground truth generation with seed terminology and Bedrock integration.

This module provides comprehensive ground truth generation capabilities for
medical transcription evaluation, with support for specialized medical terminology,
AWS Bedrock integration, and configurable storage backends.

The module handles multiple medical verticals (aesthetic medicine, dermatology,
plastic surgery) and includes advanced features for terminology seed logic,
error simulation, and quality assessment.

Example:
    Basic usage for generating medical consultation scripts:

    >>> from transcription_evaluator.core.generation import EnhancedGroundTruthGenerator
    >>> generator = EnhancedGroundTruthGenerator()
    >>> script = generator.generate_script(
    ...     medical_vertical="aesthetic_medicine",
    ...     target_word_count=600,
    ...     selected_terms=["botox", "juvederm"],
    ...     selected_brands=["BOTOX", "JUVEDERM"]
    ... )
    >>> print(script.content)
"""

import json
import logging
import os
import random
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from ..config.parameter_store import get_backend_config
from ..config.settings import get_settings
from .storage import StorageBackend, create_storage_backend

logger = logging.getLogger(__name__)

BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
BEDROCK_REGION = "us-east-1"


@dataclass
class SeedTerminology:
    """Data class for organizing seed terminology by medical vertical."""
    
    vertical: str
    difficulty_terms: List[str]
    brand_names: List[str]
    technical_terms: List[str]
    common_errors: List[str]
    phonetic_challenges: List[str]
    numerical_terms: List[str]


@dataclass
class GenerationParameters:
    """Configuration parameters for ground truth generation."""
    
    medical_vertical: str
    target_word_count: int
    seed_terminology: Optional[SeedTerminology]
    terminology_focus: List[str]
    challenge_level: str
    language: str
    seed_term_density: float
    error_simulation: bool
    phonetic_focus: bool
    brand_name_density: float


@dataclass
class GeneratedScript:
    """Container for generated ground truth script and metadata."""
    
    script_id: str
    content: str
    word_count: int
    medical_vertical: str
    language: str
    generation_parameters: GenerationParameters
    seed_terms_used: List[str]
    brand_names_used: List[str]
    technical_terms_used: List[str]
    error_patterns_targeted: List[str]
    difficulty_score: float
    transcription_challenge_score: float
    voice_actor_challenge_score: float
    metadata: Dict[str, Any]
    storage_path: str


class SeedTerminologyManager:
    """Manages seed terminology sourced exclusively from DynamoDB."""

    def __init__(self, aws_profile: Optional[str] = None):
        """Initialize with optional AWS profile and DynamoDB client."""
        self.aws_profile = aws_profile

        # Initialize DynamoDB client
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.dynamodb_client = session.client(
                "dynamodb", region_name=BEDROCK_REGION
            )
        else:
            self.dynamodb_client = boto3.client("dynamodb", region_name=BEDROCK_REGION)

        # Get table names from environment
        self.medical_brands_table = os.getenv("MEDICAL_BRANDS_TABLE_NAME")
        self.medical_terms_table = os.getenv("MEDICAL_TERMS_TABLE_NAME")

        # Cache for DynamoDB data
        self._db_cache = {}

    def load_brands_from_dynamodb(self, vertical: str) -> List[str]:
        """Load brand names from DynamoDB for a specific medical vertical."""
        cache_key = f"brands_{vertical}"
        if cache_key in self._db_cache:
            return self._db_cache[cache_key]

        if not self.medical_brands_table:
            logger.warning("MEDICAL_BRANDS_TABLE_NAME not set")
            return []

        try:
            response = self.dynamodb_client.scan(
                TableName=self.medical_brands_table,
                FilterExpression="vertical = :vertical",
                ExpressionAttributeValues={":vertical": {"S": vertical}},
            )

            brands = []
            for item in response.get("Items", []):
                name = item.get("name", {}).get("S", "")
                if name:
                    brands.append(name)

            self._db_cache[cache_key] = brands
            logger.info(f"Loaded {len(brands)} brands for {vertical} from DynamoDB")
            return brands

        except Exception as e:
            logger.error(f"Failed to load brands from DynamoDB: {e}")
            return []

    def load_terms_from_dynamodb(self, vertical: str) -> List[str]:
        """Load medical terms from DynamoDB for a specific medical vertical."""
        cache_key = f"terms_{vertical}"
        if cache_key in self._db_cache:
            return self._db_cache[cache_key]

        if not self.medical_terms_table:
            logger.warning("MEDICAL_TERMS_TABLE_NAME not set")
            return []

        try:
            response = self.dynamodb_client.scan(
                TableName=self.medical_terms_table,
                FilterExpression="vertical = :vertical",
                ExpressionAttributeValues={":vertical": {"S": vertical}},
            )

            terms = []
            for item in response.get("Items", []):
                name = item.get("name", {}).get("S", "")
                if name:
                    terms.append(name)

            self._db_cache[cache_key] = terms
            logger.info(f"Loaded {len(terms)} terms for {vertical} from DynamoDB")
            return terms

        except Exception as e:
            logger.error(f"Failed to load terms from DynamoDB: {e}")
            return []

    def get_available_verticals(self) -> List[str]:
        """Get list of available medical verticals from DynamoDB."""
        # For now, return the known verticals since they're stored per-item
        return ["aesthetic_medicine", "dermatology", "plastic_surgery", "venous_care"]


class EnhancedGroundTruthGenerator:
    """Enhanced ground truth generator using DynamoDB data exclusively."""

    def __init__(self, storage_backend: Optional[StorageBackend] = None, aws_profile: Optional[str] = None):
        """Initialize the generator with storage backend."""
        self.storage_backend = storage_backend or create_storage_backend()
        self.seed_manager = SeedTerminologyManager(aws_profile=aws_profile)
        
        # Initialize Bedrock client
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.bedrock_client = session.client("bedrock-runtime", region_name=BEDROCK_REGION)
        else:
            self.bedrock_client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

    def _generate_with_bedrock(self, prompt: str) -> str:
        """Generate content using AWS Bedrock Claude."""
        try:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })

            response = self.bedrock_client.invoke_model(
                body=body,
                modelId=BEDROCK_MODEL_ID,
                accept="application/json",
                contentType="application/json"
            )

            response_body = json.loads(response.get("body").read())
            content = response_body.get("content", [{}])[0].get("text", "")
            
            return content.strip()

        except Exception as e:
            logger.error(f"Failed to generate content with Bedrock: {e}")
            raise

    def generate_script(
        self,
        medical_vertical: str = "aesthetic_medicine",
        language: str = "english",
        target_word_count: int = 600,
        challenge_level: str = "both",
        seed_term_density: float = 0.15,
        include_product_names: bool = True,
        selected_terms: Optional[List[str]] = None,
        selected_brands: Optional[List[str]] = None,
    ) -> GeneratedScript:
        """Generate enhanced ground truth script using only user-selected terms from DynamoDB."""

        # Load available data from DynamoDB
        available_brands = self.seed_manager.load_brands_from_dynamodb(medical_vertical)
        available_terms = self.seed_manager.load_terms_from_dynamodb(medical_vertical)

        # Use user selections if provided, otherwise generate empty script
        if selected_terms:
            final_terms = selected_terms
            logger.info(f"Using user-selected terms: {len(final_terms)} terms")
        else:
            # No terms selected - generate basic script without terminology
            final_terms = []
            logger.info("No terms selected by user - generating basic script")

        if selected_brands and include_product_names:
            final_brands = selected_brands
            logger.info(f"Using user-selected brands: {len(final_brands)} brands")
        else:
            # No brands selected or product names disabled
            final_brands = []
            logger.info("No brands selected by user or product names disabled")

        # Build terminology for prompt
        all_terminology = final_terms + final_brands
        terminology_text = (
            ", ".join(all_terminology)
            if all_terminology
            else "standard medical terminology"
        )

        # Generate conversation context
        import random
        doctor_names = [
            "Dr. Chen", "Dr. Rodriguez", "Dr. Johnson", "Dr. Patel", "Dr. Williams", 
            "Dr. Kim", "Dr. Thompson", "Dr. Anderson", "Dr. Lee", "Dr. Garcia"
        ]
        patient_characteristics = [
            "first-time patient who is nervous about the procedure",
            "returning patient who had previous treatments",
            "well-informed patient who has researched extensively", 
            "patient with specific concerns about side effects"
        ]
        conversation_styles = [
            "thorough and educational approach",
            "conversational and reassuring style", 
            "direct and efficient discussion",
            "collaborative decision-making approach"
        ]
        
        selected_doctor = random.choice(doctor_names)
        selected_patient_type = random.choice(patient_characteristics)
        selected_style = random.choice(conversation_styles)

        # Create prompt
        prompt = f"""You are an expert medical writer creating realistic {medical_vertical} consultation scripts for training purposes.

Generate a natural consultation dialogue between a Doctor and Patient for {medical_vertical}. 

REQUIREMENTS:
- Target word count: {target_word_count} words
- Include these specific terms naturally: {terminology_text}
- Focus on {medical_vertical} procedures and treatments
- Create realistic patient concerns and doctor explanations
- Use proper medical terminology
- Make dialogue sound natural and conversational
- Doctor: {selected_doctor}
- Patient scenario: {selected_patient_type}
- Conversation style: {selected_style}

FORMAT:
- Start each line with "Doctor: " or "Patient: "
- No asterisks or extra punctuation after speaker labels
- Natural conversation flow
- Include treatment recommendations and explanations

Create an engaging, educational consultation that would be challenging for both voice actors and transcription systems."""

        # Generate content
        content = self._generate_with_bedrock(prompt)

        # Calculate metrics
        word_count = len(content.split())

        # Calculate difficulty scores based on selected terminology
        difficulty_score = min(len(final_terms) / 20.0, 1.0)
        transcription_challenge = min(
            len([t for t in final_terms if len(t.split()) > 1]) / 10.0, 1.0
        )
        voice_actor_challenge = min(
            len([t for t in final_terms if any(c in t for c in "'-")]) / 10.0,
            1.0,
        )

        # Generate script ID
        script_id = f"{medical_vertical}_initial_{target_word_count}w_{random.randint(1000, 9999)}"

        # Create generation parameters
        parameters = GenerationParameters(
            medical_vertical=medical_vertical,
            target_word_count=target_word_count,
            seed_terminology=None,  # No longer using hardcoded data
            terminology_focus=["selected_terms", "selected_brands"],
            challenge_level=challenge_level,
            language=language,
            seed_term_density=seed_term_density,
            error_simulation=True,
            phonetic_focus=True,
            brand_name_density=0.1,
        )

        # Create metadata
        metadata = {
            "generation_timestamp": datetime.now().isoformat(),
            "model_id": BEDROCK_MODEL_ID,
            "user_selected_terms_count": len(final_terms),
            "user_selected_brands_count": len(final_brands),
            "available_terms_count": len(available_terms),
            "available_brands_count": len(available_brands),
            "terminology_source": "dynamodb_user_selections"
        }

        # Store the script
        storage_path = self.storage_backend.save_script(script_id, content, metadata)

        return GeneratedScript(
            script_id=script_id,
            content=content,
            word_count=word_count,
            medical_vertical=medical_vertical,
            language=language,
            generation_parameters=parameters,
            seed_terms_used=final_terms,
            brand_names_used=final_brands,
            technical_terms_used=[],  # Not categorizing anymore
            error_patterns_targeted=[],  # Not simulating errors anymore
            difficulty_score=difficulty_score,
            transcription_challenge_score=transcription_challenge,
            voice_actor_challenge_score=voice_actor_challenge,
            metadata=metadata,
            storage_path=storage_path,
        )