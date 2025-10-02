# Network Infrastructure

VPC and networking components for the A360 Data Platform modernization.

## Components

- **VPC Stack**: Dedicated VPC with public/private subnets
- **VPC Endpoints**: Secure AWS service connectivity
- **VPC Lattice**: Cross-account service networking
- **Internet Gateway**: Managed internet access for public subnets
- **NAT Gateway**: Controlled internet access for private subnets
- **Route Tables**: Traffic routing configuration
- **VPC Flow Logs**: Network monitoring and compliance

## VPC Lattice Service Network

### Service Targets
- **Patient API**: Patient data and consultation services
- **Consultation API**: Real-time consultation and transcript services

### Security Features
- **IAM Authentication**: Service-level access control
- **Access Logging**: Comprehensive traffic monitoring
- **Health Checks**: Service availability monitoring
- **Resource Policies**: Cross-account access control

## Architecture

    ```shell
Data Platform VPC (10.1.0.0/16)
├── Private Subnets
│   ├── Dagster Agents
│   ├── LakeFS Services
│   └── VPC Lattice Association
└── VPC Lattice Service Network
    ├── Patient API Service
    ├── Consultation API Service
    └── Target Groups
        └── Health Checks

Patient Services VPC (Existing)
├── FastAPI Services
├── WebSocket Services
└── VPC Lattice Association
    ```

## Cross-Account Integration

VPC Lattice enables secure communication between:
- Data platform processing services
- Patient consultation APIs
- Healthcare data services
- Real-time transcript streams

## Dependencies

- AWS CDK v2
- Existing Lake Formation and S3 storage resources
- Cross-account communication with a360-service-patients infrastructure

## Usage

```python
from infra.stacks.network import NetworkStack

# Create network stack
network_stack = NetworkStack(app, "NetworkStack", env=env)
```

## Configuration

### VPC Configuration
- CIDR Block: TBD (to avoid conflicts with existing a360-service-patients VPC)
- Availability Zones: TBD
- Subnet Configuration: TBD

### Cross-Account Integration
- Target Account: TBD (a360-service-patients infrastructure)
- VPC Peering/Transit Gateway: TBD

### Tagging Standards
- Environment: TBD
- Project: TBD
- Owner: TBD
- CostCenter: TBD

## Deployment

```bash
# Deploy network stack
cdk deploy NetworkStack

# Deploy with specific configuration
cdk deploy NetworkStack --context vpc-cidr=10.0.0.0/16
```

## Monitoring

- VPC Flow Logs are automatically enabled
- CloudWatch metrics for network performance
- Compliance auditing through Flow Logs

## Compliance

This stack is designed to meet HIPAA compliance requirements for healthcare data processing:
- Network isolation and segmentation
- Comprehensive logging and monitoring
- Security controls for data access
- Audit trail for network activities 