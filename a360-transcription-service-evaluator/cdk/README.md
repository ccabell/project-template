# Transcription Evaluator Service - API Documentation & Integration Guide

## Overview

The Transcription Evaluator Service is a secure, production-ready FastAPI application deployed on AWS ECS Fargate for analyzing transcription quality and generating ground truth scripts. The service provides comprehensive analysis capabilities including false positive/negative identification, accuracy metrics, and ground truth generation for medical consultations.

## Architecture

- **Platform**: AWS ECS Fargate (ARM64)
- **Framework**: FastAPI with async/await support
- **Database**: S3 for transcript and analysis storage
- **Security**: Internal-only Application Load Balancer (no public access)
- **Infrastructure**: AWS CDK for Infrastructure as Code
- **Runtime**: Python 3.12 with Gunicorn/Uvicorn

## Security Configuration

✅ **NOT EXPOSED TO PUBLIC INTERNET**
- Internal Application Load Balancer only (`internal-*` DNS)
- VPC with private isolated subnets (no NAT Gateway)
- Security groups restrict access to VPC CIDR only
- No public subnets or internet gateway access
- VPC endpoints for AWS service communication only

## Service Status Verification

### Current Deployment (GenAI-Platform-Sandbox)
- **Stack Name**: TranscriptionEvaluatorStack
- **Service URL**: http://internal-Transc-Trans-wVWDicgitEED-1118273835.us-east-1.elb.amazonaws.com
- **Load Balancer**: Internal Application Load Balancer
- **Health Status**: ✅ HEALTHY
- **ECS Task Status**: ✅ RUNNING

### Load Balancer Details
- **Scheme**: internal
- **Type**: application
- **State**: active
- **Target Health**: healthy (10.1.1.213:8000)

## API Endpoints

### 1. Health Check
```bash
GET /health
```
**Response:**
```json
{
  "status": "healthy",
  "service": "transcription-evaluator",
  "version": "1.0.0",
  "timestamp": "2025-01-04T18:06:40Z"
}
```

### 2. Single Transcript Analysis
```bash
POST /analyze/single
Content-Type: application/json
```
**Request Body:**
```json
{
  "consultation_id": "test_consultation_001",
  "original_text": "The patient has acne on their face.",
  "corrected_text": "The patient has severe acne on their facial area.",
  "ground_truth_text": "The patient has moderate acne on their face.",
  "backend": "deepgram_nova2",
  "confidence_threshold": 0.7
}
```
**Response:**
```json
{
  "consultation_id": "test_consultation_001",
  "false_positive_count": 1,
  "false_negative_count": 0,
  "accuracy": 0.8750,
  "character_error_rate": 0.1250,
  "report_path": "fp-fn-analysis/english/test_consultation_001_2025-01-04T18:30:00.json"
}
```

### 3. Batch Analysis
```bash
POST /analyze/batch
Content-Type: application/json
```
**Request Body:**
```json
{
  "consultations": [
    {
      "consultation_id": "consultation_001",
      "consultation_uuid": "uuid-here",
      "backend": "deepgram_nova2",
      "ground_truth_text": "The patient has moderate acne."
    }
  ],
  "confidence_threshold": 0.7
}
```

### 4. Report Retrieval
```bash
GET /analyze/report/{report_path:path}
```
Returns the detailed analysis report in JSON format.

### 5. API Documentation
```bash
GET /docs
```
Interactive OpenAPI documentation (Swagger UI)

```bash
GET /redoc
```
Alternative API documentation (ReDoc)

## Testing the API Endpoints

### Prerequisites
Since the service runs on an internal load balancer, you need access to the VPC. Use one of these methods:

#### Method 1: AWS Systems Manager (Recommended)
```bash
# Connect to bastion host via SSM
aws --profile=GenAI-Platform-Sandbox ssm start-session --target i-03ea3c9942a640b0c

# Test health endpoint
curl -X GET http://internal-Transc-Trans-wVWDicgitEED-1118273835.us-east-1.elb.amazonaws.com/health

# Test single analysis
curl -X POST \
  http://internal-Transc-Trans-wVWDicgitEED-1118273835.us-east-1.elb.amazonaws.com/analyze/single \
  -H "Content-Type: application/json" \
  -d '{
    "consultation_id": "test_001",
    "original_text": "Patient has acne",
    "corrected_text": "Patient has severe acne",
    "ground_truth_text": "Patient has moderate acne",
    "backend": "test_backend"
  }'
```

#### Method 2: AWS CLI Remote Commands
```bash
# Send test command via SSM
aws --profile=GenAI-Platform-Sandbox ssm send-command \
  --instance-ids i-03ea3c9942a640b0c \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["curl -s http://internal-Transc-Trans-wVWDicgitEED-1118273835.us-east-1.elb.amazonaws.com/health"]'

# Get results (replace COMMAND_ID)
aws --profile=GenAI-Platform-Sandbox ssm get-command-invocation \
  --command-id COMMAND_ID \
  --instance-id i-03ea3c9942a640b0c
```

