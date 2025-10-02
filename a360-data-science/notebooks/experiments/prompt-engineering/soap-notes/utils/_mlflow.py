from typing import Any

import mlflow
from mlflow.entities import Experiment

from .aws import sagemaker_client
from .bedrock import BedrockModel


def set_sagemaker_tracking_server(server_name: str) -> str:
    """
    Sets existing MLflow Tracking Server as active

    Args:
        server_name: Name of the MLflow Tracking Server

    Returns:
        ARN of the MLflow Tracking Server

    Raises:
        SageMaker.Client.exceptions.ResourceNotFound: If the server with the specified name does not exist
    """
    tracking_server_arn = sagemaker_client.describe_mlflow_tracking_server(
        TrackingServerName=server_name
    )["TrackingServerArn"]
    mlflow.set_tracking_uri(tracking_server_arn)
    return tracking_server_arn


def set_experiment(
    name: str, tags: dict[str, str] | None = None
) -> Experiment:
    """Set an MLflow experiment by name.

    If the experiment does not exist, it will be created, optionally specifying
    the tags.

    Args:
        name: Name of the experiment.
        tags: Optional tags to assign when creating a new experiment.

    Returns:
        The active MLflow experiment.
    """
    experiment = mlflow.get_experiment_by_name(name)
    if experiment is None:
        experiment = mlflow.create_experiment(name, tags=tags)
    return mlflow.set_experiment(name)


def log_model_params(
    model: BedrockModel, param_prefix: str | None = None
) -> dict[str, Any]:
    """Log parameters of a `BedrockModel` to the current MLflow run.

    Parameters are extracted from the model's attributes and optionally prefixed.

    Args:
        model: The model whose parameters should be logged.
        param_prefix: Optional prefix to add to each parameter key.

    Returns:
        The dictionary of logged parameters.
    """
    params = {
        "model": model.id,
        "inferenceConfig": model.inf_config,
        "additionalModelRequestFields": model.additional_req_fields,
        "isReasoner": model.is_reasoner,
        **model.info,
    }
    if param_prefix is not None:
        params = {param_prefix + k: v for k, v in params.items()}
    mlflow.log_params(params)
    return params