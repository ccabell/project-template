# LakeFS AWS Deployment Guide

## Overview

LakeFS has been repositioned for AWS deployment with dynamic account resolution. The solution provides enterprise-grade data version control for the A360 Data Lake with automatic AWS account and region detection.

## Architecture

### 🏗️ Infrastructure Components

1. **ECS Fargate Service**: Hosts LakeFS server containers
2. **RDS PostgreSQL**: Metadata storage with high availability
3. **S3 Buckets**: Data storage with versioning and lifecycle policies
4. **Application Load Balancer**: Internal load balancing with health checks
5. **IAM Roles**: Fine-grained permissions with least privilege
6. **VPC Integration**: Private networking with existing foundation VPC
7. **Monitoring & Audit**: CloudWatch metrics, alarms, and audit trails

### 🎯 Dynamic Account Resolution

The solution automatically detects:
- **AWS Account ID**: `Aws.ACCOUNT_ID` (resolves dynamically)
- **AWS Region**: `Aws.REGION` (resolves dynamically)
- **Environment**: From CDK context (dev, staging, prod)

### 📊 Repository Structure

#### Consultation Pipeline (Medallion Architecture):
- `consultation-landing`: Raw consultation data
- `consultation-bronze`: Transcribed data  
- `consultation-silver`: PHI-redacted data
- `consultation-gold`: Analytics-ready insights

#### Podcast Pipeline (Medallion Architecture):
- `podcast-landing`: Raw audio files
- `podcast-bronze`: Transcribed data
- `podcast-silver`: Cleaned transcriptions
- `podcast-gold`: Analytics-ready insights

#### Foundation Data:
- `foundation-metadata`: Shared schemas and configurations
- `foundation-models`: ML models and AI artifacts

## Deployment Process

### 1. Prerequisites

```bash
# Ensure AWS credentials are configured
aws configure list

# Verify CDK is installed
npx cdk --version

# Install dependencies
npm install
```

### 2. Deploy LakeFS Infrastructure

The LakeFS stack is already integrated into the main CDK app. Deploy with:

```bash
# Deploy to development environment
ENV_NAME=dev AWS_DEFAULT_REGION=us-east-1 CDK_DEFAULT_ACCOUNT=277707121008 npx cdk deploy LakeFSStack-dev

# Deploy to staging environment
ENV_NAME=staging AWS_DEFAULT_REGION=us-east-1 CDK_DEFAULT_ACCOUNT=277707121008 npx cdk deploy LakeFSStack-staging

# Deploy to production environment
ENV_NAME=prod AWS_DEFAULT_REGION=us-east-1 CDK_DEFAULT_ACCOUNT=277707121008 npx cdk deploy LakeFSStack-prod
```

**Note**: The deployment includes automatic TLS certificate provisioning and HTTPS-only configuration.

### 3. Verify Deployment

After deployment, verify the resources:

```bash
# Check ECS service status
aws ecs describe-services --cluster a360-lakefs-cluster --services a360-lakefs-server

# Check RDS database
aws rds describe-db-instances --db-instance-identifier lakefs-database

# Get LakeFS endpoint
aws ssm get-parameter --name "/a360-lakefs/endpoint/url" --query "Parameter.Value"
```

### 4. Access LakeFS Web UI

1. Get the ALB endpoint from CloudFormation outputs
2. Access LakeFS at: `https://<alb-dns-name>` (HTTPS on port 443)
3. Use admin credentials from Secrets Manager
4. Verify TLS certificate is properly configured

### 5. Create Repositories

Use the repository manager to create all repositories:

```python
# Using the repository manager
from infra.stacks.lakefs.repository_manager import LakeFSRepositoryManager

# Initialize with endpoint and credentials
manager = LakeFSRepositoryManager(
    lakefs_endpoint="https://<alb-dns-name>",
    access_key="<access-key>",
    secret_key="<secret-key>"
)

# Create all repositories
results = manager.create_all_repositories(env="dev")
print(f"Created {results['summary']['succeeded']} repositories")
```

