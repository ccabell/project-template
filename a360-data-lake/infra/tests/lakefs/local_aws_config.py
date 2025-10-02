"""AWS configuration for LakeFS testing - CI/CD friendly.

This configuration automatically detects the environment:
1. CI/CD pipeline: Uses safe fallback constants (no AWS calls needed)
2. Local development: Can optionally use actual AWS resource IDs

Works seamlessly with 'uv run pytest' in any environment.
"""

import os

# Safe constants for CI/CD pipelines - these work without AWS access
CI_CD_TEST_CONFIG = {
    # VPC Configuration (realistic format but safe test IDs)
    "vpc_id": "vpc-0test1234567890ab",
    # Private Subnet IDs (realistic format but safe test IDs)
    "private_subnet_ids": [
        "subnet-0test1234567890a",  # us-east-1a
        "subnet-0test1234567890b",  # us-east-1b
        "subnet-0test1234567890c",  # us-east-1d
    ],
    # KMS Keys (realistic format but safe test ARNs)
    "foundation_kms_key_arn": "arn:aws:kms:us-east-1:277707121008:key/test1234-5678-90ab-cdef-test12345678",
    "consultation_kms_key_arn": "arn:aws:kms:us-east-1:277707121008:key/test5678-90ab-cdef-1234-test56789012",
    # Account and Region
    "account": "277707121008",
    "region": "us-east-1",
    # Test Bucket Names
    "consultation_buckets": {
        "landing": "test-consultation-landing-bucket",
        "bronze": "test-consultation-bronze-bucket",
        "silver": "test-consultation-silver-bucket",
        "gold": "test-consultation-gold-bucket",
    },
    # Test Bucket ARNs
    "consultation_bucket_arns": {
        "landing": "arn:aws:s3:::test-consultation-landing-bucket",
        "bronze": "arn:aws:s3:::test-consultation-bronze-bucket",
        "silver": "arn:aws:s3:::test-consultation-silver-bucket",
        "gold": "arn:aws:s3:::test-consultation-gold-bucket",
    },
}

# Optional local development configuration - only loaded if marker file exists
LOCAL_DEV_CONFIG = None


def _load_local_dev_config():
    """Load local development config if available."""
    global LOCAL_DEV_CONFIG

    # Check for local development marker file
    marker_file = os.path.join(os.path.dirname(__file__), ".local_dev_marker")
    if os.path.exists(marker_file):
        try:
            LOCAL_DEV_CONFIG = {
                # Actual VPC Configuration
                "vpc_id": "vpc-0bc7e712a641bf872",
                # Actual Private Subnet IDs
                "private_subnet_ids": [
                    "subnet-0a38e04ecb0100f4d",  # us-east-1a
                    "subnet-0662dcc5cf4833592",  # us-east-1b
                    "subnet-02d46d8788a99548a",  # us-east-1d
                ],
                # Actual KMS Keys
                "foundation_kms_key_arn": "arn:aws:kms:us-east-1:277707121008:key/a3671adb-5957-4961-a82c-dfd324fa7f22",
                "consultation_kms_key_arn": "arn:aws:kms:us-east-1:277707121008:key/c8947f59-b486-461e-8d66-7534d1a3fbe9",
                # Account and Region
                "account": "277707121008",
                "region": "us-east-1",
                # Test Bucket Names (for local testing)
                "consultation_buckets": {
                    "landing": "test-consultation-landing-bucket-local",
                    "bronze": "test-consultation-bronze-bucket-local",
                    "silver": "test-consultation-silver-bucket-local",
                    "gold": "test-consultation-gold-bucket-local",
                },
                # Test Bucket ARNs (for local testing)
                "consultation_bucket_arns": {
                    "landing": "arn:aws:s3:::test-consultation-landing-bucket-local",
                    "bronze": "arn:aws:s3:::test-consultation-bronze-bucket-local",
                    "silver": "arn:aws:s3:::test-consultation-silver-bucket-local",
                    "gold": "arn:aws:s3:::test-consultation-gold-bucket-local",
                },
            }
            print(f"✓ Loaded local development config from {marker_file}")
        except Exception as e:
            print(f"⚠️  Failed to load local dev config: {e}")
            LOCAL_DEV_CONFIG = None


def get_aws_config():
    """Get AWS configuration - CI/CD friendly with optional local dev override.

    Returns:
        dict: Dictionary containing AWS resource IDs for testing

    Environment Detection:
    - CI/CD: Always uses safe CI_CD_TEST_CONFIG constants
    - Local Dev: Uses LOCAL_DEV_CONFIG if .local_dev_marker file exists, otherwise CI_CD_TEST_CONFIG
    """
    # Load local dev config if not already loaded
    if LOCAL_DEV_CONFIG is None:
        _load_local_dev_config()

    # Use local dev config if available, otherwise use CI/CD safe config
    config = LOCAL_DEV_CONFIG if LOCAL_DEV_CONFIG else CI_CD_TEST_CONFIG

    return config.copy()


def get_lakefs_props():
    """Get LakeFSStackProps with appropriate AWS resource IDs.

    Returns:
        dict: Dictionary suitable for LakeFSStackProps initialization

    This function is CI/CD friendly and will work in any environment.
    """
    config = get_aws_config()
    return {
        "vpc_id": config["vpc_id"],
        "private_subnet_ids": config["private_subnet_ids"],
        "existing_kms_key_arn": config["foundation_kms_key_arn"],
        "consultation_bucket_names": config["consultation_buckets"],
        "consultation_bucket_arns": config["consultation_bucket_arns"],
        "environment_name": "dev",
    }


def enable_local_dev_mode():
    """Enable local development mode by creating the marker file.

    Call this function in your local development environment to use actual AWS resource IDs.
    The marker file is automatically ignored by git.
    """
    marker_file = os.path.join(os.path.dirname(__file__), ".local_dev_marker")
    with open(marker_file, "w") as f:
        f.write("Local development mode enabled\n")
        f.write("This file enables actual AWS resource IDs for local testing.\n")
        f.write("Safe to delete - tests will fall back to CI/CD constants.\n")
    print(f"✓ Local development mode enabled. Created {marker_file}")


def disable_local_dev_mode():
    """Disable local development mode by removing the marker file."""
    marker_file = os.path.join(os.path.dirname(__file__), ".local_dev_marker")
    if os.path.exists(marker_file):
        os.remove(marker_file)
        global LOCAL_DEV_CONFIG
        LOCAL_DEV_CONFIG = None
        print(f"✓ Local development mode disabled. Removed {marker_file}")
    else:
        print("ℹ️  Local development mode was not enabled.")


# Initialize on import
_load_local_dev_config()
