"""LakeFS resources for Dagster+ integration."""

import json
import requests
from base64 import b64encode
from typing import Dict, Any, Optional

import boto3
from dagster import ConfigurableResource, get_dagster_logger
from pydantic import Field


class LakeFSResource(ConfigurableResource):
    """Resource for LakeFS data version control integration."""

    endpoint_url: str = Field(
        description="LakeFS server endpoint URL", default="http://lakefs-internal.us-east-1.amazonaws.com:8000"
    )
    admin_secret_arn: str = Field(description="ARN of Secrets Manager secret containing LakeFS admin credentials")
    region_name: str = Field(description="AWS region name", default="us-east-1")

    def _get_credentials(self) -> tuple[str, str]:
        """Get LakeFS admin credentials from Secrets Manager.

        Supports both LakeFS format (access_key_id/secret_access_key) and
        legacy format (username/password) for backward compatibility.

        Returns:
            tuple[str, str]: (access_key_id, secret_access_key)
        """
        client = boto3.client("secretsmanager", region_name=self.region_name)
        response = client.get_secret_value(SecretId=self.admin_secret_arn)
        secret = json.loads(response["SecretString"])

        # Try LakeFS standard format first
        if "access_key_id" in secret and "secret_access_key" in secret:
            return secret["access_key_id"], secret["secret_access_key"]

        # Try camelCase variants
        if "accessKeyId" in secret and "secretAccessKey" in secret:
            return secret["accessKeyId"], secret["secretAccessKey"]

        # Fallback to legacy username/password format for backward compatibility
        if "username" in secret and "password" in secret:
            return secret["username"], secret["password"]

        # Error if no valid credential format found
        available_keys = list(secret.keys())
        raise ValueError(
            f"Invalid credential format in secret. Expected either "
            f"('access_key_id', 'secret_access_key'), ('accessKeyId', 'secretAccessKey'), "
            f"or ('username', 'password'). Found keys: {available_keys}"
        )

    def _get_auth_header(self) -> str:
        """Get basic authentication header for LakeFS API."""
        access_key_id, secret_access_key = self._get_credentials()
        return b64encode(f"{access_key_id}:{secret_access_key}".encode()).decode()

    def _make_request(
        self, method: str, path: str, data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """Make authenticated request to LakeFS API."""
        url = f"{self.endpoint_url}/api/v1{path}"
        headers = {"Authorization": f"Basic {self._get_auth_header()}", "Content-Type": "application/json"}

        logger = get_dagster_logger()
        logger.info(f"LakeFS API {method} {path}")

        if method.upper() == "GET":
            return requests.get(url, headers=headers, params=params)
        elif method.upper() == "POST":
            return requests.post(url, headers=headers, json=data)
        elif method.upper() == "PUT":
            return requests.put(url, headers=headers, json=data)
        elif method.upper() == "DELETE":
            return requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

    def create_repository(self, name: str, storage_namespace: str, default_branch: str = "main") -> bool:
        """Create a LakeFS repository.

        Args:
            name: Repository name
            storage_namespace: S3 storage namespace (e.g., s3://bucket-name/prefix)
            default_branch: Default branch name

        Returns:
            True if repository was created or already exists, False otherwise
        """
        logger = get_dagster_logger()

        # Check if repository exists
        response = self._make_request("GET", f"/repositories/{name}")
        if response.status_code == 200:
            logger.info(f"Repository {name} already exists")
            return True

        # Create repository
        data = {"name": name, "storage_namespace": storage_namespace, "default_branch": default_branch}

        response = self._make_request("POST", "/repositories", data=data)
        if response.status_code == 201:
            logger.info(f"Created repository {name} with storage {storage_namespace}")
            return True
        else:
            logger.error(f"Failed to create repository {name}: {response.text}")
            return False

    def create_branch(self, repository: str, branch: str, source_branch: str = "main") -> bool:
        """Create a branch in a LakeFS repository.

        Args:
            repository: Repository name
            branch: New branch name
            source_branch: Source branch to branch from

        Returns:
            True if branch was created or already exists, False otherwise
        """
        logger = get_dagster_logger()

        # Check if branch exists
        response = self._make_request("GET", f"/repositories/{repository}/branches/{branch}")
        if response.status_code == 200:
            logger.info(f"Branch {branch} already exists in {repository}")
            return True

        # Create branch
        data = {"name": branch, "source": source_branch}

        response = self._make_request("POST", f"/repositories/{repository}/branches", data=data)
        if response.status_code == 201:
            logger.info(f"Created branch {branch} in {repository}")
            return True
        else:
            logger.error(f"Failed to create branch {branch} in {repository}: {response.text}")
            return False

    def commit_changes(
        self, repository: str, branch: str, message: str, metadata: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """Commit changes to a branch.

        Args:
            repository: Repository name
            branch: Branch name
            message: Commit message
            metadata: Optional commit metadata

        Returns:
            Commit ID if successful, None otherwise
        """
        logger = get_dagster_logger()

        data = {"message": message, "metadata": metadata or {}}

        response = self._make_request("POST", f"/repositories/{repository}/branches/{branch}/commits", data=data)
        if response.status_code == 201:
            commit_id = response.json()["id"]
            logger.info(f"Committed to {repository}:{branch} - {commit_id}")
            return commit_id
        else:
            logger.error(f"Failed to commit to {repository}:{branch}: {response.text}")
            return None

    def merge_branch(
        self, repository: str, source_branch: str, destination_branch: str, message: Optional[str] = None
    ) -> bool:
        """Merge one branch into another.

        Args:
            repository: Repository name
            source_branch: Source branch to merge from
            destination_branch: Destination branch to merge into
            message: Optional merge message

        Returns:
            True if merge was successful, False otherwise
        """
        logger = get_dagster_logger()

        data = {
            "source": source_branch,
            "destination": destination_branch,
        }

        if message:
            data["message"] = message

        response = self._make_request("POST", f"/repositories/{repository}/refs/{destination_branch}/merge", data=data)
        if response.status_code == 200:
            logger.info(f"Merged {source_branch} into {destination_branch} in {repository}")
            return True
        else:
            logger.error(f"Failed to merge {source_branch} into {destination_branch} in {repository}: {response.text}")
            return False

    def merge_branches(
        self, repository: str, source_branch: str, destination_branch: str, message: Optional[str] = None
    ) -> bool:
        """Compatibility alias for merge_branch method.

        This method provides backward compatibility for code that expects merge_branches (plural).
        """
        return self.merge_branch(repository, source_branch, destination_branch, message)

    def list_commits(self, repository: str, branch: str, limit: int = 100) -> list[Dict[str, Any]]:
        """List commits in a branch.

        Args:
            repository: Repository name
            branch: Branch name
            limit: Maximum number of commits to return

        Returns:
            List of commit information
        """
        logger = get_dagster_logger()

        params = {"amount": limit}
        response = self._make_request("GET", f"/repositories/{repository}/refs/{branch}/commits", params=params)

        if response.status_code == 200:
            commits = response.json().get("results", [])
            logger.info(f"Retrieved {len(commits)} commits from {repository}:{branch}")
            return commits
        else:
            logger.error(f"Failed to list commits for {repository}:{branch}: {response.text}")
            return []

    def get_repository_metadata(self, repository: str) -> Optional[Dict[str, Any]]:
        """Get repository metadata.

        Args:
            repository: Repository name

        Returns:
            Repository metadata if successful, None otherwise
        """
        logger = get_dagster_logger()

        response = self._make_request("GET", f"/repositories/{repository}")
        if response.status_code == 200:
            metadata = response.json()
            logger.info(f"Retrieved metadata for repository {repository}")
            return metadata
        else:
            logger.error(f"Failed to get metadata for repository {repository}: {response.text}")
            return None

    def tag_commit(self, repository: str, commit_id: str, tag: str, message: Optional[str] = None) -> bool:
        """Create a tag for a specific commit.

        Args:
            repository: Repository name
            commit_id: Commit ID to tag
            tag: Tag name
            message: Optional tag message

        Returns:
            True if tag was created, False otherwise
        """
        logger = get_dagster_logger()

        data = {"id": commit_id, "message": message or f"Tag {tag} created by Dagster pipeline"}

        response = self._make_request("POST", f"/repositories/{repository}/tags", data=data)
        if response.status_code == 201:
            logger.info(f"Created tag {tag} for commit {commit_id} in {repository}")
            return True
        else:
            logger.error(f"Failed to create tag {tag} for commit {commit_id} in {repository}: {response.text}")
            return False


class LakeFSRepositoryManager:
    """Helper class for managing LakeFS repositories in Dagster pipelines."""

    def __init__(self, lakefs_resource: LakeFSResource):
        """Initialize with LakeFS resource."""
        self.lakefs = lakefs_resource

    def setup_consultation_repositories(self, consultation_buckets: Dict[str, str]) -> Dict[str, bool]:
        """Set up LakeFS repositories for consultation data pipeline.

        Args:
            consultation_buckets: Dictionary mapping bucket types to S3 URIs

        Returns:
            Dictionary mapping repository names to creation status
        """
        results = {}

        for bucket_type, s3_uri in consultation_buckets.items():
            repo_name = f"consultation-{bucket_type}"
            success = self.lakefs.create_repository(name=repo_name, storage_namespace=s3_uri, default_branch="main")
            results[repo_name] = success

            # Create environment branches if repository was created successfully
            if success:
                for env in ["dev", "staging", "prod"]:
                    branch_name = f"{env}"
                    self.lakefs.create_branch(repository=repo_name, branch=branch_name, source_branch="main")

        return results

    def commit_pipeline_stage(
        self, repository: str, branch: str, stage: str, run_id: str, assets: list[str]
    ) -> Optional[str]:
        """Commit changes for a specific pipeline stage.

        Args:
            repository: Repository name
            branch: Branch name
            stage: Pipeline stage name
            run_id: Dagster run ID
            assets: List of asset names processed

        Returns:
            Commit ID if successful, None otherwise
        """
        message = f"Pipeline stage '{stage}' completed"
        metadata = {
            "dagster_run_id": run_id,
            "pipeline_stage": stage,
            "processed_assets": json.dumps(assets),
            "timestamp": json.dumps({"iso": "now"}),  # LakeFS will populate
        }

        return self.lakefs.commit_changes(repository=repository, branch=branch, message=message, metadata=metadata)
