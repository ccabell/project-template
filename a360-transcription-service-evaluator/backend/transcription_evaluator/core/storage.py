#!/usr/bin/env python3
"""
Storage abstraction for transcription evaluation toolkit.

This module provides a unified interface for storing and retrieving files
using either S3 (default) or local filesystem storage.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def save_text(self, path: str, content: str) -> str:
        """Save text content to storage."""
        pass
    
    @abstractmethod
    def save_json(self, path: str, data: Dict[str, Any]) -> str:
        """Save JSON data to storage."""
        pass
    
    @abstractmethod
    def save_binary(self, path: str, data: bytes) -> str:
        """Save binary data to storage."""
        pass
    
    @abstractmethod
    def load_text(self, path: str) -> str:
        """Load text content from storage."""
        pass
    
    @abstractmethod
    def load_json(self, path: str) -> Dict[str, Any]:
        """Load JSON data from storage."""
        pass
    
    @abstractmethod
    def load_binary(self, path: str) -> bytes:
        """Load binary data from storage."""
        pass
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if file exists in storage."""
        pass
    
    @abstractmethod
    def list_files(self, prefix: str) -> List[str]:
        """List files with given prefix."""
        pass
    
    @abstractmethod
    def get_url(self, path: str) -> str:
        """Get access URL for the file."""
        pass


