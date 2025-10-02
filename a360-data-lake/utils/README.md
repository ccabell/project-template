# Data Lake Utilities

[![Python Version](https://img.shields.io/badge/python-3.12.9-blue.svg)](https://www.python.org/downloads/)
[![UV Package Manager](https://img.shields.io/badge/uv-0.7.9-green.svg)](https://github.com/astral-sh/uv)
[![AWS CDK](https://img.shields.io/badge/AWS%20CDK-2.176.0-orange.svg)](https://aws.amazon.com/cdk/)

This directory contains utility scripts and modules for working with the Data Lake infrastructure.

## Directory Structure

```
utils/
├── 📁 data/                                # Local data storage (gitignored)
│   ├── .gitignore                          # Git ignore for generated files
│   └── # Generated CSV/Parquet files stored here
├── 📄 s3_access.py                         # S3 bucket access and permissions
├── 📄 s3_csv_preview.py                    # CSV file operations in S3
├── 📄 s3_sample_data_uploader.py           # Sample data generator and uploader
└── 📄 README.md                            # This file
```

## Overview

This utility automates the process of creating sample data, uploading it to S3, and configuring AWS Glue databases and tables. Designed to simplify data pipeline creation for testing and development workflows.

## Features

- **Sample Data Generation**: Creates realistic CSV and Parquet datasets locally
- **S3 Upload**: Uploads datasets to specified S3 bucket and prefix  
- **Glue Integration**: Creates AWS Glue databases and external tables automatically
- **Configurable**: Supports custom buckets, prefixes, and AWS profiles


## Available Utilities

### s3_access.py
Utility module for managing S3 bucket access and permissions. Provides functions for:
- Checking bucket access
- Managing bucket policies
- Handling cross-account access

### s3_csv_preview.py
Stand-alone utility for working with CSV files in S3 buckets. Can be used both as a command-line tool and as an imported module.

#### Command-line Usage
```bash
# List CSV files in a bucket
python s3_csv_preview.py list <bucket> [prefix]

# Preview a CSV file
python s3_csv_preview.py preview <bucket> <key> [--rows N] [--columns N]

# Load a CSV file
python s3_csv_preview.py load <bucket> <key> [--output file.csv]
```

#### Exit Codes
- `0`: Success
- `1`: Invalid arguments
- `2`: S3 access error
- `3`: CSV parsing error
- `4`: File I/O error

#### Module Usage
```python
from utils.s3_csv_preview import list_csv_files, preview_csv, load_csv

# List CSV files
files = list_csv_files('my-bucket', prefix='data/')

# Preview a CSV
df, metadata = preview_csv('my-bucket', 'data/file.csv', nrows=5)

# Load a CSV
df = load_csv('my-bucket', 'data/file.csv')
# or save to file
load_csv('my-bucket', 'data/file.csv', output_file='local.csv')
```

#### Dependencies
- boto3
- pandas
- botocore

## Sample Data Uploader (`s3_sample_data_uploader.py`)

### Usage


```bash
# Basic usage with defaults
uv run s3_sample_data_uploader.py

# Custom configuration
uv run s3_sample_data_uploader.py \
  --bucket a360-datalake-raw-bucket-123456789012-us-east-1 \
  --prefix healthcare_samples \
  --profile DataLake-Dev

# Show help
uv run s3_sample_data_uploader.py --help
```

### Command-line Arguments

- `--bucket`: S3 bucket name (default: `a360-datalake-raw-bucket-863518416131-us-east-1`)
- `--prefix`: S3 prefix for data storage (default: `sample_data`) 
- `--profile`: AWS CLI profile (default: `DataLake-Staging`)

### Generated Datasets

**Sales Data (CSV)**
```csv
transaction_date,product_id,quantity,amount
2023-01-01,1234,5,157.50
2023-01-02,5678,2,89.99
...
```

**Customer Data (Parquet)**
- `customer_id`: int64
- `registration_date`: timestamp  
- `name`: string
- `email`: string
- `total_purchases`: float64

### AWS Glue Configuration

The script creates these AWS Glue resources:

**Database**: `raw` (created if not exists)

**Tables**:
- `sales_data` (CSV format with OpenCSV SerDe)
- `customer_data` (Parquet format with Parquet SerDe)

Each table includes:
- Proper schema definitions with correct data types
- SerDe configurations optimized for Athena queries
- Input/output format specifications

### Example Output

```bash
$ uv run s3_sample_data_uploader.py --bucket my-bucket --prefix test_data

Creating sample datasets...
✓ Generated sales_data.csv (365 records)
✓ Generated customer_data.parquet (1000 records)

Uploading to S3...
✓ Uploaded test_data/sales_data.csv
✓ Uploaded test_data/customer_data.parquet

Creating Glue resources...
✓ Database 'raw' ready
✓ Table 'sales_data' created
✓ Table 'customer_data' created

Sample data setup complete!
Query with: SELECT * FROM raw.sales_data LIMIT 10;
```

## Prerequisites

- **Python 3.12.9+** with uv package manager
- **AWS CLI v2** configured with appropriate profiles
- **AWS Permissions** for S3 and Glue operations

## Quick Setup

```bash
# Verify AWS credentials
aws sts get-caller-identity --profile DataLake-Dev

# Run the uploader
uv run s3_sample_data_uploader.py --profile DataLake-Dev
```

## Error Handling

The script includes robust error handling for:

- **Missing AWS credentials**: Validates credentials before execution
- **S3 access issues**: Handles bucket permission errors gracefully  
- **Existing resources**: Updates existing Glue tables instead of failing
- **Network issues**: Provides clear error messages for connectivity problems

### Common Troubleshooting

**AWS Credentials**
```bash
aws sts get-caller-identity --profile DataLake-Staging
```

**S3 Bucket Access**  
```bash
aws s3 ls s3://your-bucket-name --profile DataLake-Staging
```

**Glue Permissions**
```bash
aws glue get-database --name raw --profile DataLake-Staging
```

## Data Quality

Generated datasets follow these patterns:
- **Realistic data distributions**: Sales amounts, dates, and IDs follow logical patterns
- **Consistent schemas**: Proper data types for efficient querying
- **Query optimization**: Partitioning and compression for performance

## Contributing

1. Test changes with actual S3 and Glue services
2. Validate data quality of generated datasets  
3. Ensure error handling covers edge cases
4. Update documentation for any new parameters

## Cross-Account S3 Access Test Workflow (Notebook)

This workflow demonstrates how to:
- Create a sample CSV using pandas
- Upload it to a source S3 bucket using `upload_to_s3` from `s3_sample_data_uploader.py` and a specific AWS profile
- List and preview the CSV in S3 using `list_csv_keys` and `preview_csv` from `s3_csv_preview.py`, supporting both profile and assumed role access
- Clean up the sample data after testing

### Steps

1. **Create and Save Sample CSV**
   - Use pandas to create a DataFrame and save it as a CSV in `utils/data/`.
   - Example:
     ```python
     import pandas as pd
     import os
     df_sample = pd.DataFrame({
         'id': range(1, 6),
         'name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve'],
         'amount': [100.5, 200.0, 150.75, 300.2, 50.0]
     })
     local_dir = os.path.join('utils', 'data')
     os.makedirs(local_dir, exist_ok=True)
     local_csv_path = os.path.join(local_dir, 'cross_account_sample.csv')
     df_sample.to_csv(local_csv_path, index=False)
     ```

2. **Upload the CSV to S3**
   - Use `upload_to_s3` from `s3_sample_data_uploader.py` to upload the CSV to the source bucket and prefix using the target profile.
   - Example:
     ```python
     from utils.s3_sample_data_uploader import upload_to_s3
     uploaded_files = upload_to_s3(
         local_directory=local_dir,
         bucket_name=SOURCE_BUCKET,
         prefix=SAMPLE_PREFIX,
         profile=TARGET_PROFILE
     )
     ```

3. **List and Preview the CSV (with optional assumed role)**
   - Use `list_csv_keys` and `preview_csv` from `s3_csv_preview.py` to list and preview the uploaded CSV in S3. You can specify both `profile` and `assume_role_arn` for cross-account scenarios.
   - Example:
     ```python
     from utils.s3_csv_preview import list_csv_keys, preview_csv
     # Optionally set assume_role_arn for cross-account access
     ASSUME_ROLE_ARN = 'arn:aws:iam::<target-account-id>:role/<target-role-name>'
     csv_files = list_csv_keys(
         bucket=SOURCE_BUCKET,
         prefix=SAMPLE_PREFIX,
         profile=TARGET_PROFILE,  # or SOURCE_PROFILE
         assume_role_arn=ASSUME_ROLE_ARN  # Optional
     )
     if csv_files:
         df_preview, metadata = preview_csv(
             bucket=SOURCE_BUCKET,
             key=csv_files[0],
             nrows=5,
             profile=TARGET_PROFILE,  # or SOURCE_PROFILE
             assume_role_arn=ASSUME_ROLE_ARN  # Optional
         )
         print(metadata)
         display(df_preview)
     ```

4. **Clean Up**
   - Delete the uploaded sample CSV from S3 using boto3 and the target profile or assumed role.
   - Example:
     ```python
     import boto3
     session = boto3.Session(profile_name=TARGET_PROFILE)
     s3 = session.client('s3')
     for key in csv_files:
         s3.delete_object(Bucket=SOURCE_BUCKET, Key=key)
     ```

**Notes:**
- If you receive `AccessDenied` errors, the utility functions will print a message and return an empty DataFrame or list, so your notebook will not crash.
- Always verify that your IAM roles and bucket policies allow the required actions for the chosen profile or assumed role.

This workflow ensures that cross-account S3 access is working as expected and that the target profile or assumed role can read and clean up data in the source bucket without AccessDenied errors.

