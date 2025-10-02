# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "boto3",
#     "pandas",
#     "pyarrow",
# ]
# ///
import argparse
import contextlib
import os
import urllib.request

import boto3
import pandas as pd
from botocore.exceptions import NoCredentialsError


def download_sample_data() -> str:
    """Downloads sample CSV and Parquet files and stores them locally.

    Returns:
        str: The local directory containing the downloaded data.
    """
    os.makedirs("data", exist_ok=True)

    csv_url = "https://people.sc.fsu.edu/~jburkardt/data/csv/airtravel.csv"
    csv_path = "data/air_travel_data.csv"
    # Security: downloading from trusted HTTPS source for sample data
    urllib.request.urlretrieve(csv_url, csv_path)  # noqa: S310

    parquet_url = "https://github.com/Teradata/kylo/raw/master/samples/sample-data/parquet/userdata1.parquet"
    parquet_path = "data/user_data.parquet"
    # Security: downloading from trusted HTTPS source for sample data
    urllib.request.urlretrieve(parquet_url, parquet_path)  # noqa: S310

    return "data"


def clean_csv(file_path: str) -> str:
    """Cleans a CSV file by removing quotes from headers and values.

    Args:
        file_path (str): The path to the original CSV file.

    Returns:
        str: The path to the cleaned CSV file.
    """
    cleaned_path = file_path.replace(".csv", "_cleaned.csv")
    df = pd.read_csv(file_path, quotechar='"', skipinitialspace=True)
    df.to_csv(cleaned_path, index=False)
    return cleaned_path


def upload_to_s3(
    local_directory: str,
    bucket_name: str,
    prefix: str,
    profile: str,
) -> list[str]:
    """Uploads files from a local directory to an S3 bucket under a specified prefix.

    Args:
        local_directory (str): The path to the local directory containing files to upload.
        bucket_name (str): The name of the S3 bucket.
        prefix (str): The S3 prefix under which to store data.
        profile (str): The AWS CLI profile to use for authentication.

    Returns:
        List[str]: A list of S3 keys for the uploaded files.
    """
    session = boto3.Session(profile_name=profile)
    s3 = session.client("s3")
    uploaded_files = []

    for root, _, files in os.walk(local_directory):
        for file in files:
            file_path = os.path.join(root, file)
            s3_key = os.path.join(prefix, file)

            try:
                s3.upload_file(file_path, bucket_name, s3_key)
                uploaded_files.append(s3_key)
            except NoCredentialsError as e:
                msg = "AWS credentials not found."
                raise RuntimeError(msg) from e

    return uploaded_files


def create_glue_table(
    database_name: str,
    table_name: str,
    bucket_name: str,
    prefix: str,
    schema: list[dict],
    profile: str,
    file_format: str = "csv",
) -> None:
    """Creates a Glue table configured for Athena queries.

    Args:
        database_name: The name of the Glue database.
        table_name: The name of the Glue table.
        bucket_name: The name of the S3 bucket containing the data.
        prefix: The S3 prefix where the data is stored.
        schema: The schema for the Glue table as a list of column definitions.
        profile: The AWS CLI profile to use for authentication.
        file_format: The format of the source files ('csv' or 'parquet').
    """
    session = boto3.Session(profile_name=profile)
    glue = session.client("glue")

    storage_descriptor = {
        "Columns": schema,
        "Location": f"s3://{bucket_name}/{prefix}",
    }

    if file_format == "csv":
        storage_descriptor.update(
            {
                "InputFormat": "org.apache.hadoop.mapred.TextInputFormat",
                "OutputFormat": "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat",
                "SerdeInfo": {
                    "SerializationLibrary": "org.apache.hadoop.hive.serde2.OpenCSVSerde",
                    "Parameters": {
                        "separatorChar": ",",
                        "quoteChar": '"',
                        "escapeChar": "\\",
                    },
                },
                "Parameters": {"skip.header.line.count": "1", "classification": "csv"},
            },
        )
    elif file_format == "parquet":
        storage_descriptor.update(
            {
                "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                "SerdeInfo": {
                    "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe",
                    "Parameters": {"serialization.format": "1"},
                },
                "Parameters": {"classification": "parquet"},
            },
        )
    else:
        msg = f"Unsupported file format: {file_format}"
        raise ValueError(msg)

    table_input = {
        "Name": table_name,
        "StorageDescriptor": storage_descriptor,
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {"classification": file_format},
    }

    try:
        glue.create_table(DatabaseName=database_name, TableInput=table_input)
    except glue.exceptions.AlreadyExistsException:
        glue.update_table(DatabaseName=database_name, TableInput=table_input)


