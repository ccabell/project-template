"""
Lambda handler for enabling SageMaker Projects and ServiceCatalog integration.

This module provides Lambda handlers for a custom resource that enables
SageMaker Projects and associates execution roles with ServiceCatalog portfolios.
"""

import time
from typing import Any, Dict, List

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
sagemaker_client = boto3.client("sagemaker")
servicecatalog_client = boto3.client("servicecatalog")


def enable_sagemaker_portfolio(execution_roles: List[str]) -> None:
    """
    Enable SageMaker ServiceCatalog portfolio and associate roles.

    Args:
        execution_roles: List of IAM role ARNs to associate with the portfolio

    Raises:
        Exception: If enabling the portfolio or associating roles fails
    """
    logger.info("Enabling SageMaker ServiceCatalog portfolio")
    try:
        sagemaker_client.enable_sagemaker_servicecatalog_portfolio()
        logger.info("SageMaker ServiceCatalog portfolio enabled successfully")
    except Exception:
        logger.exception("Failed to enable SageMaker ServiceCatalog portfolio")
        raise

    time.sleep(10)  # Allow time for portfolio to be created

    try:
        portfolio_shares = servicecatalog_client.list_accepted_portfolio_shares()
        logger.info("Retrieved portfolio shares", extra={"shares": portfolio_shares})
    except Exception:
        logger.exception("Failed to list portfolio shares")
        raise

    for portfolio in portfolio_shares.get("PortfolioDetails", []):
        if "SageMaker" in portfolio.get("DisplayName", ""):
            portfolio_id = portfolio.get("Id")
            logger.info(
                "Found SageMaker portfolio", extra={"portfolio_id": portfolio_id}
            )

            for role_arn in execution_roles:
                try:
                    logger.info(
                        "Associating role with portfolio",
                        extra={"role_arn": role_arn, "portfolio_id": portfolio_id},
                    )

                    servicecatalog_client.associate_principal_with_portfolio(
                        PortfolioId=portfolio_id,
                        PrincipalARN=role_arn,
                        PrincipalType="IAM",
                    )

                    logger.info(
                        "Successfully associated role with portfolio",
                        extra={"role_arn": role_arn},
                    )
                except Exception:
                    logger.exception(
                        "Failed to associate role with portfolio",
                        extra={"role_arn": role_arn},
                    )
                    raise


@logger.inject_lambda_context
def on_event_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Handle custom resource lifecycle events.

    Args:
        event: CloudFormation custom resource event
        context: Lambda execution context

    Returns:
        Response dictionary based on the event type
    """
    logger.set_correlation_id(context.aws_request_id)
    logger.info(
        "SageMaker Projects custom resource event received", extra={"event": event}
    )

    request_type = event["RequestType"]
    properties = event.get("ResourceProperties", {})
    physical_resource_id = event.get(
        "PhysicalResourceId", f"sagemaker-projects-{context.aws_request_id}"
    )

    if request_type == "Create" or request_type == "Update":
        try:
            execution_roles = properties.get("ExecutionRoles", [])

            if not execution_roles:
                raise ValueError("No execution roles provided")

            enable_sagemaker_portfolio(execution_roles)

            return {
                "Status": "SUCCESS",
                "PhysicalResourceId": physical_resource_id,
                "Data": {"Message": "Successfully enabled SageMaker Projects"},
            }
        except Exception as e:
            logger.exception("Failed to enable SageMaker Projects")
            return {
                "Status": "FAILED",
                "PhysicalResourceId": physical_resource_id,
                "Reason": str(e),
            }

    if request_type == "Delete":
        return {
            "Status": "SUCCESS",
            "PhysicalResourceId": physical_resource_id,
            "Data": {"Message": "Delete operation is a no-op for SageMaker Projects"},
        }

    return {
        "Status": "FAILED",
        "PhysicalResourceId": physical_resource_id,
        "Reason": f"Unsupported request type: {request_type}",
    }
