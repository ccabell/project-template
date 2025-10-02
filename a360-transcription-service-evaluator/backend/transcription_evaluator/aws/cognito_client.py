"""AWS Cognito User Pool integration client.

This module provides a PyCognito-based client for AWS Cognito User Pool
operations, including user authentication, registration, and management
for the A360 Transcription Service Evaluator.

The module includes:
    • User authentication using SRP protocol
    • User registration and confirmation
    • Password management and MFA support
    • User group management for role-based access
    • Token validation and refresh operations

Example:
    Basic Cognito client usage:

    >>> from transcription_evaluator.aws.cognito_client import CognitoClient
    >>> cognito = CognitoClient()
    >>> user = await cognito.authenticate_user("user@example.com", "password")
    >>> await cognito.add_user_to_group(user.user_id, "evaluator")
"""

import logging
import os
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from datetime import datetime

import boto3
from pycognito import Cognito
from aws_lambda_powertools import Logger

logger = Logger(service="cognito-client")
stdlib_logger = logging.getLogger(__name__)


@dataclass
class CognitoUserInfo:
    """Represents a Cognito user with group and attribute information."""
    
    user_id: str
    username: str
    email: str
    name: str
    groups: List[str]
    attributes: Dict[str, Any]
    is_active: bool
    email_verified: bool
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


