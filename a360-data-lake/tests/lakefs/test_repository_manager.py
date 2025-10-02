#!/usr/bin/env python3
"""Tests for LakeFS Repository Manager.

This module contains unit and integration tests for the LakeFS repository
management functionality including repository creation, configuration,
and validation.
"""

import os

# Import the repository manager from the infra module
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'infra', 'stacks'))

try:
    from lakefs.repository_manager import LakeFSRepositoryManager, RepositoryConfig
except ImportError:
    # Fallback for different import paths
    from infra.stacks.lakefs.repository_manager import (
        LakeFSRepositoryManager,
        RepositoryConfig,
    )


class TestRepositoryConfig(unittest.TestCase):
    """Test cases for RepositoryConfig dataclass."""

    def test_repository_config_creation(self):
        """Test creation of repository configuration."""
        config = RepositoryConfig(
            name="test-repo",
            description="Test repository",
            medallion_layer="bronze"
        )

        self.assertEqual(config.name, "test-repo")
        self.assertEqual(config.description, "Test repository")
        self.assertEqual(config.medallion_layer, "bronze")

    def test_repository_config_defaults(self):
        """Test default values in repository configuration."""
        config = RepositoryConfig(
            name="test-repo",
            description="Test repository"
        )

        # Should have default medallion_layer
        self.assertIsNotNone(config.medallion_layer)


class TestLakeFSRepositoryManager(unittest.TestCase):
    """Test cases for LakeFS Repository Manager."""

    def setUp(self):
        """Set up test fixtures."""
        self.lakefs_endpoint = "https://test-lakefs.example.com"
        self.access_key = "test_access_key"
        self.secret_key = "test_secret_key"

        # Mock AWS STS and session
        with patch('boto3.client') as mock_boto_client, \
             patch('boto3.Session') as mock_session:

            # Mock STS client for account ID
            mock_sts = Mock()
            mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}

            # Mock session for region
            mock_session_instance = Mock()
            mock_session_instance.region_name = 'us-east-1'
            mock_session.return_value = mock_session_instance

            # Configure boto3.client to return appropriate mocks
            def client_side_effect(service_name):
                if service_name == 'sts':
                    return mock_sts
                return Mock()

            mock_boto_client.side_effect = client_side_effect

            self.manager = LakeFSRepositoryManager(
                self.lakefs_endpoint,
                self.access_key,
                self.secret_key
            )

    @patch('requests.Session')
    def test_repository_manager_initialization(self, mock_session):
        """Test repository manager initialization."""
        with patch('boto3.client') as mock_boto_client, \
             patch('boto3.Session') as mock_session_boto:

            # Mock STS client
            mock_sts = Mock()
            mock_sts.get_caller_identity.return_value = {'Account': '123456789012'}
            mock_boto_client.return_value = mock_sts

            # Mock session for region
            mock_session_instance = Mock()
            mock_session_instance.region_name = 'us-east-1'
            mock_session_boto.return_value = mock_session_instance

            manager = LakeFSRepositoryManager(
                "https://test.example.com",
                "access_key",
                "secret_key"
            )

            self.assertEqual(manager.lakefs_endpoint, "https://test.example.com")
            self.assertEqual(manager.account_id, "123456789012")
            self.assertEqual(manager.region, "us-east-1")

    def test_repository_exists_true(self):
        """Test repository_exists method when repository exists."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        self.manager.session.get = Mock(return_value=mock_response)

        result = self.manager.repository_exists("test-repo")

        self.assertTrue(result)
        self.manager.session.get.assert_called_once()

    def test_repository_exists_false(self):
        """Test repository_exists method when repository doesn't exist."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        self.manager.session.get = Mock(return_value=mock_response)

        result = self.manager.repository_exists("test-repo")

        self.assertFalse(result)

    def test_repository_exists_exception(self):
        """Test repository_exists method when exception occurs."""
        # Mock exception
        self.manager.session.get = Mock(side_effect=Exception("Connection error"))

        result = self.manager.repository_exists("test-repo")

        self.assertFalse(result)

    def test_create_repository_success(self):
        """Test successful repository creation."""
        config = RepositoryConfig(
            name="test-repo",
            description="Test repository",
            medallion_layer="bronze"
        )

        # Mock repository doesn't exist initially
        self.manager.repository_exists = Mock(return_value=False)

        # Mock successful creation response
        mock_response = Mock()
        mock_response.status_code = 201
        self.manager.session.post = Mock(return_value=mock_response)

        # Mock branch creation
        self.manager._create_branches = Mock()

        success, message = self.manager.create_repository(config)

        self.assertTrue(success)
        self.assertIn("Created repository", message)
        self.manager._create_branches.assert_called_once()

    def test_create_repository_already_exists(self):
        """Test repository creation when repository already exists."""
        config = RepositoryConfig(
            name="existing-repo",
            description="Existing repository",
            medallion_layer="bronze"
        )

        # Mock repository already exists
        self.manager.repository_exists = Mock(return_value=True)

        success, message = self.manager.create_repository(config)

        self.assertTrue(success)
        self.assertIn("already exists", message)

    def test_create_repository_failure(self):
        """Test repository creation failure."""
        config = RepositoryConfig(
            name="test-repo",
            description="Test repository",
            medallion_layer="bronze"
        )

        # Mock repository doesn't exist
        self.manager.repository_exists = Mock(return_value=False)

        # Mock failed creation response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        self.manager.session.post = Mock(return_value=mock_response)

        success, message = self.manager.create_repository(config)

        self.assertFalse(success)
        self.assertIn("Failed to create", message)

    def test_get_lakefs_bucket_name(self):
        """Test LakeFS bucket name generation."""
        bucket_name = self.manager._get_lakefs_bucket_name("dev")
        expected = "a360-lakefs-data-dev-123456789012"

        self.assertEqual(bucket_name, expected)

    def test_create_all_repositories(self):
        """Test creating all repositories."""
        # Mock successful creation for all repos
        self.manager.create_repository = Mock(return_value=(True, "Created successfully"))

        results = self.manager.create_all_repositories("dev")

        # Should have created repositories for consultation and podcast pipelines
        self.assertIn('summary', results)
        self.assertIn('succeeded', results['summary'])
        self.assertIn('failed', results['summary'])

        # Should have called create_repository multiple times
        self.assertGreater(self.manager.create_repository.call_count, 0)


