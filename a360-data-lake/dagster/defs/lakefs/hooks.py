"""LakeFS hooks for Dagster+ pipeline integration."""

import json
import os
from typing import Dict, Any, Optional

from dagster import (
    HookContext,
    failure_hook,
    success_hook,
    get_dagster_logger,
)

from .resources import LakeFSResource


@success_hook(required_resource_keys={"lakefs"})
def lakefs_commit_on_success(context: HookContext) -> None:
    """Commit changes to LakeFS when asset or op succeeds.

    This hook automatically commits data changes to the appropriate
    LakeFS repository when a Dagster asset or op completes successfully.
    """
    logger = get_dagster_logger()
    lakefs: LakeFSResource = context.resources.lakefs  # type: ignore

    # Get asset/op information
    asset_key = None
    op_name = None
    op_def = getattr(context, "op_def", None) or getattr(context, "solid_def", None)
    if op_def is not None:  # Op execution
        op_name = op_def.name
        entity_name = op_name
        entity_type = "op"
    elif context.asset_key is not None:  # Asset execution
        asset_key = context.asset_key
        entity_name = asset_key.to_user_string()
        entity_type = "asset"
    else:
        logger.warning("Unable to determine entity type for LakeFS commit")
        return

    # Determine repository and branch based on asset/op
    repo_info = _get_repository_info(entity_name, context)
    if not repo_info:
        logger.info(f"No LakeFS repository configured for {entity_type} {entity_name}")
        return

    repository = repo_info["repository"]
    branch = repo_info["branch"]

    # Create commit message
    run_id = context.run_id
    message = f"Completed {entity_type} '{entity_name}' (run: {run_id})"

    # Add metadata
    metadata = {
        "dagster_run_id": run_id,
        "entity_type": entity_type,
        "entity_name": entity_name,
        "status": "success",
        "partition_key": getattr(context, "partition_key", None),
    }

    # Remove None values
    metadata = {k: v for k, v in metadata.items() if v is not None}

    # Commit changes
    commit_result = lakefs.commit_changes(repository=repository, branch=branch, message=message, metadata=metadata)

    # Handle both commit ID (string) and boolean returns
    if commit_result:
        # If commit_result is a string, it's the commit ID; if boolean True, use generic success message
        commit_id_str = commit_result if isinstance(commit_result, str) else "success"
        logger.info(f"LakeFS commit successful: {repository}:{branch} - {commit_id_str}")

        # Send EventBridge event for audit logging
        _send_lakefs_event(
            event_type="Repository Commit",
            details={
                "repository": repository,
                "branch": branch,
                "commit_id": commit_id_str,
                "message": message,
                "dagster_context": {
                    "run_id": run_id,
                    "entity_type": entity_type,
                    "entity_name": entity_name,
                },
            },
            context=context,
        )
    else:
        logger.error(f"LakeFS commit failed for {entity_type} {entity_name}")


@failure_hook(required_resource_keys={"lakefs"})
def lakefs_branch_on_failure(context: HookContext) -> None:
    """Create failure branch when asset or op fails.

    This hook creates a failure branch in LakeFS when a Dagster asset
    or op fails, preserving the state for debugging and recovery.
    """
    logger = get_dagster_logger()
    lakefs: LakeFSResource = context.resources.lakefs  # type: ignore

    # Get asset/op information
    if context.op_def is not None:
        entity_name = context.op_def.name
        entity_type = "op"
    elif context.asset_key is not None:
        entity_name = context.asset_key.to_user_string()
        entity_type = "asset"
    else:
        logger.warning("Unable to determine entity type for LakeFS failure branch")
        return

    # Determine repository
    repo_info = _get_repository_info(entity_name, context)
    if not repo_info:
        logger.info(f"No LakeFS repository configured for {entity_type} {entity_name}")
        return

    repository = repo_info["repository"]
    source_branch = repo_info["branch"]

    # Create failure branch name
    run_id = context.run_id
    failure_branch = f"failure-{run_id}-{entity_name.replace('/', '-')}"

    # Create failure branch
    success = lakefs.create_branch(repository=repository, branch=failure_branch, source_branch=source_branch)

    if success:
        logger.info(f"Created failure branch: {repository}:{failure_branch}")

        # Send EventBridge event
        _send_lakefs_event(
            event_type="Branch Created",
            details={
                "repository": repository,
                "branch": failure_branch,
                "source_branch": source_branch,
                "reason": "pipeline_failure",
                "dagster_context": {
                    "run_id": run_id,
                    "entity_type": entity_type,
                    "entity_name": entity_name,
                },
            },
            context=context,
        )
    else:
        logger.error(f"Failed to create failure branch for {entity_type} {entity_name}")


