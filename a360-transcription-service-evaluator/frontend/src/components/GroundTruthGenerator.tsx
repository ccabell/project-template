/**
 * Ground truth generator component for creating test scripts.
 */

import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { BrandsTermsManager } from './BrandsTermsManager';
import { JobQueue } from './JobQueue';
import { useGroundTruth } from '../hooks/useGroundTruth';

interface FormData {
  medical_vertical: string;
  target_word_count: number;
  seed_term_density: number;
  include_product_names: boolean;
  language: string;
  encounter_type: string;
}

export const GroundTruthGenerator: React.FC = () => {
  // Form state
  const [error, setError] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [showGenerator, setShowGenerator] = useState<boolean>(true);
  const [showBrandsTermsManager, setShowBrandsTermsManager] = useState(false);
  const [showSuccessNotification, setShowSuccessNotification] = useState(false);
  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false);
  const [jobToDelete, setJobToDelete] = useState<string | null>(null);
  
  // Selected brands and terms from BrandsTermsManager
  const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
  const [selectedTerms, setSelectedTerms] = useState<string[]>([]);
  
  // Tab state - similar to ScriptAssignment pattern
  const [currentView, setCurrentView] = useState<'generation' | 'jobs'>('generation');

  const {
    jobs,
    generateScript,
    clearJob,
    clearAllJobs,
    availableVerticals,
    loadingVerticals,
    error: groundTruthError,
    clearError: clearGroundTruthError,
    refreshJobs
  } = useGroundTruth();

  const { register, handleSubmit, watch } = useForm<FormData>({
    defaultValues: {
      medical_vertical: 'aesthetic_medicine',
      target_word_count: 1000,
      seed_term_density: 0.5,
      include_product_names: true,
      language: 'english',
      encounter_type: 'initial_consultation'
    }
  });

  const wordCount = watch('target_word_count');
  const seedTermDensity = watch('seed_term_density');

  const clearError = () => setError(null);

  // Handler for selections from BrandsTermsManager
  const handleSelectionsChange = (brands: string[], terms: string[]) => {
    setSelectedBrands(brands);
    setSelectedTerms(terms);
  };

  const onSubmit = async (data: FormData) => {
    try {
      clearError();
      // Include selected brands and terms in the request
      const requestData = {
        ...data,
        selected_brands: selectedBrands,
        selected_terms: selectedTerms
      };
      await generateScript(requestData);
      // Show success notification
      setShowSuccessNotification(true);
      // Auto-hide after 3 seconds
      setTimeout(() => setShowSuccessNotification(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    }
  };

  // Handle tab switching and auto-switch to jobs tab when job is selected
  const handleSelectJob = (jobId: string) => {
    console.log('[GroundTruthGenerator DEBUG] Job selected:', jobId);
    console.log('[GroundTruthGenerator DEBUG] Available jobs:', jobs.map(j => ({id: j.jobId, status: j.status.status, hasResult: !!j.result})));
    setSelectedJobId(jobId);
    setShowGenerator(false);
    
    // Check if the job has results - if so, switch to generation tab to show script
    const selectedJob = jobs.find(job => job.jobId === jobId);
    if (selectedJob && selectedJob.result) {
      setCurrentView('generation');
      console.log('[GroundTruthGenerator DEBUG] Job has results, switched to generation tab');
    } else {
      // If no results yet, stay on jobs tab to show status
      setCurrentView('jobs');
      console.log('[GroundTruthGenerator DEBUG] Job has no results, staying on jobs tab');
    }
    console.log('[GroundTruthGenerator DEBUG] Set selectedJobId to:', jobId, 'showGenerator to false');
  };

  const downloadJobResult = (job: any) => {
    const content = `Ground Truth Script
Generated: ${new Date().toLocaleString()}
Job ID: ${job.jobId}
Word Count: ${job.result.word_count}
Medical Vertical: ${job.request.medical_vertical}
Language: ${job.request.language}
Medical Complexity: Based on Selected Terminology

${job.result.content}`;

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ground-truth-${job.jobId.slice(0, 8)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDeleteScript = (jobId: string) => {
    setJobToDelete(jobId);
    setShowDeleteConfirmation(true);
  };

  const confirmDeleteScript = async () => {
    if (jobToDelete) {
      try {
        await clearJob(jobToDelete);
        // If we just deleted the currently displayed job, go back to generator
        if (selectedJobId === jobToDelete) {
          setSelectedJobId(null);
          setShowGenerator(true);
        }
        setShowDeleteConfirmation(false);
        setJobToDelete(null);
      } catch (error) {
        console.error('Failed to delete script:', error);
        setError('Failed to delete script. Please try again.');
      }
    }
  };

  const cancelDeleteScript = () => {
    setShowDeleteConfirmation(false);
    setJobToDelete(null);
  };

  // Get the selected job or the most recent completed job
  const getDisplayJob = () => {
    console.log('[GroundTruthGenerator DEBUG] getDisplayJob called - showGenerator:', showGenerator, 'selectedJobId:', selectedJobId);
    
    // If explicitly showing generator, don't return any job
    if (showGenerator) {
      console.log('[GroundTruthGenerator DEBUG] Showing generator, returning null');
      return null;
    }
    
    if (selectedJobId) {
      const selectedJob = jobs.find(job => job.jobId === selectedJobId);
      console.log('[GroundTruthGenerator DEBUG] Looking for selectedJob:', selectedJobId, 'found:', !!selectedJob, 'hasResult:', !!selectedJob?.result);
      if (selectedJob) {
        console.log('[GroundTruthGenerator DEBUG] Selected job details:', {
          jobId: selectedJob.jobId,
          status: selectedJob.status.status,
          hasResult: !!selectedJob.result,
          resultKeys: selectedJob.result ? Object.keys(selectedJob.result) : []
        });
      }
      return selectedJob;
    }
    // Return the most recent completed job
    const completedJob = jobs.find(job => job.status.status === 'completed');
    console.log('[GroundTruthGenerator DEBUG] No selectedJobId, looking for completed job:', !!completedJob);
    return completedJob;
  };

  const displayJob = getDisplayJob();

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Success Notification */}
      {showSuccessNotification && (
        <div className="fixed top-4 right-4 z-50 bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg animate-pulse">
          <div className="flex items-center">
            <span className="text-lg mr-2">✅</span>
            <span className="font-medium">Script generation job added to queue!</span>
          </div>
        </div>
      )}
      
      <div className="flex-1 flex flex-col min-h-0 overflow-y-auto">
        <div className="p-8 flex-1 flex flex-col">
      
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Ground Truth Generator</h2>
        <p className="text-gray-600">
          Generate medical consultation scripts for transcription evaluation and manage job processing.
        </p>
        
        {/* Tab Navigation */}
        <div className="mt-4 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setCurrentView('generation')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                currentView === 'generation'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Script Generation
            </button>
            <button
              onClick={() => setCurrentView('jobs')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                currentView === 'jobs'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Job Status
              {jobs.length > 0 && (
                <span className="ml-2 bg-blue-500 text-white text-xs rounded-full px-2 py-1">
                  {jobs.length}
                </span>
              )}
            </button>
          </nav>
        </div>
      </div>

      {/* Conditional Tab Content */}
      {currentView === 'generation' ? (
        // Script Generation Tab
        <div className="flex-1 flex flex-col space-y-6">
          {(error || groundTruthError) && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">Error occurred</h3>
                  <div className="mt-2 text-sm text-red-700">
                    <p>{error || groundTruthError}</p>
                  </div>
                  <div className="mt-4">
                    <button
                      type="button"
                      onClick={() => {
                        clearError();
                        if (groundTruthError) clearGroundTruthError();
                      }}
                      className="bg-red-50 px-2 py-1.5 rounded-md text-red-800 hover:bg-red-100 text-sm font-medium"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Header with action buttons */}
          <div className="flex justify-between items-center mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                {displayJob && displayJob.result ? 'Generated Script' : 'Script Generation'}
              </h3>
            </div>
            <div className="flex items-center space-x-2">
              {(!displayJob || !displayJob.result) && (
                <button
                  onClick={() => setShowBrandsTermsManager(true)}
                  className="px-3 py-1 text-sm bg-purple-600 text-white rounded hover:bg-purple-700"
                >
                  Manage Brands & Terms
                </button>
              )}
              {displayJob && displayJob.result && (
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => downloadJobResult(displayJob)}
                    className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500"
                  >
                    Download Script
                  </button>
                  <button
                    onClick={() => handleDeleteScript(displayJob.jobId)}
                    className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500"
                  >
                    Delete Script
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Show Generated Script if available, otherwise show Generator Form */}
          {displayJob && displayJob.result ? (
            // Generated Script Content
            <div className="bg-white p-6 rounded-lg shadow-sm">
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-xl font-semibold text-gray-900">Generated Script Results</h3>
                <div className="flex items-center space-x-3">
                  <button
                    onClick={() => {
                      // Clear the selected job and show generator
                      setSelectedJobId(null);
                      setShowGenerator(true);
                    }}
                    className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    Back to Generator
                  </button>
                </div>
              </div>

              {/* Script Parameters */}
              <div className="mb-6 bg-gray-50 p-6 rounded-lg border">
                <h4 className="text-lg font-medium text-gray-900 mb-4">Generation Parameters</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-white p-4 rounded-lg shadow-sm">
                    <div className="text-sm font-medium text-gray-600">Medical Vertical</div>
                    <div className="text-lg font-semibold text-gray-900">
                      {(displayJob.request.medical_vertical || 'aesthetic_medicine')
                        .replace('_', ' ')
                        .replace(/\b\w/g, l => l.toUpperCase())}
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow-sm">
                    <div className="text-sm font-medium text-gray-600">Language</div>
                    <div className="text-lg font-semibold text-gray-900">
                      {(displayJob.request.language || 'english')
                        .replace(/\b\w/g, l => l.toUpperCase())}
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow-sm">
                    <div className="text-sm font-medium text-gray-600">Encounter Type</div>
                    <div className="text-lg font-semibold text-gray-900">
                      {(displayJob.request.encounter_type || 'initial_consultation')
                        .replace('_', ' ')
                        .replace(/\b\w/g, l => l.toUpperCase())}
                    </div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-lg shadow-sm">
                    <div className="text-sm font-medium text-gray-600">Medical Complexity</div>
                    <div className="text-lg font-semibold text-gray-900">
                      Based on Selected Terminology
                    </div>
                  </div>
                </div>
              </div>

              {/* Terms Used Section */}
              {(() => {
                let result = displayJob.result;
                // Parse result if it's a string
                if (typeof result === 'string') {
                  try {
                    result = JSON.parse(result);
                  } catch (e) {
                    result = displayJob.result;
                  }
                }
                
                const seedTerms = result?.metadata?.seed_terms_used || [];
                const brandNames = result?.metadata?.brand_names_used || [];
                
                console.log('[GroundTruthGenerator DEBUG] Terms parsing - result:', result);
                console.log('[GroundTruthGenerator DEBUG] seedTerms:', seedTerms);
                console.log('[GroundTruthGenerator DEBUG] brandNames:', brandNames);
                
                return (seedTerms.length > 0 || brandNames.length > 0) && (
                  <div className="bg-amber-50 p-6 rounded-lg border border-amber-200 mb-6">
                    <h4 className="text-lg font-medium text-gray-900 mb-4">Terms Used in Generation</h4>
                    <div className="flex flex-wrap gap-2">
                      {seedTerms.map((term: string, index: number) => (
                        <span
                          key={index}
                          className="inline-block px-3 py-1 text-sm bg-green-100 text-green-800 rounded border border-green-200 font-medium"
                          title={`Seed term: ${term}`}
                        >
                          {term}
                        </span>
                      ))}
                      {brandNames.map((brand: string, index: number) => (
                        <span
                          key={`brand-${index}`}
                          className="inline-block px-3 py-1 text-sm bg-purple-100 text-purple-800 rounded border border-purple-200 font-medium"
                          title={`Brand name: ${brand}`}
                        >
                          {brand}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })()}

              {/* Generated Script Content */}
              <div className="bg-gray-50 p-6 rounded-lg border flex-1 flex flex-col min-h-0">
                <h4 className="text-lg font-medium text-gray-900 mb-4">Generated Script Content</h4>
                <div className="bg-white p-6 rounded-lg border flex-1 flex flex-col min-h-0 max-h-[60vh]">
                  <div className="flex-1 overflow-y-auto overflow-x-hidden scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
                    <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono leading-relaxed">
                      {(() => {
                        let result = displayJob.result;
                        // Parse result if it's a string
                        if (typeof result === 'string') {
                          try {
                            result = JSON.parse(result);
                          } catch (e) {
                            result = displayJob.result;
                          }
                        }
                        return result?.content || 'Content not available';
                      })()}
                    </pre>
                  </div>
                </div>

                {/* Metadata */}
                <div className="text-xs text-gray-500 border-t pt-4 mt-4 flex-shrink-0">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <p>Script ID: <span className="font-mono">{displayJob.result.script_id}</span></p>
                    <p>Storage Path: <span className="font-mono">{displayJob.result.storage_path}</span></p>
                    <p>Job ID: <span className="font-mono">{displayJob.jobId}</span></p>
                    <p>Created: <span className="font-mono">{new Date(displayJob.createdAt).toLocaleString()}</span></p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            // Generator Form
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-6 bg-white p-6 rounded-lg shadow-sm">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Medical Vertical
                  </label>
                  <select
                    {...register('medical_vertical', { required: 'Medical vertical is required' })}
                    disabled={loadingVerticals}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  >
                    {availableVerticals.map((vertical) => (
                      <option key={vertical} value={vertical}>
                        {vertical.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Language
                  </label>
                  <select
                    {...register('language', { required: 'Language is required' })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="english">English</option>
                    <option value="spanish">Spanish</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Encounter Type
                  </label>
                  <select
                    {...register('encounter_type', { required: 'Encounter type is required' })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="initial_consultation">Initial Consultation</option>
                    <option value="follow_up">Follow-Up</option>
                    <option value="treatment_session">Treatment Session</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Target Word Count: {wordCount.toLocaleString()}
                    {wordCount > 1200 && (
                      <span className="ml-2 text-xs text-orange-600 font-normal">
                        (Large request - may take longer)
                      </span>
                    )}
                  </label>
                  <input
                    type="range"
                    min="500"
                    max="1500"
                    step="50"
                    {...register('target_word_count')}
                    className={`w-full ${wordCount > 1200 ? 'accent-orange-500' : 'accent-blue-500'}`}
                  />
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>500</span>
                    <span className="text-center">
                      1,000<br/>
                      <span className="text-blue-500">Default</span>
                    </span>
                    <span>1,500</span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Seed Term Density: {Number(seedTermDensity || 0.5).toFixed(2)}
                  </label>
                  <input
                    type="range"
                    min="0.25"
                    max="0.75"
                    step="0.05"
                    {...register('seed_term_density')}
                    className="w-full accent-blue-500"
                  />
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>0.25 (Low)</span>
                    <span>0.50 (Default)</span>
                    <span>0.75 (High)</span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                <div className="flex items-center space-x-3 pt-6">
                  <input
                    type="checkbox"
                    {...register('include_product_names')}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <label className="text-sm font-medium text-gray-700">
                    Include Product Names
                  </label>
                </div>
              </div>


              <button
                type="submit"
                className="w-full bg-blue-600 text-white py-3 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium"
              >
                Generate Ground Truth Script
              </button>
            </form>
          )}
        </div>
      ) : (
        // Job Status Tab
        <div className="flex-1 flex flex-col space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold text-gray-900">Job Status & Management</h3>
            <span className="text-sm text-gray-600">
              {jobs.length} total jobs
            </span>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm flex-1 min-h-0">
            <JobQueue
              jobs={jobs}
              onSelectJob={handleSelectJob}
              onClearJob={clearJob}
              onClearAll={clearAllJobs}
              onDownloadResult={downloadJobResult}
              onRefresh={refreshJobs}
            />
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirmation && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md mx-4">
            <div className="flex items-center mb-4">
              <div className="flex-shrink-0">
                <svg className="w-6 h-6 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-lg font-medium text-gray-900">
                  Delete Generated Script?
                </h3>
              </div>
            </div>
            
            <div className="mb-6">
              <p className="text-sm text-gray-600">
                Are you sure you want to permanently delete this generated script? 
                <span className="font-semibold text-red-600"> This action cannot be undone.</span>
              </p>
              {jobToDelete && (
                <div className="mt-3 p-3 bg-red-50 rounded-lg">
                  <p className="text-sm text-red-800">
                    Script ID: <span className="font-mono">{jobToDelete.slice(0, 8)}...</span>
                  </p>
                </div>
              )}
            </div>
            
            <div className="flex justify-end space-x-3">
              <button
                onClick={cancelDeleteScript}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Cancel
              </button>
              <button
                onClick={confirmDeleteScript}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
              >
                Delete Permanently
              </button>
            </div>
          </div>
        </div>
      )}

      <BrandsTermsManager
        isOpen={showBrandsTermsManager}
        onClose={() => setShowBrandsTermsManager(false)}
        onSelectionsChange={handleSelectionsChange}
      />
        </div>
      </div>
    </div>
  );
};