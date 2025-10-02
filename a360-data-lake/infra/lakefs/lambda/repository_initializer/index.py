#!/usr/bin/env python3
"""LakeFS Repository Initializer Lambda.

This Lambda function handles automated repository creation and initialization
for LakeFS data version control with proper error handling and logging.
"""

import json
import os
from base64 import b64encode

import boto3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_admin_credentials():
    """Get LakeFS admin credentials from Secrets Manager."""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=os.environ['ADMIN_SECRET_ARN'])
    secret = json.loads(response['SecretString'])
    return secret['username'], secret['password']


def create_http_session():
    """Create HTTP session with retry logic."""
    session = requests.Session()

    # Configure retry strategy for reliability
    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        backoff_factor=1,
        allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def create_repository(repo_name, storage_namespace):
    """Create a LakeFS repository with proper error handling."""
    try:
        username, password = get_admin_credentials()
        auth_header = b64encode(f"{username}:{password}".encode()).decode()

        endpoint = os.environ['LAKEFS_ENDPOINT']
        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/json'
        }

        session = create_http_session()

        # Check if repository exists
        response = session.get(f"{endpoint}/api/v1/repositories/{repo_name}", headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"Repository {repo_name} already exists")
            return True

        # Create repository
        data = {
            'name': repo_name,
            'storage_namespace': storage_namespace,
            'default_branch': 'main'
        }

        response = session.post(f"{endpoint}/api/v1/repositories", headers=headers, json=data, timeout=30)
        if response.status_code == 201:
            print(f"Created repository {repo_name} with storage {storage_namespace}")

            # Create additional branches for medallion architecture
            create_additional_branches(session, endpoint, headers, repo_name)
            return True
        else:
            print(f"Failed to create repository {repo_name}: {response.text}")
            return False

    except Exception as e:
        print(f"Error creating repository {repo_name}: {e!s}")
        return False


def create_additional_branches(session, endpoint, headers, repo_name):
    """Create additional branches for data pipeline workflows."""
    branches = ["develop", "staging"]

    for branch in branches:
        try:
            branch_data = {"name": branch, "source": "main"}
            response = session.post(
                f"{endpoint}/api/v1/repositories/{repo_name}/branches",
                headers=headers,
                json=branch_data,
                timeout=10
            )
            if response.status_code == 201:
                print(f"Created branch {branch} in repository {repo_name}")
            else:
                print(f"Warning: Failed to create branch {branch}: {response.text}")
        except Exception as e:
            print(f"Warning: Error creating branch {branch}: {e!s}")


def handler(event, context):
    """Handle repository initialization requests."""
    print(f"Repository initialization event: {json.dumps(event)}")

    repositories = event.get('repositories', [])
    results = []

    for repo_config in repositories:
        name = repo_config['name']
        storage_namespace = repo_config['storage_namespace']

        success = create_repository(name, storage_namespace)
        results.append({'repository': name, 'success': success})

    return {
        'statusCode': 200,
        'body': json.dumps({'results': results})
    }
