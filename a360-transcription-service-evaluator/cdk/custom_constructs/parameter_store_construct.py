"""Parameter Store construct for A360 Transcription Service Evaluator.

This construct creates and manages AWS Systems Manager Parameter Store parameters
for configuration management across the application.
"""

import aws_cdk as cdk
from aws_cdk import aws_ssm as ssm
from constructs import Construct
from typing import Dict, Optional


class ParameterStoreConstruct(Construct):
    """Construct to manage Parameter Store parameters for the application."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_name: str,
        stage: str,
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)
        
        self.app_name = app_name
        self.stage = stage
        self.parameters = {}
        
        # Parameter name prefix for this application
        self.parameter_prefix = f"/{app_name.lower()}/{stage}"
        
    def create_parameter(
        self,
        parameter_name: str,
        parameter_value: str,
        description: str,
        parameter_type: ssm.ParameterType = ssm.ParameterType.STRING,
        secure: bool = False
    ) -> ssm.StringParameter:
        """Create a new parameter in Parameter Store.
        
        Args:
            parameter_name: Name of the parameter (will be prefixed)
            parameter_value: Value of the parameter
            description: Description of the parameter
            parameter_type: Type of parameter (STRING, STRING_LIST, SECURE_STRING)
            secure: Whether this is a secure string parameter
            
        Returns:
            The created StringParameter construct
        """
        full_parameter_name = f"{self.parameter_prefix}/{parameter_name}"
        
        if secure:
            parameter_type = ssm.ParameterType.SECURE_STRING
        
        parameter = ssm.StringParameter(
            self,
            f"Parameter{parameter_name.replace('/', '').replace('-', '').title()}",
            parameter_name=full_parameter_name,
            string_value=parameter_value,
            description=description,
            type=parameter_type,
            tier=ssm.ParameterTier.STANDARD
        )
        
        # Store reference for easy access
        self.parameters[parameter_name] = parameter
        
        # Add tags
        cdk.Tags.of(parameter).add("Environment", self.stage)
        cdk.Tags.of(parameter).add("Application", self.app_name)
        cdk.Tags.of(parameter).add("ManagedBy", "CDK")
        
        return parameter
    
    def create_frontend_parameters(
        self,
        api_gateway_url: str,
        cloudfront_url: str,
        user_pool_id: str,
        user_pool_client_id: str,
        identity_pool_id: str,
        region: str
    ) -> Dict[str, ssm.StringParameter]:
        """Create frontend-specific parameters.
        
        Args:
            api_gateway_url: API Gateway URL
            cloudfront_url: CloudFront distribution URL
            user_pool_id: Cognito User Pool ID
            user_pool_client_id: Cognito User Pool Client ID
            identity_pool_id: Cognito Identity Pool ID (optional, not used in this architecture)
            region: AWS region
            
        Returns:
            Dictionary of created parameters
        """
        frontend_params = {}
        
        frontend_params['api-gateway-url'] = self.create_parameter(
            "frontend/api-gateway-url",
            api_gateway_url,
            "API Gateway URL for frontend API calls"
        )
        
        frontend_params['cloudfront-url'] = self.create_parameter(
            "frontend/cloudfront-url", 
            cloudfront_url,
            "CloudFront distribution URL for the frontend"
        )
        
        frontend_params['cognito-user-pool-id'] = self.create_parameter(
            "frontend/cognito-user-pool-id",
            user_pool_id,
            "Cognito User Pool ID for authentication"
        )
        
        frontend_params['cognito-user-pool-client-id'] = self.create_parameter(
            "frontend/cognito-user-pool-client-id",
            user_pool_client_id,
            "Cognito User Pool Client ID for authentication"
        )
        
        # Only create identity pool parameter if ID is provided
        if identity_pool_id and identity_pool_id.strip():
            frontend_params['cognito-identity-pool-id'] = self.create_parameter(
                "frontend/cognito-identity-pool-id",
                identity_pool_id,
                "Cognito Identity Pool ID for AWS resource access"
            )
        
        frontend_params['aws-region'] = self.create_parameter(
            "frontend/aws-region",
            region,
            "AWS region where resources are deployed"
        )
        
        return frontend_params
    
    def create_backend_parameters(
        self,
        cloudfront_url: str,
        api_gateway_url: str,
        region: str,
        service_name: str
    ) -> Dict[str, ssm.StringParameter]:
        """Create backend-specific parameters.
        
        Args:
            cloudfront_url: CloudFront distribution URL
            api_gateway_url: API Gateway URL  
            region: AWS region
            service_name: Service name for identification
            
        Returns:
            Dictionary of created parameters
        """
        backend_params = {}
        
        backend_params['cloudfront-url'] = self.create_parameter(
            "backend/cloudfront-url",
            cloudfront_url,
            "CloudFront distribution URL for CORS configuration"
        )
        
        backend_params['api-gateway-url'] = self.create_parameter(
            "backend/api-gateway-url",
            api_gateway_url,
            "API Gateway URL for internal service calls"
        )
        
        backend_params['aws-region'] = self.create_parameter(
            "backend/aws-region",
            region,
            "AWS region where backend services are deployed"
        )
        
        backend_params['service-name'] = self.create_parameter(
            "backend/service-name",
            service_name,
            "Service name for identification and logging"
        )
        
        return backend_params
    
    def get_parameter_name(self, parameter_name: str) -> str:
        """Get the full parameter name with prefix.
        
        Args:
            parameter_name: Short parameter name
            
        Returns:
            Full parameter name with prefix
        """
        return f"{self.parameter_prefix}/{parameter_name}"
    
    def get_parameter_arn(self, parameter_name: str) -> str:
        """Get the ARN for a parameter.
        
        Args:
            parameter_name: Short parameter name
            
        Returns:
            Parameter ARN
        """
        return f"arn:aws:ssm:{cdk.Stack.of(self).region}:{cdk.Stack.of(self).account}:parameter{self.get_parameter_name(parameter_name)}"