#### Method 3: VPN/VPC Connection
If you have VPN access to the VPC, you can test directly from your machine.

### Sample Test Script

Create `test_api.sh`:
```bash
#!/bin/bash

# Configuration
SERVICE_URL="http://internal-Transc-Trans-wVWDicgitEED-1118273835.us-east-1.elb.amazonaws.com"

echo "Testing Transcription Evaluator API..."

# Test 1: Health Check
echo "1. Testing health endpoint:"
curl -s "$SERVICE_URL/health" | jq .

# Test 2: Single Analysis
echo "2. Testing single analysis:"
curl -X POST "$SERVICE_URL/analyze/single" \
  -H "Content-Type: application/json" \
  -d '{
    "consultation_id": "test_consultation_001",
    "original_text": "The patient has acne on their face and needs treatment for severe breakouts.",
    "corrected_text": "The patient has acne on their facial area and needs treatment for severe breakouts.",
    "ground_truth_text": "The patient has moderate acne on their face and needs treatment for severe breakouts.",
    "backend": "deepgram_nova2",
    "confidence_threshold": 0.7
  }' | jq .

# Test 3: Documentation
echo "3. Testing documentation endpoint:"
curl -s "$SERVICE_URL/docs" -I

echo "API testing complete!"
```

## Frontend Integration Architecture

### Recommended Architecture for React Frontend

```
┌─────────────────────────────────────────────────────────────┐
│                        AWS VPC                              │
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │   CloudFront    │    │        Private Subnets          │ │
│  │   + S3 Static   │    │  ┌─────────────────────────────┐ │ │
│  │   Website       │    │  │     Internal ALB            │ │ │
│  └─────────────────┘    │  │  (API Gateway Alternative) │ │ │
│           │              │  └─────────────────────────────┘ │ │
│           │              │              │                   │ │
│  ┌─────────────────┐    │  ┌─────────────────────────────┐ │ │
│  │   API Gateway   │────┼──│  Transcription Evaluator    │ │ │
│  │   (Public)      │    │  │      ECS Service            │ │ │
│  └─────────────────┘    │  └─────────────────────────────┘ │ │
└─────────────────────────────────────────────────────────────┘
```

### Required Infrastructure Components

#### 1. API Gateway Integration
```typescript
// Add to CDK stack
const apiGateway = new apigateway.RestApi(this, 'TranscriptionEvaluatorAPI', {
  restApiName: 'Transcription Evaluator Service',
  description: 'Public API Gateway for Transcription Evaluator',
  defaultCorsPreflightOptions: {
    allowOrigins: ['https://your-frontend-domain.com'],
    allowMethods: ['GET', 'POST', 'OPTIONS'],
    allowHeaders: ['Content-Type', 'Authorization']
  }
});

// VPC Link for internal ALB
const vpcLink = new apigateway.VpcLink(this, 'TranscriptionEvaluatorVpcLink', {
  targets: [this.fargate_service.load_balancer]
});
```

#### 2. CloudFront + S3 for React Frontend
```typescript
const websiteBucket = new s3.Bucket(this, 'FrontendBucket', {
  bucketName: `transcription-evaluator-frontend-${environmentName}`,
  websiteIndexDocument: 'index.html',
  websiteErrorDocument: 'error.html',
  publicReadAccess: false,
  blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL
});

const distribution = new cloudfront.Distribution(this, 'FrontendDistribution', {
  defaultBehavior: {
    origin: new origins.S3Origin(websiteBucket),
    viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
  },
  additionalBehaviors: {
    '/api/*': {
      origin: new origins.RestApiOrigin(apiGateway),
      allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED
    }
  }
});
```

### Frontend Development Setup

#### React Application Structure
```
frontend/
├── public/
│   ├── index.html
│   └── manifest.json
├── src/
│   ├── components/
│   │   ├── TranscriptAnalyzer/
│   │   ├── ReportViewer/
│   │   ├── GroundTruthGenerator/
│   │   └── common/
│   ├── services/
│   │   ├── api.ts
│   │   ├── transcriptionService.ts
│   │   └── types.ts
│   ├── hooks/
│   │   ├── useAnalyzer.ts
│   │   └── useReports.ts
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── Analysis.tsx
│   │   └── Reports.tsx
│   └── utils/
├── package.json
└── tsconfig.json
```

