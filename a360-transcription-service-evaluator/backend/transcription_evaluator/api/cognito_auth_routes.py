"""FastAPI routes for Cognito authentication and user management.

This module provides API endpoints that integrate with AWS Cognito
for authentication and user management operations.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from ..aws.authorizers import CognitoClaims, validate_cognito_token
from ..services.cognito_user_service import CognitoUserService, get_user_service

logger = logging.getLogger(__name__)
security = HTTPBearer()
router = APIRouter(prefix="/auth", tags=["authentication"])


# Pydantic models for request/response
class LoginRequest(BaseModel):
    """Request model for user login."""

    email: EmailStr
    password: str = Field(..., min_length=8)


class CreateUserRequest(BaseModel):
    """Request model for creating a new user."""

    email: EmailStr
    name: str = Field(..., min_length=1, max_length=255)
    temporary_password: str = Field(..., min_length=12)
    groups: Optional[List[str]] = Field(
        default=None, description="Cognito groups to assign"
    )
    department: Optional[str] = Field(default=None, max_length=100)
    role_level: int = Field(
        default=4, ge=1, le=4, description="Role level (1=admin, 4=voice_actor)"
    )


class UpdateUserProfileRequest(BaseModel):
    """Request model for updating user profile."""

    full_name: Optional[str] = Field(default=None, max_length=255)
    department: Optional[str] = Field(default=None, max_length=100)
    role_level: Optional[int] = Field(default=None, ge=1, le=4)
    preferences: Optional[Dict[str, Any]] = Field(default=None)


class UserGroupRequest(BaseModel):
    """Request model for adding/removing user from group."""

    group_name: str = Field(..., description="Name of the Cognito group")


class AuthResponse(BaseModel):
    """Response model for authentication."""

    success: bool
    user: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class UserProfileResponse(BaseModel):
    """Response model for user profile."""

    cognito_user_id: str
    email: str
    full_name: str
    department: Optional[str]
    role_level: int
    groups: List[str]
    preferences: Dict[str, Any]
    is_active: bool
    created_at: str
    updated_at: str


# Dependency to get current user from JWT token
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CognitoClaims:
    """Extract and validate current user from JWT token.

    Args:
        credentials: HTTP Bearer token credentials

    Returns:
        CognitoClaims with user information

    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        claims = await validate_cognito_token(credentials.credentials)
        if not claims:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return claims
    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Dependency to get user service
def get_user_service_dependency() -> CognitoUserService:
    """Get user service instance."""
    return get_user_service()


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    user_service: CognitoUserService = Depends(get_user_service_dependency),
) -> AuthResponse:
    """Authenticate user with Cognito.

    Args:
        request: Login request with email and password
        user_service: User service instance

    Returns:
        Authentication response with user information
    """
    try:
        user_info = await user_service.authenticate_user(
            request.email, request.password
        )

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        return AuthResponse(
            success=True, user=user_info, message="Authentication successful"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed for {request.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error",
        )


@router.post("/users", response_model=Dict[str, Any])
async def create_user(
    request: CreateUserRequest,
    current_user: CognitoClaims = Depends(get_current_user),
    user_service: CognitoUserService = Depends(get_user_service_dependency),
) -> Dict[str, Any]:
    """Create a new user in Cognito and local database.

    Args:
        request: User creation request
        current_user: Current authenticated user
        user_service: User service instance

    Returns:
        Created user information
    """
    try:
        user_info = await user_service.create_user(
            email=request.email,
            name=request.name,
            temporary_password=request.temporary_password,
            groups=request.groups,
            department=request.department,
            role_level=request.role_level,
            requesting_user_id=current_user.sub,
        )

        return {
            "success": True,
            "user": user_info,
            "message": "User created successfully",
        }

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"User creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User creation failed",
        )


@router.get("/profile", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: CognitoClaims = Depends(get_current_user),
    user_service: CognitoUserService = Depends(get_user_service_dependency),
) -> UserProfileResponse:
    """Get current user's profile information.

    Args:
        current_user: Current authenticated user
        user_service: User service instance

    Returns:
        User profile information
    """
    try:
        profile = await user_service.get_user_profile(current_user.sub)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found"
            )

        return UserProfileResponse(**profile)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile for {current_user.sub}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile",
        )


@router.get("/users/{cognito_user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    cognito_user_id: str,
    current_user: CognitoClaims = Depends(get_current_user),
    user_service: CognitoUserService = Depends(get_user_service_dependency),
) -> UserProfileResponse:
    """Get user profile by Cognito user ID.

    Args:
        cognito_user_id: Cognito user ID to retrieve
        current_user: Current authenticated user
        user_service: User service instance

    Returns:
        User profile information
    """
    try:
        profile = await user_service.get_user_profile(cognito_user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found"
            )

        return UserProfileResponse(**profile)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile for {cognito_user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile",
        )


@router.put("/profile", response_model=Dict[str, Any])
async def update_my_profile(
    request: UpdateUserProfileRequest,
    current_user: CognitoClaims = Depends(get_current_user),
    user_service: CognitoUserService = Depends(get_user_service_dependency),
) -> Dict[str, Any]:
    """Update current user's profile.

    Args:
        request: Profile update request
        current_user: Current authenticated user
        user_service: User service instance

    Returns:
        Update result
    """
    try:
        updates = request.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided"
            )

        success = await user_service.update_user_profile(
            cognito_user_id=current_user.sub,
            updates=updates,
            requesting_user_id=current_user.sub,
        )

        if success:
            return {"success": True, "message": "Profile updated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Profile update failed"
            )

    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Profile update failed for {current_user.sub}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed",
        )