## Integration with Dagster

### 1. Update Dagster Configuration

Update your Dagster resources to use the AWS LakeFS:

```python
from dagster.defs.lakefs.lakefs_aws_resources import LakeFSAWSResource

# In your Dagster definitions
lakefs_resource = LakeFSAWSResource(
    lakefs_endpoint="https://<alb-dns-name>",
    access_key="<access-key>",
    secret_key="<secret-key>",
    env_name="dev"
)
```

### 2. Environment Variables

Set these environment variables for Dagster:

```bash
export LAKEFS_ENDPOINT="https://<alb-dns-name>"
export LAKEFS_ACCESS_KEY="<access-key>"
export LAKEFS_SECRET_KEY="<secret-key>"
export ENV_NAME="dev"
export LAKEFS_REGION="us-east-1"
```

### 3. Repository Naming Convention

The system uses dynamic repository naming:
- **Pattern**: `{pipeline}-{layer}` (e.g., `consultation-bronze`)
- **Storage**: `s3://a360-lakefs-data-{env}-{account_id}/{pipeline}/{layer}/`
- **Branches**: `main`, `develop`, `staging`

## Key Features

### ✅ Dynamic Account Resolution
- Automatically detects AWS account and region
- No hardcoded account IDs or regions
- Environment-specific resource naming

### ✅ Enterprise Security
- Private VPC deployment with controlled internet access
- IAM roles with least privilege permissions
- Encryption at rest and in transit with TLS 1.2+
- Security groups with IP restrictions
- HTTPS-only communication with valid certificates

### ✅ High Availability
- Multi-AZ RDS deployment
- ECS Fargate with health checks
- Application Load Balancer with failover
- Automated backup and recovery

### ✅ Monitoring & Compliance
- CloudWatch metrics and alarms
- Audit trails for all operations
- Data lineage tracking
- Operational dashboards

### ✅ Cost Optimization
- S3 lifecycle policies for data archival
- ECS task scaling based on demand
- RDS with storage auto-scaling
- Efficient resource allocation

## Storage Namespaces

The system generates storage namespaces dynamically:

```
# Development Environment (Account: 277707121008)
s3://a360-lakefs-data-dev-277707121008/consultation/landing/
s3://a360-lakefs-data-dev-277707121008/consultation/bronze/
s3://a360-lakefs-data-dev-277707121008/consultation/silver/
s3://a360-lakefs-data-dev-277707121008/consultation/gold/
s3://a360-lakefs-data-dev-277707121008/podcast/landing/
s3://a360-lakefs-data-dev-277707121008/podcast/bronze/
s3://a360-lakefs-data-dev-277707121008/podcast/silver/
s3://a360-lakefs-data-dev-277707121008/podcast/gold/
s3://a360-lakefs-data-dev-277707121008/foundation/metadata/
s3://a360-lakefs-data-dev-277707121008/foundation/models/

# Production Environment (Account: 277707121008)
s3://a360-lakefs-data-prod-277707121008/consultation/landing/
s3://a360-lakefs-data-prod-277707121008/consultation/bronze/
# ... etc
```

## Next Steps

1. **Deploy Infrastructure**: Run CDK deployment for your environment
2. **Configure Access**: Set up LakeFS admin credentials
3. **Create Repositories**: Use repository manager to create all repositories
4. **Update Dagster**: Configure Dagster pipelines to use AWS LakeFS
5. **Test Workflows**: Verify data versioning and pipeline integration
6. **Monitor**: Set up alerts and monitoring dashboards

## Support

- **CloudFormation Outputs**: All important values are exported
- **SSM Parameters**: Key configuration stored in Parameter Store
- **CloudWatch Logs**: Comprehensive logging for troubleshooting
- **Health Checks**: Automated monitoring of all components

The LakeFS AWS deployment provides a production-ready, scalable, and secure data versioning solution that integrates seamlessly with your existing A360 Data Lake infrastructure.