def create_sample_data() -> str:
    """Creates and stores sample CSV and Parquet test data locally.

    Generates two test datasets:
    1. Sales data in CSV format with clean headers and consistent types
    2. Customer data in Parquet format with proper schema definition

    Returns:
        Directory path containing the generated sample data files.

    Raises:
        OSError: If directory creation or file writing fails.
    """
    from datetime import datetime, timedelta

    import numpy as np
    import pandas as pd

    os.makedirs("data", exist_ok=True)

    sales_data = pd.DataFrame(
        {
            "transaction_date": pd.date_range(
                start="2023-01-01",
                end="2023-12-31",
                freq="D",
            ),
            "product_id": np.random.randint(1000, 9999, size=365),
            "quantity": np.random.randint(1, 100, size=365),
            "amount": np.random.uniform(10.0, 1000.0, size=365).round(2),
        },
    )

    sales_data["transaction_date"] = sales_data["transaction_date"].dt.strftime(
        "%Y-%m-%d",
    )
    sales_data.to_csv("data/sales_data.csv", index=False)

    customer_data = pd.DataFrame(
        {
            "customer_id": range(1, 1001),
            "registration_date": [
                datetime.now() - timedelta(days=x) for x in range(1000)
            ],
            "name": [f"Customer_{i}" for i in range(1, 1001)],
            "email": [f"customer_{i}@example.com" for i in range(1, 1001)],
            "total_purchases": np.random.uniform(100.0, 10000.0, size=1000).round(2),
        },
    )

    customer_data.to_parquet("data/customer_data.parquet", index=False)

    return "data"


def main(bucket_name: str, prefix: str, profile: str) -> None:
    """Creates and uploads sample data, configuring Glue tables for Athena queries.

    Args:
        bucket_name: Target S3 bucket name.
        prefix: S3 prefix for data storage.
        profile: AWS credential profile.

    Raises:
        RuntimeError: If AWS credentials are invalid.
        boto3.client.exceptions.ClientError: If AWS operations fail.
    """
    database_name = "raw"
    local_data_path = create_sample_data()
    upload_to_s3(local_data_path, bucket_name, prefix, profile)

    csv_schema = [
        {"Name": "transaction_date", "Type": "string"},
        {"Name": "product_id", "Type": "int"},
        {"Name": "quantity", "Type": "int"},
        {"Name": "amount", "Type": "double"},
    ]

    parquet_schema = [
        {"Name": "customer_id", "Type": "int"},
        {"Name": "registration_date", "Type": "timestamp"},
        {"Name": "name", "Type": "string"},
        {"Name": "email", "Type": "string"},
        {"Name": "total_purchases", "Type": "double"},
    ]

    session = boto3.Session(profile_name=profile)
    glue = session.client("glue")

    with contextlib.suppress(glue.exceptions.AlreadyExistsException):
        glue.create_database(DatabaseInput={"Name": database_name})

    create_glue_table(
        database_name=database_name,
        table_name="sales_data",
        bucket_name=bucket_name,
        prefix=f"{prefix}/sales_data.csv",
        schema=csv_schema,
        profile=profile,
        file_format="csv",
    )

    create_glue_table(
        database_name=database_name,
        table_name="customer_data",
        bucket_name=bucket_name,
        prefix=f"{prefix}/customer_data.parquet",
        schema=parquet_schema,
        profile=profile,
        file_format="parquet",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upload data to S3 and create Glue resources.",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default="a360-datalake-raw-bucket-863518416131-us-east-1",
        help="Name of the S3 bucket to upload data to.",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="sample_data",
        help="S3 prefix under which to store data.",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default="DataLake-Staging",
        help="AWS CLI profile name to use for authentication.",
    )

    args = parser.parse_args()

    main(bucket_name=args.bucket, prefix=args.prefix, profile=args.profile)