@success_hook(required_resource_keys={"lakefs"})
def lakefs_promote_on_job_success(context: HookContext) -> None:
    """Promote changes between branches when job succeeds.

    This hook promotes data from development/staging branches to
    production when entire jobs complete successfully.
    """
    logger = get_dagster_logger()
    lakefs: LakeFSResource = context.resources.lakefs  # type: ignore

    # Only run on job completion
    if context.op_def is not None or context.asset_key is not None:
        return  # This is for individual assets/ops, not jobs

    # Get job information
    job_name = getattr(context, "job_name", None) or getattr(context, "pipeline_name", None)
    if not job_name:
        logger.warning("Unable to determine job name for LakeFS promotion")
        return

    # Check if this is a consultation pipeline job
    if "consultation" not in job_name.lower():
        logger.info(f"Skipping LakeFS promotion for non-consultation job: {job_name}")
        return

    run_id = context.run_id
    logger.info(f"Starting LakeFS promotion for job {job_name} (run: {run_id})")

    # Define promotion rules
    promotion_rules = [
        {"from": "dev", "to": "staging", "condition": "dev_complete"},
        {"from": "staging", "to": "prod", "condition": "staging_verified"},
    ]

    # Get current environment from job tags or config
    current_env = _get_environment_from_context(context)

    # Execute promotions based on current environment
    for rule in promotion_rules:
        if current_env == rule["from"]:
            _execute_promotion(lakefs=lakefs, rule=rule, job_name=job_name, run_id=run_id, context=context)


def _get_repository_info(entity_name: str, context: HookContext) -> Optional[Dict[str, str]]:
    """Determine LakeFS repository and branch for an entity.

    Args:
        entity_name: Name of the asset or op
        context: Dagster hook context

    Returns:
        Dictionary with repository and branch information, or None
    """
    # Map entity names to repositories
    if "consultation" in entity_name.lower():
        # Determine bucket type from entity name
        if "landing" in entity_name.lower() or "raw" in entity_name.lower():
            repository = "consultation-landing"
        elif "silver" in entity_name.lower() or "processed" in entity_name.lower():
            repository = "consultation-silver"
        elif "gold" in entity_name.lower() or "analytics" in entity_name.lower():
            repository = "consultation-gold"
        else:
            repository = "consultation-silver"  # Default to silver

        # Determine branch from environment
        branch = _get_environment_from_context(context)

        return {"repository": repository, "branch": branch}

    return None


def _get_environment_from_context(context: HookContext) -> str:
    """Get environment (dev/staging/prod) from Dagster context.

    Args:
        context: Dagster hook context

    Returns:
        Environment name (defaults to "dev")
    """
    # Try to get environment from various sources
    env = "dev"  # Default

    # Check run config
    if hasattr(context, "run_config") and context.run_config:
        env = context.run_config.get("resources", {}).get("env", {}).get("environment", env)

    # Check tags
    if hasattr(context, "run") and context.run.tags:
        env = context.run.tags.get("environment", env)

    # Check job config
    if hasattr(context, "job_config") and context.job_config:
        env = context.job_config.get("tags", {}).get("environment", env)

    return env


def _execute_promotion(
    lakefs: LakeFSResource, rule: Dict[str, str], job_name: str, run_id: str, context: HookContext
) -> None:
    """Execute a branch promotion rule.

    Args:
        lakefs: LakeFS resource
        rule: Promotion rule dictionary
        job_name: Name of the job
        run_id: Dagster run ID
        context: Hook context
    """
    logger = get_dagster_logger()

    from_branch = rule["from"]
    to_branch = rule["to"]

    # Get consultation repositories
    repositories = ["consultation-landing", "consultation-silver", "consultation-gold"]

    for repository in repositories:
        logger.info(f"Promoting {repository} from {from_branch} to {to_branch}")

        success = lakefs.merge_branch(
            repository=repository,
            source_branch=from_branch,
            destination_branch=to_branch,
            message=f"Automated promotion from {job_name} (run: {run_id})",
        )

        if success:
            logger.info(f"Successfully promoted {repository}:{from_branch} -> {to_branch}")

            # Send EventBridge event
            _send_lakefs_event(
                event_type="Branch Merge",
                details={
                    "repository": repository,
                    "source_branch": from_branch,
                    "destination_branch": to_branch,
                    "promotion_type": "automated",
                    "dagster_context": {
                        "run_id": run_id,
                        "job_name": job_name,
                        "rule": rule,
                    },
                },
                context=context,
            )
        else:
            logger.error(f"Failed to promote {repository}:{from_branch} -> {to_branch}")



def _send_lakefs_event(event_type: str, details: Dict[str, Any], context: HookContext) -> None:
    """Send EventBridge event for LakeFS operations.

    Args:
        event_type: Type of LakeFS event
        details: Event details
        context: Hook context
    """
    logger = get_dagster_logger()

    try:
        import boto3

        eventbridge = boto3.client("events")

        event = {
            "Source": "lakefs",
            "DetailType": event_type,
            "Detail": json.dumps(details),
        }

        eventbridge.put_events(Entries=[event])
        logger.info(f"Sent EventBridge event: {event_type}")

    except Exception as e:
        logger.warning(f"Failed to send EventBridge event: {str(e)}")
