"""Pydantic models for transcription evaluator service.

This module provides data models and validation schemas for the A360
Transcription Service Evaluator's RBAC system and core functionality.

The module includes:
    • User management models with authentication support
    • Role-based access control (RBAC) models
    • Permission and authorization models
    • Audit logging models
    • Script assignment models
    • API request and response models

Example:
    Basic model usage for user creation:

    >>> from transcription_evaluator.models import UserCreate, UserResponse
    >>> user_data = UserCreate(
    ...     email="user@example.com",
    ...     name="John Doe",
    ...     password="secure_password"
    ... )
    >>> # Process user creation...
"""

from .audit import *
from .role import *
from .user import *

__all__ = [
    # User models
    "UserBase",
    "UserCreate", 
    "UserUpdate",
    "UserResponse",
    "UserWithRoles",
    "LoginRequest",
    "LoginResponse",
    "TokenData",
    "RefreshTokenRequest",
    
    # Role models
    "RoleBase",
    "RoleCreate",
    "RoleUpdate", 
    "RoleResponse",
    "RoleWithPermissions",
    "PermissionBase",
    "PermissionResponse",
    "UserRoleAssignment",
    "RolePermissionAssignment",
    
    # Audit models
    "AuditLogBase",
    "AuditLogCreate",
    "AuditLogResponse",
    "AuditLogFilter"
]