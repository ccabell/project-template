"""Factory for creating consultation analysis pipelines using Dagster.

This module provides a factory function that creates complete Dagster
pipelines for clinical consultation processing, including assets, sensors,
and jobs following the medallion architecture pattern.

The factory creates pipelines that process consultation transcripts through
bronze (raw), silver (PHI-redacted), and gold (enriched) layers with
comprehensive PII/PHI detection and Bedrock embeddings.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import dagster as dg

# Handle optional dagster_aws dependency
try:
    from dagster_aws.s3 import S3Resource
except ImportError:
    # Import our fallback S3Resource
    from ..aws.resources import S3Resource

from ..aws.resources import BedrockResource, ComprehendMedicalResource, MacieResource
from ..aws.utils import parse_bedrock_json_response


def preprocess_conversation_for_analytics(
    conversation_text: str,
    bedrock: BedrockResource,
    max_length: int = 15000,
    context: dg.AssetExecutionContext = None,
) -> tuple[str, dict, bool]:
    """Preprocess conversation text for analytics, handling long conversations.

    Args:
        conversation_text: The full conversation text to process.
        bedrock: Bedrock resource for LLM operations.
        max_length: Maximum allowed length for analysis (default: 15000).
        context: Dagster context for logging (optional).

    Returns:
        Tuple of (processed_text, metadata, was_chunked).
        - processed_text: Text ready for analysis (either summarized or chunked)
        - metadata: Information about the preprocessing
        - was_chunked: True if chunking was used, False if summarization
    """
    if len(conversation_text) <= max_length:
        return conversation_text, {"method": "direct", "original_length": len(conversation_text)}, False

    # Try summarization first for very long conversations
    if len(conversation_text) > max_length * 3:  # If >3x limit, summarize
        try:
            if context:
                context.log.info("Conversation too long (%d chars), attempting summarization", len(conversation_text))

            summary_prompt = f"""You are a medical consultation summarizer. Create a comprehensive summary of this clinical consultation transcript that captures all key clinical information while staying under {max_length} characters.

Focus on:
1. Main clinical topics and findings
2. Patient concerns and symptoms
3. Provider recommendations and treatments
4. Clinical decisions made
5. Follow-up requirements

Transcript:
{conversation_text}

Provide a concise but complete summary that maintains clinical accuracy and completeness."""

            summary_response_text = bedrock.invoke_text_model(
                prompt=summary_prompt,
                max_tokens=2000,
                model_id=bedrock.resolve_model_id(bedrock.model_id)
            )

            summary_text = summary_response_text

            if len(summary_text) <= max_length:
                if context:
                    context.log.info("Successfully summarized to %d characters", len(summary_text))
                return (
                    summary_text,
                    {
                        "method": "summarization",
                        "original_length": len(conversation_text),
                        "summary_length": len(summary_text),
                        "compression_ratio": len(summary_text) / len(conversation_text),
                    },
                    False,
                )
            else:
                if context:
                    context.log.warning(
                        "Summarization still too long (%d chars), falling back to chunking", len(summary_text)
                    )
        except Exception as e:
            if context:
                context.log.warning("Summarization failed: %s, falling back to chunking", e)

    # Fall back to chunking if summarization fails or is still too long
    if context:
        context.log.info("Using chunking approach for %d character conversation", len(conversation_text))

    chunk_size = max_length - 1000  # Leave buffer for chunk metadata
    chunks = []

    for i in range(0, len(conversation_text), chunk_size):
        chunk = conversation_text[i : i + chunk_size]
        chunks.append(chunk)

    if context:
        context.log.info("Split conversation into %d chunks", len(chunks))

    return (
        conversation_text,
        {
            "method": "chunking",
            "original_length": len(conversation_text),
            "chunk_count": len(chunks),
            "chunk_size": chunk_size,
        },
        True,
    )


def analyze_conversation_chunks(
    conversation_text: str,
    chunk_size: int,
    bedrock: BedrockResource,
    context: dg.AssetExecutionContext,
) -> dict:
    """Analyze conversation in chunks and aggregate results.

    Args:
        conversation_text: The full conversation text.
        chunk_size: Size of each chunk.
        bedrock: Bedrock resource for LLM operations.
        context: Dagster context for logging.

    Returns:
        Aggregated analysis results.
    """
    chunks = []
    for i in range(0, len(conversation_text), chunk_size):
        chunk = conversation_text[i : i + chunk_size]
        chunks.append(chunk)

    all_analyses = []

    for i, chunk in enumerate(chunks):
        if context:
            context.log.info("Analyzing chunk %d/%d", i + 1, len(chunks))

        chunk_prompt = f"""Analyze this portion of a clinical consultation transcript and provide structured insights.

