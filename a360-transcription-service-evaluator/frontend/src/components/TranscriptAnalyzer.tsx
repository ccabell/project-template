/**
 * Analytics dashboard component with embedded QuickSight dashboard.
 */

import React, { useState, useEffect } from 'react';

interface QuickSightEmbedConfig {
  dashboardId: string;
  region: string;
  awsAccountId: string;
}

export const TranscriptAnalyzer: React.FC = () => {
  const [isLoading, setIsLoading] = useState(true);
  const [embedUrl, setEmbedUrl] = useState<string>('');
  const [error, setError] = useState<string>('');

  // QuickSight configuration - these would typically come from environment variables
  const quickSightConfig: QuickSightEmbedConfig = {
    dashboardId: 'your-dashboard-id', // Replace with actual dashboard ID
    region: 'us-east-1',
    awsAccountId: '471112502741' // From your AWS account
  };

  useEffect(() => {
    loadQuickSightDashboard();
  }, []);

  const loadQuickSightDashboard = async () => {
    try {
      setIsLoading(true);
      setError('');

      // In a real implementation, you would make an API call to your backend
      // to generate a signed embed URL for QuickSight
      // For now, we'll show a placeholder

      // Simulated API call delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // This would be replaced with an actual API call to generate embed URL
      // const response = await apiService.getQuickSightEmbedUrl(quickSightConfig.dashboardId);
      // setEmbedUrl(response.embedUrl);

      // For demonstration, we'll show an informational message
      setError('QuickSight dashboard configuration required. Please contact your administrator to set up the dashboard embed URL.');
      
    } catch (err) {
      console.error('Failed to load QuickSight dashboard:', err);
      setError('Failed to load analytics dashboard. Please try again later.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = () => {
    loadQuickSightDashboard();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-96 bg-white rounded-lg shadow-lg">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading Analytics Dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-lg">
      {/* Header */}
      <div className="border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Analytics Dashboard</h2>
            <p className="text-gray-600 mt-1">
              Real-time analytics and insights for transcription evaluation
            </p>
          </div>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Refresh Dashboard
          </button>
        </div>
      </div>

      {/* Dashboard Content */}
      <div className="p-6">
        {error ? (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <svg className="h-6 w-6 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.728-.833-2.498 0L4.316 15.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-lg font-medium text-amber-800">Dashboard Configuration Required</h3>
                <p className="mt-1 text-amber-700">{error}</p>
                <div className="mt-4">
                  <div className="bg-white rounded-lg p-4 border border-amber-200">
                    <h4 className="font-semibold text-amber-800 mb-2">Configuration Steps:</h4>
                    <ol className="list-decimal list-inside space-y-1 text-sm text-amber-700">
                      <li>Create QuickSight dashboard with transcription analysis data</li>
                      <li>Configure dashboard embedding permissions</li>
                      <li>Add dashboard ID to environment configuration</li>
                      <li>Implement backend API endpoint for generating embed URLs</li>
                    </ol>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : embedUrl ? (
          <div className="w-full h-screen">
            <iframe
              src={embedUrl}
              className="w-full h-full border-0 rounded-lg"
              title="QuickSight Analytics Dashboard"
              allow="fullscreen"
            />
          </div>
        ) : (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">📊</div>
            <h3 className="text-xl font-medium text-gray-900 mb-2">Analytics Dashboard</h3>
            <p className="text-gray-600 mb-4">
              Interactive analytics and reporting for transcription evaluation metrics
            </p>
            <button
              onClick={handleRefresh}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Load Dashboard
            </button>
          </div>
        )}
      </div>

      {/* Dashboard Info Panel */}
      <div className="border-t border-gray-200 bg-gray-50 px-6 py-4 rounded-b-lg">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center">
            <div className="text-lg font-semibold text-gray-900">Real-time Metrics</div>
            <div className="text-sm text-gray-600">Live transcription accuracy tracking</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-gray-900">Performance Analytics</div>
            <div className="text-sm text-gray-600">Backend comparison and optimization</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-gray-900">Historical Trends</div>
            <div className="text-sm text-gray-600">Long-term evaluation insights</div>
          </div>
        </div>
      </div>
    </div>
  );
};