class TestRepositoryManagerIntegration(unittest.TestCase):
    """Integration tests for repository manager (requires actual LakeFS instance)."""

    def setUp(self):
        """Set up integration test environment."""
        # Skip if no LakeFS environment variables are set
        self.lakefs_endpoint = os.environ.get('TEST_LAKEFS_ENDPOINT')
        self.access_key = os.environ.get('TEST_LAKEFS_ACCESS_KEY')
        self.secret_key = os.environ.get('TEST_LAKEFS_SECRET_KEY')

        if not all([self.lakefs_endpoint, self.access_key, self.secret_key]):
            self.skipTest("LakeFS integration test environment not configured")

    @unittest.skipIf(
        not all([
            os.environ.get('TEST_LAKEFS_ENDPOINT'),
            os.environ.get('TEST_LAKEFS_ACCESS_KEY'),
            os.environ.get('TEST_LAKEFS_SECRET_KEY')
        ]),
        "LakeFS integration test environment not configured"
    )
    def test_connection(self):
        """Test actual connection to LakeFS instance."""
        manager = LakeFSRepositoryManager(
            self.lakefs_endpoint,
            self.access_key,
            self.secret_key
        )

        # Test connection
        connected = manager.test_connection()
        self.assertTrue(connected, "Should be able to connect to LakeFS")


if __name__ == '__main__':
    unittest.main()