Transcript Chunk {i + 1} of {len(chunks)}:
{chunk}

Provide analysis in JSON format with:
1. consultation_type (initial, follow-up, procedure, etc.)
2. topics_discussed (list of main topics)
3. treatments_mentioned (list of treatments discussed)
4. patient_concerns (list of patient concerns/questions)
5. clinical_recommendations (list of provider recommendations)
6. sentiment_analysis (overall patient satisfaction indicators)
7. consultation_quality_score (1-10 based on thoroughness)
8. duration_appropriateness (appropriate, too_short, too_long)

Focus on clinical workflow and patient experience insights. This is chunk {i + 1} of {len(chunks)}."""

        try:
            chunk_text = bedrock.invoke_text_model(
                prompt=chunk_prompt,
                max_tokens=2000,
                model_id=bedrock.resolve_model_id(bedrock.model_id)
            )
            chunk_analysis = parse_bedrock_json_response(chunk_text)
            all_analyses.append(chunk_analysis)

        except Exception as e:
            if context:
                context.log.warning("Failed to analyze chunk %d: %s", i + 1, e)
            all_analyses.append(
                {
                    "error": str(e),
                    "chunk_index": i,
                    "analysis_failed": True,
                }
            )

    # Aggregate results from all chunks
    return aggregate_chunk_analyses(all_analyses, context)


def aggregate_chunk_analyses(chunk_analyses: list[dict], context: dg.AssetExecutionContext) -> dict:
    """Aggregate analysis results from multiple chunks.

    Args:
        chunk_analyses: List of analysis results from each chunk.
        context: Dagster context for logging.

    Returns:
        Aggregated analysis result.
    """
    if not chunk_analyses:
        return {"error": "No chunk analyses to aggregate", "analysis_failed": True}

    # Initialize aggregated result
    aggregated = {
        "consultation_type": "unknown",
        "topics_discussed": set(),
        "treatments_mentioned": set(),
        "patient_concerns": set(),
        "clinical_recommendations": set(),
        "sentiment_analysis": [],
        "consultation_quality_score": 0,
        "duration_appropriateness": "unknown",
        "chunk_count": len(chunk_analyses),
        "aggregation_method": "chunked_analysis",
    }

    valid_chunks = 0
    total_quality_score = 0

    for i, chunk_analysis in enumerate(chunk_analyses):
        if chunk_analysis.get("analysis_failed"):
            if context:
                context.log.warning("Chunk %d analysis failed, skipping from aggregation", i + 1)
            continue

        valid_chunks += 1

        # Aggregate topics and findings (deduplicate)
        if chunk_analysis.get("topics_discussed"):
            aggregated["topics_discussed"].update(chunk_analysis["topics_discussed"])

        if chunk_analysis.get("treatments_mentioned"):
            aggregated["treatments_mentioned"].update(chunk_analysis["treatments_mentioned"])

        if chunk_analysis.get("patient_concerns"):
            aggregated["patient_concerns"].update(chunk_analysis["patient_concerns"])

        if chunk_analysis.get("clinical_recommendations"):
            aggregated["clinical_recommendations"].update(chunk_analysis["clinical_recommendations"])

        # Collect sentiment analysis
        if chunk_analysis.get("sentiment_analysis"):
            aggregated["sentiment_analysis"].append({"chunk": i + 1, "sentiment": chunk_analysis["sentiment_analysis"]})

        # Aggregate quality score (average)
        if chunk_analysis.get("consultation_quality_score"):
            total_quality_score += chunk_analysis["consultation_quality_score"]

        # Use first valid consultation type and duration appropriateness
        if aggregated["consultation_type"] == "unknown" and chunk_analysis.get("consultation_type"):
            aggregated["consultation_type"] = chunk_analysis["consultation_type"]

        if aggregated["duration_appropriateness"] == "unknown" and chunk_analysis.get("duration_appropriateness"):
            aggregated["duration_appropriateness"] = chunk_analysis["duration_appropriateness"]

    # Convert sets back to lists and calculate averages
    aggregated["topics_discussed"] = list(aggregated["topics_discussed"])
    aggregated["treatments_mentioned"] = list(aggregated["treatments_mentioned"])
    aggregated["patient_concerns"] = list(aggregated["patient_concerns"])
    aggregated["clinical_recommendations"] = list(aggregated["clinical_recommendations"])

    if valid_chunks > 0:
        aggregated["consultation_quality_score"] = round(total_quality_score / valid_chunks, 1)

    if context:
        context.log.info("Aggregated %d valid chunks into final analysis", valid_chunks)

    return aggregated


@dataclass
class ConsultationDefinition:
    """Configuration for a consultation processing pipeline."""

    tenant_id: str
    tenant_name: str
    environment: str = "prod"
    max_backfill_size: int = 10


def consultation_pipeline_factory(
    consultation_def: ConsultationDefinition,
) -> dg.Definitions:
    """Create Dagster pipeline for consultation processing.

    Args:
        consultation_def: Consultation pipeline configuration.

    Returns:
        Definitions object with assets, sensors, and jobs.
    """
    partition_def = dg.DynamicPartitionsDefinition(name=f"{consultation_def.tenant_name}_consultations")

    class ConsultationConfig(dg.Config):
        """Configuration for consultation processing."""

        consultation_id: str
        tenant_id: str
        consultation_date: str
        started_at: str
        finished_at: str

    @dg.asset(
        name=f"{consultation_def.tenant_name}_pii_redacted_documents",
        partitions_def=partition_def,
        compute_kind="macie",
        group_name="consultation_pipeline",
    )
    def pii_redacted_documents_asset(
        context: dg.AssetExecutionContext,
        config: ConsultationConfig,
        s3: S3Resource,
        macie: MacieResource,
    ) -> dg.MaterializeResult:
        """Process documents in landing zone with Macie PII detection.

        Args:
            context: Dagster execution context.
            config: Consultation configuration.
            s3: S3 resource for storage.
            macie: Macie resource for PII detection.

        Returns:
            Materialization result with PII redaction metadata.
        """

        client = s3.get_client()
        macie_client = macie.get_client()

        # Use environment variables for bucket names to match actual infrastructure
        import os

        landing_bucket = os.getenv(
            "CONSULTATION_LANDING_BUCKET", f"a360-{consultation_def.environment}-consultation-landing"
        )
        silver_bucket = os.getenv(
            "CONSULTATION_SILVER_BUCKET", f"a360-{consultation_def.environment}-consultation-silver"
        )

        landing_key = f"documents/{consultation_def.tenant_id}/{config.consultation_id}/intake_forms.pdf"
        redacted_key = f"documents/{consultation_def.tenant_id}/{config.consultation_id}/intake_forms_redacted.pdf"

        context.log.info("Processing PII redaction for consultation %s", config.consultation_id)

        # Check if document exists in landing zone
        try:
            client.head_object(Bucket=landing_bucket, Key=landing_key)
        except Exception as e:
            if "404" in str(e) or "Not Found" in str(e) or "NoSuchKey" in str(e):
                context.log.info("No intake documents found, skipping PII redaction")
                return dg.MaterializeResult(
                    metadata={
                        "status": "skipped",
                        "reason": "no_documents",
                        "consultation_id": config.consultation_id,
                    }
                )
            else:
                # Re-raise other exceptions
                raise

        # Create Macie classification job
        job_response = macie_client.create_classification_job(
            jobType="ONE_TIME",
            name=f"Consultation-PII-Detection-{config.consultation_id}-{datetime.now(UTC).isoformat()}",
            managedDataIdentifierSelector="RECOMMENDED",
            s3JobDefinition={
                "bucketDefinitions": [
                    {
                        "accountId": macie._get_account_id(),
                        "buckets": [landing_bucket],
                    }
                ],
                "scoping": {
                    "includes": {
                        "and": [
                            {
                                "simpleScopeTerm": {
                                    "comparator": "STARTS_WITH",
                                    "key": "OBJECT_KEY",
                                    "values": [landing_key],
                                }
                            }
                        ]
                    }
                },
            },
        )

        job_id = job_response["jobId"]
        context.log.info("Started Macie job: %s", job_id)

        # Store job metadata in DynamoDB (would be implemented in actual Lambda)
        # TODO: Implement actual DynamoDB storage
        context.log.info(
            "Redaction metadata: consultation_id=%s, tenant_id=%s, macie_job_id=%s, landing_key=%s, redacted_key=%s, processed_at=%s",
            config.consultation_id,
            config.tenant_id,
            job_id,
            landing_key,
            redacted_key,
            datetime.now(UTC).isoformat(),
        )

        # Copy redacted document to silver layer (placeholder - actual redaction in Lambda)
        client.copy_object(
            CopySource={"Bucket": landing_bucket, "Key": landing_key},
            Bucket=silver_bucket,
            Key=redacted_key,
        )

        return dg.MaterializeResult(
            metadata={
                "macie_job_id": job_id,
                "redacted_key": redacted_key,
                "consultation_id": config.consultation_id,
                "tenant_id": config.tenant_id,
            }
        )

    @dg.asset(
        name=f"{consultation_def.tenant_name}_bronze_transcripts",
        partitions_def=partition_def,
        compute_kind="s3",
        group_name="consultation_pipeline",
    )
    def bronze_transcripts_asset(
        context: dg.AssetExecutionContext,
        config: ConsultationConfig,
        s3: S3Resource,
    ) -> dg.MaterializeResult:
        """Ingest and validate consultation transcripts from landing to bronze layer.

        Args:
            context: Dagster execution context.
            config: Consultation configuration.
            s3: S3 resource for storage.

        Returns:
            Materialization result with ingestion metadata.
        """
        import os
        import json

        client = s3.get_client()

        # Get bucket names
        landing_bucket = os.getenv(
            "CONSULTATION_LANDING_BUCKET", f"a360-{consultation_def.environment}-consultation-landing"
        )
        bronze_bucket = os.getenv(
            "CONSULTATION_BRONZE_BUCKET", f"a360-{consultation_def.environment}-consultation-bronze"
        )

        # Define keys
        landing_key = f"{config.consultation_id}/final_transcript.json"
        bronze_key = f"{config.consultation_id}/final_transcript.json"

        context.log.info("Ingesting transcript from landing to bronze for consultation %s", config.consultation_id)

        try:
            # Read from landing bucket
            response = client.get_object(Bucket=landing_bucket, Key=landing_key)
            transcript_data = json.loads(response["Body"].read())

            # Validate data structure (basic validation)
            if not transcript_data.get("transcript"):
                raise ValueError("Invalid transcript format: missing 'transcript' field")

            # Add ingestion metadata
            transcript_data["ingestion_metadata"] = {
                "ingested_at": context.run.tags.get("dagster/partition_key", "unknown"),
                "source_bucket": landing_bucket,
                "source_key": landing_key,
                "tenant_id": config.tenant_id,
                "consultation_id": config.consultation_id
            }

            # Write to bronze bucket with validation
            client.put_object(
                Bucket=bronze_bucket,
                Key=bronze_key,
                Body=json.dumps(transcript_data, indent=2),
                ContentType="application/json",
                Metadata={
                    "tenant_id": config.tenant_id,
                    "consultation_id": config.consultation_id,
                    "processing_stage": "bronze"
                }
            )

            context.log.info("Successfully ingested transcript to bronze layer")

            return dg.MaterializeResult(
                metadata={
                    "source_bucket": landing_bucket,
                    "destination_bucket": bronze_bucket,
                    "file_size_bytes": len(json.dumps(transcript_data)),
                    "consultation_id": config.consultation_id,
                    "tenant_id": config.tenant_id,
                }
            )

        except Exception as e:
            context.log.error(f"Failed to ingest transcript from landing to bronze: {e}")
            raise

    @dg.asset(
        name=f"{consultation_def.tenant_name}_phi_redacted_transcripts",
        partitions_def=partition_def,
        deps=[bronze_transcripts_asset],
        compute_kind="comprehend_medical",
        group_name="consultation_pipeline",
    )
    def phi_redacted_transcripts_asset(
        context: dg.AssetExecutionContext,
        config: ConsultationConfig,
        s3: S3Resource,
        comprehend_medical: ComprehendMedicalResource,
    ) -> dg.MaterializeResult:
        """Process consultation transcripts with Comprehend Medical PHI detection.

        Args:
            context: Dagster execution context.
            config: Consultation configuration.
            s3: S3 resource for storage.
            comprehend_medical: Comprehend Medical resource.

        Returns:
            Materialization result with PHI redaction metadata.
        """

        client = s3.get_client()

        # Use environment variables for bucket names to match actual infrastructure
        import os

        bronze_bucket = os.getenv(
            "CONSULTATION_BRONZE_BUCKET", f"a360-{consultation_def.environment}-consultation-bronze"
        )
        silver_bucket = os.getenv(
            "CONSULTATION_SILVER_BUCKET", f"a360-{consultation_def.environment}-consultation-silver"
        )

        transcript_key = f"{config.consultation_id}/final_transcript.json"
        redacted_key = f"transcripts/{consultation_def.tenant_id}/{config.consultation_id}/phi_redacted_transcript.json"

        context.log.info("Processing PHI redaction for consultation %s", config.consultation_id)

        # Get original transcript
        try:
            response = client.get_object(Bucket=bronze_bucket, Key=transcript_key)
            transcript_data = json.loads(response["Body"].read())
        except Exception as e:
            context.log.error("Failed to retrieve transcript: %s", e)
            return dg.MaterializeResult(
                metadata={
                    "status": "error",
                    "reason": "transcript_not_found",
                    "consultation_id": config.consultation_id,
                }
            )

        # Extract conversation text
        conversation_text = ""
        if transcript_data.get("conversation"):
            conversation_parts = []
            for turn in transcript_data["conversation"]:
                speaker = turn.get("speaker", "Unknown")
                text = turn.get("text", "")
                conversation_parts.append(f"{speaker}: {text}")
            conversation_text = "\n".join(conversation_parts)

        if not conversation_text:
            context.log.warning("No conversation text found")
            return dg.MaterializeResult(
                metadata={
                    "status": "skipped",
                    "reason": "no_conversation_text",
                    "consultation_id": config.consultation_id,
                }
            )

        # Detect comprehensive PHI/PII using enhanced Comprehend Medical + custom patterns
        # Process text in chunks to handle API limits
        chunk_size = 20000
        all_phi_pii_entities = []

        for i in range(0, len(conversation_text), chunk_size):
            chunk = conversation_text[i : i + chunk_size]
            
            # Use comprehensive detection method
            comprehensive_response = comprehend_medical.detect_comprehensive_pii_phi(chunk)

            # Adjust offsets for entities based on chunk position
            for entity in comprehensive_response.get("Entities", []):
                entity["BeginOffset"] += i
                entity["EndOffset"] += i
                all_phi_pii_entities.append(entity)

        # Extract PHI/PII entities with high confidence (already filtered by comprehensive method)
        phi_entities = all_phi_pii_entities

        # Redact PHI (simple masking - production would use more sophisticated redaction)
        redacted_text = conversation_text
        for entity in sorted(phi_entities, key=lambda x: x["BeginOffset"], reverse=True):
            start = entity["BeginOffset"]
            end = entity["EndOffset"]
            entity_type = entity["Type"]
            redacted_text = redacted_text[:start] + f"[REDACTED_{entity_type}]" + redacted_text[end:]

        # Create redacted transcript
        redacted_transcript = transcript_data.copy()
        if redacted_transcript.get("conversation"):
            # Update conversation with redacted text
            redacted_lines = redacted_text.split("\n")
            for i, turn in enumerate(redacted_transcript["conversation"]):
                if i < len(redacted_lines):
                    parts = redacted_lines[i].split(": ", 1)
                    if len(parts) == 2:
                        turn["text"] = parts[1]

        # Add comprehensive PHI/PII metadata
        detection_methods = set()
        entity_sources = {}
        for entity in phi_entities:
            source = entity.get("Source", "unknown")
            detection_methods.add(source)
            entity_type = entity["Type"]
            if entity_type not in entity_sources:
                entity_sources[entity_type] = []
            entity_sources[entity_type].append(source)
        
        redacted_transcript["phi_pii_redaction"] = {
            "processed_at": datetime.now(UTC).isoformat(),
            "entities_found": len(phi_entities),
            "entity_types": list({e["Type"] for e in phi_entities}),
            "detection_methods": list(detection_methods),
            "entity_sources": entity_sources,
            "confidence_threshold": 0.7,
            "comprehensive_detection": True,
        }

        # Store redacted transcript in silver layer
        client.put_object(
            Bucket=silver_bucket,
            Key=redacted_key,
            Body=json.dumps(redacted_transcript, indent=2),
            ContentType="application/json",
        )

        return dg.MaterializeResult(
            metadata={
                "redacted_key": redacted_key,
                "phi_pii_entities_found": len(phi_entities),
                "entity_types": list({e["Type"] for e in phi_entities}),
                "detection_methods": list(detection_methods),
                "comprehensive_detection": True,
                "consultation_id": config.consultation_id,
                "tenant_id": config.tenant_id,
            }
        )

    @dg.asset(
        name=f"{consultation_def.tenant_name}_embeddings",
        partitions_def=partition_def,
        deps=[phi_redacted_transcripts_asset],
        compute_kind="bedrock",
        group_name="consultation_pipeline",
    )
    def embeddings_asset(
        context: dg.AssetExecutionContext,
        config: ConsultationConfig,
        s3: S3Resource,
        bedrock: BedrockResource,
    ) -> dg.MaterializeResult:
        """Generate embeddings using Cohere Embed English v3.

        Args:
            context: Dagster execution context.
            config: Consultation configuration.
            s3: S3 resource for storage.
            bedrock: Bedrock resource for embeddings.

        Returns:
            Materialization result with embedding metadata.
        """

        client = s3.get_client()

        # Use environment variables for bucket names to match actual infrastructure
        import os

        silver_bucket = os.getenv(
            "CONSULTATION_SILVER_BUCKET", f"a360-{consultation_def.environment}-consultation-silver"
        )
        gold_bucket = os.getenv("CONSULTATION_GOLD_BUCKET", f"a360-{consultation_def.environment}-consultation-gold")

        redacted_key = f"transcripts/{consultation_def.tenant_id}/{config.consultation_id}/phi_redacted_transcript.json"
        embeddings_key = (
            f"embeddings/{consultation_def.tenant_id}/{config.consultation_id}/conversation_embeddings.json"
        )

        context.log.info("Generating embeddings for consultation %s", config.consultation_id)

        # Get redacted transcript
        try:
            response = client.get_object(Bucket=silver_bucket, Key=redacted_key)
            transcript_data = json.loads(response["Body"].read())
        except Exception as e:
            context.log.error("Failed to retrieve redacted transcript: %s", e)
            return dg.MaterializeResult(
                metadata={
                    "status": "error",
                    "reason": "redacted_transcript_not_found",
                    "consultation_id": config.consultation_id,
                }
            )

        # Extract conversation turns for embedding
        conversation_turns = []
        if transcript_data.get("conversation"):
            for turn in transcript_data["conversation"]:
                text = turn.get("text", "").strip()
                if text and len(text) > 10:  # Skip very short texts
                    conversation_turns.append(
                        {
                            "speaker": turn.get("speaker", "Unknown"),
                            "text": text,
                            "start_time": turn.get("start_time"),
                            "end_time": turn.get("end_time"),
                        }
                    )

        if not conversation_turns:
            context.log.warning("No conversation turns found for embedding")
            return dg.MaterializeResult(
                metadata={
                    "status": "skipped",
                    "reason": "no_conversation_turns",
                    "consultation_id": config.consultation_id,
                }
            )

        # Generate embeddings using Cohere Embed English v3
        embeddings_data = []
        batch_size = 10  # Process in batches

        for i in range(0, len(conversation_turns), batch_size):
            batch = conversation_turns[i : i + batch_size]
            texts = [turn["text"] for turn in batch]

            try:
                # Use the new embedding API
                embeddings = bedrock.invoke_embedding_model(texts, "cohere.embed-english-v3")

                for j, (turn, embedding) in enumerate(zip(batch, embeddings)):
                    embeddings_data.append(
                        {
                            "turn_index": i + j,
                            "speaker": turn["speaker"],
                            "text": turn["text"],
                            "start_time": turn["start_time"],
                            "end_time": turn["end_time"],
                            "embedding": embedding,
                            "embedding_model": "cohere.embed-english-v3",
                            "embedding_dimension": len(embedding),
                        }
                    )

            except Exception as e:
                context.log.error("Failed to generate embeddings for batch %d: %s", i, e)
                continue

        # Create embeddings document
        embeddings_document = {
            "consultation_id": config.consultation_id,
            "tenant_id": config.tenant_id,
            "processed_at": datetime.now(UTC).isoformat(),
            "embedding_model": "cohere.embed-english-v3",
            "total_turns": len(conversation_turns),
            "embedded_turns": len(embeddings_data),
            "embeddings": embeddings_data,
            "metadata": {
                "consultation_date": config.consultation_date,
                "started_at": config.started_at,
                "finished_at": config.finished_at,
            },
        }

        # Store embeddings in gold layer
        client.put_object(
            Bucket=gold_bucket,
            Key=embeddings_key,
            Body=json.dumps(embeddings_document, indent=2),
            ContentType="application/json",
        )

        return dg.MaterializeResult(
            metadata={
                "embeddings_key": embeddings_key,
                "total_turns": len(conversation_turns),
                "embedded_turns": len(embeddings_data),
                "embedding_model": "cohere.embed-english-v3",
                "consultation_id": config.consultation_id,
                "tenant_id": config.tenant_id,
            }
        )

    @dg.asset(
        name=f"{consultation_def.tenant_name}_enriched_analytics",
        partitions_def=partition_def,
        deps=[embeddings_asset],
        compute_kind="bedrock",
        group_name="consultation_pipeline",
    )
    def enriched_analytics_asset(
        context: dg.AssetExecutionContext,
        config: ConsultationConfig,
        s3: S3Resource,
        bedrock: BedrockResource,
    ) -> dg.MaterializeResult:
        """Generate enriched analytics and insights using Bedrock.

        Args:
            context: Dagster execution context.
            config: Consultation configuration.
            s3: S3 resource for storage.
            bedrock: Bedrock resource for analysis.

        Returns:
            Materialization result with analytics metadata.
        """

        client = s3.get_client()

        # Use environment variables for bucket names to match actual infrastructure
        import os

        silver_bucket = os.getenv(
            "CONSULTATION_SILVER_BUCKET", f"a360-{consultation_def.environment}-consultation-silver"
        )
        gold_bucket = os.getenv("CONSULTATION_GOLD_BUCKET", f"a360-{consultation_def.environment}-consultation-gold")

        redacted_key = f"transcripts/{consultation_def.tenant_id}/{config.consultation_id}/phi_redacted_transcript.json"
        analytics_key = f"analytics/{consultation_def.tenant_id}/{config.consultation_id}/enriched_insights.json"

        context.log.info("Generating enriched analytics for consultation %s", config.consultation_id)

        # Get redacted transcript
        try:
            response = client.get_object(Bucket=silver_bucket, Key=redacted_key)
            transcript_data = json.loads(response["Body"].read())
        except Exception as e:
            context.log.error("Failed to retrieve redacted transcript: %s", e)
            return dg.MaterializeResult(
                metadata={
                    "status": "error",
                    "reason": "redacted_transcript_not_found",
                    "consultation_id": config.consultation_id,
                }
            )

        # Extract conversation text for analysis
        conversation_text = ""
        if transcript_data.get("conversation"):
            conversation_parts = []
            for turn in transcript_data["conversation"]:
                speaker = turn.get("speaker", "Unknown")
                text = turn.get("text", "")
                conversation_parts.append(f"{speaker}: {text}")
            conversation_text = "\n".join(conversation_parts)

        if not conversation_text:
            context.log.warning("No conversation text for analysis")
            return dg.MaterializeResult(
                metadata={
                    "status": "skipped",
                    "reason": "no_conversation_text",
                    "consultation_id": config.consultation_id,
                }
            )

        # Preprocess conversation text for analysis (handle long conversations)
        processed_text, preprocessing_metadata, was_chunked = preprocess_conversation_for_analytics(
            conversation_text, bedrock, max_length=15000, context=context
        )

        # Generate insights using Claude Sonnet 4
        if was_chunked:
            # Use chunking approach for very long conversations
            context.log.info("Using chunked analysis approach")
            parsed_analysis = analyze_conversation_chunks(
                conversation_text, preprocessing_metadata["chunk_size"], bedrock, context
            )
        else:
            # Use standard analysis for summarized or short conversations
            analysis_prompt = f"""Analyze this clinical consultation transcript and provide structured insights.

