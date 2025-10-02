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
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import ClientError

import dagster as dg

s3_client = boto3.client("s3")


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
    partition_def = dg.DynamicPartitionsDefinition(
        name=f"{consultation_def.tenant_name}_consultations",
    )

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
    ) -> dg.MaterializeResult:
        """Placeholder asset for PII redaction orchestration.

        In practice, the landing S3 bucket and Macie run continuously. This
        asset materialization can validate redaction outputs or submit on-demand
        Macie classification for a specific consultation scope.
        """
        landing_bucket = f"a360-{consultation_def.environment}-consultation-landing"
        silver_bucket = f"a360-{consultation_def.environment}-consultation-silver"
        context.log.info(
            f"Validating PII redaction for consultation {config.consultation_id} using \n"
            f"landing={landing_bucket} silver={silver_bucket}",
        )
        return dg.MaterializeResult(
            metadata={
                "status": "validated",
                "consultation_id": config.consultation_id,
                "tenant_id": config.tenant_id,
            },
        )

    @dg.asset(
        name=f"{consultation_def.tenant_name}_phi_redacted_transcripts",
        partitions_def=partition_def,
        compute_kind="comprehend_medical",
        group_name="consultation_pipeline",
    )
    def phi_redacted_transcripts_asset(
        context: dg.AssetExecutionContext,
        config: ConsultationConfig,
    ) -> dg.MaterializeResult:
        """Emit intent to process PHI redaction for a partition.

        The actual PHI redaction runs in a Lambda triggered by S3 or
        EventBridge; here we simply register the materialization and allow
        orchestrated backfills.
        """
        silver_bucket = f"a360-{consultation_def.environment}-consultation-silver"
        redacted_key = (
            f"transcripts/{consultation_def.tenant_id}/{config.consultation_id}/"
            "phi_redacted_transcript.json"
        )
        context.log.info(
            f"PHI redaction expected at s3://{silver_bucket}/{redacted_key}",
        )
        return dg.MaterializeResult(
            metadata={
                "redacted_key": redacted_key,
                "consultation_id": config.consultation_id,
                "tenant_id": config.tenant_id,
            },
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
    ) -> dg.MaterializeResult:
        gold_bucket = f"a360-{consultation_def.environment}-consultation-gold"
        embeddings_key = (
            f"embeddings/{consultation_def.tenant_id}/{config.consultation_id}/"
            "conversation_embeddings.json"
        )
        context.log.info(
            f"Embeddings expected at s3://{gold_bucket}/{embeddings_key}",
        )
        return dg.MaterializeResult(
            metadata={
                "embeddings_key": embeddings_key,
                "consultation_id": config.consultation_id,
                "tenant_id": config.tenant_id,
            },
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
    ) -> dg.MaterializeResult:
        gold_bucket = f"a360-{consultation_def.environment}-consultation-gold"
        analytics_key = (
            f"analytics/{consultation_def.tenant_id}/{config.consultation_id}/"
            "enriched_insights.json"
        )
        context.log.info(
            f"Analytics expected at s3://{gold_bucket}/{analytics_key}",
        )
        return dg.MaterializeResult(
            metadata={
                "analytics_key": analytics_key,
                "consultation_id": config.consultation_id,
                "tenant_id": config.tenant_id,
                "processed_at": datetime.now(UTC).isoformat(),
            },
        )

    job_name = f"{consultation_def.tenant_name}_consultation_processing_job"
    consultation_job = dg.define_asset_job(
        name=job_name,
        selection=dg.AssetSelection.assets(
            pii_redacted_documents_asset,
            phi_redacted_transcripts_asset,
            embeddings_asset,
            enriched_analytics_asset,
        ),
        partitions_def=partition_def,
    )

    @dg.sensor(
        name=f"{consultation_def.tenant_name}_consultation_sensor",
        minimum_interval_seconds=60,
        default_status=dg.DefaultSensorStatus.RUNNING,
        job=consultation_job,
    )
    def consultation_sensor(context: dg.SensorEvaluationContext):
        """Monitor S3 bronze bucket for new consultation transcripts and trigger pipeline runs."""
        bronze_bucket = f"a360-{consultation_def.environment}-consultation-bronze"

        try:
            # Check for new consultation transcripts in the last hour
            new_consultations = check_for_new_consultations(bronze_bucket, context)

            run_requests = []
            for consultation in new_consultations:
                # Enforce tenant isolation - only process consultations for this tenant
                if consultation["tenant_id"] != consultation_def.tenant_id:
                    context.log.info(
                        f"Skipping consultation {consultation['consultation_id']} - tenant mismatch: "
                        f"{consultation['tenant_id']} != {consultation_def.tenant_id}",
                    )
                    continue

                # Create partition for new consultation
                partition_key = consultation["consultation_id"]
                context.log.info(
                    f"Creating partition for consultation: {partition_key}",
                )

                # Add partition to dynamic partition definition using Instance API
                instance = context.instance
                instance.add_dynamic_partitions(partition_def.name, [partition_key])

                # Create run request with consultation configuration
                asset_config = {
                    "consultation_id": consultation["consultation_id"],
                    "tenant_id": consultation["tenant_id"],
                    "consultation_date": consultation["date"],
                    "started_at": consultation["started_at"],
                    "finished_at": consultation["finished_at"],
                }

                run_requests.append(
                    dg.RunRequest(
                        partition_key=partition_key,
                        run_config={
                            "ops": {
                                "pii_redacted_documents_asset": {"config": asset_config},
                                "phi_redacted_transcripts_asset": {"config": asset_config},
                                "embeddings_asset": {"config": asset_config},
                                "enriched_analytics_asset": {"config": asset_config},
                            },
                        },
                        tags={
                            "tenant_id": consultation["tenant_id"],
                            "consultation_id": consultation["consultation_id"],
                            "source": "s3_sensor",
                        },
                    ),
                )

            if run_requests:
                context.log.info(
                    f"Triggering {len(run_requests)} pipeline runs for new consultations",
                )
            else:
                context.log.debug("No new consultations found in bronze bucket")

            return run_requests

        except Exception:
            context.log.exception("Error in consultation sensor")
            return []

    def check_for_new_consultations(
        bucket_name: str,
        context: dg.SensorEvaluationContext,
    ) -> list[dict[str, Any]]:
        """Check S3 bronze bucket for new consultation transcripts."""
        try:
            # Look for consultation transcripts in the last hour
            cutoff_time = datetime.now(UTC) - timedelta(hours=1)
            new_consultations = []

            # List objects in bronze bucket with consultation prefix
            paginator = s3_client.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(
                Bucket=bucket_name,
                Prefix="",
                PaginationConfig={"MaxItems": 1000},
            )

            for page in page_iterator:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    key = obj["Key"]
                    last_modified = obj["LastModified"].astimezone(UTC)

                    # Check if this is a consultation transcript and is recent
                    if (
                        key.endswith("/final_transcript.json")
                        and last_modified > cutoff_time
                    ):
                        # Extract tenant_id and consultation_id from key path
                        # Expected format: transcripts/{tenant_id}/{consultation_id}/final_transcript.json
                        path_parts = key.split("/")
                        if len(path_parts) >= 3 and path_parts[0] == "transcripts":
                            tenant_id = path_parts[1]
                            consultation_id = path_parts[2]
                        else:
                            # Fallback for simple format: {consultation_id}/final_transcript.json
                            consultation_id = path_parts[0]
                            tenant_id = "unknown"

                        # Try to get consultation metadata
                        consultation_info = get_consultation_metadata(
                            bucket_name,
                            tenant_id,
                            consultation_id,
                            context,
                        )

                        if consultation_info:
                            new_consultations.append(consultation_info)
                            context.log.info(
                                f"Found new consultation: {consultation_id}",
                            )

            return new_consultations

        except Exception as e:
            context.log.exception(f"Error checking S3 bucket {bucket_name}: {e!s}")
            return []

    def get_consultation_metadata(
        bucket_name: str,
        tenant_id: str,
        consultation_id: str,
        context: dg.SensorEvaluationContext,
    ) -> dict[str, Any] | None:
        """Extract consultation metadata from S3 object."""
        try:
            # Try to get metadata file first
            # Use proper path structure with tenant_id
            if tenant_id != "unknown":
                metadata_key = f"transcripts/{tenant_id}/{consultation_id}/metadata.json"
            else:
                # Fallback to simple structure
                metadata_key = f"{consultation_id}/metadata.json"
            try:
                response = s3_client.get_object(Bucket=bucket_name, Key=metadata_key)
                metadata = response["Body"].read().decode("utf-8")
                data = json.loads(metadata)

                # Extract metadata attributes
                metadata_attrs = data.get("metadataAttributes", {})
                return {
                    "consultation_id": consultation_id,
                    "tenant_id": metadata_attrs.get("tenantId", tenant_id),
                    "date": metadata_attrs.get(
                        "consultationDate",
                        datetime.now(UTC).strftime("%Y-%m-%d"),
                    ),
                    "started_at": metadata_attrs.get(
                        "startedAt",
                        datetime.now(UTC).isoformat(),
                    ),
                    "finished_at": metadata_attrs.get(
                        "finishedAt",
                        datetime.now(UTC).isoformat(),
                    ),
                }
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                    # Fallback: try to get basic info from transcript file
                    if tenant_id != "unknown":
                        transcript_key = f"transcripts/{tenant_id}/{consultation_id}/final_transcript.json"
                    else:
                        transcript_key = f"{consultation_id}/final_transcript.json"
                    try:
                        response = s3_client.get_object(
                            Bucket=bucket_name,
                            Key=transcript_key,
                        )
                        # Just return basic info without parsing full transcript
                        return {
                            "consultation_id": consultation_id,
                            "tenant_id": tenant_id,
                            "date": datetime.now(UTC).strftime("%Y-%m-%d"),
                            "started_at": datetime.now(UTC).isoformat(),
                            "finished_at": datetime.now(UTC).isoformat(),
                        }
                    except ClientError as inner_e:
                        if inner_e.response.get("Error", {}).get("Code") == "NoSuchKey":
                            return None
                        raise
                else:
                    raise

        except (ClientError, ConnectionError, TimeoutError) as e:
            # Log specific AWS/connection errors but don't fail the sensor
            context.log.warning(f"Sensor error: {e}")
            return None
        except Exception as e:
            # Log unexpected errors but don't fail the sensor
            context.log.error(f"Unexpected sensor error: {e}")
            return None

    return dg.Definitions(
        assets=[
            pii_redacted_documents_asset,
            phi_redacted_transcripts_asset,
            embeddings_asset,
            enriched_analytics_asset,
        ],
        jobs=[consultation_job],
        sensors=[consultation_sensor],
    )
