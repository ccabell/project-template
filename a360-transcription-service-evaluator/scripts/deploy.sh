#!/bin/bash

# Deployment script for transcription evaluator service.
#
# This script handles the complete deployment pipeline:
#     • Builds and pushes Docker image to ECR
#     • Synthesizes and deploys CDK stack
#     • Updates ECS service with new image
#     • Verifies deployment health

set -euo pipefail

# Configuration
AWS_REGION="us-east-1" 
AWS_ACCOUNT="590183989543"
AWS_PROFILE="GenAI-Platform-Dev"
ECR_REPOSITORY="transcription-evaluator"
STACK_NAME="TranscriptionEvaluatorStack"
SERVICE_NAME="transcription-evaluator"
CLUSTER_NAME="transcription-evaluator"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if AWS CLI is configured
check_aws_config() {
    log_info "Checking AWS configuration..."
    
    if ! aws sts get-caller-identity --profile $AWS_PROFILE &>/dev/null; then
        log_error "AWS CLI not configured or credentials invalid for profile: $AWS_PROFILE"
        exit 1
    fi
    
    CURRENT_ACCOUNT=$(aws sts get-caller-identity --profile $AWS_PROFILE --query Account --output text)
    if [ "$CURRENT_ACCOUNT" != "$AWS_ACCOUNT" ]; then
        log_error "Wrong AWS account. Expected: $AWS_ACCOUNT, Current: $CURRENT_ACCOUNT"
        exit 1
    fi
    
    log_info "AWS configuration valid for account: $AWS_ACCOUNT"
}

# Function to get ECR login token
ecr_login() {
    log_info "Logging in to Amazon ECR..."
    aws ecr get-login-password --profile $AWS_PROFILE --region $AWS_REGION | \
        docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com
}

# Function to build and push Docker image
build_and_push_image() {
    local image_tag=${1:-latest}
    local ecr_uri="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY"
    
    log_info "Building Docker image with tag: $image_tag"
    
    # Build image from service directory
    cd "$(dirname "$0")/.."
    docker build -t "$ECR_REPOSITORY:$image_tag" .
    docker tag "$ECR_REPOSITORY:$image_tag" "$ecr_uri:$image_tag"
    docker tag "$ECR_REPOSITORY:$image_tag" "$ecr_uri:latest"
    
    log_info "Pushing image to ECR: $ecr_uri"
    docker push "$ecr_uri:$image_tag"
    docker push "$ecr_uri:latest"
    
    log_info "Image pushed successfully: $ecr_uri:$image_tag"
    echo "$ecr_uri:$image_tag"
}

# Function to deploy CDK stack
deploy_cdk() {
    log_info "Deploying CDK stack: $STACK_NAME"
    
    cd cdk
    
    # Install CDK dependencies if not present
    if [ ! -d "venv" ]; then
        log_info "Creating Python virtual environment for CDK..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    else
        source venv/bin/activate
    fi
    
    # Bootstrap CDK (idempotent operation)
    log_info "Bootstrapping CDK..."
    cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION --profile $AWS_PROFILE
    
    # Deploy stack
    log_info "Synthesizing CDK stack..."
    cdk synth --profile $AWS_PROFILE
    
    log_info "Deploying CDK stack..."
    cdk deploy --require-approval never --profile $AWS_PROFILE
    
    deactivate
    cd ..
}

# Function to update ECS service
update_ecs_service() {
    local image_uri=$1
    
    log_info "Updating ECS service: $SERVICE_NAME"
    
    # Force new deployment with latest image
    aws ecs update-service \
        --profile $AWS_PROFILE \
        --cluster $CLUSTER_NAME \
        --service $SERVICE_NAME \
        --force-new-deployment \
        --region $AWS_REGION
    
    log_info "Waiting for service to stabilize..."
    aws ecs wait services-stable \
        --profile $AWS_PROFILE \
        --cluster $CLUSTER_NAME \
        --services $SERVICE_NAME \
        --region $AWS_REGION
    
    log_info "ECS service update completed"
}

# Function to verify deployment health
verify_deployment() {
    log_info "Verifying deployment health..."
    
    # Get load balancer DNS name from CDK output
    local alb_dns=$(aws cloudformation describe-stacks \
        --profile $AWS_PROFILE \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`ServiceURL`].OutputValue' \
        --output text \
        --region $AWS_REGION)
    
    if [ -z "$alb_dns" ]; then
        log_warn "Could not retrieve ALB DNS name from CloudFormation outputs"
        return 1
    fi
    
    log_info "Testing health endpoint: $alb_dns/health"
    
    # Wait for ALB to be ready and test health endpoint
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        log_info "Health check attempt $attempt/$max_attempts..."
        
        if curl -f -s "$alb_dns/health" > /dev/null; then
            log_info "✅ Health check passed! Service is responding"
            log_info "Service URL: $alb_dns"
            return 0
        fi
        
        sleep 10
        ((attempt++))
    done
    
    log_error "❌ Health check failed after $max_attempts attempts"
    return 1
}

# Main deployment function
main() {
    local image_tag=${1:-$(date +%Y%m%d-%H%M%S)}
    
    log_info "Starting deployment of transcription evaluator service..."
    log_info "Image tag: $image_tag"
    
    # Pre-deployment checks
    check_aws_config
    
    # Build and push container image
    ecr_login
    local image_uri=$(build_and_push_image "$image_tag")
    
    # Deploy infrastructure
    deploy_cdk
    
    # Update ECS service
    update_ecs_service "$image_uri"
    
    # Verify deployment
    if verify_deployment; then
        log_info "🎉 Deployment completed successfully!"
    else
        log_error "❌ Deployment verification failed"
        exit 1
    fi
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi