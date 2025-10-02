import boto3
from botocore.client import Config
from sagemaker import Session


sagemaker_session = Session()
sagemaker_client = sagemaker_session.sagemaker_client
bedrock_client = boto3.client("bedrock")
# Increase read_timeout to 1 hour for reasoning models as recommended in
# https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-37.html
bedrock_runtime_config = Config(read_timeout=3600)
bedrock_runtime_client = boto3.client(
    'bedrock-runtime', config=bedrock_runtime_config
)
SAGEMAKER_DEFAULT_BUCKET = sagemaker_session.default_bucket()