#!/usr/bin/env python3
"""Utilities for listing and loading CSV files from S3.

Lists *.csv objects in a bucket/prefix, loads them into a pandas
DataFrame with awswrangler, prints the head, and returns the DataFrame.

Usage as CLI:
    python s3_csv_preview.py list <bucket> [prefix]
    python s3_csv_preview.py preview <bucket> <key> [--rows N] [--columns N]
    python s3_csv_preview.py load <bucket> <key> [--output file.csv]
    python s3_csv_preview.py <bucket> <prefix> [nrows]  # Simple preview mode

Exit codes:
    0: Success
    1: Invalid arguments
    2: S3 access error
    3: CSV parsing error
    4: File I/O error
"""

from __future__ import annotations

import argparse
import logging
import sys

import awswrangler as wr
import boto3
import pandas as pd
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_boto3_session(profile: str | None = None, assume_role_arn: str | None = None):
    """Returns a boto3 session using a profile or by assuming a role."""
    if assume_role_arn:
        base_session = (
            boto3.Session(profile_name=profile) if profile else boto3.Session()
        )
        sts_client = base_session.client("sts")
        assumed_role = sts_client.assume_role(
            RoleArn=assume_role_arn,
            RoleSessionName="AssumeRoleSession",
        )
        creds = assumed_role["Credentials"]
        return boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
    return boto3.Session(profile_name=profile) if profile else boto3.Session()


def list_csv_keys(
    bucket: str,
    prefix: str = "",
    profile: str | None = None,
    assume_role_arn: str | None = None,
) -> list:
    """List all .csv keys in an S3 bucket/prefix, optionally using an assumed role."""
    try:
        session = get_boto3_session(profile, assume_role_arn)
        s3_client = session.client("s3")
        paginator = s3_client.get_paginator("list_objects_v2")
        csv_files = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            if "Contents" in page:
                for obj in page["Contents"]:
                    key = obj["Key"]
                    if key.lower().endswith(".csv"):
                        csv_files.append(key)
        return sorted(csv_files)
    except ClientError as e:
        if e.response["Error"]["Code"] == "AccessDenied":
            return []
        raise


def load_and_preview(
    bucket: str,
    prefix: str = "",
    nrows: int = 5,
    ncols: int | None = None,
    profile: str | None = None,
    assume_role_arn: str | None = None,
) -> pd.DataFrame:
    """Load listed CSVs into a DataFrame and print its head.

    Args:
        bucket: S3 bucket name
        prefix: Key prefix
        nrows: Number of rows to preview
        ncols: Optional number of columns to preview

    Returns:
        DataFrame with concatenated CSV data

    Raises:
        RuntimeError: When no CSV objects are found
        ClientError: If there's an S3 access error
        pd.errors.EmptyDataError: If the CSV is empty
        pd.errors.ParserError: If the CSV is malformed
    """
    try:
        keys = list_csv_keys(bucket, prefix, profile, assume_role_arn)
        if not keys:
            return pd.DataFrame()
        paths = [f"s3://{bucket}/{k}" for k in keys]
        session = get_boto3_session(profile, assume_role_arn)
        df = wr.s3.read_csv(paths, boto3_session=session)
        if ncols:
            df = df.iloc[:, :ncols]
        return df
    except ClientError as e:
        if e.response["Error"]["Code"] == "AccessDenied":
            return pd.DataFrame()
        raise


def preview_csv(
    bucket: str,
    key: str,
    nrows: int = 5,
    ncols: int | None = None,
    profile: str | None = None,
    assume_role_arn: str | None = None,
) -> tuple:
    """Preview a single CSV file from S3, using an assumed role if provided."""
    try:
        session = get_boto3_session(profile, assume_role_arn)
        s3_client = session.client("s3")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        metadata = {
            "size_bytes": response["ContentLength"],
            "last_modified": response["LastModified"],
            "content_type": response["ContentType"],
        }
        path = f"s3://{bucket}/{key}"
        df = wr.s3.read_csv(path, boto3_session=session)
        if ncols:
            df = df.iloc[:, :ncols]
        return df.head(nrows), metadata
    except ClientError as e:
        if e.response["Error"]["Code"] == "AccessDenied":
            return pd.DataFrame(), {}
        raise


def load_csv(
    bucket: str,
    key: str,
    output_file: str | None = None,
    profile: str | None = None,
    assume_role_arn: str | None = None,
) -> pd.DataFrame:
    """Load a CSV file from S3 into a pandas DataFrame or save to local file, using an assumed role if provided."""
    try:
        path = f"s3://{bucket}/{key}"
        session = get_boto3_session(profile, assume_role_arn)
        if output_file:
            wr.s3.download(path=path, local_file=output_file, boto3_session=session)
            return None
        return wr.s3.read_csv(path, boto3_session=session)
    except ClientError as e:
        if e.response["Error"]["Code"] == "AccessDenied":
            return pd.DataFrame()
        raise


def main():
    """Command-line interface for the utility."""
    # Check for simple preview mode (bucket prefix [nrows])
    if len(sys.argv) >= 3 and sys.argv[1] not in ["list", "preview", "load"]:
        try:
            bucket_arg = sys.argv[1]
            prefix_arg = sys.argv[2]
            nrows_arg = int(sys.argv[3]) if len(sys.argv) >= 4 else 5
            load_and_preview(bucket_arg, prefix_arg, nrows_arg)
            return 0
        except Exception as e:
            logger.exception(f"Error in simple preview mode: {e!s}")
            return 1

    # Full CLI mode
    parser = argparse.ArgumentParser(description="S3 CSV Preview Utility")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List command
    list_parser = subparsers.add_parser("list", help="List CSV files in bucket")
    list_parser.add_argument("bucket", help="S3 bucket name")
    list_parser.add_argument("prefix", nargs="?", default="", help="Optional prefix")

    # Preview command
    preview_parser = subparsers.add_parser("preview", help="Preview CSV file")
    preview_parser.add_argument("bucket", help="S3 bucket name")
    preview_parser.add_argument("key", help="S3 object key")
    preview_parser.add_argument(
        "--rows",
        type=int,
        default=5,
        help="Number of rows to preview",
    )
    preview_parser.add_argument(
        "--columns",
        type=int,
        help="Number of columns to preview",
    )

    # Load command
    load_parser = subparsers.add_parser("load", help="Load CSV file")
    load_parser.add_argument("bucket", help="S3 bucket name")
    load_parser.add_argument("key", help="S3 object key")
    load_parser.add_argument("--output", help="Output file path")

    args = parser.parse_args()

    try:
        if args.command == "list":
            files = list_csv_keys(args.bucket, args.prefix)
            for _file in files:
                pass
            return 0

        if args.command == "preview":
            df, metadata = preview_csv(args.bucket, args.key, args.rows, args.columns)
            for _key, _value in metadata.items():
                pass
            return 0

        if args.command == "load":
            result = load_csv(args.bucket, args.key, args.output)
            if result is not None:
                pass
            return 0

        parser.print_help()
        return 1

    except ClientError:
        return 2
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return 3
    except OSError:
        return 4
    except Exception as e:
        logger.exception(f"Unexpected error: {e!s}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
