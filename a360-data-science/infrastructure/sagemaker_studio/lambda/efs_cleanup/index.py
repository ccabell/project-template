"""
Lambda handlers for EFS filesystem cleanup custom resource.

This module provides the Lambda functions required to implement a custom resource
for safely cleaning up EFS filesystems and mount targets when SageMaker Studio
domains are deleted.
"""

import datetime
from typing import Any, Dict, List, Optional, TypedDict

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
efs_client = boto3.client("efs")


class EfsConfig(TypedDict, total=False):
    """
    Type definition for EFS filesystem configuration.

    Attributes:
        OwnerId: AWS account ID that owns the filesystem
        CreationToken: Idempotent token used for filesystem creation
        FileSystemId: ID of the EFS filesystem
        FileSystemArn: ARN of the EFS filesystem
        CreationTime: When the filesystem was created
        LifeCycleState: Current state of the filesystem
        Name: Name tag of the filesystem
        NumberOfMountTargets: Number of mount targets for the filesystem
        SizeInBytes: Size information about the filesystem
        PerformanceMode: Performance mode of the filesystem
        Encrypted: Whether the filesystem is encrypted
        KmsKeyId: ID of the KMS key used for encryption
        ThroughputMode: Throughput mode of the filesystem
        ProvisionedThroughputInMibps: Provisioned throughput if applicable
        AvailabilityZoneName: Availability zone for One Zone filesystems
        AvailabilityZoneId: ID of the availability zone
        Tags: Tags attached to the filesystem
    """

    OwnerId: str
    CreationToken: str
    FileSystemId: str
    FileSystemArn: str
    CreationTime: datetime.datetime
    LifeCycleState: str
    Name: str
    NumberOfMountTargets: float
    SizeInBytes: Dict[str, Any]
    PerformanceMode: str
    Encrypted: bool
    KmsKeyId: str
    ThroughputMode: str
    ProvisionedThroughputInMibps: float
    AvailabilityZoneName: str
    AvailabilityZoneId: str
    Tags: List[Dict[str, str]]


def describe_file_system(file_system_id: str) -> Optional[EfsConfig]:
    """
    Retrieve the configuration of an EFS filesystem.

    Args:
        file_system_id: ID of the EFS filesystem to describe

    Returns:
        Configuration of the filesystem if it exists, None otherwise

    Raises:
        ValueError: If file_system_id is not provided
    """
    if not file_system_id:
        raise ValueError("file_system_id not provided")

    logger.info("Describing EFS filesystem", extra={"file_system_id": file_system_id})

    try:
        response = efs_client.describe_file_systems(FileSystemId=file_system_id)
        logger.info("EFS filesystem description received", extra={"response": response})

        if response.get("FileSystems"):
            return response.get("FileSystems")[0]

        return None

    except efs_client.exceptions.FileSystemNotFound:
        logger.info(
            "EFS filesystem not found", extra={"file_system_id": file_system_id}
        )
        return None

    except Exception:
        logger.exception("Failed to describe EFS filesystem")
        return None


def delete_file_system(file_system_id: str) -> None:
    """
    Delete an EFS filesystem and its mount targets.

    Args:
        file_system_id: ID of the EFS filesystem to delete

    Raises:
        ValueError: If file_system_id is not provided
    """
    if not file_system_id:
        raise ValueError("file_system_id not provided")

    logger.info("Deleting EFS filesystem", extra={"file_system_id": file_system_id})

    mount_targets = efs_client.describe_mount_targets(FileSystemId=file_system_id).get(
        "MountTargets", []
    )

    logger.info("Mount targets retrieved", extra={"mount_targets": mount_targets})

    if not mount_targets:
        efs_client.delete_file_system(FileSystemId=file_system_id)
        logger.info("EFS filesystem deleted", extra={"file_system_id": file_system_id})
        return

    for mount_target in mount_targets:
        mount_target_id = mount_target.get("MountTargetId")
        logger.info("Deleting mount target", extra={"mount_target_id": mount_target_id})

        try:
            efs_client.delete_mount_target(MountTargetId=mount_target_id)
        except Exception:
            logger.exception("Failed to delete mount target")


@logger.inject_lambda_context
def on_create(event: Dict[str, Any], context: LambdaContext) -> Dict[str, str]:
    """
    Handle the Create event for the custom resource.

    Not required for EFS cleanup, but provided for completeness.

    Args:
        event: CloudFormation custom resource event
        context: Lambda execution context

    Returns:
        Dictionary indicating successful handling of the event
    """
    logger.info("Create event handler invoked (no-op)")
    return {"Status": "SUCCESS"}


@logger.inject_lambda_context
def is_create_complete(
    event: Dict[str, Any], context: LambdaContext
) -> Dict[str, bool]:
    """
    Check if the Create operation is complete.

    Args:
        event: CloudFormation custom resource event
        context: Lambda execution context

    Returns:
        Dictionary indicating that the operation is complete
    """
    logger.info("Create completion check invoked (always complete)")
    return {"IsComplete": True}


