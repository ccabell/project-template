#!/usr/bin/env python
"""Utilities for listing and loading CSV files from S3.

Lists *.csv objects in a bucket/prefix, loads them into a pandas
DataFrame with awswrangler, prints the head, and returns the DataFrame.

Example:
    $ python s3_csv_preview.py my-bucket sample_prefix 10
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import awswrangler as wr
import boto3

if TYPE_CHECKING:
    import pandas as pd


def list_csv_keys(bucket: str, prefix: str = "") -> list[str]:
    """Return keys of all .csv objects in an S3 prefix.

    Args:
        bucket: S3 bucket name.
        prefix: Key prefix.

    Returns:
        list[str]: CSV object keys.
    """
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
    return [
        obj["Key"]
        for page in pages
        for obj in page.get("Contents", [])
        if obj["Key"].lower().endswith(".csv")
    ]


def load_and_preview(bucket: str, prefix: str = "", n: int = 5) -> pd.DataFrame:
    """Load listed CSVs into a DataFrame and print its head.

    Args:
        bucket: S3 bucket.
        prefix: Key prefix.
        n: Rows to display with `head()`.

    Returns:
        pd.DataFrame: Concatenated DataFrame.

    Raises:
        RuntimeError: When no CSV objects are found.
    """
    keys = list_csv_keys(bucket, prefix)
    if not keys:
        msg = f"No CSV files found in s3://{bucket}/{prefix}"
        raise RuntimeError(msg)
    paths = [f"s3://{bucket}/{k}" for k in keys]
    return wr.s3.read_csv(paths)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        msg = "Usage: python s3_csv_preview.py <bucket> <prefix> [nrows]"
        raise SystemExit(msg)
    bucket_arg = sys.argv[1]
    prefix_arg = sys.argv[2]
    nrows_arg = int(sys.argv[3]) if len(sys.argv) >= 4 else 5
    load_and_preview(bucket_arg, prefix_arg, nrows_arg)
