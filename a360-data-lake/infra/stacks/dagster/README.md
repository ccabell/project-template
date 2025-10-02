# Dagster+ ECS Infrastructure

ECS cluster and service infrastructure for running Dagster+ hybrid agents that process healthcare data from the existing MDA data lake.

## Components

- **ECS Cluster**: Fargate cluster with Container Insights for agent deployment
- **Task Definition**: Dagster+ agent container configuration with health checks
- **ECS Service**: Agent service with auto-scaling and deployment strategies
- **CloudWatch Logs**: Centralized logging for agent operations
- **Service Discovery**: Private DNS namespace for code server communication

## Integration with Data Lake

The ECS infrastructure integrates with existing a360-data-lake components:

- Uses existing VPC and private subnets from NetworkStack
- Leverages existing IAM roles for data lake access
- Connects to existing S3 buckets for data processing
- Integrates with Lake Formation for data governance
