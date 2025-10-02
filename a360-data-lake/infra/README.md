# Infrastructure

![AWS CDK](https://img.shields.io/badge/AWS%20CDK-2.176.0-orange.svg)
![Python](https://img.shields.io/badge/python-3.12.9-blue.svg)
![CDK Nag](https://img.shields.io/badge/CDK%20Nag-enabled-green.svg)

AWS CDK infrastructure code for the A360 Data Lake platform.

## Directory Structure

```
infra/
├── 🏗️ stacks/
│   ├── 🔐 access/
│   │   └── 🔐 ram_datalake_permissions.py                      # Cross-account sharing
│   ├── 📊 catalog/
│   │   └── 📊 glue_datalake_catalog.py                         # Glue Data Catalog
│   ├── 🚀 cicd/
│   │   └── 🚀 github_oidc_role_stack.py                       # GitHub OIDC integration
│   ├── ⚙️ configs/
│   │   ├── ⚙️ account_config.py                               # Account configurations
│   │   ├── ⚙️ database_config.py                              # Database settings
│   │   └── ⚙️ table_config.py                                 # Table definitions
│   ├── 🏛️ management/
│   │   └── 🏛️ lakeformation_datalake_management.py             # Lake Formation
│   ├── 🛡️ permissions/
│   │   └── 🛡️ iam_datalake_permissions.py                     # IAM roles and policies
│   ├── 💾 storage/
│   │   └── 💾 s3_datalake_storage.py                          # S3 buckets and KMS
│   └── 🏗️ component.py                                        # Main orchestration stack
├── 🧪 tests/
│   ├── 🧪 test_datalake_stack.py                              # Infrastructure tests
│   └── 🧪 nag_suppressions.py                                # Security scan suppressions
├── 🐍 app.py                                                  # CDK app entry point
├── 📋 cdk.json                                                # CDK configuration
├── 📋 cdk.context.json                                        # Environment contexts
├── 📦 package.json                                            # Node.js dependencies
└── 🔒 package-lock.json                                       # Dependency lock file
```

## Stack Architecture

The infrastructure is organized into modular stacks:

- **Storage Stack**: S3 buckets, KMS encryption, lifecycle policies
- **Permissions Stack**: IAM roles, Lake Formation service roles
- **Catalog Stack**: Glue databases, crawlers, security configurations
- **Management Stack**: Lake Formation permissions and resource registration
- **Access Stack**: Cross-account sharing via AWS RAM
- **CI/CD Stack**: GitHub OIDC integration for automated deployment

## Configuration

### Account Configuration (`cdk.context.json`)
```json
{
  "staging": {
    "account": "863518416131",
    "region": "us-east-1"
  },
  "prod": {
    "account": "664418972896", 
    "region": "us-east-1"
  }
}
```

## Deployment

### Prerequisites
```bash
npm ci
uv sync --all-extras --dev
```

### Commands
```bash
# Synthesize templates (for validation)
uv run cdk synth --context stage=staging

# View differences (before deployment)
uv run cdk diff --context stage=staging
```

**Note:** Actual deployment is handled via GitHub Actions workflows. See [.github/workflows/README.md](../.github/workflows/README.md) for deployment procedures.

## Security

### CDK Nag Integration
Automated security analysis runs during synthesis:
```bash
# View security findings
cat cdk.out/*NagReport.csv
```

### Key Security Features
- Customer-managed KMS keys with rotation
- Least-privilege IAM policies
- Lake Formation fine-grained access controls
- Cross-account sharing with resource-based policies
- Encryption at rest and in transit

## Testing

```bash
# Run all infrastructure tests
uv run pytest

# Run specific test
uv run pytest tests/test_datalake_stack.py

# Test with coverage
uv run pytest --cov=stacks --cov-report=html
```

## Key Components

### DataFoundation Stack (`stacks/component.py`)
Main orchestration stack that coordinates all other stacks with proper dependency management.

### Storage Stack (`stacks/storage/s3_datalake_storage.py`)
- **S3 Buckets**: Bronze/Silver/Gold zones plus logs and Athena buckets
- **KMS Encryption**: Customer-managed keys with cross-account access
- **Lifecycle Policies**: Automated data tiering for cost optimization

### Permissions Stack (`stacks/permissions/iam_datalake_permissions.py`)
- **User Roles**: Data Admin, Engineer, Analyst with appropriate permissions
- **Service Roles**: Lake Formation workflow and custom service roles
- **Cross-Account**: Federated access for external consumers

### Catalog Stack (`stacks/catalog/glue_datalake_catalog.py`)
- **Glue Databases**: Raw, stage, analytics databases
- **Crawlers**: Automated schema discovery
- **Security**: Encryption for jobs, logs, and bookmarks

## Troubleshooting

### Common Issues

**Lake Formation Permissions**
```bash
aws lakeformation get-data-lake-settings
```

**KMS Key Access**
```bash
aws kms describe-key --key-id alias/a360-datalake-datalake-cmk
```

**Cross-Account Sharing**
```bash
aws ram get-resource-shares --resource-owner SELF
```

### Debug Mode
```bash
export CDK_DEBUG=true
uv run cdk synth --verbose
```

## Best Practices

- **Modularity**: Each stack has a single responsibility
- **Dependencies**: Clear hierarchy with minimal cross-stack references
- **Naming**: Consistent conventions across all resources
- **Security**: Regular CDK Nag scans and security reviews
- **Testing**: Comprehensive unit and integration tests

## Contributing

1. Create feature branch from `main`
2. Make changes in appropriate stack module
3. Add/update tests for new functionality
4. Run `uv run cdk synth` to validate locally
5. Submit pull request with clear description

**Note:** Deployment is automated via GitHub Actions - do not deploy manually.