
from typing import Any

import requests

from dagster import Field, StringSource, resource


@resource(
    config_schema={
        "lakefs_url": Field(StringSource, default_value="http://localhost:8000"),
        "access_key": Field(StringSource),
        "secret_key": Field(StringSource),
    },
)
def lakefs_resource(context) -> "LakeFSClient":
    """LakeFS resource for Dagster integration."""
    return LakeFSClient(
        url=context.resource_config["lakefs_url"],
        access_key=context.resource_config["access_key"],
        secret_key=context.resource_config["secret_key"],
    )


class LakeFSClient:
    """LakeFS client for data versioning operations."""

    def __init__(self, url: str, access_key: str, secret_key: str):
        self.base_url = url.rstrip('/')
        self.auth = (access_key, secret_key)
        self.session = requests.Session()
        self.session.auth = self.auth

    def create_branch(self, repo: str, branch: str, source_ref: str = "main") -> bool:
        """Create a new branch in a repository."""
        branch_data = {"name": branch, "source": source_ref}

        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/repositories/{repo}/branches",
                json=branch_data,
            )
            return response.status_code in [201, 409]  # Created or already exists
        except Exception:
            return False

    def commit_changes(self, repo: str, branch: str, message: str, metadata: dict[str, Any] = None) -> bool:
        """Commit changes to a branch."""
        commit_data = {
            "message": message,
            "metadata": metadata or {},
        }

        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/repositories/{repo}/branches/{branch}/commits",
                json=commit_data,
            )
            return response.status_code == 201
        except Exception:
            return False

    def merge_branches(self, repo: str, source_branch: str, destination_branch: str) -> bool:
        """Merge source branch into destination branch."""
        merge_data = {
            "source": source_branch,
            "destination": destination_branch,
        }

        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/repositories/{repo}/refs/{destination_branch}/merge",
                json=merge_data,
            )
            return response.status_code == 200
        except Exception:
            return False

    def upload_object(self, repo: str, branch: str, path: str, content: bytes) -> bool:
        """Upload an object to LakeFS."""
        try:
            response = self.session.put(
                f"{self.base_url}/api/v1/repositories/{repo}/branches/{branch}/objects",
                params={"path": path},
                data=content,
                headers={"Content-Type": "application/octet-stream"},
            )
            return response.status_code == 201
        except Exception:
            return False

    def get_object(self, repo: str, ref: str, path: str) -> bytes | None:
        """Get an object from LakeFS."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/repositories/{repo}/refs/{ref}/objects",
                params={"path": path},
            )
            if response.status_code == 200:
                return response.content
            return None
        except Exception:
            return None
