#!/usr/bin/env python3
"""LakeFS Branch Manager Lambda.

This Lambda function handles automated branch creation, deletion, and management
for LakeFS repositories with proper error handling and retry logic.
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


def create_branch(repo_name, branch_name, source_branch='main'):
    """Create a new branch in a LakeFS repository."""
    try:
        username, password = get_admin_credentials()
        auth_header = b64encode(f"{username}:{password}".encode()).decode()

        endpoint = os.environ['LAKEFS_ENDPOINT']
        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/json'
        }

        session = create_http_session()

        # Check if branch exists
        response = session.get(
            f"{endpoint}/api/v1/repositories/{repo_name}/branches/{branch_name}",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            print(f"Branch {branch_name} already exists in {repo_name}")
            return True

        # Create branch
        data = {
            'name': branch_name,
            'source': source_branch
        }

        response = session.post(
            f"{endpoint}/api/v1/repositories/{repo_name}/branches",
            headers=headers,
            json=data,
            timeout=30
        )
        if response.status_code == 201:
            print(f"Created branch {branch_name} in {repo_name}")
            return True
        else:
            print(f"Failed to create branch {branch_name} in {repo_name}: {response.text}")
            return False

    except Exception as e:
        print(f"Error creating branch {branch_name} in {repo_name}: {e!s}")
        return False


def delete_branch(repo_name, branch_name):
    """Delete a branch from a LakeFS repository."""
    try:
        username, password = get_admin_credentials()
        auth_header = b64encode(f"{username}:{password}".encode()).decode()

        endpoint = os.environ['LAKEFS_ENDPOINT']
        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/json'
        }

        session = create_http_session()

        # Prevent deletion of main branch
        if branch_name.lower() == 'main':
            print(f"Cannot delete main branch in {repo_name}")
            return False

        response = session.delete(
            f"{endpoint}/api/v1/repositories/{repo_name}/branches/{branch_name}",
            headers=headers,
            timeout=30
        )
        if response.status_code == 204:
            print(f"Deleted branch {branch_name} from {repo_name}")
            return True
        else:
            print(f"Failed to delete branch {branch_name} from {repo_name}: {response.text}")
            return False

    except Exception as e:
        print(f"Error deleting branch {branch_name} from {repo_name}: {e!s}")
        return False


def handler(event, context):
    """Handle branch management requests."""
    print(f"Branch management event: {json.dumps(event)}")

    repo_name = event.get('repository')
    branch_name = event.get('branch')
    operation = event.get('operation', 'create')
    source_branch = event.get('source_branch', 'main')

    if not repo_name or not branch_name:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'repository and branch are required'})
        }

    if operation == 'create':
        success = create_branch(repo_name, branch_name, source_branch)
    elif operation == 'delete':
        success = delete_branch(repo_name, branch_name)
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Unknown operation: {operation}'})
        }

    return {
        'statusCode': 200,
        'body': json.dumps({
            'success': success,
            'repository': repo_name,
            'branch': branch_name,
            'operation': operation
        })
    }
