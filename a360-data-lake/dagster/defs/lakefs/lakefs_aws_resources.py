#!/usr/bin/env python3
"""
LakeFS AWS Dagster Resources
===========================

Dagster resources for LakeFS integration with dynamic AWS account resolution.
Supports consultation and podcast pipelines with versioned data workflows.
"""

import boto3
import os
from typing import Dict, Any, Optional, List
from dagster import (
    resource,
    Field,
    StringSource,
    IntSource,
    ConfigurableResource,
    InitResourceContext
)
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dataclasses import dataclass


@dataclass
class LakeFSRepository:
    """LakeFS repository information."""
    name: str
    storage_namespace: str
    default_branch: str
    creation_date: str


class LakeFSAWSResource(ConfigurableResource):
    """
    LakeFS resource with AWS integration and dynamic account resolution.
    
    This resource provides LakeFS operations with automatic AWS account
    and region detection for the A360 Data Lake.
    """
    
    lakefs_endpoint: str = Field(
        description="LakeFS server endpoint URL"
    )
    access_key: str = Field(
        description="LakeFS access key"
    )
    secret_key: str = Field(
        description="LakeFS secret key"
    )
    environment: str = Field(
        default="dev",
        description="Environment (dev, staging, prod)"
    )
    timeout: int = Field(
        default=30,
        description="Request timeout in seconds"
    )
    
    def setup_for_execution(self, context: InitResourceContext) -> "LakeFSClient":
        """Setup the LakeFS client for execution."""
        return LakeFSClient(
            endpoint=self.lakefs_endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            environment=self.environment,
            timeout=self.timeout,
            logger=context.log
        )


