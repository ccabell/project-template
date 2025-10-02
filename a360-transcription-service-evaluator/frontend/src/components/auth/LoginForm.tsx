/**
 * Login form component using AWS Amplify authentication.
 * 
 * This component provides a form for users to sign in with their
 * email and password using AWS Cognito authentication.
 */

import React, { useState } from 'react';
import { signIn, confirmSignIn, SignInInput } from 'aws-amplify/auth';
import { useAuth } from '../../contexts/AuthContext';
import toast from 'react-hot-toast';

interface LoginFormProps {
  onSuccess?: () => void;
}

const LoginForm: React.FC<LoginFormProps> = ({ onSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showNewPasswordForm, setShowNewPasswordForm] = useState(false);
  const { refreshAuth } = useAuth();

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    
    if (!email || !password) {
      toast.error('Please enter both email and password');
      return;
    }

    setIsLoading(true);

    try {
      const signInDetails: SignInInput = {
        username: email,
        password: password,
      };

      const result = await signIn(signInDetails);
      
      if (result.isSignedIn) {
        await refreshAuth();
        toast.success('Successfully signed in!');
        onSuccess?.();
      } else if (result.nextStep?.signInStep === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED') {
        console.log('NEW_PASSWORD_REQUIRED challenge received');
        setShowNewPasswordForm(true);
        toast('Please set a new password to complete sign in', { icon: 'ℹ️' });
      } else {
        console.log('Unexpected sign in result:', result);
        toast.error('Sign in was not completed. Please try again.');
      }
    } catch (error: any) {
      console.error('Sign in error:', error);
      
      let errorMessage = 'Failed to sign in. Please try again.';
      
      if (error.name === 'NotAuthorizedException') {
        errorMessage = 'Invalid email or password';
      } else if (error.name === 'UserNotConfirmedException') {
        errorMessage = 'Please verify your email before signing in';
      } else if (error.name === 'PasswordResetRequiredException') {
        errorMessage = 'Password reset required. Please contact support.';
      } else if (error.name === 'UserNotFoundException') {
        errorMessage = 'User not found. Please check your email address.';
      } else if (error.name === 'TooManyRequestsException') {
        errorMessage = 'Too many failed attempts. Please try again later.';
      }
      
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewPasswordSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    
    if (!newPassword || !confirmPassword) {
      toast.error('Please enter and confirm your new password');
      return;
    }

    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    if (newPassword.length < 12) {
      toast.error('Password must be at least 12 characters long');
      return;
    }

    // Validate password requirements to match Cognito policy
    const hasUppercase = /[A-Z]/.test(newPassword);
    const hasLowercase = /[a-z]/.test(newPassword);
    const hasNumbers = /\d/.test(newPassword);
    const hasSymbols = /[!@#$%^&*(),.?":{}|<>]/.test(newPassword);

    if (!hasUppercase || !hasLowercase || !hasNumbers || !hasSymbols) {
      toast.error('Password must contain uppercase, lowercase, numbers, and special characters');
      return;
    }

    setIsLoading(true);

    try {
      const result = await confirmSignIn({
        challengeResponse: newPassword,
      });
      
      if (result.isSignedIn) {
        await refreshAuth();
        toast.success('Password updated and signed in successfully!');
        onSuccess?.();
      } else {
        console.log('Unexpected confirmSignIn result:', result);
        toast.error('Failed to complete password change. Please try again.');
      }
    } catch (error: any) {
      console.error('New password error:', error);
      
      let errorMessage = 'Failed to set new password. Please try again.';
      
      if (error.name === 'InvalidPasswordException') {
        errorMessage = 'Password does not meet requirements. Please ensure it has uppercase, lowercase, numbers, and special characters.';
      } else if (error.name === 'InvalidParameterException') {
        errorMessage = 'Invalid password format. Please check password requirements.';
      }
      
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            {showNewPasswordForm ? 'Set New Password' : 'Sign in to your account'}
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            {showNewPasswordForm ? 'Your temporary password must be changed' : 'A360 Transcription Service Evaluation System'}
          </p>
        </div>
        
        {!showNewPasswordForm ? (
          <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
            <div className="space-y-4">
              <div>
                <label htmlFor="email" className="sr-only">
                  Email address
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  className="form-input"
                  placeholder="Email address"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              <div>
                <label htmlFor="password" className="sr-only">
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  className="form-input"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            </div>

            <div>
              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full flex justify-center py-2 px-4"
              >
                {isLoading ? (
                  <div className="spinner w-5 h-5" />
                ) : (
                  'Sign in'
                )}
              </button>
            </div>

            <div className="text-center">
              <p className="text-sm text-gray-600">
                Need an account? Contact your administrator.
              </p>
            </div>
          </form>
        ) : (
          <form className="mt-8 space-y-6" onSubmit={handleNewPasswordSubmit}>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-gray-600 mb-4">
                  Signed in as: <strong>{email}</strong>
                </p>
              </div>
              <div>
                <label htmlFor="newPassword" className="sr-only">
                  New Password
                </label>
                <input
                  id="newPassword"
                  name="newPassword"
                  type="password"
                  autoComplete="new-password"
                  required
                  className="form-input"
                  placeholder="New Password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              <div>
                <label htmlFor="confirmPassword" className="sr-only">
                  Confirm New Password
                </label>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  required
                  className="form-input"
                  placeholder="Confirm New Password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="text-xs text-gray-600 bg-gray-100 p-3 rounded">
              <p className="font-medium mb-1">Password Requirements:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>At least 12 characters long</li>
                <li>Contains uppercase letters (A-Z)</li>
                <li>Contains lowercase letters (a-z)</li>
                <li>Contains numbers (0-9)</li>
                <li>Contains special characters (!@#$%^&*)</li>
              </ul>
            </div>

            <div>
              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full flex justify-center py-2 px-4"
              >
                {isLoading ? (
                  <div className="spinner w-5 h-5" />
                ) : (
                  'Set New Password'
                )}
              </button>
            </div>

            <div className="text-center">
              <button
                type="button"
                onClick={() => {
                  setShowNewPasswordForm(false);
                  setNewPassword('');
                  setConfirmPassword('');
                }}
                className="text-sm text-blue-600 hover:text-blue-500"
                disabled={isLoading}
              >
                ← Back to sign in
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default LoginForm;