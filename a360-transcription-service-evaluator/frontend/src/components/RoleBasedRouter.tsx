/**
 * Role-based router component that displays different views based on user's Cognito groups.
 */

import React, { useState, useEffect } from 'react';
import { getCurrentUser } from 'aws-amplify/auth';
import { GroundTruthGenerator } from './GroundTruthGenerator';
import { JobQueue } from './JobQueue';
import { ReaderView } from './ReaderView';
import { TranscriptAnalyzer } from './TranscriptAnalyzer';
import { BrandsTermsManager } from './BrandsTermsManager';
import { ScriptAssignment } from './ScriptAssignment';
import { apiService } from '../services/api';

interface UserInfo {
  username: string;
  groups: string[];
  email?: string;
}

type UserRole = 'admin' | 'evaluator' | 'reader' | 'reviewer' | 'unknown';

interface RoleBasedRouterProps {
  onSignOut: () => void;
}

export const RoleBasedRouter: React.FC<RoleBasedRouterProps> = ({ onSignOut }) => {
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [currentView, setCurrentView] = useState<string>('generator');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showBrandsModal, setShowBrandsModal] = useState(false);

  useEffect(() => {
    loadUserInfo();
  }, []);

  const loadUserInfo = async () => {
    try {
      setLoading(true);
      
      // Get basic user info from Cognito
      const user = await getCurrentUser();
      
      // Get user groups from API endpoint (avoids Identity Pool)
      let groups: string[] = [];
      try {
        const userInfo = await apiService.getUserInfo();
        groups = userInfo.groups || [];
        console.log('Retrieved user groups from API:', groups);
      } catch (apiError) {
        console.warn('Could not retrieve user groups from API:', apiError);
        // Continue with empty groups - user will see appropriate access denied messages
      }
      
      setUserInfo({
        username: user.username,
        groups,
        email: user.signInDetails?.loginId,
      });
      
      // Set default view based on primary role
      const primaryRole = determinePrimaryRole(groups);
      if (primaryRole === 'reader') {
        setCurrentView('assignments');
      } else {
        setCurrentView('generator');
      }
      
    } catch (err: any) {
      console.error('Error loading user info:', err);
      setError(err.message || 'Failed to load user information');
    } finally {
      setLoading(false);
    }
  };


  const determinePrimaryRole = (groups: string[]): UserRole => {
    // Priority order: admin > evaluator > reader > reviewer
    if (groups.includes('admin')) return 'admin';
    if (groups.includes('evaluator')) return 'evaluator';
    if (groups.includes('reader')) return 'reader';
    if (groups.includes('reviewer')) return 'reviewer';
    return 'unknown';
  };

  const hasPermission = (requiredGroups: string[]): boolean => {
    if (!userInfo) return false;
    return requiredGroups.some(group => userInfo.groups.includes(group));
  };

  const getAvailableViews = () => {
    if (!userInfo) return [];

    const views = [];
    
    // Views available to admin, evaluator, reviewer (content creators/managers)
    if (hasPermission(['admin', 'evaluator', 'reviewer'])) {
      views.push(
        { key: 'generator', label: 'Ground Truth Generator' },
      );
    }

    // Admin-only views (Script Assignment comes after Ground Truth Generator)
    if (hasPermission(['admin'])) {
      views.push(
        { key: 'assignments', label: 'Script Assignment' }
      );
    }

    // Transcript Analyzer temporarily hidden
    // if (hasPermission(['admin', 'evaluator', 'reviewer'])) {
    //   views.push(
    //     { key: 'analyzer', label: 'Transcript Analyzer' }
    //   );
    // }

    // Reader view
    if (hasPermission(['reader'])) {
      views.push(
        { key: 'assignments', label: 'My Assignments' }
      );
    }

    return views;
  };

  const renderCurrentView = () => {
    if (!userInfo) return null;

    switch (currentView) {
      case 'generator':
        if (hasPermission(['admin', 'evaluator', 'reviewer'])) {
          return <GroundTruthGenerator />;
        }
        break;
        
      case 'analyzer':
        if (hasPermission(['admin', 'evaluator', 'reviewer'])) {
          return <TranscriptAnalyzer />;
        }
        break;
        
      case 'jobs':
        if (hasPermission(['admin', 'evaluator', 'reviewer'])) {
          // Jobs view redirects to generator which has full job integration
          return <GroundTruthGenerator />;
        }
        break;
        
      case 'brands':
        if (hasPermission(['admin'])) {
          setShowBrandsModal(true);
          setCurrentView('generator'); // Return to generator view
          return <GroundTruthGenerator />;
        }
        break;
        
      case 'assignments':
        if (hasPermission(['admin'])) {
          return <ScriptAssignment />;
        } else if (hasPermission(['reader'])) {
          return <ReaderView userGroups={userInfo.groups} />;
        }
        break;
        
      default:
        // Fallback based on role
        const primaryRole = determinePrimaryRole(userInfo.groups);
        if (primaryRole === 'reader') {
          return <ReaderView userGroups={userInfo.groups} />;
        } else if (hasPermission(['admin', 'evaluator', 'reviewer'])) {
          return <GroundTruthGenerator />;
        }
    }

    // Unauthorized view
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="text-4xl mb-4">🚫</div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">Access Denied</h3>
          <p className="text-gray-600">You don't have permission to access this view.</p>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading your workspace...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="bg-white p-8 rounded-lg border border-red-200 max-w-md">
          <div className="text-center">
            <div className="text-4xl mb-4">⚠️</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Error Loading Workspace</h3>
            <p className="text-gray-600 mb-4">{error}</p>
            <div className="space-y-2">
              <button
                onClick={loadUserInfo}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md"
              >
                Retry
              </button>
              <button
                onClick={onSignOut}
                className="w-full bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded-md"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const availableViews = getAvailableViews();
  const primaryRole = userInfo ? determinePrimaryRole(userInfo.groups) : 'unknown';

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-gray-900">
                A360 Transcription Evaluation System
              </h1>
              {userInfo && (
                <div className="flex items-center space-x-4 mt-1 text-sm text-gray-600">
                  <span>{userInfo.email || userInfo.username}</span>
                  <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
                    {primaryRole.replace('_', ' ').toUpperCase()}
                  </span>
                  {userInfo.groups.length > 1 && (
                    <span className="text-xs text-gray-500">
                      +{userInfo.groups.length - 1} more groups
                    </span>
                  )}
                </div>
              )}
            </div>
            
            <div className="flex items-center space-x-4">
              {/* View Navigation */}
              {availableViews.length > 1 && (
                <div className="flex bg-gray-100 rounded-lg p-1">
                  {availableViews.map((view) => (
                    <button
                      key={view.key}
                      onClick={() => {
                        if (view.key === 'brands') {
                          setShowBrandsModal(true);
                        } else {
                          setCurrentView(view.key);
                        }
                      }}
                      className={`relative px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                        currentView === view.key
                          ? 'bg-white text-blue-600 shadow-sm'
                          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                      }`}
                    >
                      <span className="relative z-10">{view.label}</span>
                      {currentView === view.key && (
                        <div className="absolute inset-0 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-md opacity-50" />
                      )}
                    </button>
                  ))}
                </div>
              )}
              
              <button
                onClick={onSignOut}
                className="text-gray-600 hover:text-gray-900 px-3 py-2 rounded-md text-sm font-medium"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {renderCurrentView()}
      </main>

      {/* Brands & Terms Modal */}
      {showBrandsModal && (
        <BrandsTermsManager 
          isOpen={showBrandsModal}
          onClose={() => setShowBrandsModal(false)}
        />
      )}
    </div>
  );
};