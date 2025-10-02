# A360 Dagster Pipelines

## Setup

### Authenticate and Prepare Environment

```bash
aws --version                      # ensure ≥2.9.6
aws sso login --profile DataLake-Dev
export AWS_PROFILE=DataLake-Dev    # use the SSO credential cache
```

### Spin Up Local Dagster Instance

```bash
export DAGSTER_HOME="$(pwd)/home" # REPO_ROOT/dagster/home
uv sync
uv run dagster dev
```
