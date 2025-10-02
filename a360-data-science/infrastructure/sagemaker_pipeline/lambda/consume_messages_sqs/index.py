import datetime
import json
import os
import uuid
from datetime import timezone
from typing import Any, Dict

from helper import (
    convert_floats_to_decimals,
    convert_list_to_csv_string,
    get_desired_endpoint_name,
    parse_response,
    query_endpoint,
    write_single_item_to_dynamodb,
)


def process_sqs_message(
    event: Dict[str, Any], inference_table: str, partition_key: str
) -> Dict[str, Any]:
    """Processes a single SQS message containing inference data.

    Extracts data from the message, performs model inference, and stores
    results in DynamoDB with additional metadata.

    Args:
        event: Lambda event containing SQS message data.
        inference_table: Name of DynamoDB table for storing results.
        partition_key: Primary key name for DynamoDB table.

    Returns:
        Dictionary containing processed item data.

    Raises:
        KeyError: If required fields are missing from message.
        JSONDecodeError: If message body is not valid JSON.
    """
    body = event["Records"][0]["body"]
    item_dict = json.loads(body)

    desired_dim = item_dict.pop("desired_dim")
    ground_truth = item_dict.pop("Churn?_True.")

    csv_list = [value for key, value in item_dict.items()]
    payload = convert_list_to_csv_string(csv_list)

    desired_endpoint_name = get_desired_endpoint_name(desired_dim)
    query_response = query_endpoint(payload, desired_endpoint_name)
    prediction = parse_response(query_response)

    current_datetime = datetime.datetime.now(timezone.utc)
    current_datetime_str = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

    result_dict = {
        "prediction": round(prediction),
        "prediction_prob": prediction,
        "ground_truth": ground_truth,
        "desired_dim": desired_dim,
        "created_at": current_datetime_str,
        partition_key: str(uuid.uuid4()),
        **item_dict,
    }

    processed_dict = convert_floats_to_decimals(result_dict)
    write_single_item_to_dynamodb(processed_dict, inference_table)

    return processed_dict


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, int]:
    """AWS Lambda handler for processing SQS messages with ML model inference.

    Processes messages containing feature data, performs model inference,
    and stores results in DynamoDB. Handles both production and development
    environments.

    Args:
        event: Lambda event containing SQS message data.
        context: Lambda context object.

    Returns:
        Dictionary with HTTP status code.

    Raises:
        Exception: If message processing fails.
    """
    try:
        inference_table = os.environ["inference_ddb_table"]
        partition_key = os.environ["partition_key"]
    except Exception:
        inference_table = "InferenceResultsStack-inferencetable513B141C-1S8SO4SMYKJD3"
        partition_key = "id"

    process_sqs_message(event, inference_table, partition_key)

    return {"statusCode": 200}


if __name__ == "__main__":
    test_event = {
        "Records": [
            {
                "body": '{"Churn?_True.":0,"Account Length":62.0,"VMail Message":0.0,"Day Mins":5.07215206,"Day Calls":5.0,"Eve Mins":6.60041134,"Eve Calls":2.0,"Night Mins":3.53350108,"Night Calls":300.0,"Intl Mins":4.3952999,"Intl Calls":7.0,"CustServ Calls":6.0,"Dimension":1.0,"State_AK":0.0,"State_AL":0.0,"State_AR":0.0,"State_AZ":0.0,"State_CA":0.0,"State_CO":0.0,"State_CT":0.0,"State_DC":0.0,"State_DE":0.0,"State_FL":0.0,"State_GA":0.0,"State_HI":0.0,"State_IA":0.0,"State_ID":0.0,"State_IL":0.0,"State_IN":0.0,"State_KS":0.0,"State_KY":0.0,"State_LA":0.0,"State_MA":0.0,"State_MD":0.0,"State_ME":0.0,"State_MI":0.0,"State_MN":0.0,"State_MO":0.0,"State_MS":0.0,"State_MT":0.0,"State_NC":0.0,"State_ND":0.0,"State_NE":0.0,"State_NH":0.0,"State_NJ":0.0,"State_NM":0.0,"State_NV":0.0,"State_NY":0.0,"State_OH":0.0,"State_OK":0.0,"State_OR":0.0,"State_PA":0.0,"State_RI":0.0,"State_SC":0.0,"State_SD":0.0,"State_TN":0.0,"State_TX":0.0,"State_UT":0.0,"State_VA":0.0,"State_VT":1.0,"State_WA":0.0,"State_WI":0.0,"State_WV":0.0,"State_WY":0.0,"Area Code_657":0.0,"Area Code_658":0.0,"Area Code_659":0.0,"Area Code_676":0.0,"Area Code_677":0.0,"Area Code_678":0.0,"Area Code_686":0.0,"Area Code_707":0.0,"Area Code_716":0.0,"Area Code_727":0.0,"Area Code_736":0.0,"Area Code_737":0.0,"Area Code_758":0.0,"Area Code_766":0.0,"Area Code_776":0.0,"Area Code_777":0.0,"Area Code_778":0.0,"Area Code_786":0.0,"Area Code_787":0.0,"Area Code_788":0.0,"Area Code_797":0.0,"Area Code_798":0.0,"Area Code_806":0.0,"Area Code_827":0.0,"Area Code_836":0.0,"Area Code_847":0.0,"Area Code_848":0.0,"Area Code_858":0.0,"Area Code_866":0.0,"Area Code_868":1.0,"Area Code_876":0.0,"Area Code_877":0.0,"Area Code_878\'":0.0," \\"Int\'l Plan_no\\"":0.0," \\"Int\'l Plan_yes\\"":1.0," \'VMail Plan_no":1.0,"VMail Plan_yes":0.0,"desired_dim":"DummyDim2"}'
            }
        ]
    }
    lambda_handler(test_event, None)
