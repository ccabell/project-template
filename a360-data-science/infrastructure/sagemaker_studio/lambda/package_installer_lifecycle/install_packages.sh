#!/bin/bash

set -eux

# Install and configure uv
curl -sSf https://astral.sh/uv/install.sh | sh
PATH="$HOME/.cargo/bin:$PATH"

# Install Python 3.12.8 if not already available
if ! command -v python3.12 &> /dev/null; then
    pyenv install 3.12.8
    pyenv global 3.12.8
fi

# Install common data science packages using uv
uv pip install --upgrade \
    pandas==2.2.3 \
    scikit-learn==1.5.0 \
    matplotlib==3.10.0 \
    seaborn==0.13.2 \
    plotly==6.0.0 \
    ipywidgets==8.1.5 \
    boto3==1.36.15 \
    sagemaker==2.239.0 \
    awswrangler==3.11.0 \
    scipy==1.15.1 \
    statsmodels==0.14.1 \
    xgboost==2.1.4 \
    polars==1.21.0 \
    duckdb==1.2.0 \
    spacy==3.8.2 \
    fireducks==1.1.8 \
    pyspark==3.5.4 \
    modin==0.32.0 \
    ray==2.37.0 \
    aws-cdk-lib==2.178.0 \
    constructs==10.4.2

# Setup notebook extensions
jupyter labextension install @jupyter-widgets/jupyterlab-manager

# Create .python-version file in home directory
echo "3.12.8" > $HOME/.python-version