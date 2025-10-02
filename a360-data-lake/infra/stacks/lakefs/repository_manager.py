#!/usr/bin/env python3
"""LakeFS Repository Manager
========================

Manages LakeFS repositories with dynamic AWS account resolution for A360 Data Lake.
Creates repositories for consultation and podcast pipelines following medallion architecture.
"""

from dataclasses import dataclass

import boto3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class RepositoryConfig:
    """Configuration for a LakeFS repository."""
    name: str
    description: str
    layer: str  # landing, bronze, silver, gold
    pipeline: str  # consultation, podcast, foundation

    def get_storage_namespace(self, bucket_name: str) -> str:
        """Generate S3 storage namespace for this repository."""
        if self.pipeline == "foundation":
            return f"s3://{bucket_name}/{self.pipeline}/{self.name.split('-')[1]}/"
        else:
            return f"s3://{bucket_name}/{self.pipeline}/{self.layer}/"


class LakeFSRepositoryManager:
    """Manages LakeFS repositories with dynamic AWS configuration."""

    def __init__(self, lakefs_endpoint: str, access_key: str, secret_key: str):
        """Initialize repository manager.

        Args:
            lakefs_endpoint: LakeFS server endpoint
            access_key: LakeFS access key
            secret_key: LakeFS secret key
        """
        self.lakefs_endpoint = lakefs_endpoint.rstrip('/')
        self.auth = (access_key, secret_key)
        self.session = requests.Session()
        self.session.auth = self.auth

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            backoff_factor=1,
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Get AWS account info dynamically
        self.account_id = self._get_aws_account_id()
        self.region = self._get_aws_region()

    def _get_aws_account_id(self) -> str:
        """Get current AWS account ID dynamically."""
        try:
            sts_client = boto3.client('sts')
            response = sts_client.get_caller_identity()
            return response['Account']
        except Exception as e:
            raise RuntimeError(f"Failed to get AWS account ID: {e}")

    def _get_aws_region(self) -> str:
        """Get current AWS region dynamically."""
        try:
            session = boto3.Session()
            return session.region_name or "us-east-1"
        except Exception:
            return "us-east-1"

    def _get_lakefs_bucket_name(self, env: str = "dev") -> str:
        """Get LakeFS S3 bucket name dynamically."""
        return f"a360-lakefs-data-{env}-{self.account_id}"

    def get_repository_configurations(self) -> list[RepositoryConfig]:
        """Get all repository configurations for A360 Data Lake."""
        return [
            # Consultation Pipeline (Medallion Architecture)
            RepositoryConfig(
                name="consultation-landing",
                description="Raw consultation data ingestion (Landing layer)",
                layer="landing",
                pipeline="consultation",
            ),
            RepositoryConfig(
                name="consultation-bronze",
                description="Transcribed consultation data (Bronze layer)",
                layer="bronze",
                pipeline="consultation",
            ),
            RepositoryConfig(
                name="consultation-silver",
                description="PHI-redacted consultation data (Silver layer)",
                layer="silver",
                pipeline="consultation",
            ),
            RepositoryConfig(
                name="consultation-gold",
                description="Analytics-ready consultation insights (Gold layer)",
                layer="gold",
                pipeline="consultation",
            ),

            # Podcast Pipeline (Medallion Architecture)
            RepositoryConfig(
                name="podcast-landing",
                description="Raw podcast audio files (Landing layer)",
                layer="landing",
                pipeline="podcast",
            ),
            RepositoryConfig(
                name="podcast-bronze",
                description="Transcribed podcast data (Bronze layer)",
                layer="bronze",
                pipeline="podcast",
            ),
            RepositoryConfig(
                name="podcast-silver",
                description="Cleaned podcast transcriptions (Silver layer)",
                layer="silver",
                pipeline="podcast",
            ),
            RepositoryConfig(
                name="podcast-gold",
                description="Analytics-ready podcast insights (Gold layer)",
                layer="gold",
                pipeline="podcast",
            ),

            # Foundation/Shared Data
            RepositoryConfig(
                name="foundation-metadata",
                description="Shared metadata, schemas, and configurations",
                layer="metadata",
                pipeline="foundation",
            ),
            RepositoryConfig(
                name="foundation-models",
                description="ML models, embeddings, and AI artifacts",
                layer="models",
                pipeline="foundation",
            ),
        ]

    def test_connection(self) -> bool:
        """Test connection to LakeFS server."""
        try:
            response = self.session.get(f"{self.lakefs_endpoint}/api/v1/repositories", timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def repository_exists(self, repo_name: str) -> bool:
        """Check if repository exists."""
        try:
            response = self.session.get(f"{self.lakefs_endpoint}/api/v1/repositories/{repo_name}", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def create_repository(self, config: RepositoryConfig, env: str = "dev") -> tuple[bool, str]:
        """Create a LakeFS repository.

        Args:
            config: Repository configuration
            env: Environment (dev, staging, prod)

        Returns:
            Tuple of (success, message)
        """
        bucket_name = self._get_lakefs_bucket_name(env)
        storage_namespace = config.get_storage_namespace(bucket_name)

        repo_data = {
            "name": config.name,
            "storage_namespace": storage_namespace,
            "default_branch": "main",
            "sample_data": False,
        }

        try:
            # Check if repository already exists
            if self.repository_exists(config.name):
                return True, f"Repository '{config.name}' already exists"

            # Create repository
            response = self.session.post(
                f"{self.lakefs_endpoint}/api/v1/repositories",
                json=repo_data,
                timeout=30,
            )

            if response.status_code == 201:
                # Create additional branches (develop, staging)
                self._create_branches(config.name)
                return True, f"Created repository '{config.name}'"
            else:
                error_msg = response.text
                return False, f"Failed to create '{config.name}': {error_msg}"

        except Exception as e:
            return False, f"Error creating '{config.name}': {e!s}"

    def _create_branches(self, repo_name: str) -> None:
        """Create additional branches for a repository."""
        branches = ["develop", "staging"]

        for branch in branches:
            try:
                branch_data = {"name": branch, "source": "main"}
                self.session.post(
                    f"{self.lakefs_endpoint}/api/v1/repositories/{repo_name}/branches",
                    json=branch_data,
                    timeout=10,
                )
            except Exception:
                pass  # Branch creation is optional

    def create_all_repositories(self, env: str = "dev") -> dict[str, dict]:
        """Create all A360 Data Lake repositories.

        Args:
            env: Environment (dev, staging, prod)

        Returns:
            Dictionary with creation results
        """
        results = {
            "success": [],
            "failed": [],
            "summary": {},
        }

        configs = self.get_repository_configurations()

        for config in configs:
            success, message = self.create_repository(config, env)

            if success:
                results["success"].append({
                    "name": config.name,
                    "message": message,
                    "storage_namespace": config.get_storage_namespace(self._get_lakefs_bucket_name(env)),
                })
            else:
                results["failed"].append({
                    "name": config.name,
                    "error": message,
                })

        results["summary"] = {
            "total": len(configs),
            "succeeded": len(results["success"]),
            "failed": len(results["failed"]),
        }

        return results

    def list_repositories(self) -> list[dict]:
        """List all repositories."""
        try:
            response = self.session.get(f"{self.lakefs_endpoint}/api/v1/repositories", timeout=10)
            if response.status_code == 200:
                return response.json().get("results", [])
            return []
        except Exception:
            return []

    def get_repository_info(self, repo_name: str) -> dict | None:
        """Get detailed information about a repository."""
        try:
            response = self.session.get(f"{self.lakefs_endpoint}/api/v1/repositories/{repo_name}", timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None


def main():
    """Example usage of LakeFS Repository Manager."""
    import os

    # Get configuration from environment or parameters
    lakefs_endpoint = os.environ.get("LAKEFS_ENDPOINT", "http://localhost:8000")
    access_key = os.environ.get("LAKEFS_ACCESS_KEY")
    secret_key = os.environ.get("LAKEFS_SECRET_KEY")
    env = os.environ.get("ENVIRONMENT", "dev")

    if not access_key or not secret_key:
        print("Error: LAKEFS_ACCESS_KEY and LAKEFS_SECRET_KEY environment variables required")
        return

    # Initialize manager
    manager = LakeFSRepositoryManager(lakefs_endpoint, access_key, secret_key)

    # Test connection
    print(f"Testing connection to LakeFS at {lakefs_endpoint}...")
    if not manager.test_connection():
        print("Error: Could not connect to LakeFS")
        return

    print("Connection successful!")
    print(f"AWS Account: {manager.account_id}")
    print(f"AWS Region: {manager.region}")
    print(f"S3 Bucket: {manager._get_lakefs_bucket_name(env)}")

    # Create all repositories
    print(f"\nCreating repositories for environment: {env}")
    results = manager.create_all_repositories(env)

    # Print results
    print("\n=== Repository Creation Results ===")
    print(f"Total: {results['summary']['total']}")
    print(f"Succeeded: {results['summary']['succeeded']}")
    print(f"Failed: {results['summary']['failed']}")

    if results["success"]:
        print("\n✅ Successfully created:")
        for repo in results["success"]:
            print(f"  - {repo['name']}: {repo['message']}")

    if results["failed"]:
        print("\n❌ Failed to create:")
        for repo in results["failed"]:
            print(f"  - {repo['name']}: {repo['error']}")


if __name__ == "__main__":
    main()