class CognitoClient:
    """AWS Cognito User Pool client with comprehensive user management.
    
    Provides Cognito User Pool operations including authentication, user
    management, and group operations using PyCognito and boto3.
    """
    
    def __init__(
        self,
        user_pool_id: Optional[str] = None,
        client_id: Optional[str] = None,
        region: Optional[str] = None
    ):
        """Initialize Cognito client with User Pool configuration.
        
        Args:
            user_pool_id: Cognito User Pool ID (from environment if not provided)
            client_id: Cognito User Pool Client ID (from environment if not provided)
            region: AWS region (from environment if not provided)
            
        Raises:
            ValueError: If required configuration is missing
        """
        self.user_pool_id = user_pool_id or os.getenv('COGNITO_USER_POOL_ID')
        self.client_id = client_id or os.getenv('COGNITO_CLIENT_ID')
        self.region = region or os.getenv('AWS_REGION', 'us-east-1')
        
        if not self.user_pool_id or not self.client_id:
            raise ValueError(
                "Cognito User Pool ID and Client ID must be provided via parameters "
                "or environment variables (COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID)"
            )
        
        # Initialize boto3 client for admin operations
        self.cognito_idp = boto3.client('cognito-idp', region_name=self.region)
        
        logger.info(
            "Cognito client initialized",
            extra={
                "user_pool_id": self.user_pool_id,
                "region": self.region
            }
        )
    
    def _get_user_cognito_instance(self, username: str) -> Cognito:
        """Create PyCognito instance for specific user.
        
        Args:
            username: Username for the Cognito instance
            
        Returns:
            Cognito: Configured PyCognito instance
        """
        return Cognito(
            user_pool_id=self.user_pool_id,
            client_id=self.client_id,
            username=username
        )
    
    async def authenticate_user(
        self, 
        email: str, 
        password: str
    ) -> Optional[CognitoUserInfo]:
        """Authenticate user with email and password.
        
        Args:
            email: User email address
            password: User password
            
        Returns:
            Optional[CognitoUserInfo]: User information if authentication successful
            
        Raises:
            Exception: If credentials are invalid or user account is not confirmed
            
        Example:
            >>> cognito = CognitoClient()
            >>> user = await cognito.authenticate_user("user@example.com", "password")
            >>> print(f"Authenticated user: {user.email}")
        """
        try:
            cognito_user = self._get_user_cognito_instance(email)
            cognito_user.authenticate(password=password)
            
            # Get user information
            user_info = await self._get_user_info(email)
            
            logger.info(
                "User authenticated successfully",
                extra={
                    "email": email,
                    "user_id": user_info.user_id if user_info else None
                }
            )
            
            return user_info
            
        except Exception as e:
            error_msg = str(e)
            if "NotAuthorizedException" in error_msg or "Incorrect username or password" in error_msg:
                logger.warning(
                    "Authentication failed - invalid credentials",
                    extra={"email": email}
                )
                return None
            elif "UserNotConfirmedException" in error_msg or "User is not confirmed" in error_msg:
                logger.warning(
                    "Authentication failed - user not confirmed",
                    extra={"email": email}
                )
                raise
            else:
                logger.error(
                    "Authentication error",
                    extra={
                        "email": email,
                        "error": error_msg
                    }
                )
                raise
    
    async def create_user(
        self,
        email: str,
        temporary_password: str,
        name: str,
        groups: Optional[List[str]] = None,
        send_welcome_email: bool = True
    ) -> CognitoUserInfo:
        """Create a new Cognito user.
        
        Args:
            email: User email address (used as username)
            temporary_password: Temporary password for new user
            name: User's full name
            groups: Optional list of group names to assign
            send_welcome_email: Whether to send welcome email
            
        Returns:
            CognitoUserInfo: Created user information
            
        Raises:
            Exception: If user creation fails
            
        Example:
            >>> cognito = CognitoClient()
            >>> user = await cognito.create_user(
            ...     email="newuser@example.com",
            ...     temporary_password="TempPass123!",
            ...     name="New User",
            ...     groups=["voice_actor"]
            ... )
        """
        try:
            # Create user with admin API
            response = self.cognito_idp.admin_create_user(
                UserPoolId=self.user_pool_id,
                Username=email,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'name', 'Value': name},
                    {'Name': 'email_verified', 'Value': 'true'}
                ],
                TemporaryPassword=temporary_password,
                MessageAction='SUPPRESS' if not send_welcome_email else 'SEND'
            )
            
            user_id = response['User']['Username']
            
            # Add user to groups if specified
            if groups:
                for group_name in groups:
                    await self.add_user_to_group(user_id, group_name)
            
            # Get complete user information
            user_info = await self._get_user_info(email)
            
            logger.info(
                "User created successfully",
                extra={
                    "email": email,
                    "user_id": user_id,
                    "groups": groups or []
                }
            )
            
            return user_info
            
        except Exception as e:
            logger.error(
                "User creation failed",
                extra={
                    "email": email,
                    "error": str(e)
                }
            )
            raise
    
    async def add_user_to_group(self, username: str, group_name: str) -> bool:
        """Add user to a Cognito group.
        
        Args:
            username: Username (email) of the user
            group_name: Name of the group to add user to
            
        Returns:
            bool: True if operation successful
            
        Raises:
            Exception: If group assignment fails
        """
        try:
            self.cognito_idp.admin_add_user_to_group(
                UserPoolId=self.user_pool_id,
                Username=username,
                GroupName=group_name
            )
            
            logger.info(
                "User added to group",
                extra={
                    "username": username,
                    "group_name": group_name
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to add user to group",
                extra={
                    "username": username,
                    "group_name": group_name,
                    "error": str(e)
                }
            )
            raise
    
    async def remove_user_from_group(self, username: str, group_name: str) -> bool:
        """Remove user from a Cognito group.
        
        Args:
            username: Username (email) of the user
            group_name: Name of the group to remove user from
            
        Returns:
            bool: True if operation successful
        """
        try:
            self.cognito_idp.admin_remove_user_from_group(
                UserPoolId=self.user_pool_id,
                Username=username,
                GroupName=group_name
            )
            
            logger.info(
                "User removed from group",
                extra={
                    "username": username,
                    "group_name": group_name
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to remove user from group",
                extra={
                    "username": username,
                    "group_name": group_name,
                    "error": str(e)
                }
            )
            raise
    
    async def get_user_groups(self, username: str) -> List[str]:
        """Get all groups for a user.
        
        Args:
            username: Username (email) of the user
            
        Returns:
            List[str]: List of group names the user belongs to
        """
        try:
            response = self.cognito_idp.admin_list_groups_for_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )
            
            groups = [group['GroupName'] for group in response.get('Groups', [])]
            
            logger.debug(
                "Retrieved user groups",
                extra={
                    "username": username,
                    "groups": groups
                }
            )
            
            return groups
            
        except Exception as e:
            logger.error(
                "Failed to get user groups",
                extra={
                    "username": username,
                    "error": str(e)
                }
            )
            return []
    
    async def list_users(
        self, 
        limit: int = 60, 
        pagination_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """List users in the User Pool.
        
        Args:
            limit: Maximum number of users to return
            pagination_token: Token for pagination
            
        Returns:
            Dict containing users list and pagination info
        """
        try:
            params = {
                'UserPoolId': self.user_pool_id,
                'Limit': limit
            }
            
            if pagination_token:
                params['PaginationToken'] = pagination_token
            
            response = self.cognito_idp.list_users(**params)
            
            users = []
            for user_data in response.get('Users', []):
                user_info = await self._parse_user_data(user_data)
                users.append(user_info)
            
            return {
                'users': users,
                'pagination_token': response.get('PaginationToken'),
                'total_returned': len(users)
            }
            
        except Exception as e:
            logger.error(
                "Failed to list users",
                extra={"error": str(e)}
            )
            raise
    
    async def delete_user(self, username: str) -> bool:
        """Delete a user from the User Pool.
        
        Args:
            username: Username (email) of the user to delete
            
        Returns:
            bool: True if deletion successful
        """
        try:
            self.cognito_idp.admin_delete_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )
            
            logger.info(
                "User deleted successfully",
                extra={"username": username}
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete user",
                extra={
                    "username": username,
                    "error": str(e)
                }
            )
            raise
    
    async def _get_user_info(self, username: str) -> Optional[CognitoUserInfo]:
        """Get comprehensive user information.
        
        Args:
            username: Username (email) of the user
            
        Returns:
            Optional[CognitoUserInfo]: User information or None if not found
        """
        try:
            response = self.cognito_idp.admin_get_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )
            
            return await self._parse_user_data(response)
            
        except self.cognito_idp.exceptions.UserNotFoundException:
            return None
        except Exception as e:
            logger.error(
                "Failed to get user info",
                extra={
                    "username": username,
                    "error": str(e)
                }
            )
            return None
    
    async def _parse_user_data(self, user_data: Dict[str, Any]) -> CognitoUserInfo:
        """Parse Cognito user data into CognitoUserInfo object.
        
        Args:
            user_data: Raw user data from Cognito API
            
        Returns:
            CognitoUserInfo: Parsed user information
        """
        # Extract attributes
        attributes = {}
        for attr in user_data.get('UserAttributes', []):
            attributes[attr['Name']] = attr['Value']
        
        username = user_data.get('Username', '')
        
        # Get user groups
        groups = await self.get_user_groups(username)
        
        return CognitoUserInfo(
            user_id=username,
            username=username,
            email=attributes.get('email', ''),
            name=attributes.get('name', ''),
            groups=groups,
            attributes=attributes,
            is_active=user_data.get('UserStatus') == 'CONFIRMED',
            email_verified=attributes.get('email_verified', 'false').lower() == 'true',
            created_at=user_data.get('UserCreateDate'),
            last_login=user_data.get('UserLastModifiedDate')
        )


# Global Cognito client instance
_cognito_client: Optional[CognitoClient] = None


def get_cognito_client() -> CognitoClient:
    """Get or create the global Cognito client instance.
    
    Returns:
        CognitoClient: Singleton Cognito client instance
    """
    global _cognito_client
    
    if _cognito_client is None:
        _cognito_client = CognitoClient()
    
    return _cognito_client