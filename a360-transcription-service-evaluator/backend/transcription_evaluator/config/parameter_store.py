"""Parameter Store configuration helper for A360 Transcription Service Evaluator.

This module provides utilities to read configuration values from AWS Systems Manager
Parameter Store, with fallback to environment variables for local development.
"""

import os
import logging
from typing import Dict, Optional
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class ParameterStoreConfig:
    """Configuration manager using AWS Parameter Store with environment variable fallback."""

    def __init__(
        self, 
        app_name: str = "a360transcriptionevaluator",
        stage: str = None,
        region: str = None
    ):
        """Initialize Parameter Store configuration.
        
        Args:
            app_name: Application name for parameter prefix
            stage: Deployment stage (dev, prod, etc.)
            region: AWS region
        """
        self.app_name = app_name.lower()
        self.stage = stage or os.getenv("TRANSCRIPTION_EVALUATOR_STAGE", "dev")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        
        # Parameter prefix
        self.parameter_prefix = f"/{self.app_name}/{self.stage}"
        
        # Initialize SSM client if possible
        self.ssm_client = None
        try:
            self.ssm_client = boto3.client("ssm", region_name=self.region)
        except (NoCredentialsError, ClientError) as e:
            logger.warning(f"Could not initialize SSM client: {e}. Using environment variables only.")
    
    @lru_cache(maxsize=32)
    def get_parameter(
        self, 
        parameter_name: str, 
        fallback_env_var: str = None,
        default_value: str = None,
        secure: bool = False
    ) -> Optional[str]:
        """Get parameter value from Parameter Store or environment variable.
        
        Args:
            parameter_name: Parameter name (without prefix)
            fallback_env_var: Environment variable to check if Parameter Store fails
            default_value: Default value if neither source has the parameter
            secure: Whether this is a secure string parameter
            
        Returns:
            Parameter value or None if not found
        """
        full_parameter_name = f"{self.parameter_prefix}/{parameter_name}"
        
        # Try Parameter Store first
        if self.ssm_client:
            try:
                response = self.ssm_client.get_parameter(
                    Name=full_parameter_name,
                    WithDecryption=secure
                )
                value = response["Parameter"]["Value"]
                logger.debug(f"Retrieved parameter {full_parameter_name} from Parameter Store")
                return value
                
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "ParameterNotFound":
                    logger.debug(f"Parameter {full_parameter_name} not found in Parameter Store")
                else:
                    logger.warning(f"Error retrieving parameter {full_parameter_name}: {e}")
        
        # Fallback to environment variable
        if fallback_env_var and fallback_env_var in os.environ:
            value = os.getenv(fallback_env_var)
            logger.debug(f"Retrieved parameter {parameter_name} from environment variable {fallback_env_var}")
            return value
        
        # Use default value
        if default_value is not None:
            logger.debug(f"Using default value for parameter {parameter_name}")
            return default_value
        
        logger.warning(f"Parameter {parameter_name} not found in Parameter Store, environment, or defaults")
        return None
    
    def get_frontend_config(self) -> Dict[str, str]:
        """Get all frontend configuration parameters.
        
        Returns:
            Dictionary with frontend configuration
        """
        return {
            "api_gateway_url": self.get_parameter(
                "frontend/api-gateway-url",
                "REACT_APP_API_URL",
                f"https://api.{self.app_name}.com"
            ),
            "cloudfront_url": self.get_parameter(
                "frontend/cloudfront-url",
                "REACT_APP_CLOUDFRONT_URL"
            ),
            "cognito_user_pool_id": self.get_parameter(
                "frontend/cognito-user-pool-id",
                "REACT_APP_COGNITO_USER_POOL_ID"
            ),
            "cognito_user_pool_client_id": self.get_parameter(
                "frontend/cognito-user-pool-client-id", 
                "REACT_APP_COGNITO_USER_POOL_CLIENT_ID"
            ),
            "cognito_identity_pool_id": self.get_parameter(
                "frontend/cognito-identity-pool-id",
                "REACT_APP_COGNITO_IDENTITY_POOL_ID"
            ),
            "aws_region": self.get_parameter(
                "frontend/aws-region",
                "AWS_REGION",
                self.region
            ),
        }
    
    def get_backend_config(self) -> Dict[str, str]:
        """Get all backend configuration parameters.
        
        Returns:
            Dictionary with backend configuration
        """
        return {
            "cloudfront_url": self.get_parameter(
                "backend/cloudfront-url",
                "CLOUDFRONT_URL"
            ),
            "api_gateway_url": self.get_parameter(
                "backend/api-gateway-url",
                "API_GATEWAY_URL"
            ),
            "aws_region": self.get_parameter(
                "backend/aws-region",
                "AWS_REGION",
                self.region
            ),
            "service_name": self.get_parameter(
                "backend/service-name",
                "SERVICE_NAME",
                "a360-transcription-evaluator-api"
            ),
        }


# Global instance for easy access
_parameter_store = None


def get_parameter_store() -> ParameterStoreConfig:
    """Get global Parameter Store configuration instance.
    
    Returns:
        ParameterStoreConfig instance
    """
    global _parameter_store
    if _parameter_store is None:
        _parameter_store = ParameterStoreConfig()
    return _parameter_store


def get_parameter(parameter_name: str, fallback_env_var: str = None, default_value: str = None) -> Optional[str]:
    """Convenience function to get a parameter value.
    
    Args:
        parameter_name: Parameter name (without prefix)
        fallback_env_var: Environment variable fallback
        default_value: Default value
        
    Returns:
        Parameter value or None
    """
    return get_parameter_store().get_parameter(parameter_name, fallback_env_var, default_value)


def get_frontend_config() -> Dict[str, str]:
    """Get frontend configuration.
    
    Returns:
        Frontend configuration dictionary
    """
    return get_parameter_store().get_frontend_config()


def get_backend_config() -> Dict[str, str]:
    """Get backend configuration.
    
    Returns:
        Backend configuration dictionary  
    """
    return get_parameter_store().get_backend_config()