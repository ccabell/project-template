"""Role and permission models for A360 Transcription Service Evaluator.

This module provides Pydantic models for role-based access control (RBAC)
functionality, supporting flexible permission management and user authorization.

The RBAC system supports hierarchical roles, fine-grained permissions,
and dynamic role assignments for comprehensive access control.

Example:
    Creating a new role with permissions:

    >>> from transcription_evaluator.models.role import RoleCreate
    >>> role = RoleCreate(
    ...     name="Data Analyst",
    ...     description="Access to view and analyze transcription data", 
    ...     permissions=["read", "analyze", "export"]
    ... )
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class PermissionBase(BaseModel):
    """Base permission model with common fields."""
    
    name: str = Field(..., min_length=1, max_length=100, description="Permission name")
    description: Optional[str] = Field(None, description="Permission description")
    resource_type: Optional[str] = Field(None, max_length=100, description="Type of resource this permission applies to")


class PermissionResponse(PermissionBase):
    """Model for permission API responses."""
    
    id: UUID = Field(..., description="Unique permission ID")
    created_at: datetime = Field(..., description="Timestamp when permission was created")
    updated_at: datetime = Field(..., description="Timestamp when permission was last updated")
    
    class Config:
        from_attributes = True


class RoleBase(BaseModel):
    """Base role model with common fields."""
    
    name: str = Field(..., min_length=1, max_length=100, description="Role name")
    description: Optional[str] = Field(None, description="Role description")
    is_system_role: bool = Field(False, description="Whether this is a system-defined role")
    permissions: List[str] = Field(default_factory=list, description="List of permission names")


class RoleCreate(RoleBase):
    """Model for creating new roles."""
    pass


class RoleUpdate(BaseModel):
    """Model for updating existing roles."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Updated role name")
    description: Optional[str] = Field(None, description="Updated role description")
    permissions: Optional[List[str]] = Field(None, description="Updated list of permission names")


class RoleResponse(RoleBase):
    """Model for role API responses."""
    
    id: UUID = Field(..., description="Unique role ID")
    created_at: datetime = Field(..., description="Timestamp when role was created")
    updated_at: datetime = Field(..., description="Timestamp when role was last updated")
    
    class Config:
        from_attributes = True


class RoleWithPermissions(RoleResponse):
    """Model for role responses including detailed permission information."""
    
    permission_details: List[PermissionResponse] = Field(default_factory=list, description="Detailed permission information")


class UserRoleAssignment(BaseModel):
    """Model for user-role assignment operations."""
    
    user_id: UUID = Field(..., description="ID of the user")
    role_id: UUID = Field(..., description="ID of the role")
    assigned_by: Optional[UUID] = Field(None, description="ID of the user who made the assignment")
    assigned_at: Optional[datetime] = Field(None, description="Timestamp when assignment was made")
    
    class Config:
        from_attributes = True


class RolePermissionAssignment(BaseModel):
    """Model for role-permission assignment operations."""
    
    role_id: UUID = Field(..., description="ID of the role")
    permission_id: UUID = Field(..., description="ID of the permission")
    assigned_at: Optional[datetime] = Field(None, description="Timestamp when assignment was made")
    
    class Config:
        from_attributes = True