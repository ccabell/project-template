"""
Transcription Evaluation Toolkit

A comprehensive toolkit for evaluating transcription services with advanced
false positive/negative analysis, ground truth generation, and S3 storage.
"""

from .config.settings import get_settings, update_settings
from .core.generation import EnhancedGroundTruthGenerator
from .core.storage import StorageBackend, S3Backend, LocalBackend, create_storage_backend

__version__ = "0.1.0"

__all__ = [
    "get_settings",
    "update_settings", 
    "EnhancedGroundTruthGenerator",
    "StorageBackend",
    "S3Backend",
    "LocalBackend", 
    "create_storage_backend",
]
