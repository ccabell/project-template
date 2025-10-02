/**
 * AWS Amplify configuration for Cognito authentication.
 * 
 * This configuration connects the React frontend to AWS Cognito User Pool
 * for authentication. We use API Gateway with Cognito Authorizer, so we
 * only need User Pool tokens, not Identity Pool credentials.
 */

import { Amplify } from 'aws-amplify';

const awsConfig = {
  Auth: {
    Cognito: {
      userPoolId: process.env.REACT_APP_COGNITO_USER_POOL_ID || 'us-east-1_O6Ib3izRC',
      userPoolClientId: process.env.REACT_APP_COGNITO_USER_POOL_CLIENT_ID || '5sia5bf01l5mg7uacn5aqg4og9',
      identityPoolId: process.env.REACT_APP_COGNITO_IDENTITY_POOL_ID || 'us-east-1:650ea3aa-4196-4046-8803-9f0d3923a9cf',
      loginWith: {
        email: true,
      },
      signUpVerificationMethod: 'code' as const,
      userAttributes: {
        email: {
          required: true,
        },
      },
      allowGuestAccess: false,
      passwordFormat: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireNumbers: true,
        requireSpecialCharacters: true,
      },
    },
  },
};

// Configure Amplify
Amplify.configure(awsConfig);

export default awsConfig;