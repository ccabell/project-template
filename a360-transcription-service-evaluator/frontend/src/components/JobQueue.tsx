
/**
 * Job queue component for displaying generation job statuses in horizontal layout.
 */

import React, { useState, useMemo, useEffect } from 'react';
import { GroundTruthGenerationRequest, GroundTruthJobStatus } from '../types/api';

interface JobQueueItem {
  jobId: string;
  status: GroundTruthJobStatus;
  request: GroundTruthGenerationRequest;
  result?: any;
  error?: string;
  createdAt: string;
  script_title?: string;
}

interface JobQueueProps {
  jobs: JobQueueItem[];
  onSelectJob: (jobId: string) => void;
  onClearJob: (jobId: string) => void;
  onClearAll: () => void;
  onDownloadResult: (job: JobQueueItem) => void;
  onRefresh?: () => void;
}

interface JobFilters {
  status: string[];
  vertical: string[];
  encounterType: string[];
  language: string[];
  difficulty: string[];
}

export const JobQueue: React.FC<JobQueueProps> = ({
  jobs,
  onSelectJob,
  onClearJob,
  onClearAll,
  onDownloadResult,
  onRefresh
}) => {
  const [filters, setFilters] = useState<JobFilters>({
    status: ['queued', 'processing', 'completed', 'failed'],
    vertical: [],
    encounterType: [],
    language: [],
    difficulty: []
  });

  const [currentPage, setCurrentPage] = useState(0);
  const [showAllJobs, setShowAllJobs] = useState(false);
  const [forceUpdate, setForceUpdate] = useState(0);
  
  // Fixed jobs per page
  const JOBS_PER_PAGE = 4;

  // Calculate base displayable jobs (jobs that can actually be shown)
  const displayableJobs = useMemo(() => {
    return jobs.filter(job => {
      // A job is displayable if it has the minimum required properties
      return job.status && job.status.status && job.request && job.jobId && job.createdAt;
    });
  }, [jobs]);

  // Get all unique options for each filter category (memoized)
  const filterOptions = useMemo(() => {
    const uniqueVerticals = Array.from(new Set(displayableJobs.map(job => job.request.medical_vertical).filter((v): v is string => Boolean(v)))).sort();
    const uniqueEncounterTypes = Array.from(new Set(displayableJobs.map(job => job.request.encounter_type).filter((v): v is string => Boolean(v)))).sort();
    const uniqueLanguages = Array.from(new Set(displayableJobs.map(job => job.request.language).filter((v): v is string => Boolean(v)))).sort();
    const uniqueDifficulties = Array.from(new Set(displayableJobs.map(job => job.request.difficulty_level).filter((v): v is string => Boolean(v)))).sort();
    
    return {
      verticals: uniqueVerticals,
      encounterTypes: uniqueEncounterTypes,
      languages: uniqueLanguages,
      difficulties: uniqueDifficulties
    };
  }, [displayableJobs]);

  // Force re-render when job results change to update terms display and View Script buttons
  useEffect(() => {
    const completedJobsWithResults = jobs.filter(job => 
      job.status.status === 'completed' && job.result
    ).length;
    
    console.log('[JobQueue DEBUG] Force update check - completed jobs with results:', completedJobsWithResults);
    console.log('[JobQueue DEBUG] Jobs data:', jobs.map(j => ({
      id: j.jobId, 
      status: j.status.status, 
      hasResult: !!j.result,
      hasMetadata: !!(j.result?.metadata)
    })));
    
    setForceUpdate(prev => prev + 1);
  }, [jobs.map(job => `${job.jobId}-${job.status.status}-${!!job.result}-${job.status.updated_at}`).join(',')]);

  // Initialize filters with all available options
  React.useEffect(() => {
    if (jobs.length > 0) {
      setFilters(prev => ({
        status: prev.status.length === 0 ? ['queued', 'processing', 'completed', 'failed'] : prev.status,
        vertical: prev.vertical.length === 0 ? [] : prev.vertical.filter(v => filterOptions.verticals.includes(v)),
        encounterType: prev.encounterType.length === 0 ? [] : prev.encounterType.filter(v => filterOptions.encounterTypes.includes(v)),
        language: prev.language.length === 0 ? [] : prev.language.filter(v => filterOptions.languages.includes(v)),
        difficulty: prev.difficulty.length === 0 ? [] : prev.difficulty.filter(v => filterOptions.difficulties.includes(v))
      }));
    }
  }, [jobs.length, filterOptions.verticals, filterOptions.encounterTypes, filterOptions.languages, filterOptions.difficulties]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'queued':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'processing':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'queued':
        return <div className="w-3 h-3 text-blue-600">🕐</div>;
      case 'processing':
        return <div className="w-3 h-3 animate-spin">⚙️</div>;
      case 'completed':
        return <div className="w-3 h-3 text-green-600">✅</div>;
      case 'failed':
        return <div className="w-3 h-3 text-red-600">❌</div>;
      default:
        return <div className="w-3 h-3">🔄</div>;
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  };

  const getWordCount = (request: GroundTruthGenerationRequest) => {
    console.log('[JobQueue DEBUG] getWordCount - request:', request);
    console.log('[JobQueue DEBUG] target_word_count:', request.target_word_count);
    return request.target_word_count || null;
  };

  const getVertical = (request: GroundTruthGenerationRequest) => {
    console.log('[JobQueue DEBUG] getVertical - request:', request);
    console.log('[JobQueue DEBUG] medical_vertical:', request.medical_vertical);
    return request.medical_vertical 
      ? request.medical_vertical.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())
      : null;
  };

  const getEncounterType = (request: GroundTruthGenerationRequest) => {
    return request.encounter_type
      ? request.encounter_type.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())
      : null;
  };

  const getLanguage = (request: GroundTruthGenerationRequest) => {
    return request.language
      ? request.language.replace(/\b\w/g, (l: string) => l.toUpperCase())
      : null;
  };

  const getDifficulty = (request: GroundTruthGenerationRequest) => {
    return request.difficulty_level
      ? request.difficulty_level.replace(/\b\w/g, (l: string) => l.toUpperCase())
      : null;
  };


  // Filter and sort jobs (newest first) - memoized for performance
  const filteredJobs = useMemo(() => {
    return displayableJobs
      .filter(job => {
        // Status filter (OR within category)
        if (filters.status.length > 0 && !filters.status.includes(job.status.status)) return false;
        
        // Vertical filter (OR within category) - include jobs without medical_vertical
        if (filters.vertical.length > 0) {
          const jobVertical = job.request.medical_vertical || '';
          if (jobVertical && !filters.vertical.includes(jobVertical)) return false;
        }
        
        // Encounter Type filter (OR within category) - include jobs without encounter_type
        if (filters.encounterType.length > 0) {
          const jobEncounterType = job.request.encounter_type || '';
          if (jobEncounterType && !filters.encounterType.includes(jobEncounterType)) return false;
        }
        
        // Language filter (OR within category) - include jobs without language
        if (filters.language.length > 0) {
          const jobLanguage = job.request.language || '';
          if (jobLanguage && !filters.language.includes(jobLanguage)) return false;
        }
        
        // Difficulty filter (OR within category) - include jobs without difficulty_level
        if (filters.difficulty.length > 0) {
          const jobDifficulty = job.request.difficulty_level || '';
          if (jobDifficulty && !filters.difficulty.includes(jobDifficulty)) return false;
        }
        
        return true;
      })
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()); // Newest first
  }, [displayableJobs, filters]);

  // Pagination calculations
  const totalPages = Math.ceil(filteredJobs.length / JOBS_PER_PAGE);
  const startIndex = showAllJobs ? 0 : currentPage * JOBS_PER_PAGE;
  const endIndex = showAllJobs ? filteredJobs.length : startIndex + JOBS_PER_PAGE;
  const currentJobs = filteredJobs.slice(startIndex, endIndex);
  const itemsPerPage = showAllJobs ? filteredJobs.length : Math.min(JOBS_PER_PAGE, filteredJobs.length - startIndex);

  // Reset to first page if current page is out of bounds
  React.useEffect(() => {
    if (currentPage >= totalPages && totalPages > 0) {
      setCurrentPage(0);
    }
  }, [currentPage, totalPages]);

  const updateFilter = (key: keyof JobFilters, value: string) => {
    setFilters(prev => ({
      ...prev,
      [key]: prev[key].includes(value)
        ? prev[key].filter(v => v !== value)
        : [...prev[key], value]
    }));
    setCurrentPage(0); // Reset to first page when filters change
    setShowAllJobs(false); // Reset show all when filters change
  };

  const clearAllFilters = () => {
    setFilters({
      status: ['queued', 'processing', 'completed', 'failed'],
      vertical: filterOptions.verticals,
      encounterType: filterOptions.encounterTypes,
      language: filterOptions.languages,
      difficulty: filterOptions.difficulties
    });
    setCurrentPage(0);
    setShowAllJobs(false);
  };

  const goToPreviousPage = () => {
    setCurrentPage(prev => Math.max(0, prev - 1));
    setShowAllJobs(false);
  };

  const goToNextPage = () => {
    setCurrentPage(prev => Math.min(totalPages - 1, prev + 1));
    setShowAllJobs(false);
  };

  const toggleShowAll = () => {
    setShowAllJobs(!showAllJobs);
    setCurrentPage(0);
  };

  return (
    <div className="h-full bg-gray-50 p-4 flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-600">
            Showing {currentJobs.length} of {filteredJobs.length} filtered ({displayableJobs.length} total)
          </span>
          {filteredJobs.length > JOBS_PER_PAGE && (
            <>
              <button
                onClick={toggleShowAll}
                className="text-sm text-blue-600 hover:text-blue-800 underline font-medium"
              >
                {showAllJobs ? `Show Pages (${JOBS_PER_PAGE} per page)` : `Show All ${filteredJobs.length}`}
              </button>
              {!showAllJobs && totalPages > 1 && (
                <div className="flex items-center space-x-2">
                  <button
                    onClick={goToPreviousPage}
                    disabled={currentPage === 0}
                    className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-gray-400"
                  >
                    ←
                  </button>
                  <span className="text-xs text-gray-500">
                    {currentPage + 1}/{totalPages}
                  </span>
                  <button
                    onClick={goToNextPage}
                    disabled={currentPage >= totalPages - 1}
                    className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-gray-400"
                  >
                    →
                  </button>
                </div>
              )}
            </>
          )}
          <div className="flex items-center space-x-3">
            {onRefresh && (
              <button
                onClick={onRefresh}
                className="text-sm bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                Refresh
              </button>
            )}
            {jobs.length > 0 && (
              <button
                onClick={onClearAll}
                className="text-sm text-red-600 hover:text-red-800 underline"
              >
                Clear All
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-4 flex-shrink-0">
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-medium text-gray-700">
            Filters
          </label>
          <button
            onClick={clearAllFilters}
            className="text-xs text-blue-600 hover:text-blue-800 underline"
          >
            Select All
          </button>
        </div>

        <div className="grid grid-cols-5 gap-4">
          {/* Status Filter */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Status</label>
            <div className="space-y-1">
              {['queued', 'processing', 'completed', 'failed'].map(status => {
                const isSelected = filters.status.includes(status);
                
                return (
                  <label key={status} className="flex items-center space-x-1 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => updateFilter('status', status)}
                      className="w-3 h-3 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <span className="text-xs text-gray-700">
                      {status.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Vertical Filter */}
          {filterOptions.verticals.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Vertical</label>
              <div className="space-y-1">
                {filterOptions.verticals.map(vertical => {
                  const isSelected = filters.vertical.includes(vertical);
                  
                  return (
                    <label key={vertical} className="flex items-center space-x-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => updateFilter('vertical', vertical)}
                        className="w-3 h-3 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <span className="text-xs text-gray-700">
                        {vertical.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Encounter Type Filter */}
          {filterOptions.encounterTypes.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Type</label>
              <div className="space-y-1">
                {filterOptions.encounterTypes.map(type => {
                  const isSelected = filters.encounterType.includes(type);
                  
                  return (
                    <label key={type} className="flex items-center space-x-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => updateFilter('encounterType', type)}
                        className="w-3 h-3 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <span className="text-xs text-gray-700">
                        {type.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Language Filter */}
          {filterOptions.languages.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Language</label>
              <div className="space-y-1">
                {filterOptions.languages.map(language => {
                  const isSelected = filters.language.includes(language);
                  
                  return (
                    <label key={language} className="flex items-center space-x-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => updateFilter('language', language)}
                        className="w-3 h-3 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <span className="text-xs text-gray-700">
                        {language.replace(/\b\w/g, (l: string) => l.toUpperCase())}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* Difficulty Filter */}
          {filterOptions.difficulties.length > 0 && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Difficulty</label>
              <div className="space-y-1">
                {filterOptions.difficulties.map(difficulty => {
                  const isSelected = filters.difficulty.includes(difficulty);
                  
                  return (
                    <label key={difficulty} className="flex items-center space-x-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => updateFilter('difficulty', difficulty)}
                        className="w-3 h-3 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <span className="text-xs text-gray-700">
                        {difficulty.replace(/\b\w/g, (l: string) => l.toUpperCase())}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Job Cards with Navigation */}
      <div className="flex-1 flex flex-col min-h-0">
        {filteredJobs.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-500">
              {jobs.length === 0 ? (
                <>
                  <div className="text-4xl mb-2">📝</div>
                  <p>No jobs in queue</p>
                  <p className="text-sm mt-1">Start generating scripts to see them here</p>
                </>
              ) : (
                <>
                  <div className="text-4xl mb-2">🔍</div>
                  <p>No jobs match current filters</p>
                  <p className="text-sm mt-1">Try adjusting your filter selections</p>
                </>
              )}
            </div>
          </div>
        ) : (
          <>
            {/* Navigation Header */}
            {!showAllJobs && totalPages > 1 && (
              <div className="flex items-center justify-between mb-3 flex-shrink-0 bg-white p-3 rounded-lg border">
                <button
                  onClick={goToPreviousPage}
                  disabled={currentPage === 0}
                  className="flex items-center space-x-2 px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-gray-400"
                >
                  <span>←</span>
                  <span>Previous</span>
                </button>
                
                <div className="flex items-center space-x-4">
                  <span className="text-sm text-gray-600 font-medium">
                    Page {currentPage + 1} of {totalPages}
                  </span>
                  <span className="text-xs text-gray-500">
                    Showing {itemsPerPage} of {filteredJobs.length} jobs
                  </span>
                </div>
                
                <button
                  onClick={goToNextPage}
                  disabled={currentPage >= totalPages - 1}
                  className="flex items-center space-x-2 px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-gray-400"
                >
                  <span>Next</span>
                  <span>→</span>
                </button>
              </div>
            )}

            {showAllJobs && filteredJobs.length > JOBS_PER_PAGE && (
              <div className="mb-3 text-center flex-shrink-0 bg-white p-3 rounded-lg border">
                <span className="text-sm text-gray-600 font-medium">
                  Showing all {filteredJobs.length} jobs (normally paginated at {JOBS_PER_PAGE} per page)
                </span>
              </div>
            )}


            {/* Job Cards - Full Width Grid Layout */}
            <div className="flex-1 overflow-y-auto min-h-0 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100 pr-2">
              <div className="space-y-4 pb-4">
                {(showAllJobs ? filteredJobs : currentJobs).map((job) => (
                  <div
                    key={job.jobId}
                    className={`bg-white rounded-lg border p-4 cursor-pointer transition-all hover:shadow-md ${getStatusColor(job.status.status)} flex flex-col h-auto`}
                    onClick={() => {
                      console.log('[JobQueue DEBUG] Job card clicked:', job.jobId);
                      console.log('[JobQueue DEBUG] onSelectJob function:', onSelectJob);
                      onSelectJob(job.jobId);
                    }}
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center space-x-2">
                        {getStatusIcon(job.status.status)}
                        <span className="text-sm font-medium capitalize">
                          {job.status.status}
                        </span>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onClearJob(job.jobId);
                        }}
                        className="text-gray-400 hover:text-gray-600 flex-shrink-0"
                      >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                      </button>
                    </div>

                    {/* Script Title - Remove redundant prefix */}
                    <div className="border-b border-gray-100 pb-2 mb-3">
                      <div className="text-sm flex flex-wrap items-start">
                        <span className="font-medium text-gray-700">Script:</span> 
                        <span className="ml-2 text-gray-600 break-words flex-1 min-w-0">
                          {(() => {
                            // Debug logging to trace script_title issue
                            console.log('[JobQueue DEBUG] Job data:', {
                              jobId: job.jobId,
                              script_title: job.script_title,
                              hasScriptTitle: job.script_title !== undefined,
                              scriptTitleType: typeof job.script_title,
                              fullJob: job
                            });
                            
                            // Try script_title from job first (stored separately in backend)
                            let title = job.script_title;
                            
                            // If no script_title, try parsing from result
                            if (!title && job.result) {
                              let result = job.result;
                              // Parse result if it's a string
                              if (typeof result === 'string') {
                                try {
                                  result = JSON.parse(result);
                                } catch (e) {
                                  console.warn('[JobQueue] Failed to parse result JSON:', e);
                                }
                              }
                              title = result && result.script_title;
                            }
                            
                            // Show error message for missing title instead of fallback
                            if (!title) {
                              return (
                                <span className="text-red-600 italic">
                                  Script title unavailable
                                </span>
                              );
                            }
                            
                            // Display full title without truncation
                            return title;
                          })()}
                        </span>
                      </div>
                    </div>

                    {/* Details */}
                    <div className="text-sm space-y-2 flex-1">
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <span className="font-medium text-gray-700">Words:</span> 
                          <div className="text-gray-600">
                            {(() => {
                              // Show actual word count if completed, otherwise show requested
                              if (job.status.status === 'completed' && job.result) {
                                let result = job.result;
                                if (typeof result === 'string') {
                                  try {
                                    result = JSON.parse(result);
                                  } catch (e) {
                                    console.warn('[JobQueue] Failed to parse result JSON for word count:', e);
                                    result = null;
                                  }
                                }
                                const actualWordCount = result?.word_count;
                                if (actualWordCount && typeof actualWordCount === 'number') {
                                  return actualWordCount.toLocaleString();
                                }
                              }
                              const wordCount = getWordCount(job.request);
                              return wordCount ? wordCount.toLocaleString() : (
                                <span className="text-red-600 italic text-xs">Not specified</span>
                              );
                            })()}
                          </div>
                        </div>
                        {getLanguage(job.request) && (
                          <div>
                            <span className="font-medium text-gray-700">Language:</span> 
                            <div className="text-gray-600">{getLanguage(job.request)}</div>
                          </div>
                        )}
                        {getVertical(job.request) && (
                          <div>
                            <span className="font-medium text-gray-700">Vertical:</span> 
                            <div className="text-gray-600 text-xs">{getVertical(job.request)}</div>
                          </div>
                        )}
                        {getDifficulty(job.request) && (
                          <div>
                            <span className="font-medium text-gray-700">Difficulty:</span> 
                            <div className="text-gray-600">{getDifficulty(job.request)}</div>
                          </div>
                        )}
                      </div>
                      
                      {getEncounterType(job.request) && (
                        <div>
                          <span className="font-medium text-gray-700">Type:</span> 
                          <div className="text-gray-600 text-sm">{getEncounterType(job.request)}</div>
                        </div>
                      )}
                      
                      {/* Terms Used Section - Show for completed jobs */}
                      {job.status.status === 'completed' && (() => {
                        let result = job.result;
                        // Parse result if it's a string
                        if (typeof result === 'string') {
                          try {
                            result = JSON.parse(result);
                          } catch (e) {
                            console.warn('[JobQueue] Failed to parse result JSON for terms:', e);
                            result = null;
                          }
                        }
                        
                        const seedTerms = result?.metadata?.seed_terms_used || [];
                        const brandNames = result?.metadata?.brand_names_used || [];
                        
                        console.log('[JobQueue DEBUG] Terms parsing - result:', result);
                        console.log('[JobQueue DEBUG] seedTerms:', seedTerms);
                        console.log('[JobQueue DEBUG] brandNames:', brandNames);
                        
                        return (seedTerms.length > 0 || brandNames.length > 0) && (
                          <div className="border-t border-gray-100 pt-2 mt-2">
                            <span className="font-medium text-gray-700">Terms Used:</span>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {seedTerms.map((term: string, index: number) => (
                                <span
                                  key={index}
                                  className="inline-block px-2 py-1 text-xs bg-green-100 text-green-800 rounded border border-green-200"
                                  title={term}
                                >
                                  {term}
                                </span>
                              ))}
                              {brandNames.map((brand: string, index: number) => (
                                <span
                                  key={`brand-${index}`}
                                  className="inline-block px-2 py-1 text-xs bg-purple-100 text-purple-800 rounded border border-purple-200"
                                  title={brand}
                                >
                                  {brand}
                                </span>
                              ))}
                            </div>
                          </div>
                        );
                      })()}
                      
                      <div className="border-t border-gray-100 pt-2 text-sm">
                        <span className="font-medium text-gray-700">Created:</span> 
                        <div className="text-gray-600">{formatTime(job.createdAt)}</div>
                      </div>
                      
                      {/* Only show completion timestamp for finished jobs */}
                      {job.status.status === 'completed' && job.status.updated_at && (
                        <div className="text-sm">
                          <span className="font-medium text-green-700">Completed:</span> 
                          <div className="text-green-600">{formatTime(job.status.updated_at)}</div>
                        </div>
                      )}
                      {job.status.status === 'failed' && job.status.updated_at && (
                        <div className="text-sm">
                          <span className="font-medium text-red-700">Failed:</span> 
                          <div className="text-red-600">{formatTime(job.status.updated_at)}</div>
                        </div>
                      )}
                    </div>

                    {/* Status/Action Section */}
                    <div className="mt-4 pt-3 border-t border-gray-100">
                      {job.error && (
                        <div className="text-sm text-red-700 bg-red-50 p-3 rounded border border-red-200 mb-3">
                          <span className="font-medium">Error:</span> 
                          <div className="mt-1 text-sm break-words">{job.error}</div>
                        </div>
                      )}

                      {(job.result || job.status.status === 'completed') && (
                        <div className="bg-green-50 p-3 rounded border border-green-200">
                          <div className="text-sm text-green-700 mb-3">
                            <span className="font-medium">Generated:</span> {job.result?.word_count || 'Available'}
                            {job.result?.word_count && ' words'}
                          </div>
                          <div className="space-y-2">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onSelectJob(job.jobId);
                              }}
                              className="w-full text-sm bg-blue-600 text-white py-2 px-3 rounded hover:bg-blue-700 transition-colors font-medium"
                            >
                              View Script
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onDownloadResult(job);
                              }}
                              className="w-full text-sm bg-green-600 text-white py-2 px-3 rounded hover:bg-green-700 transition-colors font-medium"
                            >
                              Download Script
                            </button>
                          </div>
                        </div>
                      )}

                      {job.status.status === 'processing' && !job.result && (
                        <div className="bg-yellow-50 p-3 rounded border border-yellow-200">
                          <div className="text-sm text-yellow-700 mb-2">
                            <span className="font-medium">Processing...</span>
                          </div>
                          <div className="w-full bg-yellow-200 rounded-full h-2">
                            <div className="bg-yellow-600 h-2 rounded-full animate-pulse" style={{ width: '60%' }}></div>
                          </div>
                        </div>
                      )}

                      {job.status.status === 'queued' && !job.result && (
                        <div className="bg-blue-50 p-3 rounded border border-blue-200">
                          <div className="text-sm text-blue-700 mb-2">
                            <span className="font-medium">In Queue</span>
                          </div>
                          <div className="w-full bg-blue-200 rounded-full h-2">
                            <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: '30%' }}></div>
                          </div>
                        </div>
                      )}

                      {job.status.status === 'failed' && !job.error && (
                        <div className="bg-red-50 p-3 rounded border border-red-200">
                          <div className="text-sm text-red-700 text-center">
                            <span className="font-medium">Failed</span>
                          </div>
                        </div>
                      )}

                      {job.status.status === 'completed' && !job.result && (
                        <div className="bg-green-50 p-3 rounded border border-green-200">
                          <div className="text-sm text-green-700 text-center">
                            <span className="font-medium">Completed</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}; 