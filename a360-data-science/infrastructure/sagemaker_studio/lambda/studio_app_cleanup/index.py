"""
Lambda handlers for SageMaker Studio application cleanup custom resource.

This module provides the Lambda functions required to implement a custom resource
for safely cleaning up SageMaker Studio applications, spaces, and user profiles
when deleted.
"""

import datetime
from typing import Any, Dict, List, TypedDict

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
sagemaker_client = boto3.client("sagemaker")


class AppConfig(TypedDict, total=False):
    """
    Type definition for SageMaker Studio application configuration.

    Attributes:
        DomainId: ID of the SageMaker domain
        UserProfileName: Name of the user profile (if applicable)
        SpaceName: Name of the space (if applicable)
        AppType: Type of the Studio application
        AppName: Name of the application
        Status: Current status of the application
        CreationTime: When the application was created
    """

    DomainId: str
    UserProfileName: str
    SpaceName: str
    AppType: str
    AppName: str
    Status: str
    CreationTime: datetime.datetime


class SpaceConfig(TypedDict, total=False):
    """
    Type definition for SageMaker Studio space configuration.

    Attributes:
        DomainId: ID of the SageMaker domain
        SpaceName: Name of the space
        Status: Current status of the space
        CreationTime: When the space was created
        LastModifiedTime: When the space was last modified
        SpaceSettingsSummary: Summary of space settings
        SpaceSharingSettingsSummary: Summary of space sharing settings
        OwnershipSettingsSummary: Summary of ownership settings
        SpaceDisplayName: Display name of the space
    """

    DomainId: str
    SpaceName: str
    Status: str
    CreationTime: datetime.datetime
    LastModifiedTime: datetime.datetime
    SpaceSettingsSummary: Dict[str, Any]
    SpaceSharingSettingsSummary: Dict[str, Any]
    OwnershipSettingsSummary: Dict[str, Any]
    SpaceDisplayName: str


def delete_studio_apps(apps: List[AppConfig]) -> List[AppConfig]:
    """
    Delete a list of SageMaker Studio applications.

    Args:
        apps: List of application configurations to delete

    Returns:
        List of applications that failed to delete
    """
    failed_apps = []

    for app in apps:
        try:
            if app.get("Status") != "InService":
                continue

            delete_params = {
                "DomainId": app["DomainId"],
                "AppName": app["AppName"],
                "AppType": app["AppType"],
            }

            if app.get("UserProfileName"):
                delete_params["UserProfileName"] = app["UserProfileName"]
            elif app.get("SpaceName"):
                delete_params["SpaceName"] = app["SpaceName"]

            logger.info("Deleting Studio application", extra=delete_params)
            sagemaker_client.delete_app(**delete_params)

        except Exception:
            logger.exception("Failed to delete Studio application", extra={"app": app})
            failed_apps.append(app)

    return failed_apps


@logger.inject_lambda_context
def on_create(event: Dict[str, Any], context: LambdaContext) -> Dict[str, str]:
    """
    Handle the Create event for the custom resource.

    Not required for Studio app cleanup, but provided for completeness.

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

    Not required for Studio app cleanup, but provided for completeness.

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


def on_delete(
    domain_id: str, user_profile_name: str, space_name: str, physical_resource_id: str
) -> Dict[str, Any]:
    """
    Handle the Delete event for the custom resource.

    Args:
        domain_id: ID of the SageMaker domain
        user_profile_name: Name of the user profile to delete
        space_name: Name of the space to delete
        physical_resource_id: Physical resource ID of the custom resource

    Returns:
        Dictionary indicating the result of the operation
    """
    logger.info(
        "Delete event handler invoked",
        extra={
            "domain_id": domain_id,
            "user_profile_name": user_profile_name,
            "space_name": space_name,
        },
    )

    try:
        profile_apps = []
        space_apps = []

        if user_profile_name:
            profile_apps = sagemaker_client.list_apps(
                DomainIdEquals=domain_id, UserProfileNameEquals=user_profile_name
            ).get("Apps", [])

        if space_name:
            space_apps = sagemaker_client.list_apps(
                DomainIdEquals=domain_id, SpaceNameEquals=space_name
            ).get("Apps", [])

        all_apps = {"Apps": profile_apps + space_apps}

        logger.info(
            "Retrieved Studio applications",
            extra={"app_count": len(all_apps.get("Apps", []))},
        )

        failed_apps = delete_studio_apps(all_apps)

        if failed_apps:
            failure_details = [
                {
                    "profile": app.get("UserProfileName", ""),
                    "space": app.get("SpaceName", ""),
                    "app": app.get("AppName", ""),
                }
                for app in failed_apps
            ]

            logger.error(
                "Failed to delete some Studio applications",
                extra={"failures": failure_details},
            )

            return {
                "Status": "FAILED",
                "PhysicalResourceId": physical_resource_id,
                "Reason": f"Failed to delete some Studio applications: {failure_details}",
            }

        return {"Status": "SUCCESS", "PhysicalResourceId": physical_resource_id}

    except Exception:
        logger.exception("Error handling Studio app cleanup")
        return {"Status": "FAILED", "PhysicalResourceId": physical_resource_id}


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
    user_profile_name = properties.get("user_profile_name", "")
    space_name = properties.get("space_name", "")
    physical_resource_id = event.get("PhysicalResourceId", "")

    if request_type == "Create":
        return on_create(event, context)

    if request_type == "Update":
        return on_update(event, context)

    if request_type == "Delete":
        return on_delete(domain_id, user_profile_name, space_name, physical_resource_id)

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

    if request_type == "Create":
        return is_create_complete(event, context)

    if request_type == "Update":
        return is_update_complete(event, context)

    if request_type == "Delete":
        return {"IsComplete": True}  # Studio apps are deleted synchronously

    raise ValueError(f"Invalid request type: {request_type}")
