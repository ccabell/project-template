"""Utility functions for S3 access across accounts.
This module provides functions to interact with S3 buckets in different AWS accounts.
"""

import logging

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_s3_client(profile_name: str | None = None) -> boto3.client:
    """Get an S3 client using the specified AWS profile.

    Args:
        profile_name (str, optional): AWS profile name to use. If None, uses default credentials.

    Returns:
        boto3.client: Configured S3 client
    """
    session = boto3.Session(profile_name=profile_name)
    return session.client("s3")


def list_bucket_objects(
    bucket_name: str,
    prefix: str = "",
    profile_name: str | None = None,
) -> list[str]:
    """List objects in an S3 bucket with the given prefix.

    Args:
        bucket_name (str): Name of the S3 bucket
        prefix (str, optional): Prefix to filter objects. Defaults to ''.
        profile_name (str, optional): AWS profile name to use. Defaults to None.

    Returns:
        List[str]: List of object keys in the bucket

    Raises:
        ClientError: If there's an error accessing the bucket
    """
    try:
        s3_client = get_s3_client(profile_name)
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

        if "Contents" not in response:
            logger.info(
                f"No objects found in bucket {bucket_name} with prefix {prefix}",
            )
            return []

        return [obj["Key"] for obj in response["Contents"]]

    except ClientError as e:
        logger.exception(f"Error listing objects in bucket {bucket_name}: {e!s}")
        raise


def read_object(
    bucket_name: str,
    object_key: str,
    profile_name: str | None = None,
) -> bytes:
    """Read an object from an S3 bucket.

    Args:
        bucket_name (str): Name of the S3 bucket
        object_key (str): Key of the object to read
        profile_name (str, optional): AWS profile name to use. Defaults to None.

    Returns:
        bytes: Contents of the object

    Raises:
        ClientError: If there's an error reading the object
    """
    try:
        s3_client = get_s3_client(profile_name)
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        return response["Body"].read()

    except ClientError as e:
        logger.exception(
            f"Error reading object {object_key} from bucket {bucket_name}: {e!s}",
        )
        raise


def test_bucket_access(
    bucket_name: str,
    profile_name: str | None = None,
    prefix: str = "",
) -> bool:
    """Test access to an S3 bucket by attempting to list objects.

    Args:
        bucket_name (str): Name of the S3 bucket to test
        profile_name (str, optional): AWS profile name to use. Defaults to None.
        prefix (str, optional): Prefix to filter objects. Defaults to ''.

    Returns:
        bool: True if access is successful, False otherwise
    """
    try:
        objects = list_bucket_objects(bucket_name, prefix, profile_name)
        logger.info(
            f"Successfully accessed bucket {bucket_name}. Found {len(objects)} objects.",
        )
        return True
    except ClientError as e:
        logger.exception(f"Failed to access bucket {bucket_name}: {e!s}")
        return False