class LakeFSClient:
    """LakeFS client with AWS integration."""
    
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        environment: str = "dev",
        timeout: int = 30,
        logger=None
    ):
        """
        Initialize LakeFS client.
        
        Args:
            endpoint: LakeFS server endpoint
            access_key: LakeFS access key
            secret_key: LakeFS secret key
            environment: Environment (dev, staging, prod)
            timeout: Request timeout
            logger: Dagster logger
        """
        self.endpoint = endpoint.rstrip('/')
        self.auth = (access_key, secret_key)
        self.environment = environment
        self.timeout = timeout
        self.logger = logger
        
        # Setup HTTP session with retry logic
        self.session = requests.Session()
        self.session.auth = self.auth

        # Configure retry strategy for reliability
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
        self.bucket_name = f"a360-lakefs-data-{environment}-{self.account_id}"
        
        if self.logger:
            self.logger.info(f"LakeFS client initialized - Account: {self.account_id}, Region: {self.region}")
    
    def _get_aws_account_id(self) -> str:
        """Get current AWS account ID dynamically."""
        try:
            # Try environment variable first
            if 'AWS_ACCOUNT_ID' in os.environ:
                return os.environ['AWS_ACCOUNT_ID']
            
            # Get from STS
            sts_client = boto3.client('sts')
            response = sts_client.get_caller_identity()
            return response['Account']
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Could not get AWS account ID: {e}")
            return "unknown"
    
    def _get_aws_region(self) -> str:
        """Get current AWS region dynamically."""
        try:
            # Try environment variable first
            if 'AWS_DEFAULT_REGION' in os.environ:
                return os.environ['AWS_DEFAULT_REGION']
            
            # Get from session
            session = boto3.Session()
            return session.region_name or "us-east-1"
        except Exception:
            return "us-east-1"
    
    def _make_request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make HTTP request to LakeFS API."""
        url = f"{self.endpoint}/api/v1{path}"
        kwargs.setdefault('timeout', self.timeout)
        
        try:
            response = getattr(self.session, method.lower())(url, **kwargs)
            return response
        except requests.exceptions.RequestException as e:
            if self.logger:
                self.logger.error(f"LakeFS API request failed: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test connection to LakeFS."""
        try:
            response = self._make_request('GET', '/repositories')
            return response.status_code == 200
        except Exception:
            return False
    
    def list_repositories(self) -> List[LakeFSRepository]:
        """List all repositories."""
        try:
            response = self._make_request('GET', '/repositories')
            if response.status_code == 200:
                repos_data = response.json().get('results', [])
                return [
                    LakeFSRepository(
                        name=repo['id'],
                        storage_namespace=repo['storage_namespace'],
                        default_branch=repo['default_branch'],
                        creation_date=repo['creation_date']
                    )
                    for repo in repos_data
                ]
            return []
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to list repositories: {e}")
            return []
    
    def create_branch(self, repository: str, branch: str, source_ref: str = "main") -> bool:
        """Create a new branch in a repository."""
        branch_data = {"name": branch, "source": source_ref}
        
        try:
            response = self._make_request(
                'POST',
                f'/repositories/{repository}/branches',
                json=branch_data
            )
            success = response.status_code in [201, 409]  # Created or already exists
            
            if self.logger and success:
                status = "created" if response.status_code == 201 else "already exists"
                self.logger.info(f"Branch '{branch}' {status} in repository '{repository}'")
            
            return success
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create branch '{branch}': {e}")
            return False
    
    def commit_changes(
        self,
        repository: str,
        branch: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Commit changes to a branch."""
        commit_data = {
            "message": message,
            "metadata": metadata or {}
        }
        
        try:
            response = self._make_request(
                'POST',
                f'/repositories/{repository}/branches/{branch}/commits',
                json=commit_data
            )
            success = response.status_code == 201
            
            if self.logger and success:
                self.logger.info(f"Committed changes to '{repository}:{branch}': {message}")
            
            return success
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to commit changes: {e}")
            return False
    
    def merge_branches(
        self,
        repository: str,
        source_branch: str,
        destination_branch: str
    ) -> bool:
        """Merge source branch into destination branch."""
        merge_data = {
            "source": source_branch,
            "destination": destination_branch
        }
        
        try:
            response = self._make_request(
                'POST',
                f'/repositories/{repository}/refs/{destination_branch}/merge',
                json=merge_data
            )
            success = response.status_code == 200
            
            if self.logger and success:
                self.logger.info(f"Merged '{source_branch}' into '{destination_branch}' in '{repository}'")
            
            return success
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to merge branches: {e}")
            return False
    
    def upload_object(
        self,
        repository: str,
        branch: str,
        path: str,
        content: bytes,
        content_type: str = "application/octet-stream"
    ) -> bool:
        """Upload an object to LakeFS."""
        try:
            response = self._make_request(
                'PUT',
                f'/repositories/{repository}/branches/{branch}/objects',
                params={"path": path},
                data=content,
                headers={"Content-Type": content_type}
            )
            success = response.status_code == 201
            
            if self.logger and success:
                self.logger.info(f"Uploaded object '{path}' to '{repository}:{branch}'")
            
            return success
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to upload object '{path}': {e}")
            return False
    
    def get_object(self, repository: str, ref: str, path: str) -> Optional[bytes]:
        """Get an object from LakeFS."""
        try:
            response = self._make_request(
                'GET',
                f'/repositories/{repository}/refs/{ref}/objects',
                params={"path": path}
            )
            if response.status_code == 200:
                return response.content
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to get object '{path}': {e}")
            return None
    
    def get_storage_namespace(self, pipeline: str, layer: str) -> str:
        """Get storage namespace for a pipeline and layer."""
        return f"s3://{self.bucket_name}/{pipeline}/{layer}/"
    
    def get_repository_name(self, pipeline: str, layer: str) -> str:
        """Get repository name for a pipeline and layer."""
        if pipeline == "foundation":
            return f"foundation-{layer}"
        else:
            return f"{pipeline}-{layer}"


# Legacy resource for backward compatibility
@resource(
    config_schema={
        "lakefs_endpoint": Field(
            StringSource,
            description="LakeFS server endpoint URL"
        ),
        "access_key": Field(
            StringSource,
            description="LakeFS access key"
        ),
        "secret_key": Field(
            StringSource,
            description="LakeFS secret key"
        ),
        "environment": Field(
            StringSource,
            default_value="dev",
            description="Environment (dev, staging, prod)"
        ),
        "timeout": Field(
            IntSource,
            default_value=30,
            description="Request timeout in seconds"
        )
    }
)
def lakefs_aws_resource(context) -> LakeFSClient:
    """Legacy LakeFS resource for backward compatibility."""
    return LakeFSClient(
        endpoint=context.resource_config["lakefs_endpoint"],
        access_key=context.resource_config["access_key"],
        secret_key=context.resource_config["secret_key"],
        environment=context.resource_config["environment"],
        timeout=context.resource_config["timeout"],
        logger=context.log
    )