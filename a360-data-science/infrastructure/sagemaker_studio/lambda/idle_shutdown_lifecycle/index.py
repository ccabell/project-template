"""
Lambda handlers for SageMaker Studio idle app shutdown lifecycle configuration.

This module provides the Lambda functions required to implement a custom resource
for managing idle application shutdown lifecycle configurations in SageMaker Studio.
"""

import base64
from typing import Any, Dict

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
sagemaker_client = boto3.client("sagemaker")


def read_script_content() -> str:
    """
    Read the idle app shutdown script from file.

    Returns:
        Base64-encoded content of the shutdown script.

    Raises:
        FileNotFoundError: If the script file cannot be found.
    """
    with open("shutdown_idle_apps.sh", "rb") as file:
        script_content = file.read()

    return base64.b64encode(script_content).decode()


def create_lifecycle_config(domain_id: str, config_name: str) -> Dict[str, Any]:
    """
    Create a new lifecycle configuration for idle app shutdown.

    Args:
        domain_id: SageMaker domain ID to attach the configuration to
        config_name: Name to assign to the lifecycle configuration

    Returns:
        Dictionary containing the operation status and resource ID.

    Raises:
        Exception: If any stage of the lifecycle configuration creation fails.
    """
    logger.info(
        "Creating idle shutdown lifecycle configuration",
        extra={"domain_id": domain_id, "config_name": config_name},
    )

    try:
        script_content = read_script_content()

        response = sagemaker_client.create_studio_lifecycle_config(
            StudioLifecycleConfigName=config_name,
            StudioLifecycleConfigContent=script_content,
            StudioLifecycleConfigAppType="JupyterLab",
        )

        config_arn = response["StudioLifecycleConfigArn"]
        logger.info("Created lifecycle configuration", extra={"config_arn": config_arn})

        existing_configs = sagemaker_client.list_studio_lifecycle_configs(
            AppTypeEquals="JupyterLab"
        ).get("StudioLifecycleConfigs", [])

        if existing_configs:
            config_arns = [cfg["StudioLifecycleConfigArn"] for cfg in existing_configs]
            if config_arn not in config_arns:
                config_arns.append(config_arn)
        else:
            config_arns = [config_arn]

        logger.info(
            "Updating domain with lifecycle configurations",
            extra={"config_arns": config_arns},
        )

        sagemaker_client.update_domain(
            DomainId=domain_id,
            DefaultUserSettings={
                "JupyterLabAppSettings": {
                    "DefaultResourceSpec": {
                        "LifecycleConfigArn": config_arn,
                        "InstanceType": "ml.t3.medium",
                    },
                    "LifecycleConfigArns": config_arns,
                }
            },
        )

        return {"Status": "SUCCESS", "PhysicalResourceId": config_arn}

    except Exception as e:
        logger.exception("Failed to create lifecycle configuration")
        return {"Status": "FAILED", "Reason": str(e)}


def update_lifecycle_config(
    domain_id: str, config_name: str, physical_resource_id: str
) -> Dict[str, Any]:
    """
    Update an existing lifecycle configuration.

    Args:
        domain_id: SageMaker domain ID the configuration is attached to
        config_name: Name of the lifecycle configuration
        physical_resource_id: Physical resource ID of the existing configuration

    Returns:
        Dictionary containing the operation status and resource ID.
    """
    logger.info(
        "Updating idle shutdown lifecycle configuration",
        extra={"domain_id": domain_id, "config_name": config_name},
    )

    try:
        delete_lifecycle_config(config_name, physical_resource_id)
        return create_lifecycle_config(domain_id, config_name)

    except Exception as e:
        logger.exception("Failed to update lifecycle configuration")
        return {
            "Status": "FAILED",
            "PhysicalResourceId": physical_resource_id,
            "Reason": str(e),
        }


def delete_lifecycle_config(
    config_name: str, physical_resource_id: str
) -> Dict[str, Any]:
    """
    Delete a lifecycle configuration.

    Args:
        config_name: Name of the lifecycle configuration to delete
        physical_resource_id: Physical resource ID of the configuration

    Returns:
        Dictionary containing the operation status and resource ID.
    """
    logger.info(
        "Deleting idle shutdown lifecycle configuration",
        extra={"config_name": config_name},
    )

    try:
        sagemaker_client.delete_studio_lifecycle_config(
            StudioLifecycleConfigName=config_name
        )
        return {"Status": "SUCCESS", "PhysicalResourceId": physical_resource_id}

    except Exception as e:
        logger.exception("Failed to delete lifecycle configuration")
        return {
            "Status": "FAILED",
            "PhysicalResourceId": physical_resource_id,
            "Reason": str(e),
        }


def is_creation_complete() -> Dict[str, bool]:
    """
    Check if lifecycle configuration creation is complete.

    Returns:
        Dictionary indicating completion status.
    """
    return {"IsComplete": True}


def is_update_complete() -> Dict[str, bool]:
    """
    Check if lifecycle configuration update is complete.

    Returns:
        Dictionary indicating completion status.
    """
    return {"IsComplete": True}


def is_deletion_complete(config_name: str) -> Dict[str, bool]:
    """
    Check if lifecycle configuration deletion is complete.

    Args:
        config_name: Name of the lifecycle configuration being deleted

    Returns:
        Dictionary indicating completion status.
    """
    try:
        sagemaker_client.describe_studio_lifecycle_config(
            StudioLifecycleConfigName=config_name
        )

        logger.info(
            "Lifecycle configuration still exists, deleting again",
            extra={"config_name": config_name},
        )

        sagemaker_client.delete_studio_lifecycle_config(
            StudioLifecycleConfigName=config_name
        )
        return {"IsComplete": False}

    except sagemaker_client.exceptions.ResourceNotFound:
        logger.info(
            "Lifecycle configuration deleted successfully",
            extra={"config_name": config_name},
        )
        return {"IsComplete": True}

    except Exception:
        logger.exception("Error checking lifecycle configuration deletion status")
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
    domain_id = properties.get("domain_id", "")
    config_name = properties.get("lifecycle_config_name", "")
    physical_resource_id = event.get("PhysicalResourceId", "")

    if request_type == "Create":
        return create_lifecycle_config(domain_id, config_name)

    if request_type == "Update":
        return update_lifecycle_config(domain_id, config_name, physical_resource_id)

    if request_type == "Delete":
        return delete_lifecycle_config(config_name, physical_resource_id)

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
    config_name = properties.get("lifecycle_config_name", "")

    if request_type == "Create":
        return is_creation_complete()

    if request_type == "Update":
        return is_update_complete()

    if request_type == "Delete":
        return is_deletion_complete(config_name)

    raise ValueError(f"Invalid request type: {request_type}")