class S3Backend(StorageBackend):
    """S3 storage backend implementation."""
    
    def __init__(
        self, 
        bucket_name: str,
        aws_profile: Optional[str] = None
    ):
        self.bucket_name = bucket_name
        
        if aws_profile:
            session = boto3.Session(profile_name=aws_profile)
            self.s3_client = session.client('s3')
        else:
            self.s3_client = boto3.client('s3')
        
        logger.info(f"Initialized S3Backend with bucket: {bucket_name}")
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path for S3 (remove leading slash)."""
        return path.lstrip('/')
    
    def save_text(self, path: str, content: str) -> str:
        """Save text content to S3."""
        try:
            key = self._normalize_path(path)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content.encode('utf-8'),
                ContentType='text/plain'
            )
            url = f"s3://{self.bucket_name}/{key}"
            logger.info(f"Saved text file to: {url}")
            return url
        except Exception as e:
            logger.error(f"Failed to save text to S3: {e}")
            raise
    
    def save_json(self, path: str, data: Dict[str, Any]) -> str:
        """Save JSON data to S3."""
        try:
            key = self._normalize_path(path)
            content = json.dumps(data, indent=2, ensure_ascii=False)
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content.encode('utf-8'),
                ContentType='application/json'
            )
            url = f"s3://{self.bucket_name}/{key}"
            logger.info(f"Saved JSON file to: {url}")
            return url
        except Exception as e:
            logger.error(f"Failed to save JSON to S3: {e}")
            raise
    
    def save_binary(self, path: str, data: bytes) -> str:
        """Save binary data to S3."""
        try:
            key = self._normalize_path(path)
            # Determine content type based on file extension
            content_type = 'application/octet-stream'
            if path.endswith('.mp3'):
                content_type = 'audio/mpeg'
            elif path.endswith('.png'):
                content_type = 'image/png'
            elif path.endswith('.csv'):
                content_type = 'text/csv'
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type
            )
            url = f"s3://{self.bucket_name}/{key}"
            logger.info(f"Saved binary file to: {url}")
            return url
        except Exception as e:
            logger.error(f"Failed to save binary to S3: {e}")
            raise
    
    def load_text(self, path: str) -> str:
        """Load text content from S3."""
        try:
            key = self._normalize_path(path)
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            content = response['Body'].read().decode('utf-8')
            logger.debug(f"Loaded text from S3: {key}")
            return content
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"File not found in S3: {path}")
            logger.error(f"Failed to load text from S3: {e}")
            raise
    
    def load_json(self, path: str) -> Dict[str, Any]:
        """Load JSON data from S3."""
        try:
            content = self.load_text(path)
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load JSON from S3: {e}")
            raise
    
    def load_binary(self, path: str) -> bytes:
        """Load binary data from S3."""
        try:
            key = self._normalize_path(path)
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            data = response['Body'].read()
            logger.debug(f"Loaded binary from S3: {key}")
            return data
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"File not found in S3: {path}")
            logger.error(f"Failed to load binary from S3: {e}")
            raise
    
    def exists(self, path: str) -> bool:
        """Check if file exists in S3."""
        try:
            key = self._normalize_path(path)
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking file existence in S3: {e}")
            raise
    
    def list_files(self, prefix: str) -> List[str]:
        """List files with given prefix in S3."""
        try:
            prefix = self._normalize_path(prefix)
            paginator = self.s3_client.get_paginator('list_objects_v2')
            files = []
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get('Contents', []):
                    files.append(obj['Key'])
            
            logger.debug(f"Listed {len(files)} files with prefix: {prefix}")
            return files
        except Exception as e:
            logger.error(f"Failed to list files in S3: {e}")
            raise
    
    def get_url(self, path: str) -> str:
        """Get S3 URL for the file."""
        key = self._normalize_path(path)
        return f"s3://{self.bucket_name}/{key}"


class LocalBackend(StorageBackend):
    """Local filesystem storage backend implementation."""
    
    def __init__(self, base_path: Union[str, Path] = "./output"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized LocalBackend with base path: {self.base_path}")
    
    def _get_full_path(self, path: str) -> Path:
        """Get full local path."""
        return self.base_path / path.lstrip('/')
    
    def save_text(self, path: str, content: str) -> str:
        """Save text content to local filesystem."""
        try:
            full_path = self._get_full_path(path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Saved text file to: {full_path}")
            return str(full_path)
        except Exception as e:
            logger.error(f"Failed to save text locally: {e}")
            raise
    
    def save_json(self, path: str, data: Dict[str, Any]) -> str:
        """Save JSON data to local filesystem."""
        try:
            full_path = self._get_full_path(path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved JSON file to: {full_path}")
            return str(full_path)
        except Exception as e:
            logger.error(f"Failed to save JSON locally: {e}")
            raise
    
    def save_binary(self, path: str, data: bytes) -> str:
        """Save binary data to local filesystem."""
        try:
            full_path = self._get_full_path(path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'wb') as f:
                f.write(data)
            
            logger.info(f"Saved binary file to: {full_path}")
            return str(full_path)
        except Exception as e:
            logger.error(f"Failed to save binary locally: {e}")
            raise
    
    def load_text(self, path: str) -> str:
        """Load text content from local filesystem."""
        try:
            full_path = self._get_full_path(path)
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.debug(f"Loaded text from: {full_path}")
            return content
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except Exception as e:
            logger.error(f"Failed to load text locally: {e}")
            raise
    
    def load_json(self, path: str) -> Dict[str, Any]:
        """Load JSON data from local filesystem."""
        try:
            content = self.load_text(path)
            return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load JSON locally: {e}")
            raise
    
    def load_binary(self, path: str) -> bytes:
        """Load binary data from local filesystem."""
        try:
            full_path = self._get_full_path(path)
            with open(full_path, 'rb') as f:
                data = f.read()
            logger.debug(f"Loaded binary from: {full_path}")
            return data
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
        except Exception as e:
            logger.error(f"Failed to load binary locally: {e}")
            raise
    
    def exists(self, path: str) -> bool:
        """Check if file exists in local filesystem."""
        full_path = self._get_full_path(path)
        return full_path.exists()
    
    def list_files(self, prefix: str) -> List[str]:
        """List files with given prefix in local filesystem."""
        try:
            prefix_path = self._get_full_path(prefix)
            files = []
            
            if prefix_path.is_dir():
                # List all files in directory recursively
                for file_path in prefix_path.rglob('*'):
                    if file_path.is_file():
                        # Return relative path from base_path
                        relative_path = file_path.relative_to(self.base_path)
                        files.append(str(relative_path))
            else:
                # Pattern matching for files
                parent_dir = prefix_path.parent
                if parent_dir.exists():
                    pattern = prefix_path.name + '*'
                    for file_path in parent_dir.glob(pattern):
                        if file_path.is_file():
                            relative_path = file_path.relative_to(self.base_path)
                            files.append(str(relative_path))
            
            logger.debug(f"Listed {len(files)} files with prefix: {prefix}")
            return files
        except Exception as e:
            logger.error(f"Failed to list files locally: {e}")
            raise
    
    def get_url(self, path: str) -> str:
        """Get local file URL."""
        full_path = self._get_full_path(path)
        return f"file://{full_path.absolute()}"


def create_storage_backend(
    backend_type: str = "s3",
    **kwargs
) -> StorageBackend:
    """
    Factory function to create storage backend.
    
    Args:
        backend_type: Either "s3" or "local"
        **kwargs: Additional arguments for the backend
    
    Returns:
        StorageBackend instance
    """
    if backend_type.lower() == "s3":
        return S3Backend(**kwargs)
    elif backend_type.lower() == "local":
        return LocalBackend(**kwargs)
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")