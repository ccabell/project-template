#!/usr/bin/env python3
"""Tests for LakeFS Operations Lambda Functions.

This module contains unit tests for the Lambda functions that handle
repository initialization, branch management, and merge automation.
"""

import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add the Lambda source directories to Python path
lambda_base_path = os.path.join(os.path.dirname(__file__), '..', '..', 'infra', 'lakefs', 'lambda')

sys.path.insert(0, os.path.join(lambda_base_path, 'repository_initializer'))
sys.path.insert(0, os.path.join(lambda_base_path, 'branch_manager'))
sys.path.insert(0, os.path.join(lambda_base_path, 'merge_automation'))

try:
    # Import the Lambda handlers
    import branch_manager.index as branch_mgr
    import merge_automation.index as merge_auto
    import repository_initializer.index as repo_init
except ImportError as e:
    print(f"Warning: Could not import Lambda modules: {e}")
    # Create mock modules for testing
    repo_init = Mock()
    branch_mgr = Mock()
    merge_auto = Mock()


class TestRepositoryInitializer(unittest.TestCase):
    """Test cases for Repository Initializer Lambda."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables
        self.env_vars = {
            'LAKEFS_ENDPOINT': 'https://test-lakefs.example.com',
            'ADMIN_SECRET_ARN': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:lakefs-admin'
        }

    @patch.dict(os.environ, {'LAKEFS_ENDPOINT': 'https://test.com', 'ADMIN_SECRET_ARN': 'test-arn'})
    @patch('boto3.client')
    @patch('requests.Session')
    def test_repository_creation_success(self, mock_session_class, mock_boto_client):
        """Test successful repository creation."""
        if not hasattr(repo_init, 'handler'):
            self.skipTest("Repository initializer module not available")

        # Mock Secrets Manager
        mock_secrets = Mock()
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'username': 'admin', 'password': 'password'})
        }
        mock_boto_client.return_value = mock_secrets

        # Mock HTTP session
        mock_session = Mock()
        mock_get_response = Mock()
        mock_get_response.status_code = 404  # Repository doesn't exist
        mock_session.get.return_value = mock_get_response

        mock_post_response = Mock()
        mock_post_response.status_code = 201  # Created successfully
        mock_session.post.return_value = mock_post_response

        mock_session_class.return_value = mock_session

        # Test event
        event = {
            'repositories': [
                {
                    'name': 'test-repo',
                    'storage_namespace': 's3://test-bucket/test-repo/'
                }
            ]
        }

        # Mock context
        context = Mock()

        # Call handler
        response = repo_init.handler(event, context)

        # Verify response
        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertIn('results', body)
        self.assertEqual(len(body['results']), 1)
        self.assertTrue(body['results'][0]['success'])

    @patch.dict(os.environ, {'LAKEFS_ENDPOINT': 'https://test.com', 'ADMIN_SECRET_ARN': 'test-arn'})
    def test_repository_creation_no_repos(self):
        """Test handler with no repositories in event."""
        if not hasattr(repo_init, 'handler'):
            self.skipTest("Repository initializer module not available")

        event = {'repositories': []}
        context = Mock()

        response = repo_init.handler(event, context)

        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertEqual(len(body['results']), 0)

    @patch.dict(os.environ, {'LAKEFS_ENDPOINT': 'https://test.com', 'ADMIN_SECRET_ARN': 'test-arn'})
    @patch('boto3.client')
    def test_get_admin_credentials(self, mock_boto_client):
        """Test getting admin credentials from Secrets Manager."""
        if not hasattr(repo_init, 'get_admin_credentials'):
            self.skipTest("Repository initializer module not available")

        # Mock Secrets Manager
        mock_secrets = Mock()
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'username': 'test_user', 'password': 'test_pass'})
        }
        mock_boto_client.return_value = mock_secrets

        username, password = repo_init.get_admin_credentials()

        self.assertEqual(username, 'test_user')
        self.assertEqual(password, 'test_pass')


class TestBranchManager(unittest.TestCase):
    """Test cases for Branch Manager Lambda."""

    def setUp(self):
        """Set up test fixtures."""
        self.env_vars = {
            'LAKEFS_ENDPOINT': 'https://test-lakefs.example.com',
            'ADMIN_SECRET_ARN': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:lakefs-admin'
        }

    @patch.dict(os.environ, {'LAKEFS_ENDPOINT': 'https://test.com', 'ADMIN_SECRET_ARN': 'test-arn'})
    @patch('boto3.client')
    @patch('requests.Session')
    def test_branch_creation_success(self, mock_session_class, mock_boto_client):
        """Test successful branch creation."""
        if not hasattr(branch_mgr, 'handler'):
            self.skipTest("Branch manager module not available")

        # Mock Secrets Manager
        mock_secrets = Mock()
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'username': 'admin', 'password': 'password'})
        }
        mock_boto_client.return_value = mock_secrets

        # Mock HTTP session
        mock_session = Mock()
        mock_get_response = Mock()
        mock_get_response.status_code = 404  # Branch doesn't exist
        mock_session.get.return_value = mock_get_response

        mock_post_response = Mock()
        mock_post_response.status_code = 201  # Created successfully
        mock_session.post.return_value = mock_post_response

        mock_session_class.return_value = mock_session

        # Test event
        event = {
            'repository': 'test-repo',
            'branch': 'test-branch',
            'source_branch': 'main'
        }

        context = Mock()
        response = branch_mgr.handler(event, context)

        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertTrue(body['success'])

    @patch.dict(os.environ, {'LAKEFS_ENDPOINT': 'https://test.com', 'ADMIN_SECRET_ARN': 'test-arn'})
    def test_branch_creation_missing_params(self):
        """Test branch creation with missing parameters."""
        if not hasattr(branch_mgr, 'handler'):
            self.skipTest("Branch manager module not available")

        # Test event missing repository
        event = {
            'branch': 'test-branch'
        }

        context = Mock()
        response = branch_mgr.handler(event, context)

        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)

    @patch.dict(os.environ, {'LAKEFS_ENDPOINT': 'https://test.com', 'ADMIN_SECRET_ARN': 'test-arn'})
    @patch('boto3.client')
    @patch('requests.Session')
    def test_branch_deletion_success(self, mock_session_class, mock_boto_client):
        """Test successful branch deletion."""
        if not hasattr(branch_mgr, 'handler'):
            self.skipTest("Branch manager module not available")

        # Mock Secrets Manager
        mock_secrets = Mock()
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'username': 'admin', 'password': 'password'})
        }
        mock_boto_client.return_value = mock_secrets

        # Mock HTTP session
        mock_session = Mock()
        mock_delete_response = Mock()
        mock_delete_response.status_code = 204  # Deleted successfully
        mock_session.delete.return_value = mock_delete_response

        mock_session_class.return_value = mock_session

        # Test event
        event = {
            'repository': 'test-repo',
            'branch': 'test-branch',
            'operation': 'delete'
        }

        context = Mock()
        response = branch_mgr.handler(event, context)

        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertTrue(body['success'])
        self.assertEqual(body['operation'], 'delete')


class TestMergeAutomation(unittest.TestCase):
    """Test cases for Merge Automation Lambda."""

    @patch.dict(os.environ, {'LAKEFS_ENDPOINT': 'https://test.com', 'ADMIN_SECRET_ARN': 'test-arn'})
    @patch('boto3.client')
    @patch('requests.Session')
    def test_merge_success(self, mock_session_class, mock_boto_client):
        """Test successful merge operation."""
        if not hasattr(merge_auto, 'handler'):
            self.skipTest("Merge automation module not available")

        # Mock Secrets Manager
        mock_secrets = Mock()
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'username': 'admin', 'password': 'password'})
        }
        mock_boto_client.return_value = mock_secrets

        # Mock HTTP session
        mock_session = Mock()

        # Mock diff check (no conflicts)
        mock_diff_response = Mock()
        mock_diff_response.status_code = 200
        mock_diff_response.json.return_value = {'results': []}

        # Mock merge response
        mock_merge_response = Mock()
        mock_merge_response.status_code = 200
        mock_merge_response.json.return_value = {'commit': 'abc123'}

        # Configure session to return appropriate responses
        def session_side_effect(*args, **kwargs):
            if 'diff' in args[0]:
                return mock_diff_response
            else:
                return mock_merge_response

        mock_session.get.side_effect = session_side_effect
        mock_session.post.return_value = mock_merge_response
        mock_session_class.return_value = mock_session

        # Test event
        event = {
            'repository': 'test-repo',
            'source_branch': 'develop',
            'destination_branch': 'main'
        }

        context = Mock()
        response = merge_auto.handler(event, context)

        self.assertEqual(response['statusCode'], 200)
        body = json.loads(response['body'])
        self.assertTrue(body['success'])

    @patch.dict(os.environ, {'LAKEFS_ENDPOINT': 'https://test.com', 'ADMIN_SECRET_ARN': 'test-arn'})
    def test_merge_missing_params(self):
        """Test merge operation with missing parameters."""
        if not hasattr(merge_auto, 'handler'):
            self.skipTest("Merge automation module not available")

        # Test event missing destination_branch
        event = {
            'repository': 'test-repo',
            'source_branch': 'develop'
        }

        context = Mock()
        response = merge_auto.handler(event, context)

        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)

    @patch.dict(os.environ, {'LAKEFS_ENDPOINT': 'https://test.com', 'ADMIN_SECRET_ARN': 'test-arn'})
    def test_merge_same_branch(self):
        """Test merge operation with same source and destination branch."""
        if not hasattr(merge_auto, 'handler'):
            self.skipTest("Merge automation module not available")

        # Test event with same source and destination
        event = {
            'repository': 'test-repo',
            'source_branch': 'main',
            'destination_branch': 'main'
        }

        context = Mock()
        response = merge_auto.handler(event, context)

        self.assertEqual(response['statusCode'], 400)
        body = json.loads(response['body'])
        self.assertIn('error', body)
        self.assertIn('Cannot merge branch', body['error'])


class TestLambdaCommonFunctions(unittest.TestCase):
    """Test cases for common functions used across Lambda functions."""

    @patch('requests.Session')
    def test_http_session_creation(self, mock_session_class):
        """Test HTTP session creation with retry logic."""
        if not hasattr(repo_init, 'create_http_session'):
            self.skipTest("HTTP session creation function not available")

        mock_session = Mock()
        mock_session_class.return_value = mock_session

        session = repo_init.create_http_session()

        # Verify session was configured
        mock_session.mount.assert_called()
        self.assertTrue(mock_session.mount.call_count >= 2)  # Should mount both http and https


if __name__ == '__main__':
    unittest.main()
