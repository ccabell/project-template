# Data Lake Notebooks

[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Jupyter](https://img.shields.io/badge/Jupyter-Notebook-orange.svg)](https://jupyter.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

This directory contains Jupyter notebooks for working with the Data Lake infrastructure. These notebooks provide interactive examples and documentation for common data lake operations.

## Quick Start


1. Set up and sync your environment with uv:
   ```bash
   python3 -m pip install --upgrade uv
   uv venv --python 3.12
   source .venv/bin/activate
   uv sync
   ```

2. Start Jupyter Lab:
   ```bash
   jupyter lab
   ```

3. Open the notebook you want to work with from the Jupyter Lab interface.

## Directory Layout

```
notebooks/
├── README.md                 # This file
├── data_exploration/         # Notebooks for exploring data
│   ├── preview_data.ipynb    # Preview and validate data
│   └── analyze_schema.ipynb  # Analyze data schemas
├── data_quality/            # Data quality notebooks
│   ├── validate_data.ipynb  # Data validation checks
│   └── quality_report.ipynb # Generate quality reports
└── examples/                # Example notebooks
    ├── basic_usage.ipynb    # Basic data lake operations
    └── advanced_usage.ipynb # Advanced features
```

## Available Notebooks

### Data Exploration
- `preview_data.ipynb`: Preview and validate data in the data lake
- `analyze_schema.ipynb`: Analyze and document data schemas

### Data Quality
- `validate_data.ipynb`: Run data quality checks
- `quality_report.ipynb`: Generate data quality reports

### Examples
- `basic_usage.ipynb`: Basic data lake operations
- `advanced_usage.ipynb`: Advanced features and best practices

## Troubleshooting

### Common Issues

1. **Kernel Connection Issues**
   - Ensure you're using the correct Python environment
   - Try restarting the Jupyter server
   - Check your AWS credentials are properly configured

2. **AWS Authentication Errors**
   - Verify your AWS credentials are set up correctly
   - Check that your IAM role has the necessary permissions
   - Ensure your AWS profile is active

3. **Memory Issues**
   - Use the `s3_csv_preview.py` utility for large files
   - Consider using Dask for distributed computing
   - Monitor your notebook's memory usage

### Getting Help

1. Check the [utils documentation](../utils/README.md) for utility functions
2. Review the AWS documentation for service-specific issues
3. Contact the data lake team for support

## Best Practices

1. **Data Handling**
   - Use the provided utilities for S3 operations
   - Preview data before loading large files
   - Clean up temporary files and variables

2. **Notebook Organization**
   - Keep notebooks focused on specific tasks
   - Document assumptions and dependencies
   - Include markdown cells for documentation

3. **Performance**
   - Use appropriate chunk sizes for large files
   - Leverage parallel processing when possible
   - Monitor memory usage

## Contributing

1. Follow the notebook template for new notebooks
2. Include proper documentation and examples
3. Test notebooks with different data sizes
4. Update this README when adding new notebooks

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details. 