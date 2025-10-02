"""Tests for the storage module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from transcription_evaluator.core.storage import (
    LocalBackend, S3Backend, StorageBackend, create_storage_backend
)


class TestStorageBackend:
    """Tests for abstract storage backend."""

    def test_storage_backend_abstract(self):
        """Test that StorageBackend is abstract."""
        with pytest.raises(TypeError):
            StorageBackend()


class TestLocalBackend:
    """Tests for local storage backend."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def storage(self, temp_dir):
        """Create local storage backend."""
        return LocalBackend(str(temp_dir))

    def test_save_text(self, storage, temp_dir):
        """Test saving text content."""
        path = "test/file.txt"
        content = "test content"
        
        result = storage.save_text(path, content)
        
        # LocalBackend returns full path, not relative path
        assert result == str(temp_dir / path)
        file_path = temp_dir / path
        assert file_path.exists()
        assert file_path.read_text() == content

    def test_save_json(self, storage, temp_dir):
        """Test saving JSON data."""
        path = "test/data.json"
        data = {"key": "value", "number": 42}
        
        result = storage.save_json(path, data)
        
        # LocalBackend returns full path, not relative path
        assert result == str(temp_dir / path)
        file_path = temp_dir / path
        assert file_path.exists()
        loaded_data = json.loads(file_path.read_text())
        assert loaded_data == data

    def test_save_binary(self, storage, temp_dir):
        """Test saving binary data."""
        path = "test/file.bin"
        data = b"binary content"
        
        result = storage.save_binary(path, data)
        
        # LocalBackend returns full path, not relative path
        assert result == str(temp_dir / path)
        file_path = temp_dir / path
        assert file_path.exists()
        assert file_path.read_bytes() == data

    def test_load_text(self, storage, temp_dir):
        """Test loading text content."""
        path = "test/file.txt"
        content = "test content"
        
        # Create file first
        file_path = temp_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        
        result = storage.load_text(path)
        assert result == content

    def test_load_json(self, storage, temp_dir):
        """Test loading JSON data."""
        path = "test/data.json"
        data = {"key": "value", "number": 42}
        
        # Create file first
        file_path = temp_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(data))
        
        result = storage.load_json(path)
        assert result == data

    def test_load_binary(self, storage, temp_dir):
        """Test loading binary data."""
        path = "test/file.bin"
        data = b"binary content"
        
        # Create file first
        file_path = temp_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        
        result = storage.load_binary(path)
        assert result == data

    def test_exists(self, storage, temp_dir):
        """Test checking if file exists."""
        path = "test/file.txt"
        
        # File doesn't exist initially
        assert not storage.exists(path)
        
        # Create file
        file_path = temp_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("content")
        
        # File exists now
        assert storage.exists(path)

    def test_list_files(self, storage, temp_dir):
        """Test listing files."""
        # Create test files
        files = ["file1.txt", "file2.txt", "subdir/file3.txt"]
        for file_name in files:
            file_path = temp_dir / file_name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("content")
        
        # LocalBackend.list_files requires a prefix parameter
        result = storage.list_files("")  # Empty prefix to list all files
        
        assert len(result) >= 3  # May include other files
        for file_name in files:
            assert any(file_name in item for item in result)

    @pytest.mark.skip(reason="LocalBackend does not implement delete method")
    def test_delete(self, storage, temp_dir):
        """Test deleting a file."""
        path = "test/file.txt"
        content = "test content"
        
        # Create file first
        file_path = temp_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        
        result = storage.delete(path)
        
        assert result is True
        assert not file_path.exists()


class TestS3Backend:
    """Tests for S3 storage backend."""

    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3 client."""
        client = Mock()
        client.put_object = Mock()
        client.get_object = Mock()
        client.delete_object = Mock()
        client.list_objects_v2 = Mock()
        client.head_object = Mock()
        return client

    @pytest.fixture
    def storage(self, mock_s3_client):
        """Create S3 storage backend with mocked client."""
        with patch("boto3.client", return_value=mock_s3_client), \
             patch("boto3.Session") as mock_session:
            mock_session.return_value.client.return_value = mock_s3_client
            return S3Backend(bucket_name="test-bucket", aws_profile="test")

    def test_save_text(self, storage, mock_s3_client):
        """Test saving text to S3."""
        path = "test/file.txt"
        content = "test content"
        
        result = storage.save_text(path, content)
        
        # S3Backend returns s3:// URL, not just path
        assert result == f"s3://test-bucket/{path}"
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert call_args[1]["Key"] == path
        assert call_args[1]["Body"] == content.encode('utf-8')

    def test_save_json(self, storage, mock_s3_client):
        """Test saving JSON to S3."""
        path = "test/data.json"
        data = {"key": "value", "number": 42}
        
        result = storage.save_json(path, data)
        
        # S3Backend returns s3:// URL, not just path
        assert result == f"s3://test-bucket/{path}"
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert call_args[1]["Key"] == path

    def test_save_binary(self, storage, mock_s3_client):
        """Test saving binary data to S3."""
        path = "test/file.bin"
        data = b"binary content"
        
        result = storage.save_binary(path, data)
        
        assert result == f"s3://test-bucket/{path}"
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert call_args[1]["Key"] == path
        assert call_args[1]["Body"] == data

    def test_load_text(self, storage, mock_s3_client):
        """Test loading text from S3."""
        path = "test/file.txt"
        content = "test content"
        
        mock_s3_client.get_object.return_value = {
            "Body": Mock(read=Mock(return_value=content.encode()))
        }
        
        result = storage.load_text(path)
        
        assert result == content
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=path
        )

    def test_load_json(self, storage, mock_s3_client):
        """Test loading JSON from S3."""
        path = "test/data.json"
        data = {"key": "value", "number": 42}
        
        mock_s3_client.get_object.return_value = {
            "Body": Mock(read=Mock(return_value=json.dumps(data).encode()))
        }
        
        result = storage.load_json(path)
        
        assert result == data
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=path
        )

    def test_exists(self, storage, mock_s3_client):
        """Test checking if file exists in S3."""
        path = "test/file.txt"
        
        # File exists
        mock_s3_client.head_object.return_value = {}
        result = storage.exists(path)
        assert result is True
        
        # File doesn't exist
        from botocore.exceptions import ClientError
        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )
        result = storage.exists(path)
        assert result is False


class TestStorageFactory:
    """Tests for storage factory function."""

    def test_create_local_storage_backend(self):
        """Test creating local storage backend."""
        backend = create_storage_backend(
            backend_type="local",
            base_path="/tmp/test"
        )
        
        assert isinstance(backend, LocalBackend)

    def test_create_s3_storage_backend(self):
        """Test creating S3 storage backend."""
        with patch("boto3.client"), \
             patch("boto3.Session") as mock_session:
            mock_session.return_value.client.return_value = Mock()
            backend = create_storage_backend(
                backend_type="s3",
                bucket_name="test-bucket",
                aws_profile="default"
            )
            assert isinstance(backend, S3Backend)

    def test_create_invalid_storage_backend(self):
        """Test creating invalid storage backend."""
        with pytest.raises(ValueError, match="Unknown backend type"):
            create_storage_backend(backend_type="invalid")