Transcript:
{processed_text}

Provide analysis in JSON format with:
1. consultation_type (initial, follow-up, procedure, etc.)
2. topics_discussed (list of main topics)
3. treatments_mentioned (list of treatments discussed)
4. patient_concerns (list of patient concerns/questions)
5. clinical_recommendations (list of provider recommendations)
6. sentiment_analysis (overall patient satisfaction indicators)
7. consultation_quality_score (1-10 based on thoroughness)
8. duration_appropriateness (appropriate, too_short, too_long)

Focus on clinical workflow and patient experience insights."""

            try:
                analysis_text = bedrock.invoke_text_model(
                    prompt=analysis_prompt,
                    max_tokens=4000,
                    model_id=bedrock.resolve_model_id(bedrock.model_id)
                )
                parsed_analysis = parse_bedrock_json_response(analysis_text)

            except Exception as e:
                context.log.error("Failed to generate insights: %s", e)
                parsed_analysis = {
                    "error": str(e),
                    "consultation_type": "unknown",
                    "analysis_failed": True,
                }

        # Create enriched analytics document
        analytics_document = {
            "consultation_id": config.consultation_id,
            "tenant_id": config.tenant_id,
            "processed_at": datetime.now(UTC).isoformat(),
            "analysis_model": bedrock.resolve_model_id(bedrock.model_id),
            "insights": parsed_analysis,
            "metadata": {
                "consultation_date": config.consultation_date,
                "started_at": config.started_at,
                "finished_at": config.finished_at,
                "transcript_length": len(conversation_text),
                "phi_pii_redacted": transcript_data.get("phi_pii_redaction", {}).get("entities_found", 0) > 0,
                "preprocessing": preprocessing_metadata,
                "analysis_method": "chunked" if was_chunked else "standard",
            },
        }

        # Store analytics in gold layer
        client.put_object(
            Bucket=gold_bucket,
            Key=analytics_key,
            Body=json.dumps(analytics_document, indent=2),
            ContentType="application/json",
        )

        return dg.MaterializeResult(
            metadata={
                "analytics_key": analytics_key,
                "consultation_type": parsed_analysis.get("consultation_type", "unknown"),
                "topics_count": len(parsed_analysis.get("topics_discussed", [])),
                "treatments_count": len(parsed_analysis.get("treatments_mentioned", [])),
                "quality_score": parsed_analysis.get("consultation_quality_score", 0),
                "consultation_id": config.consultation_id,
                "tenant_id": config.tenant_id,
            }
        )

    # Define job for consultation processing
    job_name = f"{consultation_def.tenant_name}_consultation_processing_job"

    consultation_job = dg.define_asset_job(
        name=job_name,
        selection=dg.AssetSelection.assets(
            bronze_transcripts_asset,
            pii_redacted_documents_asset,
            phi_redacted_transcripts_asset,
            embeddings_asset,
            enriched_analytics_asset,
        ),
        partitions_def=partition_def,
    )

    @dg.sensor(
        name=f"{consultation_def.tenant_name}_consultation_sensor",
        minimum_interval_seconds=300,  # Check every 5 minutes
        default_status=dg.DefaultSensorStatus.RUNNING,
        job=consultation_job,
    )
    def consultation_sensor(context: dg.SensorEvaluationContext):
        """Monitor for new consultations to process.

        Args:
            context: Sensor evaluation context.

        Returns:
            Sensor result with run requests.
        """
        import boto3

        # Connect to S3 to check for new consultations in landing bucket
        s3_client = boto3.client("s3")
        landing_bucket = f"a360-{consultation_def.environment}-consultation-landing"

        try:
            # List recent objects (last hour)
            from datetime import UTC, datetime, timedelta

            cutoff_time = datetime.now(UTC) - timedelta(hours=1)

            response = s3_client.list_objects_v2(
                Bucket=landing_bucket,
                Prefix="",
                MaxKeys=100,
            )

            new_consultations = []
            for obj in response.get("Contents", []):
                for obj in response.get("Contents", []):
                    # Ensure both datetimes are timezone-aware for comparison
                    last_modified = obj["LastModified"]
                    if not last_modified.tzinfo:
                        last_modified = last_modified.replace(tzinfo=UTC)
                    if last_modified > cutoff_time:
                        key = obj["Key"]
                    if key.endswith("/final_transcript.json"):
                        consultation_id = key.split("/")[0]

                        # Check if this consultation is for our tenant
                        try:
                            metadata_key = f"{consultation_id}/metadata.json"
                            metadata_response = s3_client.get_object(Bucket=landing_bucket, Key=metadata_key)
                            metadata = json.loads(metadata_response["Body"].read())

                            tenant_id = metadata.get("metadataAttributes", {}).get("tenantId")
                            if tenant_id == consultation_def.tenant_id:
                                new_consultations.append(
                                    {
                                        "consultation_id": consultation_id,
                                        "tenant_id": tenant_id,
                                        "metadata": metadata.get("metadataAttributes", {}),
                                    }
                                )

                        except Exception as e:
                            context.log.warning("Failed to get metadata for %s: %s", consultation_id, e)
                            continue

            # Create run requests for new consultations
            run_requests = []
            for consultation in new_consultations:
                partition_key = consultation["consultation_id"]

                # Check if partition already exists
                if context.instance.get_dynamic_partitions(partition_def.name):
                    existing_partitions = context.instance.get_dynamic_partitions(partition_def.name)
                    if partition_key in existing_partitions:
                        continue

                # Add partition and create run request
                context.instance.add_dynamic_partitions(partition_def.name, [partition_key])

                run_config = {
                    "ops": {
                        "consultation_config": {
                            "config": {
                                "consultation_id": consultation["consultation_id"],
                                "tenant_id": consultation["tenant_id"],
                                "consultation_date": consultation["metadata"].get("consultationDate", ""),
                                "started_at": consultation["metadata"].get("startedAt", ""),
                                "finished_at": consultation["metadata"].get("finishedAt", ""),
                            }
                        }
                    }
                }

                run_requests.append(
                    dg.RunRequest(
                        partition_key=partition_key,
                        run_config=run_config,
                    )
                )

            if run_requests:
                context.log.info("Found %d new consultations to process", len(run_requests))

            return run_requests

        except Exception as e:
            context.log.error("Sensor error: %s", e)
            return []

    return dg.Definitions(
        assets=[
            bronze_transcripts_asset,
            pii_redacted_documents_asset,
            phi_redacted_transcripts_asset,
            embeddings_asset,
            enriched_analytics_asset,
        ],
        jobs=[consultation_job],
        sensors=[consultation_sensor],
    )
