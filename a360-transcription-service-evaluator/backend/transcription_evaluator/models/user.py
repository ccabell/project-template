"""User management models for A360 Transcription Service Evaluator.

This module provides Pydantic models for user management and authentication
functionality, supporting AWS Cognito integration and role-based access control.

The user system integrates with AWS Cognito for authentication while maintaining
local user profiles with role assignments and audit trails.

Example:
    Creating a new user request:

    >>> from transcription_evaluator.models.user import UserCreate
    >>> user = UserCreate(
    ...     email="user@example.com",
    ...     name="John Doe",
    ...     username="johndoe",
    ...     password="SecurePassword123!"
    ... )
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


class UserStatus(str, Enum):
    """User account status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class UserBase(BaseModel):
    """Base user model with common fields."""
    
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=100, description="Unique username")
    full_name: str = Field(..., min_length=1, max_length=255, description="User's full name")
    status: UserStatus = Field(UserStatus.ACTIVE, description="User account status")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional user metadata")


class UserCreate(UserBase):
    """Model for creating new users."""
    
    password: str = Field(..., min_length=8, description="User password (temporary for Cognito)")
    send_welcome_email: bool = Field(True, description="Whether to send welcome email")
    groups: List[str] = Field(default_factory=list, description="Initial Cognito groups to assign")


class UserUpdate(BaseModel):
    """Model for updating existing users."""
    
    full_name: Optional[str] = Field(None, min_length=1, max_length=255, description="Updated full name")
    status: Optional[UserStatus] = Field(None, description="Updated account status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class UserResponse(UserBase):
    """Model for user API responses."""
    
    id: UUID = Field(..., description="Unique user ID")
    cognito_user_id: str = Field(..., description="AWS Cognito user identifier")
    email_verified: bool = Field(False, description="Whether email address is verified")
    created_at: datetime = Field(..., description="Timestamp when user was created")
    updated_at: datetime = Field(..., description="Timestamp when user was last updated")
    last_login: Optional[datetime] = Field(None, description="Timestamp of last login")
    
    class Config:
        from_attributes = True


class UserWithRoles(UserResponse):
    """Model for user responses including role information."""
    
    roles: List[str] = Field(default_factory=list, description="List of assigned role names")
    permissions: List[str] = Field(default_factory=list, description="Effective permissions from all roles")


class LoginRequest(BaseModel):
    """Model for user login requests."""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")
    remember_me: bool = Field(False, description="Whether to extend session duration")


class LoginResponse(BaseModel):
    """Model for login API responses."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: UserWithRoles = Field(..., description="Authenticated user information")


class TokenData(BaseModel):
    """Model for JWT token payload data."""
    
    user_id: UUID = Field(..., description="User ID from token")
    cognito_user_id: str = Field(..., description="Cognito user ID")
    email: EmailStr = Field(..., description="User email")
    username: str = Field(..., description="Username")
    roles: List[str] = Field(default_factory=list, description="User roles")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    exp: int = Field(..., description="Token expiration timestamp")
    iat: int = Field(..., description="Token issued at timestamp")


class RefreshTokenRequest(BaseModel):
    """Model for token refresh requests."""
    
    refresh_token: str = Field(..., description="Valid refresh token")