#### API Service Integration
```typescript
// src/services/api.ts
const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

export class TranscriptionEvaluatorAPI {
  private baseURL: string;

  constructor(baseURL: string = API_BASE_URL) {
    this.baseURL = baseURL;
  }

  async analyzeSingle(request: SingleAnalysisRequest): Promise<AnalysisResponse> {
    const response = await fetch(`${this.baseURL}/analyze/single`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  }

  async generateGroundTruth(params: GroundTruthParams): Promise<GeneratedScript> {
    const response = await fetch(`${this.baseURL}/generate/ground-truth`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(params)
    });

    return response.json();
  }

  async getReport(reportPath: string): Promise<DetailedReport> {
    const response = await fetch(`${this.baseURL}/analyze/report/${encodeURIComponent(reportPath)}`);
    return response.json();
  }
}
```

#### React Components
```typescript
// src/components/TranscriptAnalyzer/TranscriptAnalyzer.tsx
import React, { useState } from 'react';
import { TranscriptionEvaluatorAPI } from '../../services/api';

interface TranscriptAnalyzerProps {
  api: TranscriptionEvaluatorAPI;
}

export const TranscriptAnalyzer: React.FC<TranscriptAnalyzerProps> = ({ api }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleAnalyze = async (data: SingleAnalysisRequest) => {
    setLoading(true);
    try {
      const result = await api.analyzeSingle(data);
      setAnalysis(result);
    } catch (error) {
      console.error('Analysis failed:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="transcript-analyzer">
      {/* Analysis form and results */}
    </div>
  );
};
```

## Environment Variables

### Service Configuration
```bash
# Container Environment Variables (set in CDK)
AWS_DEFAULT_REGION=us-east-1
STORAGE_BACKEND=s3
S3_BUCKET_NAME=a360-sandbox-transcript-evaluations
```

### Frontend Configuration
```bash
# React Environment Variables
REACT_APP_API_URL=https://your-api-gateway-url/prod
REACT_APP_ENV=sandbox
```

## Deployment & CI/CD

### Service Deployment
```bash
cd cdk
source venv/bin/activate
cdk --profile=GenAI-Platform-Sandbox deploy
```

### Frontend Deployment
```bash
cd frontend
npm run build
aws --profile=GenAI-Platform-Sandbox s3 sync build/ s3://transcription-evaluator-frontend-sandbox/
aws --profile=GenAI-Platform-Sandbox cloudfront create-invalidation --distribution-id E123456789 --paths "/*"
```

## Monitoring & Logging

### CloudWatch Logs
- **Log Group**: `/transcription-evaluator/service`
- **Retention**: 30 days
- **Access**: AWS Console → CloudWatch → Log Groups

### Metrics
- **ECS Service**: CPU/Memory utilization
- **ALB**: Request count, response times, error rates
- **Custom Metrics**: Analysis success rates, processing times

### Health Monitoring
```bash
# Check service health via CloudWatch
aws --profile=GenAI-Platform-Sandbox logs get-log-events \
  --log-group-name "/transcription-evaluator/service" \
  --log-stream-name "transcription-evaluator/TranscriptionEvaluatorContainer/TASK_ID"
```

## Development Workflow

### Local Development
```bash
# Run service locally
cd src
uvicorn transcription_evaluator.api.main:app --reload --host 0.0.0.0 --port 8000

# Test locally
curl http://localhost:8000/health
```

### Testing Strategy
```bash
# Run unit tests
poetry run pytest tests/unit/ -v

# Run integration tests
poetry run pytest tests/integration/ -v

# Load testing
locust -f tests/load/locustfile.py --host=http://internal-alb-url
```

## Security Considerations

### Authentication (Future)
- **AWS Cognito**: User authentication
- **API Keys**: Service-to-service authentication
- **JWT Tokens**: Session management

### Data Protection
- **Encryption**: S3 server-side encryption
- **Access Control**: IAM roles and policies
- **Network**: VPC isolation, security groups
- **Audit**: CloudTrail logging

## Troubleshooting

### Common Issues

#### 1. Service Not Responding
```bash
# Check ECS task status
aws --profile=GenAI-Platform-Sandbox ecs list-tasks --cluster transcription-evaluator

# Check logs
aws --profile=GenAI-Platform-Sandbox logs get-log-events \
  --log-group-name "/transcription-evaluator/service" \
  --log-stream-name "STREAM_NAME"
```

#### 2. Load Balancer Health Check Failures
```bash
# Check target health
aws --profile=GenAI-Platform-Sandbox elbv2 describe-target-health \
  --target-group-arn TARGET_GROUP_ARN
```

#### 3. Frontend Can't Reach API
- Verify API Gateway configuration
- Check CORS settings
- Confirm VPC Link connectivity

### Support Contacts
- **Infrastructure**: DevOps Team
- **Application**: Development Team
- **Security**: Security Team

## Next Steps

1. **Implement Authentication**: Add Cognito user pools
2. **Add Caching**: Redis for frequently accessed reports
3. **Implement Batch Processing**: SQS for large analysis jobs
4. **Add Real-time Updates**: WebSocket support for progress updates
5. **Enhanced Monitoring**: Custom dashboards and alerts
6. **Performance Optimization**: Auto-scaling policies

## Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [AWS API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)