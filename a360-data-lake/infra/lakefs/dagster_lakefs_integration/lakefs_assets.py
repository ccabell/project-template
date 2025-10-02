
import json
from datetime import datetime

from dagster import AssetMaterialization, MetadataValue, asset


@asset(required_resource_keys={"lakefs"})
def consultation_bronze_data(context):
    """Process consultation data and store in LakeFS bronze layer."""
    lakefs = context.resources.lakefs

    # Create a development branch for this run
    branch_name = f"consultation-process-{context.run_id}"
    lakefs.create_branch("consultation-bronze", branch_name)

    # Simulate processing consultation data
    processed_data = {
        "consultation_id": "cons_12345",
        "transcript": "Patient consultation transcript...",
        "processed_at": datetime.now().isoformat(),
        "dagster_run_id": context.run_id,
    }

    # Upload to LakeFS
    file_path = f"consultations/{processed_data['consultation_id']}/transcript.json"
    content = json.dumps(processed_data, indent=2).encode('utf-8')

    success = lakefs.upload_object(
        repo="consultation-bronze",
        branch=branch_name,
        path=file_path,
        content=content,
    )

    if success:
        # Commit the changes
        lakefs.commit_changes(
            repo="consultation-bronze",
            branch=branch_name,
            message=f"Add consultation {processed_data['consultation_id']}",
            metadata={
                "dagster_run_id": context.run_id,
                "asset_name": "consultation_bronze_data",
            },
        )

        context.log.info(f"Successfully processed consultation to LakeFS branch: {branch_name}")

        return AssetMaterialization(
            asset_key="consultation_bronze_data",
            metadata={
                "lakefs_repo": MetadataValue.text("consultation-bronze"),
                "lakefs_branch": MetadataValue.text(branch_name),
                "file_path": MetadataValue.text(file_path),
                "consultation_id": MetadataValue.text(processed_data['consultation_id']),
            },
        )
    else:
        raise Exception("Failed to upload to LakeFS")


@asset(required_resource_keys={"lakefs"})
def consultation_silver_data(context, consultation_bronze_data):
    """Process bronze data and create silver layer with PHI redaction."""
    lakefs = context.resources.lakefs

    # Create silver branch
    branch_name = f"consultation-silver-{context.run_id}"
    lakefs.create_branch("consultation-silver", branch_name)

    # Simulate PHI redaction processing
    silver_data = {
        "consultation_id": "cons_12345",
        "redacted_transcript": "[REDACTED] consultation transcript...",
        "phi_entities_found": 5,
        "processed_at": datetime.now().isoformat(),
        "source_asset": "consultation_bronze_data",
        "dagster_run_id": context.run_id,
    }

    # Upload to silver layer
    file_path = f"consultations/{silver_data['consultation_id']}/redacted_transcript.json"
    content = json.dumps(silver_data, indent=2).encode('utf-8')

    success = lakefs.upload_object(
        repo="consultation-silver",
        branch=branch_name,
        path=file_path,
        content=content,
    )

    if success:
        lakefs.commit_changes(
            repo="consultation-silver",
            branch=branch_name,
            message=f"Add PHI-redacted consultation {silver_data['consultation_id']}",
            metadata={
                "dagster_run_id": context.run_id,
                "asset_name": "consultation_silver_data",
                "phi_entities_found": silver_data['phi_entities_found'],
            },
        )

        return AssetMaterialization(
            asset_key="consultation_silver_data",
            metadata={
                "lakefs_repo": MetadataValue.text("consultation-silver"),
                "lakefs_branch": MetadataValue.text(branch_name),
                "phi_entities_found": MetadataValue.int(silver_data['phi_entities_found']),
            },
        )
    else:
        raise Exception("Failed to upload to LakeFS silver layer")


# Job definition
from dagster import job


@job(resource_defs={"lakefs": lakefs_resource})
def consultation_processing_job():
    """Job that processes consultation data through LakeFS versioned layers."""
    consultation_silver_data(consultation_bronze_data())
