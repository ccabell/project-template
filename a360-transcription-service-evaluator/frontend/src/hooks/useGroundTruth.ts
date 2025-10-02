/**
 * React hook for ground truth generation functionality.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { apiService } from '../services/api';
import {
  GroundTruthGenerationRequest,
  GroundTruthResponse,
  GroundTruthJobStatus
} from '../types/api';

interface JobQueueItem {
  jobId: string;
  status: GroundTruthJobStatus;
  request: GroundTruthGenerationRequest;
  result?: GroundTruthResponse;
  error?: string;
  createdAt: string;
  script_title?: string;
}

interface UseGroundTruthResult {
  generating: boolean;
  loadingVerticals: boolean;
  jobs: JobQueueItem[];
  availableVerticals: string[];
  error: string | null;
  generateScript: (request: GroundTruthGenerationRequest) => Promise<void>;
  selectJob: (jobId: string) => void;
  clearJob: (jobId: string) => void;
  clearAllJobs: () => void;
  clearError: () => void;
  refreshJobs: () => Promise<void>;
}

export const useGroundTruth = (): UseGroundTruthResult => {
  const [generating, setGenerating] = useState(false);
  const [loadingVerticals, setLoadingVerticals] = useState(false);
  const [jobs, setJobs] = useState<JobQueueItem[]>([]);
  const [availableVerticals, setAvailableVerticals] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const pollingIntervalsRef = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Load initial data on mount
  useEffect(() => {
    const loadInitialData = async () => {
      setLoadingVerticals(true);
      
      // Load verticals (public endpoint - no auth required)
      try {
        const response: any = await apiService.getAvailableVerticals();
        // Extract vertical IDs from the API response - API returns {verticals: [...]}
        const verticals = response.verticals || [];
        const verticalIds = verticals.map((v: any) => v.id);
        setAvailableVerticals(verticalIds);
        console.log('[Verticals] Successfully loaded verticals:', verticalIds);
      } catch (err) {
        console.error('Failed to load verticals:', err);
        if (err instanceof Error && err.message.includes('Authentication failed')) {
          setError('Please sign in to access medical verticals');
          setAvailableVerticals([]);
        } else {
          // Set default verticals as fallback for other errors
          console.log('[Verticals] Using fallback verticals due to error');
          setAvailableVerticals([
            'aesthetic_medicine',
            'dermatology',
            'venous_care',
            'plastic_surgery'
          ]);
        }
      } finally {
        setLoadingVerticals(false);
      }

      // Try to load user jobs (protected endpoint - may fail if backend not deployed)
      try {
        console.log('[Jobs] Attempting to load user jobs...');
        const userJobsResponse = await apiService.getUserJobs();
        const backendJobs = userJobsResponse.jobs || [];
        
        // Convert backend jobs to frontend format
        const convertedJobs: JobQueueItem[] = backendJobs.map(job => {
          console.log('[DEBUG] Backend job data:', job);
          console.log('[DEBUG] Job request_data:', job.request_data);
          console.log('[DEBUG] Job request_data type:', typeof job.request_data);
          
          // Handle request_data parsing - it might be a string, object, or undefined
          let parsedRequestData = {};
          if (job.request_data) {
            if (typeof job.request_data === 'string') {
              try {
                parsedRequestData = JSON.parse(job.request_data);
                console.log('[DEBUG] Parsed request_data from string:', parsedRequestData);
              } catch (e) {
                console.error('[DEBUG] Failed to parse request_data string:', e);
                parsedRequestData = {};
              }
            } else if (typeof job.request_data === 'object') {
              parsedRequestData = job.request_data;
              console.log('[DEBUG] Using object request_data:', parsedRequestData);
            }
          } else {
            console.log('[DEBUG] No request_data found for job:', job.job_id);
          }
          
          // Parse result if it's a JSON string (DynamoDB stores as string)
          let parsedResult = job.result;
          if (typeof parsedResult === 'string' && parsedResult.trim()) {
            try {
              parsedResult = JSON.parse(parsedResult);
              console.log('[DEBUG] Parsed result from JSON string:', parsedResult);
            } catch (e) {
              console.error('[DEBUG] Failed to parse result JSON:', e);
              parsedResult = null;
            }
          }
          
          // Create proper result object for completed jobs with content
          let groundTruthResult = undefined;
          if (job.status === 'completed' && parsedResult && parsedResult.content) {
            console.log('[DEBUG] Creating groundTruthResult with metadata:', parsedResult.metadata);
            groundTruthResult = {
              success: true,
              script_id: job.job_id,
              content: parsedResult.content || '',
              word_count: parsedResult.word_count || 0,
              storage_path: job.result_path,
              metadata: parsedResult.metadata || {},
              message: 'Ground truth generation completed'
            };
            console.log('[DEBUG] Final groundTruthResult:', groundTruthResult);
          }

          return {
            jobId: job.job_id,
            status: {
              job_id: job.job_id,
              status: job.status,
              updated_at: job.updated_at,
              error: job.error_message,
              result: groundTruthResult
            },
            request: parsedRequestData,
            result: groundTruthResult,
            error: job.error_message,
            script_title: job.script_title,
            createdAt: job.created_at || job.updated_at
          };
        });

        setJobs(convertedJobs);

        // Start polling for any processing jobs
        const processingJobs = convertedJobs.filter(job => job.status.status === 'processing');
        
        if (processingJobs.length > 0) {
          setGenerating(true);
          // Set up polling for processing jobs
          setTimeout(() => {
            processingJobs.forEach(job => {
              const interval = setInterval(async () => {
                try {
                  const status = await apiService.getJobStatus(job.jobId);
                  
                  setJobs(prevJobs => 
                    prevJobs.map(prevJob => {
                      if (prevJob.jobId === job.jobId) {
                        const updatedJob = { ...prevJob, status };
                        
                        if (status.status === 'completed' && status.result) {
                          updatedJob.result = status.result;
                          // Stop polling for this job
                          const interval = pollingIntervalsRef.current.get(job.jobId);
                          if (interval) {
                            clearInterval(interval);
                            pollingIntervalsRef.current.delete(job.jobId);
                          }
                        } else if (status.status === 'failed') {
                          updatedJob.error = status.error || 'Script generation failed';
                          // Stop polling for this job
                          const interval = pollingIntervalsRef.current.get(job.jobId);
                          if (interval) {
                            clearInterval(interval);
                            pollingIntervalsRef.current.delete(job.jobId);
                          }
                        }
                        
                        return updatedJob;
                      }
                      return prevJob;
                    })
                  );

                  // Update generating status
                  setJobs(prevJobs => {
                    const hasProcessing = prevJobs.some(job => job.status.status === 'processing');
                    setGenerating(hasProcessing);
                    return prevJobs;
                  });

                } catch (err) {
                  console.error(`Failed to poll job ${job.jobId}:`, err);
                }
              }, 2000);
              pollingIntervalsRef.current.set(job.jobId, interval);
            });
          }, 100);
        }

        console.log(`[Jobs] Successfully loaded ${convertedJobs.length} jobs from backend`);
      } catch (err) {
        console.warn('[Jobs] Failed to load user jobs - this is expected if backend is not deployed yet:', err);
        // Don't set an error - just continue without user jobs
        console.log('[Jobs] Continuing without persistent job storage - new jobs will work but won\'t persist across sessions');
      }
    };

    loadInitialData();

    // Set up auto-refresh for job status every 30 seconds
    const startAutoRefresh = () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
      
      refreshIntervalRef.current = setInterval(async () => {
        try {
          console.log('[AutoRefresh] Refreshing user jobs...');
          const userJobsResponse = await apiService.getUserJobs();
          const backendJobs = userJobsResponse.jobs || [];
          
          // Convert backend jobs to frontend format (same logic as initial load)
          const convertedJobs: JobQueueItem[] = backendJobs.map(job => {
            let parsedRequestData = {};
            if (job.request_data) {
              if (typeof job.request_data === 'string') {
                try {
                  parsedRequestData = JSON.parse(job.request_data);
                } catch (e) {
                  console.error('[AutoRefresh] Failed to parse request_data string:', e);
                  parsedRequestData = {};
                }
              } else if (typeof job.request_data === 'object') {
                parsedRequestData = job.request_data;
              }
            }
            
            let parsedResult = job.result;
            if (typeof parsedResult === 'string' && parsedResult.trim()) {
              try {
                parsedResult = JSON.parse(parsedResult);
              } catch (e) {
                console.error('[AutoRefresh] Failed to parse result JSON:', e);
                parsedResult = null;
              }
            }
            
            let groundTruthResult = undefined;
            if (job.status === 'completed' && parsedResult && parsedResult.content) {
              groundTruthResult = {
                success: true,
                script_id: job.job_id,
                content: parsedResult.content || '',
                word_count: parsedResult.word_count || 0,
                storage_path: job.result_path,
                metadata: parsedResult.metadata || {},
                message: 'Ground truth generation completed'
              };
            }

            return {
              jobId: job.job_id,
              status: {
                job_id: job.job_id,
                status: job.status,
                updated_at: job.updated_at,
                error: job.error_message,
                result: groundTruthResult
              },
              request: parsedRequestData,
              result: groundTruthResult,
              error: job.error_message,
              script_title: job.script_title,
              createdAt: job.created_at || job.updated_at
            };
          });

          setJobs(convertedJobs);
          console.log(`[AutoRefresh] Updated ${convertedJobs.length} jobs`);
        } catch (err) {
          console.warn('[AutoRefresh] Failed to refresh jobs:', err);
          // Don't show error to user for background refresh failures
        }
      }, 30000); // 30 seconds
    };

    // Start auto-refresh
    startAutoRefresh();

    // Cleanup on unmount
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, []);

  // Polling function for a specific job
  const pollJobStatus = useCallback(async (jobId: string) => {
    try {
      const status = await apiService.getJobStatus(jobId);
      
      setJobs(prevJobs => 
        prevJobs.map(job => {
          if (job.jobId === jobId) {
            const updatedJob = { ...job, status };
            
            if (status.status === 'completed' && status.result) {
              updatedJob.result = status.result;
              // Stop polling for this job
              const interval = pollingIntervalsRef.current.get(jobId);
              if (interval) {
                clearInterval(interval);
                pollingIntervalsRef.current.delete(jobId);
              }
            } else if (status.status === 'failed') {
              updatedJob.error = status.error || 'Script generation failed';
              // Stop polling for this job
              const interval = pollingIntervalsRef.current.get(jobId);
              if (interval) {
                clearInterval(interval);
                pollingIntervalsRef.current.delete(jobId);
              }
            }
            
            return updatedJob;
          }
          return job;
        })
      );

      // Update generating status based on whether any jobs are still processing
      setJobs(prevJobs => {
        const hasProcessing = prevJobs.some(job => job.status.status === 'processing');
        setGenerating(hasProcessing);
        return prevJobs;
      });

    } catch (err) {
      console.error(`Failed to poll job ${jobId}:`, err);
      // Mark job as failed and stop polling
      setJobs(prevJobs => 
        prevJobs.map(job => 
          job.jobId === jobId 
            ? { ...job, error: err instanceof Error ? err.message : 'Failed to check job status' }
            : job
        )
      );
      
      const interval = pollingIntervalsRef.current.get(jobId);
      if (interval) {
        clearInterval(interval);
        pollingIntervalsRef.current.delete(jobId);
      }
    }
  }, []);

  const generateScript = useCallback(async (request: GroundTruthGenerationRequest) => {
    setError(null);

    try {
      const jobResponse = await apiService.generateGroundTruth(request);
      
      // Create new job queue item
      const newJob: JobQueueItem = {
        jobId: jobResponse.job_id,
        status: {
          job_id: jobResponse.job_id,
          status: 'processing',
          updated_at: new Date().toISOString()
        },
        request,
        createdAt: new Date().toISOString()
      };

      // Add job to queue
      setJobs(prevJobs => [...prevJobs, newJob]);
      setGenerating(true);

      // Start polling for this specific job
      const interval = setInterval(() => {
        pollJobStatus(jobResponse.job_id);
      }, 2000); // Poll every 2 seconds

      pollingIntervalsRef.current.set(jobResponse.job_id, interval);

      // Initial poll
      await pollJobStatus(jobResponse.job_id);
    } catch (err) {
      if (err instanceof Error && err.message.includes('Authentication service unavailable')) {
        setError('Backend authentication not ready - please wait for deployment to complete or try again later');
      } else {
        setError(err instanceof Error ? err.message : 'Script generation failed');
      }
    }
  }, [pollJobStatus]);

  const selectJob = useCallback((jobId: string) => {
    // This function can be used to highlight or focus on a specific job
    // For now, we'll just scroll to it or highlight it in the UI
    console.log('Selected job:', jobId);
  }, []);

  const clearJob = useCallback((jobId: string) => {
    // Stop polling for this job
    const interval = pollingIntervalsRef.current.get(jobId);
    if (interval) {
      clearInterval(interval);
      pollingIntervalsRef.current.delete(jobId);
    }

    // Remove job from queue
    setJobs(prevJobs => {
      const updatedJobs = prevJobs.filter(job => job.jobId !== jobId);
      // Update generating status
      const hasProcessing = updatedJobs.some(job => job.status.status === 'processing');
      setGenerating(hasProcessing);
      return updatedJobs;
    });
  }, []);

  const clearAllJobs = useCallback(() => {
    // Stop all polling intervals
    pollingIntervalsRef.current.forEach(interval => clearInterval(interval));
    pollingIntervalsRef.current.clear();

    // Clear all jobs
    setJobs([]);
    setGenerating(false);
    setError(null);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const refreshJobs = useCallback(async () => {
    console.log('[RefreshJobs] Manual refresh triggered');
    try {
      const userJobsResponse = await apiService.getUserJobs();
      const backendJobs = userJobsResponse.jobs || [];
      
      // Convert backend jobs to frontend format (same logic as initial load)
      const convertedJobs: JobQueueItem[] = backendJobs.map(job => {
        let parsedRequestData = {};
        if (job.request_data) {
          if (typeof job.request_data === 'string') {
            try {
              parsedRequestData = JSON.parse(job.request_data);
            } catch (e) {
              console.error('[RefreshJobs] Failed to parse request_data string:', e);
              parsedRequestData = {};
            }
          } else if (typeof job.request_data === 'object') {
            parsedRequestData = job.request_data;
          }
        }
        
        let parsedResult = job.result;
        if (typeof parsedResult === 'string' && parsedResult.trim()) {
          try {
            parsedResult = JSON.parse(parsedResult);
          } catch (e) {
            console.error('[RefreshJobs] Failed to parse result JSON:', e);
            parsedResult = null;
          }
        }
        
        let groundTruthResult = undefined;
        if (job.status === 'completed' && parsedResult && parsedResult.content) {
          groundTruthResult = {
            success: true,
            script_id: job.job_id,
            content: parsedResult.content || '',
            word_count: parsedResult.word_count || 0,
            storage_path: job.result_path,
            metadata: parsedResult.metadata || {},
            message: 'Ground truth generation completed'
          };
        }

        return {
          jobId: job.job_id,
          status: {
            job_id: job.job_id,
            status: job.status,
            updated_at: job.updated_at,
            error: job.error_message,
            result: groundTruthResult
          },
          request: parsedRequestData,
          result: groundTruthResult,
          error: job.error_message,
          script_title: job.script_title,
          createdAt: job.created_at || job.updated_at
        };
      });

      setJobs(convertedJobs);
      console.log(`[RefreshJobs] Successfully refreshed ${convertedJobs.length} jobs`);
    } catch (err) {
      console.warn('[RefreshJobs] Failed to refresh jobs:', err);
      // Don't show error to user for manual refresh failures - just log
    }
  }, []);

  // Additional cleanup on unmount
  useEffect(() => {
    return () => {
      pollingIntervalsRef.current.forEach(interval => clearInterval(interval));
      pollingIntervalsRef.current.clear();
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, []);

  return {
    generating,
    loadingVerticals,
    jobs,
    availableVerticals,
    error,
    generateScript,
    selectJob,
    clearJob,
    clearAllJobs,
    clearError,
    refreshJobs,
  };
};