# Transcription Evaluator - Local Build and Deployment Guide

## Prerequisites

### System Requirements
- Node.js 18+ and npm
- Python 3.12+
- AWS CLI configured with proper credentials
- AWS CDK CLI
- Docker (for local backend development)

### AWS Profile Setup
Ensure you have the correct AWS profile configured:
```bash
aws configure --profile GenAI-Platform-Sandbox
# Enter your AWS credentials for the sandbox environment
```

## Backend Development

### Local Setup
1. **Navigate to the backend directory:**
   ```bash
   cd /path/to/transcription_evaluator/backend
   ```

2. **Install dependencies:**
   ```bash
   pip install -e .
   ```

3. **Set environment variables:**
   ```bash
   export STORAGE_BACKEND=local  # or s3
   export AWS_DEFAULT_REGION=us-east-1
   # For S3 backend:
   export S3_BUCKET_NAME=a360-sandbox-transcript-evaluations
   ```

4. **Run the development server:**
   ```bash
   uvicorn transcription_evaluator.api.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Local Testing
- **Health Check:** `curl http://localhost:8000/health`
- **API Documentation:** http://localhost:8000/docs
- **OpenAPI Schema:** http://localhost:8000/openapi.json

## Infrastructure Deployment

### CDK Setup
1. **Navigate to CDK directory:**
   ```bash
   cd /path/to/transcription_evaluator/cdk
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install CDK dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Deploy infrastructure:**
   ```bash
   AWS_PROFILE=GenAI-Platform-Sandbox cdk deploy --require-approval never
   ```

5. **Get stack outputs:**
   ```bash
   AWS_PROFILE=GenAI-Platform-Sandbox aws cloudformation describe-stacks \
     --stack-name TranscriptionEvaluatorStack \
     --query 'Stacks[0].Outputs'
   ```

## Frontend Development

### Local Setup
1. **Navigate to frontend directory:**
   ```bash
   cd /path/to/transcription_evaluator/frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Create local environment file:**
   ```bash
   cat > .env.local << EOF
   REACT_APP_API_URL=http://localhost:8000
   REACT_APP_ENV=development
   REACT_APP_COGNITO_USER_POOL_ID=us-east-1_XlJMh6HX6
   REACT_APP_COGNITO_USER_POOL_CLIENT_ID=o47acdr5tq2eqsttq6kj8mie7
   REACT_APP_COGNITO_IDENTITY_POOL_ID=us-east-1:561f05df-6f29-49a0-97dd-8f93d2e8a509
   REACT_APP_COGNITO_REGION=us-east-1
   EOF
   ```

4. **Start development server:**
   ```bash
   npm start
   ```

### Local Testing
- **Application:** http://localhost:3000
- **Network Tab:** Check API calls to backend
- **Console:** Monitor for authentication errors

### Production Build
1. **Build the application:**
   ```bash
   npm run build
   ```

2. **Test production build locally:**
   ```bash
   npm install -g serve
   serve -s build -p 3000
   ```

## Frontend Deployment to AWS

### Automated Deployment
Use the provided deployment script:
```bash
chmod +x deploy-simple.sh
./deploy-simple.sh GenAI-Platform-Sandbox sandbox
```

### Manual Deployment
1. **Get stack outputs:**
   ```bash
   FRONTEND_BUCKET=$(aws --profile=GenAI-Platform-Sandbox cloudformation describe-stacks \
     --stack-name TranscriptionEvaluatorStack \
     --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
     --output text)
   
   API_GATEWAY_URL=$(aws --profile=GenAI-Platform-Sandbox cloudformation describe-stacks \
     --stack-name TranscriptionEvaluatorStack \
     --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
     --output text)
   ```

2. **Create production environment:**
   ```bash
   cat > .env.production << EOF
   REACT_APP_API_URL=${API_GATEWAY_URL}
   REACT_APP_ENV=production
   REACT_APP_COGNITO_USER_POOL_ID=us-east-1_XlJMh6HX6
   REACT_APP_COGNITO_USER_POOL_CLIENT_ID=o47acdr5tq2eqsttq6kj8mie7
   REACT_APP_COGNITO_IDENTITY_POOL_ID=us-east-1:561f05df-6f29-49a0-97dd-8f93d2e8a509
   REACT_APP_COGNITO_REGION=us-east-1
   GENERATE_SOURCEMAP=false
   EOF
   ```

3. **Build and deploy:**
   ```bash
   npm run build
   aws --profile=GenAI-Platform-Sandbox s3 sync build/ s3://$FRONTEND_BUCKET/ --delete
   ```

## Authentication Setup

### Cognito Configuration
The infrastructure includes:
- **User Pool:** `us-east-1_XlJMh6HX6`
- **User Pool Client:** `o47acdr5tq2eqsttq6kj8mie7`
- **Identity Pool:** `us-east-1:561f05df-6f29-49a0-97dd-8f93d2e8a509`

### User Management
1. **Create test user (via AWS CLI):**
   ```bash
   aws --profile=GenAI-Platform-Sandbox cognito-idp admin-create-user \
     --user-pool-id us-east-1_XlJMh6HX6 \
     --username testuser \
     --user-attributes Name=email,Value=test@example.com \
     --temporary-password TempPassword123! \
     --message-action SUPPRESS
   ```

2. **Set permanent password:**
   ```bash
   aws --profile=GenAI-Platform-Sandbox cognito-idp admin-set-user-password \
     --user-pool-id us-east-1_XlJMh6HX6 \
     --username testuser \
     --password PermanentPassword123! \
     --permanent
   ```

## Troubleshooting

### Common Issues

1. **403 Forbidden on S3 Website:**
   - Check bucket policy allows public read access
   - Verify `index.html` exists in bucket
   - Confirm bucket website configuration

2. **API Gateway 503 Service Unavailable:**
   - Check ECS service is running and healthy
   - Verify VPC Link is in AVAILABLE state
   - Check target group health in ALB

3. **Authentication Errors:**
   - Verify Cognito User Pool configuration
   - Check User Pool Client settings
   - Confirm Identity Pool role mappings

### Monitoring Commands
```bash
# Check ECS service status
aws --profile=GenAI-Platform-Sandbox ecs describe-services \
  --cluster transcription-evaluator \
  --services transcription-evaluator

# Check API Gateway VPC Link status
aws --profile=GenAI-Platform-Sandbox apigatewayv2 get-vpc-links

# View service logs
aws --profile=GenAI-Platform-Sandbox logs tail /transcription-evaluator/service --since 10m

# Check target health
aws --profile=GenAI-Platform-Sandbox elbv2 describe-target-health \
  --target-group-arn [TARGET_GROUP_ARN]
```

## Deployment URLs

After successful deployment:
- **Frontend:** http://a360-sandbox-transcription-evaluator-frontend.s3-website-us-east-1.amazonaws.com
- **API Gateway:** https://amrnty7hea.execute-api.us-east-1.amazonaws.com
- **API Docs:** https://amrnty7hea.execute-api.us-east-1.amazonaws.com/docs

## Security Notes

- Frontend S3 bucket is configured for public read access (required for static hosting)
- API Gateway uses VPC Link to internal ALB (no public internet exposure for ECS)
- Cognito authentication required for API access
- All communication uses HTTPS where possible
- ECS tasks run in isolated private subnets