# Spark Processing

![Python Version](https://img.shields.io/badge/python-3.11.9-blue.svg)
![PySpark](https://img.shields.io/badge/PySpark-3.5.5-orange.svg)
![Great Expectations](https://img.shields.io/badge/Great%20Expectations-0.15.6-blue.svg)
![EMR Serverless](https://img.shields.io/badge/EMR%20Serverless-7.9.0-green.svg)

PySpark applications for scalable data processing in the A360 Data Lake.

## Directory Structure

```
spark/
├── 📁 src/
│   ├── 📄 agg_trip_distance.py              # Example aggregation job
│   └── 📄 __init__.py
├── 📁 test/
│   ├── 📄 test_agg_trip_distance.py         # Unit tests
│   └── 📄 __init__.py
├── 📄 Dockerfile                            # Container for EMR Serverless
├── 📄 pyproject.toml                        # Python dependencies
└── 📄 README.md                             # This file
```

## Overview

Healthcare-optimized Spark processing framework providing:
- **HIPAA-Compliant Processing**: Secure handling of PHI data
- **Data Quality Integration**: Great Expectations validation
- **EMR Serverless**: Cost-effective, serverless Spark execution
- **Healthcare Data Patterns**: Specialized transformations for healthcare datasets

## Quick Start

### Local Development
```bash
cd spark
uv sync --dev
uv run pytest
```

### Local Spark Session
```bash
uv run python -c "
from pyspark.sql import SparkSession
spark = SparkSession.builder.appName('local-dev').master('local[*]').getOrCreate()
import logging
logging.info(f'Spark UI: {spark.sparkContext.uiWebUrl}')
"
```

## Security & Compliance

### Encryption
- S3 server-side encryption with customer-managed KMS keys
- In-transit encryption for Spark shuffle operations
- Memory encryption for sensitive data processing

### Access Controls
- EMR Serverless execution roles with minimal required permissions
- Lake Formation integration for data access
- VPC isolation for network security

### Audit Logging
- Comprehensive job execution logging to CloudWatch
- Data lineage tracking through Glue Data Catalog
- Access pattern monitoring via CloudTrail

## Best Practices

### Code Organization
- Separate business logic from Spark configuration
- Use type hints and docstrings
- Implement comprehensive error handling
- Create reusable utility functions

### Healthcare Data Handling
- Always validate PHI compliance before processing
- Implement consistent de-identification patterns
- Use secure data transfer methods
- Maintain audit trails for compliance

### Performance
- Partition data by query access patterns
- Use columnar formats (Parquet) for analytics workloads
- Implement incremental processing for large datasets
- Cache frequently accessed reference data

## Contributing

1. Follow PEP 8 style guidelines
2. Include unit tests for all new functions
3. Document healthcare-specific requirements
4. Test with sample PHI data (synthetic only)
5. Validate HIPAA compliance for all transformations

## References

- [AWS EMR Serverless v7.9.0](https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-release-app-versions-7.x.html)
