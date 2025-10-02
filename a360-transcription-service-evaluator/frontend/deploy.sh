#!/bin/bash

# Frontend deployment script for Transcription Evaluator
# This script builds the React app and deploys it to S3 + CloudFront

set -e

# Configuration
PROFILE="${1:-GenAI-Platform-Sandbox}"
ENVIRONMENT="${2:-sandbox}"
STACK_NAME="VoiceActorStack"

echo "🚀 Starting frontend deployment..."
echo "Profile: $PROFILE"
echo "Environment: $ENVIRONMENT"
echo "Stack: $STACK_NAME"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is required but not installed"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed"
    exit 1
fi

# Get stack outputs
echo "📋 Getting CloudFormation stack outputs..."
API_GATEWAY_URL=$(aws --profile=$PROFILE cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
    --output text)

WEBSITE_URL=$(aws --profile=$PROFILE cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`FrontendUrl`].OutputValue' \
    --output text)

if [ -z "$API_GATEWAY_URL" ] || [ -z "$WEBSITE_URL" ]; then
    echo "❌ Failed to get required stack outputs"
    echo "API Gateway URL: $API_GATEWAY_URL"
    echo "Website URL: $WEBSITE_URL"
    exit 1
fi

# Extract S3 bucket name from website URL
# URL format: http://a360-sandbox-voice-actor-frontend.s3-website-us-east-1.amazonaws.com
FRONTEND_BUCKET=$(echo $WEBSITE_URL | sed 's|http://\([^.]*\)\.s3-website-.*|\1|')

echo "✅ Stack outputs retrieved:"
echo "  Frontend Bucket: $FRONTEND_BUCKET"  
echo "  API Gateway URL: $API_GATEWAY_URL"
echo "  Website URL: $WEBSITE_URL"

# Install dependencies
echo "📦 Installing dependencies..."
npm install --silent

# Create environment file for build
echo "🔧 Creating build environment..."
cat > .env.production << EOF
REACT_APP_API_URL=${API_GATEWAY_URL}
REACT_APP_ENV=$ENVIRONMENT
GENERATE_SOURCEMAP=false
EOF

# Build the React app
echo "🏗️  Building React application..."
npm run build

if [ ! -d "build" ]; then
    echo "❌ Build directory not found"
    exit 1
fi

# Deploy to S3
echo "☁️  Deploying to S3 bucket: $FRONTEND_BUCKET"
aws --profile=$PROFILE s3 sync build/ s3://$FRONTEND_BUCKET/ \
    --delete \
    --exact-timestamps \
    --cache-control "public, max-age=31536000" \
    --exclude "*.html" \
    --exclude "service-worker.js" \
    --exclude "manifest.json"

# Deploy HTML files with no cache
echo "📄 Deploying HTML files with no-cache policy..."
aws --profile=$PROFILE s3 sync build/ s3://$FRONTEND_BUCKET/ \
    --exclude "*" \
    --include "*.html" \
    --include "service-worker.js" \
    --include "manifest.json" \
    --cache-control "no-cache, no-store, must-revalidate"

# Set correct content types
echo "🔧 Setting content types..."
aws --profile=$PROFILE s3 cp s3://$FRONTEND_BUCKET/index.html s3://$FRONTEND_BUCKET/index.html \
    --metadata-directive REPLACE \
    --content-type "text/html" \
    --cache-control "no-cache, no-store, must-revalidate"

# No CloudFront in this setup - using S3 website hosting directly
echo "✅ Files uploaded to S3 website"

# Clean up
echo "🧹 Cleaning up..."
rm -f .env.production

echo ""
echo "🎉 Frontend deployment completed successfully!"
echo ""
echo "📊 Deployment Summary:"
echo "  Environment: $ENVIRONMENT"
echo "  S3 Bucket: $FRONTEND_BUCKET" 
echo "  Website URL: $WEBSITE_URL"
echo "  API Endpoint: ${API_GATEWAY_URL}"
echo ""
echo "🌐 Your application is now available at:"
echo "  $WEBSITE_URL"
echo ""
echo "⏱️  Note: S3 website changes are available immediately."

# Optional: Open in browser (macOS)
if [[ "$OSTYPE" == "darwin"* ]] && [ "${OPEN_BROWSER:-false}" = "true" ]; then
    echo "🌐 Opening website in browser..."
    open "$WEBSITE_URL"
fi