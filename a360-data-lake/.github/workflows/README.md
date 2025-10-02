# CI/CD Workflows

![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-enabled-green.svg)
![Dev Account](https://img.shields.io/badge/dev-277707121008-blue.svg)
![Staging Account](https://img.shields.io/badge/staging-863518416131-yellow.svg)
![Prod Account](https://img.shields.io/badge/prod-664418972896-red.svg)

Automated CI/CD pipelines for the **A360 Data Lake** platform.

---

## Table of Contents
1. [Directory Structure](#directory-structure)
2. [Workflows Overview](#workflows-overview)  
   2.1 [Dev Build and Deploy](#dev-build-and-deploy-dev-build-and-deployyaml)  
   2.2 [Deploy](#deploy-cdk-diff-deployyaml)
3. [Environment Configuration](#environment-configuration)  
   3.1 [Branch Mapping](#branch-mapping)  
   3.2 [OIDC Integration](#oidc-integration)
4. [Pipeline Features](#pipeline-features)  
   4.1 [Security Scanning](#security-scanning)  
   4.2 [Multi‑Environment Support](#multi-environment-support)  
   4.3 [Artifact Management](#artifact-management)
5. [Usage](#usage)  
   5.1 [Development Workflow](#development-workflow)  
   5.2 [Deployment Workflow](#deployment-workflow)
6. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
7. [Security Best Practices](#security-best-practices)
8. [Performance Optimization](#performance-optimization)
9. [Contributing](#contributing)

---

## Directory Structure

```
.github/workflows/
├── 📄 dev-build-and-deploy.yaml           # Dev build / test / synth pipeline
├── 📄 cdk-diff-deploy.yaml                # Manual diff / deploy pipeline
└── 📄 README.md                           # This file
```

---

## Workflows Overview

### Dev Build and Deploy (`dev-build-and-deploy.yaml`)

| Trigger | Condition |
|---------|-----------|
| Push    | branch = `develop` |
| Pull Request | **source branch** starts with `ADE-`, `DSO-`, or `AIML-` |
| Manual  | `workflow_dispatch` |

**Stages**

1. Environment setup (Node 22, Python 3.12, Docker Buildx, uv)  
2. Dependency install (`npm ci` + `uv sync`)  
3. Tests (`pytest`)  
4. CDK synth (NPX CDK with *dev* context)  
5. Security scan (cdk‑nag)  
6. Artifact upload (`cdk.out` + reports)

**Key Features**

* Builds always target the **dev** AWS account `277707121008`.  
* OIDC role assumption keeps the pipeline credential‑free.  
* Security findings are reported but non‑blocking.  
* Synth artifacts are published for downstream deploy jobs.

### Deploy (`cdk-diff-deploy.yaml`)

| Trigger | Manual (`workflow_dispatch`) |
|---------|-----------------------------|
| Inputs  | `environment` (dev / staging / prod)<br>`cdk_action` (diff / deploy) |

**Stages**

1. Environment & OIDC setup  
2. Artifact download  
3. CDK diff / deploy  
4. Post‑deploy verification  

*Environment ↔︎ Account mapping*

| Environment | Account ID |
|-------------|------------|
| dev     | `277707121008` |
| staging | `863518416131` |
| prod    | `664418972896` |

---

## Environment Configuration

### Branch Mapping
* `develop` → **dev** (`277707121008`)  
* `release` → **staging** (`863518416131`)  
* `main` → **prod** (`664418972896`)

### OIDC Integration

Trust relationship for the GitHub OIDC role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:Aesthetics-360/a360-data-lake:*"
        }
      }
    }
  ]
}
```

---

## Pipeline Features

### Security Scanning
* Integrated **cdk‑nag** run during synth  
* CSV report in `cdk.out`  
* Counts critical issues but does not fail *dev* builds

### Multi‑Environment Support
Dynamic account selection per environment:
* `dev` → `277707121008`  
* `staging` → `863518416131`  
* `prod` → `664418972896`

### Artifact Management
* Synth templates, security reports, and test outputs stored as GitHub Artifacts  
* Shared across workflows; retention managed by repo settings

---

## Usage

### Development Workflow

```bash
# 1  Create a feature branch with a JIRA key
git checkout -b ADE-123-new-data-source

# 2  Work, commit, push
git push -u origin ADE-123-new-data-source

# 3  Open a PR (any target branch)
#     → Dev Build and Deploy runs automatically
#     → Review tests & security scan

# 4  Merge into develop when approved
```

### Deployment Workflow

1. Go to **Actions → Deploy (cdk-diff-deploy)**  
2. Click **Run workflow**  
3. Select parameters (`environment` + `cdk_action`)  
4. Monitor; verify post‑deploy checks

---

## Monitoring and Troubleshooting

### Build Failures
* Test failures → check `pytest` log  
* Security scan issues → inspect `cdk.out/*NagReport.csv`  
* Synth errors → run `npx cdk synth` locally

### Deployment Issues
```bash
# Verify OIDC role
aws iam get-role --role-name AWSGitHubOIDCAdministratorRole

# Check trust policy
aws iam get-role --role-name AWSGitHubOIDCAdministratorRole                  --query 'Role.AssumeRolePolicyDocument'
```
* Validate cross‑account role assumptions  
* Ensure CDK bootstrap permissions are correct

### Workflow Debugging
Set debug flags:

```yaml
env:
  ACTIONS_STEP_DEBUG: true
  ACTIONS_RUNNER_DEBUG: true
```

Run steps locally with **`act`**:

```bash
act --workflows .github/workflows/dev-build-and-deploy.yaml
```

---

## Security Best Practices
* No hard‑coded secrets; use GitHub Secrets + OIDC  
* Least‑privilege IAM policies  
* Automated vuln scans and linting  
* Protected branches and required reviews

---

## Performance Optimization
* NPM & uv caching  
* Docker Buildx layer caching  
* Parallel jobs when feasible  
* Prudent artifact retention

---

## Contributing

1. Test workflow changes locally  
2. Open a PR with clear description  
3. Ensure no credentials are exposed  
4. Validate in *staging* before merging to *main*  

Follow semantic commits and GitHub Actions security guidelines.