@logger.inject_lambda_context
def on_update(event: Dict[str, Any], context: LambdaContext) -> Dict[str, str]:
    """
    Handle the Update event for the custom resource.

    Not required for EFS cleanup, but provided for completeness.

    Args:
        event: CloudFormation custom resource event
        context: Lambda execution context

    Returns:
        Dictionary indicating successful handling of the event
    """
    logger.info("Update event handler invoked (no-op)")
    return {"Status": "SUCCESS"}


@logger.inject_lambda_context
def is_update_complete(
    event: Dict[str, Any], context: LambdaContext
) -> Dict[str, bool]:
    """
    Check if the Update operation is complete.

    Args:
        event: CloudFormation custom resource event
        context: Lambda execution context

    Returns:
        Dictionary indicating that the operation is complete
    """
    logger.info("Update completion check invoked (always complete)")
    return {"IsComplete": True}


def on_delete(file_system_id: str, physical_resource_id: str) -> Dict[str, Any]:
    """
    Handle the Delete event for the custom resource.

    Args:
        file_system_id: ID of the EFS filesystem to delete
        physical_resource_id: Physical resource ID of the custom resource

    Returns:
        Dictionary indicating the result of the operation
    """
    logger.info(
        "Delete event handler invoked", extra={"file_system_id": file_system_id}
    )

    try:
        efs_config = describe_file_system(file_system_id)

        if not efs_config or efs_config.get("LifeCycleState") == "deleted":
            logger.info("EFS filesystem already deleted or not found")
            return {"Status": "SUCCESS", "PhysicalResourceId": physical_resource_id}

        delete_file_system(efs_config.get("FileSystemId"))
        return {"Status": "SUCCESS", "PhysicalResourceId": physical_resource_id}

    except Exception as e:
        logger.exception("Failed to delete EFS filesystem")
        return {
            "Status": "FAILED",
            "PhysicalResourceId": physical_resource_id,
            "Reason": str(e),
        }


@logger.inject_lambda_context
def is_delete_complete(
    file_system_id: str, event: Dict[str, Any], context: LambdaContext
) -> Dict[str, bool]:
    """
    Check if deletion is complete.

    Args:
        file_system_id: ID of filesystem being deleted
        event: CloudFormation custom resource event
        context: Lambda execution context

    Returns:
        Response indicating completion status
    """
    logger.info(
        "Delete completion check invoked", extra={"file_system_id": file_system_id}
    )

    try:
        efs_config = describe_file_system(file_system_id)

        if not efs_config or efs_config.get("LifeCycleState") == "deleted":
            logger.info("EFS filesystem deletion confirmed")
            return {"IsComplete": True}

        mount_targets = efs_client.describe_mount_targets(
            FileSystemId=file_system_id
        ).get("MountTargets", [])

        if mount_targets:
            logger.info(
                "Mount targets still exist",
                extra={"mount_target_count": len(mount_targets)},
            )
            return {"IsComplete": False}

        logger.info("Deleting EFS filesystem", extra={"file_system_id": file_system_id})
        efs_client.delete_file_system(FileSystemId=file_system_id)
        return {"IsComplete": False}

    except Exception:
        logger.exception("Error checking EFS filesystem deletion status")
        return {"IsComplete": False}


@logger.inject_lambda_context
def on_event_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Handle custom resource lifecycle events.

    Args:
        event: CloudFormation custom resource event
        context: Lambda execution context

    Returns:
        Response dictionary based on the event type and outcome.

    Raises:
        Exception: If the request type is invalid.
    """
    logger.set_correlation_id(context.aws_request_id)
    logger.info("Custom resource event received", extra={"event": event})

    request_type = event["RequestType"]
    properties = event.get("ResourceProperties", {})
    file_system_id = properties.get("file_system_id", "")
    physical_resource_id = event.get("PhysicalResourceId", "")

    if request_type == "Create":
        return on_create(event, context)

    if request_type == "Update":
        return on_update(event, context)

    if request_type == "Delete":
        return on_delete(file_system_id, physical_resource_id)

    raise ValueError(f"Invalid request type: {request_type}")


@logger.inject_lambda_context
def is_complete_handler(
    event: Dict[str, Any], context: LambdaContext
) -> Dict[str, bool]:
    """
    Handle isComplete checks for async custom resource operations.

    Args:
        event: CloudFormation custom resource event
        context: Lambda execution context

    Returns:
        Dictionary indicating whether the operation is complete.

    Raises:
        Exception: If the request type is invalid.
    """
    logger.set_correlation_id(context.aws_request_id)
    logger.info("isComplete check event received", extra={"event": event})

    request_type = event["RequestType"]
    properties = event.get("ResourceProperties", {})
    file_system_id = properties.get("file_system_id", "")

    if request_type == "Create":
        return is_create_complete(event, context)

    if request_type == "Update":
        return is_update_complete(event, context)

    if request_type == "Delete":
        return is_delete_complete(file_system_id, event, context)

    raise ValueError(f"Invalid request type: {request_type}")
