"""CDK application for transcription evaluator service.

This CDK application deploys the transcription evaluator service to AWS
using ECS Fargate with production-level security and best practices.

The application creates:
    • VPC with private subnets for secure deployment
    • ECS Fargate service with internal-only access
    • Application Load Balancer in private subnets
    • ECR repository for container images
    • IAM roles with least privilege access
    • Security groups with minimal required access
"""

import aws_cdk as cdk

from stacks.transcription_evaluator_stack import TranscriptionEvaluatorStack


app = cdk.App()

# Deploy to GenAI-Platform-Sandbox account with us-east-1 region
env = cdk.Environment(
    account="471112502741",  # GenAI-Platform-Sandbox
    region="us-east-1"
)

TranscriptionEvaluatorStack(
    app,
    "TranscriptionEvaluatorStack",
    env=env,
    description="Transcription evaluation service with ECS Fargate deployment"
)

app.synth()