@router.put("/users/{cognito_user_id}/profile", response_model=Dict[str, Any])
async def update_user_profile(
    cognito_user_id: str,
    request: UpdateUserProfileRequest,
    current_user: CognitoClaims = Depends(get_current_user),
    user_service: CognitoUserService = Depends(get_user_service_dependency),
) -> Dict[str, Any]:
    """Update user profile (admin only).

    Args:
        cognito_user_id: Cognito user ID to update
        request: Profile update request
        current_user: Current authenticated user
        user_service: User service instance

    Returns:
        Update result
    """
    try:
        updates = request.dict(exclude_unset=True)
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No updates provided"
            )

        success = await user_service.update_user_profile(
            cognito_user_id=cognito_user_id,
            updates=updates,
            requesting_user_id=current_user.sub,
        )

        if success:
            return {"success": True, "message": "Profile updated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Profile update failed"
            )

    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Profile update failed for {cognito_user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed",
        )


@router.post("/users/{cognito_user_id}/groups", response_model=Dict[str, Any])
async def add_user_to_group(
    cognito_user_id: str,
    request: UserGroupRequest,
    current_user: CognitoClaims = Depends(get_current_user),
    user_service: CognitoUserService = Depends(get_user_service_dependency),
) -> Dict[str, Any]:
    """Add user to a Cognito group.

    Args:
        cognito_user_id: Cognito user ID
        request: Group assignment request
        current_user: Current authenticated user
        user_service: User service instance

    Returns:
        Operation result
    """
    try:
        success = await user_service.add_user_to_group(
            cognito_user_id=cognito_user_id,
            group_name=request.group_name,
            requesting_user_id=current_user.sub,
        )

        if success:
            return {
                "success": True,
                "message": f"User added to group {request.group_name}",
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to add user to group",
            )

    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(
            f"Failed to add user {cognito_user_id} to group {request.group_name}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Group assignment failed",
        )


@router.delete(
    "/users/{cognito_user_id}/groups/{group_name}", response_model=Dict[str, Any]
)
async def remove_user_from_group(
    cognito_user_id: str,
    group_name: str,
    current_user: CognitoClaims = Depends(get_current_user),
    user_service: CognitoUserService = Depends(get_user_service_dependency),
) -> Dict[str, Any]:
    """Remove user from a Cognito group.

    Args:
        cognito_user_id: Cognito user ID
        group_name: Name of group to remove user from
        current_user: Current authenticated user
        user_service: User service instance

    Returns:
        Operation result
    """
    try:
        success = await user_service.remove_user_from_group(
            cognito_user_id=cognito_user_id,
            group_name=group_name,
            requesting_user_id=current_user.sub,
        )

        if success:
            return {"success": True, "message": f"User removed from group {group_name}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to remove user from group",
            )

    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(
            f"Failed to remove user {cognito_user_id} from group {group_name}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Group removal failed",
        )


@router.get("/users", response_model=List[Dict[str, Any]])
async def list_users(
    limit: int = 50,
    current_user: CognitoClaims = Depends(get_current_user),
    user_service: CognitoUserService = Depends(get_user_service_dependency),
) -> List[Dict[str, Any]]:
    """List all users (admin only).

    Args:
        limit: Maximum number of users to return
        current_user: Current authenticated user
        user_service: User service instance

    Returns:
        List of user information
    """
    try:
        users = await user_service.list_users(
            limit=limit, requesting_user_id=current_user.sub
        )

        return users

    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users",
        )


@router.delete("/users/{cognito_user_id}", response_model=Dict[str, Any])
async def delete_user(
    cognito_user_id: str,
    current_user: CognitoClaims = Depends(get_current_user),
    user_service: CognitoUserService = Depends(get_user_service_dependency),
) -> Dict[str, Any]:
    """Delete user from Cognito and local database (admin only).

    Args:
        cognito_user_id: Cognito user ID to delete
        current_user: Current authenticated user
        user_service: User service instance

    Returns:
        Deletion result
    """
    try:
        success = await user_service.delete_user(
            cognito_user_id=cognito_user_id, requesting_user_id=current_user.sub
        )

        if success:
            return {"success": True, "message": "User deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="User deletion failed"
            )

    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete user {cognito_user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User deletion failed",
        )


@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_info(
    current_user: CognitoClaims = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get current user information including username and groups.

    Args:
        current_user: Current authenticated user from JWT token

    Returns:
        User information with username, groups, and email
    """
    return {
        "username": current_user.name or current_user.email.split('@')[0],
        "groups": current_user.groups or [],
        "email": current_user.email,
        "cognito_user_id": current_user.sub,
    }


@router.get("/validate", response_model=Dict[str, Any])
async def validate_token(
    current_user: CognitoClaims = Depends(get_current_user),
) -> Dict[str, Any]:
    """Validate JWT token and return user information.

    Args:
        current_user: Current authenticated user

    Returns:
        Token validation result with user information
    """
    return {
        "valid": True,
        "user": {
            "cognito_user_id": current_user.sub,
            "email": current_user.email,
            "name": current_user.name,
            "groups": current_user.groups,
            "email_verified": current_user.email_verified,
            "token_use": current_user.token_use,
        },
        "expires_at": current_user.exp,
    }
