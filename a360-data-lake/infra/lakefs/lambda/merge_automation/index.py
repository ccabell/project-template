#!/usr/bin/env python3
"""LakeFS Merge Automation Lambda.

This Lambda function handles automated merge operations for LakeFS branches
with proper validation, conflict detection, and audit logging.
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


def check_merge_conflicts(repo_name, source_branch, destination_branch, session, headers):
    """Check for merge conflicts before attempting merge."""
    try:
        endpoint = os.environ['LAKEFS_ENDPOINT']

        # Get diff between branches to check for conflicts
        response = session.get(
            f"{endpoint}/api/v1/repositories/{repo_name}/refs/{source_branch}/diff/{destination_branch}",
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            diff_data = response.json()
            results = diff_data.get('results', [])

            # Check for conflicting changes (same path modified in both branches)
            conflicts = [item for item in results if item.get('type') == 'conflict']
            if conflicts:
                print(f"Merge conflicts detected between {source_branch} and {destination_branch}")
                return False, conflicts

            return True, []
        else:
            print(f"Failed to check diff: {response.text}")
            return False, []

    except Exception as e:
        print(f"Error checking merge conflicts: {e!s}")
        return False, []


def merge_branch(repo_name, source_branch, destination_branch):
    """Merge a source branch into a destination branch."""
    try:
        username, password = get_admin_credentials()
        auth_header = b64encode(f"{username}:{password}".encode()).decode()

        endpoint = os.environ['LAKEFS_ENDPOINT']
        headers = {
            'Authorization': f'Basic {auth_header}',
            'Content-Type': 'application/json'
        }

        session = create_http_session()

        # Check for merge conflicts first
        can_merge, conflicts = check_merge_conflicts(
            repo_name, source_branch, destination_branch, session, headers
        )

        if not can_merge:
            return False, f"Merge conflicts detected: {conflicts}"

        # Perform merge
        data = {
            'source': source_branch,
            'destination': destination_branch,
            'message': f'Automated merge: {source_branch} → {destination_branch}'
        }

        response = session.post(
            f"{endpoint}/api/v1/repositories/{repo_name}/refs/{destination_branch}/merge",
            headers=headers,
            json=data,
            timeout=60
        )

        if response.status_code == 200:
            merge_result = response.json()
            print(f"Merged {source_branch} into {destination_branch} in {repo_name}")
            return True, merge_result
        else:
            error_msg = f"Failed to merge {source_branch} into {destination_branch} in {repo_name}: {response.text}"
            print(error_msg)
            return False, error_msg

    except Exception as e:
        error_msg = f"Error merging {source_branch} into {destination_branch} in {repo_name}: {e!s}"
        print(error_msg)
        return False, error_msg


def validate_merge_request(repo_name, source_branch, destination_branch):
    """Validate merge request parameters."""
    if not all([repo_name, source_branch, destination_branch]):
        return False, "repository, source_branch, and destination_branch are required"

    # Prevent merging branch into itself
    if source_branch == destination_branch:
        return False, f"Cannot merge branch {source_branch} into itself"

    # Validate branch names (basic validation)
    invalid_chars = ['..', '//', ' ']
    for branch in [source_branch, destination_branch]:
        if any(char in branch for char in invalid_chars):
            return False, f"Invalid branch name: {branch}"

    return True, ""


def handler(event, context):
    """Handle merge automation requests."""
    print(f"Merge automation event: {json.dumps(event)}")

    repo_name = event.get('repository')
    source_branch = event.get('source_branch')
    destination_branch = event.get('destination_branch')

    # Validate input parameters
    valid, error_msg = validate_merge_request(repo_name, source_branch, destination_branch)
    if not valid:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': error_msg})
        }

    # Perform merge
    success, result = merge_branch(repo_name, source_branch, destination_branch)

    response_data = {
        'success': success,
        'repository': repo_name,
        'source': source_branch,
        'destination': destination_branch
    }

    if success:
        response_data['merge_result'] = result
        return {
            'statusCode': 200,
            'body': json.dumps(response_data)
        }
    else:
        response_data['error'] = result
        return {
            'statusCode': 500,
            'body': json.dumps(response_data)
        }
