"""Cognito-integrated user service for transcription evaluator.

This service handles user management operations using AWS Cognito
for authentication and local database for application-specific data.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..aws.cognito_client import CognitoClient, CognitoUserInfo, get_cognito_client
from ..aws.verified_permissions import VerifiedPermissionsClient, get_verified_permissions_client, AuthorizationDecision
from ..models.cognito_models import UserProfile, get_user_by_cognito_id
from ..config.settings import get_database_session

logger = logging.getLogger(__name__)


class CognitoUserService:
    """Service for managing users with Cognito integration."""
    
    def __init__(
        self, 
        cognito_client: Optional[CognitoClient] = None,
        avp_client: Optional[VerifiedPermissionsClient] = None
    ):
        """Initialize the user service with AWS clients.
        
        Args:
            cognito_client: Cognito client for user operations
            avp_client: Verified Permissions client for authorization
        """
        self.cognito_client = cognito_client or get_cognito_client()
        self.avp_client = avp_client or get_verified_permissions_client()
    
    async def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with Cognito and return user information.
        
        Args:
            email: User email address
            password: User password
            
        Returns:
            Dict containing user information if authentication successful
        """
        try:
            # Authenticate with Cognito
            cognito_user = await self.cognito_client.authenticate_user(email, password)
            if not cognito_user:
                return None
            
            # Get or create local user profile
            with get_database_session() as db:
                user_profile = await self._get_or_create_user_profile(db, cognito_user)
                
                return {
                    "cognito_user_id": cognito_user.user_id,
                    "email": cognito_user.email,
                    "name": cognito_user.name,
                    "groups": cognito_user.groups,
                    "profile_id": str(user_profile.id),
                    "department": user_profile.department,
                    "role_level": user_profile.role_level,
                    "is_email_verified": cognito_user.email_verified,
                    "preferences": user_profile.preferences
                }
                
        except Exception as e:
            logger.error(f"Authentication failed for {email}: {str(e)}")
            return None
    
    async def create_user(
        self, 
        email: str, 
        name: str, 
        temporary_password: str,
        groups: Optional[List[str]] = None,
        department: Optional[str] = None,
        role_level: int = 4,
        requesting_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new user in Cognito and local database.
        
        Args:
            email: User email address
            name: User's full name
            temporary_password: Temporary password for new user
            groups: Cognito groups to assign
            department: User's department
            role_level: User's role level (1-4)
            requesting_user_id: Cognito ID of user making the request
            
        Returns:
            Dict containing created user information
        """
        # Check authorization
        if requesting_user_id:
            is_authorized = await self._check_authorization(
                requesting_user_id, "CreateUser", "User"
            )
            if not is_authorized:
                raise PermissionError("Insufficient permissions to create users")
        
        try:
            # Create user in Cognito
            cognito_user = await self.cognito_client.create_user(
                email=email,
                temporary_password=temporary_password,
                name=name,
                groups=groups or [],
                send_welcome_email=True
            )
            
            # Create local user profile
            with get_database_session() as db:
                user_profile = UserProfile(
                    cognito_user_id=cognito_user.user_id,
                    email=cognito_user.email,
                    full_name=cognito_user.name,
                    department=department,
                    role_level=role_level,
                    preferences={}
                )
                
                db.add(user_profile)
                db.commit()
                db.refresh(user_profile)
                
                logger.info(f"Created user: {email} with Cognito ID: {cognito_user.user_id}")
                
                return {
                    "cognito_user_id": cognito_user.user_id,
                    "email": cognito_user.email,
                    "name": cognito_user.name,
                    "groups": cognito_user.groups,
                    "profile_id": str(user_profile.id),
                    "department": user_profile.department,
                    "role_level": user_profile.role_level,
                    "created_at": user_profile.created_at.isoformat()
                }
                
        except IntegrityError as e:
            logger.error(f"User creation failed due to database constraint: {str(e)}")
            raise ValueError("User with this email already exists")
        except Exception as e:
            logger.error(f"User creation failed for {email}: {str(e)}")
            raise
    
    async def get_user_profile(self, cognito_user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile by Cognito user ID.
        
        Args:
            cognito_user_id: Cognito user ID (sub claim)
            
        Returns:
            Dict containing user profile information
        """
        try:
            with get_database_session() as db:
                user_profile = get_user_by_cognito_id(db, cognito_user_id)
                if not user_profile:
                    return None
                
                # Get current Cognito groups
                groups = await self.cognito_client.get_user_groups(user_profile.email)
                
                return {
                    "cognito_user_id": user_profile.cognito_user_id,
                    "email": user_profile.email,
                    "full_name": user_profile.full_name,
                    "department": user_profile.department,
                    "role_level": user_profile.role_level,
                    "groups": groups,
                    "preferences": user_profile.preferences,
                    "is_active": user_profile.is_active,
                    "created_at": user_profile.created_at.isoformat(),
                    "updated_at": user_profile.updated_at.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to get user profile for {cognito_user_id}: {str(e)}")
            return None
    
    async def update_user_profile(
        self, 
        cognito_user_id: str, 
        updates: Dict[str, Any],
        requesting_user_id: Optional[str] = None
    ) -> bool:
        """Update user profile information.
        
        Args:
            cognito_user_id: Cognito user ID to update
            updates: Dictionary of fields to update
            requesting_user_id: Cognito ID of user making the request
            
        Returns:
            True if update successful
        """
        # Check authorization (users can update their own profile, or admins can update any)
        if requesting_user_id and requesting_user_id != cognito_user_id:
            is_authorized = await self._check_authorization(
                requesting_user_id, "UpdateUser", "User"
            )
            if not is_authorized:
                raise PermissionError("Insufficient permissions to update user profile")
        
        try:
            with get_database_session() as db:
                user_profile = get_user_by_cognito_id(db, cognito_user_id)
                if not user_profile:
                    raise ValueError("User profile not found")
                
                # Update allowed fields
                allowed_fields = ['full_name', 'department', 'role_level', 'preferences']
                for field, value in updates.items():
                    if field in allowed_fields and hasattr(user_profile, field):
                        setattr(user_profile, field, value)
                
                db.commit()
                logger.info(f"Updated user profile for {cognito_user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update user profile for {cognito_user_id}: {str(e)}")
            raise
    
    async def add_user_to_group(
        self, 
        cognito_user_id: str, 
        group_name: str,
        requesting_user_id: Optional[str] = None
    ) -> bool:
        """Add user to a Cognito group.
        
        Args:
            cognito_user_id: Cognito user ID
            group_name: Name of the group to add user to
            requesting_user_id: Cognito ID of user making the request
            
        Returns:
            True if operation successful
        """
        # Check authorization
        if requesting_user_id:
            is_authorized = await self._check_authorization(
                requesting_user_id, "ManageUserGroups", "User"
            )
            if not is_authorized:
                raise PermissionError("Insufficient permissions to manage user groups")
        
        try:
            # Get user email for Cognito operation
            with get_database_session() as db:
                user_profile = get_user_by_cognito_id(db, cognito_user_id)
                if not user_profile:
                    raise ValueError("User profile not found")
                
                # Add to Cognito group
                success = await self.cognito_client.add_user_to_group(
                    user_profile.email, group_name
                )
                
                if success:
                    logger.info(f"Added user {cognito_user_id} to group {group_name}")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to add user {cognito_user_id} to group {group_name}: {str(e)}")
            raise
    
    async def remove_user_from_group(
        self, 
        cognito_user_id: str, 
        group_name: str,
        requesting_user_id: Optional[str] = None
    ) -> bool:
        """Remove user from a Cognito group.
        
        Args:
            cognito_user_id: Cognito user ID
            group_name: Name of the group to remove user from
            requesting_user_id: Cognito ID of user making the request
            
        Returns:
            True if operation successful
        """
        # Check authorization
        if requesting_user_id:
            is_authorized = await self._check_authorization(
                requesting_user_id, "ManageUserGroups", "User"
            )
            if not is_authorized:
                raise PermissionError("Insufficient permissions to manage user groups")
        
        try:
            # Get user email for Cognito operation
            with get_database_session() as db:
                user_profile = get_user_by_cognito_id(db, cognito_user_id)
                if not user_profile:
                    raise ValueError("User profile not found")
                
                # Remove from Cognito group
                success = await self.cognito_client.remove_user_from_group(
                    user_profile.email, group_name
                )
                
                if success:
                    logger.info(f"Removed user {cognito_user_id} from group {group_name}")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to remove user {cognito_user_id} from group {group_name}: {str(e)}")
            raise
    
    async def list_users(
        self, 
        limit: int = 50,
        requesting_user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all users with their profiles.
        
        Args:
            limit: Maximum number of users to return
            requesting_user_id: Cognito ID of user making the request
            
        Returns:
            List of user information dictionaries
        """
        # Check authorization
        if requesting_user_id:
            is_authorized = await self._check_authorization(
                requesting_user_id, "ListUsers", "User"
            )
            if not is_authorized:
                raise PermissionError("Insufficient permissions to list users")
        
        try:
            # Get users from Cognito
            cognito_response = await self.cognito_client.list_users(limit=limit)
            cognito_users = cognito_response['users']
            
            # Get local profiles
            with get_database_session() as db:
                users = []
                for cognito_user in cognito_users:
                    user_profile = get_user_by_cognito_id(db, cognito_user.user_id)
                    
                    user_data = {
                        "cognito_user_id": cognito_user.user_id,
                        "email": cognito_user.email,
                        "name": cognito_user.name,
                        "groups": cognito_user.groups,
                        "is_active": cognito_user.is_active,
                        "created_at": cognito_user.created_at.isoformat() if cognito_user.created_at else None
                    }
                    
                    if user_profile:
                        user_data.update({
                            "department": user_profile.department,
                            "role_level": user_profile.role_level,
                            "preferences": user_profile.preferences
                        })
                    
                    users.append(user_data)
                
                return users
                
        except Exception as e:
            logger.error(f"Failed to list users: {str(e)}")
            raise
    
    async def delete_user(
        self, 
        cognito_user_id: str,
        requesting_user_id: Optional[str] = None
    ) -> bool:
        """Delete user from Cognito and local database.
        
        Args:
            cognito_user_id: Cognito user ID to delete
            requesting_user_id: Cognito ID of user making the request
            
        Returns:
            True if deletion successful
        """
        # Check authorization
        if requesting_user_id:
            is_authorized = await self._check_authorization(
                requesting_user_id, "DeleteUser", "User"
            )
            if not is_authorized:
                raise PermissionError("Insufficient permissions to delete users")
        
        try:
            with get_database_session() as db:
                user_profile = get_user_by_cognito_id(db, cognito_user_id)
                if not user_profile:
                    raise ValueError("User profile not found")
                
                # Delete from Cognito first
                success = await self.cognito_client.delete_user(user_profile.email)
                
                if success:
                    # Delete local profile
                    db.delete(user_profile)
                    db.commit()
                    logger.info(f"Deleted user {cognito_user_id}")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to delete user {cognito_user_id}: {str(e)}")
            raise
    
    async def _get_or_create_user_profile(
        self, 
        db: Session, 
        cognito_user: CognitoUserInfo
    ) -> UserProfile:
        """Get existing user profile or create new one.
        
        Args:
            db: Database session
            cognito_user: Cognito user information
            
        Returns:
            UserProfile instance
        """
        user_profile = get_user_by_cognito_id(db, cognito_user.user_id)
        
        if not user_profile:
            # Create new profile
            user_profile = UserProfile(
                cognito_user_id=cognito_user.user_id,
                email=cognito_user.email,
                full_name=cognito_user.name,
                role_level=4  # Default to lowest privilege
            )
            db.add(user_profile)
            db.commit()
            db.refresh(user_profile)
            logger.info(f"Created new user profile for {cognito_user.email}")
        
        return user_profile
    
    async def _check_authorization(
        self, 
        user_id: str, 
        action: str, 
        resource_type: str,
        resource_id: Optional[str] = None
    ) -> bool:
        """Check if user is authorized for action.
        
        Args:
            user_id: Cognito user ID
            action: Action to authorize
            resource_type: Type of resource
            resource_id: Specific resource ID
            
        Returns:
            True if authorized
        """
        try:
            # Get user groups
            with get_database_session() as db:
                user_profile = get_user_by_cognito_id(db, user_id)
                if not user_profile:
                    return False
                
                groups = await self.cognito_client.get_user_groups(user_profile.email)
                
                # Check with Verified Permissions
                response = await self.avp_client.is_authorized(
                    principal_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    principal_groups=groups
                )
                
                return response.decision == AuthorizationDecision.ALLOW
                
        except Exception as e:
            logger.error(f"Authorization check failed for {user_id}: {str(e)}")
            return False


# Global service instance
_user_service: Optional[CognitoUserService] = None


def get_user_service() -> CognitoUserService:
    """Get or create the global user service instance.
    
    Returns:
        CognitoUserService instance
    """
    global _user_service
    
    if _user_service is None:
        _user_service = CognitoUserService()
    
    return _user_service