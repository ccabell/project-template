"""
IAM role constructs for SageMaker Studio environments.

This module provides IAM role constructs that define the necessary permissions
for SageMaker Studio domains, user profiles, and execution environments.
"""

from .studio_default_role import StudioDefaultRole
from .studio_user_role import StudioUserRole

__all__ = [
    "StudioDefaultRole",
    "StudioUserRole",
]
