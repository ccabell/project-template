#!/bin/bash


set -e

BUCKET_NAME="$1"
SOURCE_PATH="$2"

if [ -z "$BUCKET_NAME" ] || [ -z "$SOURCE_PATH" ]; then
    echo "Usage: $0 <bucket-name> <source-path>"
    exit 1
fi

echo "Deploying Dagster code location to S3..."
echo "Bucket: $BUCKET_NAME"
echo "Source: $SOURCE_PATH"


cd "$SOURCE_PATH"
zip -r dagster-code-location.zip . -x "*.pyc" "__pycache__/*" "*.git*" "tests/*"


aws s3 cp dagster-code-location.zip "s3://$BUCKET_NAME/code-location/dagster-code-location.zip"


echo "{"version": "$(date +%Y%m%d-%H%M%S)", "deployed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"}" > version.json
aws s3 cp version.json "s3://$BUCKET_NAME/code-location/version.json"

echo "Deployment completed successfully!"
