import csv
import io
import json
from decimal import Decimal
from typing import Any, Dict, List

import boto3
from botocore.config import Config

config = Config(retries={"max_attempts": 5, "mode": "adaptive"})

sqs = boto3.client("sqs")
dynamodb_client = boto3.client("dynamodb")
sagemaker_client = boto3.client("sagemaker")
dynamodb_resource = boto3.resource("dynamodb")
sagemaker_runtime_client = boto3.client("runtime.sagemaker", config=config)


def get_items_from_dynamodb_table(
    table_name: str, partition_key: str, attribute_value: str
) -> Dict[str, Any]:
    """Retrieves items from DynamoDB table based on partition key.

    Args:
        table_name: Name of the DynamoDB table.
        partition_key: Name of the partition key attribute.
        attribute_value: Value to query for.

    Returns:
        Dictionary containing the retrieved item data.

    Raises:
        ClientError: If DynamoDB operation fails.
    """
    table = dynamodb_resource.Table(table_name)
    response = table.get_item(Key={partition_key: attribute_value})
    return response


def convert_floats_to_decimals(obj: Any) -> Any:
    """Recursively converts float values to Decimal for DynamoDB compatibility.

    Args:
        obj: Input object that may contain float values.

    Returns:
        Object with all float values converted to Decimal.
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimals(item) for item in obj]
    return obj


def write_single_item_to_dynamodb(
    item: Dict[str, Any], table_name: str
) -> Dict[str, Any]:
    """Writes a single item to DynamoDB table.

    Args:
        item: Dictionary containing item data to write.
        table_name: Name of the DynamoDB table.

    Returns:
        DynamoDB response dictionary.

    Raises:
        ClientError: If DynamoDB operation fails.
    """
    table = dynamodb_resource.Table(table_name)
    response = table.put_item(Item=item)
    return response


def get_desired_endpoint_name(endpoint_name: str) -> str:
    """Retrieves the full name of an active SageMaker endpoint.

    Args:
        endpoint_name: Partial or full name of the endpoint to search for.

    Returns:
        Full endpoint name if exactly one match is found,
        or "Endpoint not found" if no matches exist.

    Raises:
        ValueError: If multiple matching endpoints are found.
    """
    response = sagemaker_client.list_endpoints(
        NameContains=endpoint_name, StatusEquals="InService", MaxResults=100
    )

    if not response["Endpoints"]:
        return "Endpoint not found"

    if len(response["Endpoints"]) > 1:
        raise ValueError(f"Multiple endpoints found matching: {endpoint_name}")

    return response["Endpoints"][0]["EndpointName"]


def convert_list_to_csv_string(csv_list: List[Any]) -> bytes:
    """Converts a list to CSV-formatted bytes.

    Args:
        csv_list: List of values to convert to CSV format.

    Returns:
        UTF-8 encoded bytes containing CSV data.
    """
    # Convert list to CSV string
    csv_string = io.StringIO()
    csv_writer = csv.writer(csv_string)
    csv_writer.writerow(csv_list)

    csv_string = csv_string.getvalue()
    return csv_string.encode("utf-8")


def query_endpoint(payload: bytes, endpoint_name: str) -> Dict[str, Any]:
    """Queries a SageMaker endpoint with CSV payload.

    Args:
        payload: UTF-8 encoded CSV data.
        endpoint_name: Name of the SageMaker endpoint to query.

    Returns:
        Raw response from SageMaker endpoint.

    Raises:
        ClientError: If endpoint invocation fails.
    """
    response = sagemaker_runtime_client.invoke_endpoint(
        EndpointName=endpoint_name, ContentType="text/csv", Body=payload
    )
    return response


def parse_response(query_response: Dict[str, Any]) -> Any:
    """Parses the response from a SageMaker endpoint.

    Args:
        query_response: Raw response from SageMaker endpoint.

    Returns:
        Parsed prediction data from the endpoint response.

    Raises:
        JSONDecodeError: If response body cannot be parsed as JSON.
    """
    prediction = json.loads(query_response["Body"].read())
    return prediction
