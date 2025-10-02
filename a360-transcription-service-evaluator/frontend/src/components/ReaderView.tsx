/**
 * ReaderView component for voice actors to view assigned transcripts and record them.
 */

import React, { useState, useEffect } from 'react';
import { Assignment } from '../types/api';
import { apiService } from '../services/api';

interface ReaderViewProps {
  userGroups: string[];
}

interface RecordingState {
  isRecording: boolean;
  isPaused: boolean;
  duration: number;
  audioBlob?: Blob;
}

interface TermData {
  term: string;
  pronunciation: string;
  difficulty: string;
}

interface BrandData {
  name: string;
  pronunciation: string;
  difficulty: string;
}

export const ReaderView: React.FC<ReaderViewProps> = ({ userGroups }) => {
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [selectedAssignment, setSelectedAssignment] = useState<Assignment | null>(null);
  const [jobDetail, setJobDetail] = useState<any>(null);
  const [loadingJobDetail, setLoadingJobDetail] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recordingState, setRecordingState] = useState<RecordingState>({
    isRecording: false,
    isPaused: false,
    duration: 0,
  });
  const [showRestartConfirm, setShowRestartConfirm] = useState(false);
  const [allTerms, setAllTerms] = useState<TermData[]>([]);
  const [allBrands, setAllBrands] = useState<BrandData[]>([]);

  useEffect(() => {
    loadAssignments();
    loadTermsAndBrands();
  }, []);

  const loadTermsAndBrands = async () => {
    try {
      // Load all terms and brands for highlighting and pronunciation guide
      const [termsResponse, brandsResponse] = await Promise.all([
        apiService.getTerms(),
        apiService.getBrands()
      ]);
      
      // Handle API response structure (terms/brands may be in a terms/brands array)
      const termsArray = Array.isArray(termsResponse) ? termsResponse : termsResponse.terms || [];
      const brandsArray = Array.isArray(brandsResponse) ? brandsResponse : brandsResponse.brands || [];
      
      const terms: TermData[] = termsArray.map((term: any) => ({
        term: term.name,
        pronunciation: term.pronunciation || '',
        difficulty: term.difficulty || 'intermediate'
      }));
      
      const brands: BrandData[] = brandsArray.map((brand: any) => ({
        name: brand.name,
        pronunciation: brand.pronunciation || '',
        difficulty: brand.difficulty || 'intermediate'
      }));
      
      setAllTerms(terms);
      setAllBrands(brands);
    } catch (err) {
      console.error('Failed to load terms and brands:', err);
    }
  };

  // Timer effect for recording duration
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    
    if (recordingState.isRecording && !recordingState.isPaused) {
      interval = setInterval(() => {
        setRecordingState(prev => ({
          ...prev,
          duration: prev.duration + 1
        }));
      }, 1000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [recordingState.isRecording, recordingState.isPaused]);

  const loadAssignments = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiService.getMyAssignments();
      setAssignments(data);
      
      // Auto-select the first assigned assignment if available
      const assignedAssignment = data.find(a => a.status === 'assigned');
      if (assignedAssignment && !selectedAssignment) {
        setSelectedAssignment(assignedAssignment);
        loadJobDetail(assignedAssignment.job_id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load assignments');
    } finally {
      setLoading(false);
    }
  };

  const getPronunciationGuideItems = () => {
    const pronunciationItems: Array<{name: string, pronunciation: string, type: 'term' | 'brand'}> = [];
    
    // The jobDetail might have the data embedded differently 
    console.log('[ReaderView DEBUG] Full jobDetail structure:', jobDetail);
    
    // Process medical terms from terms_used array
    const scriptTerms = jobDetail?.terms_used || [];
    scriptTerms.forEach((item: any) => {
      if ((item.difficulty === 'hard' || item.difficulty === 'intermediate') && item.pronunciation) {
        const itemName = item.term || item.name;
        if (itemName) {
          pronunciationItems.push({
            name: itemName,
            pronunciation: item.pronunciation,
            type: 'term'
          });
        }
      }
    });
    
    // Process brands from brands_used array (NEW - this was missing!)
    const scriptBrands = jobDetail?.brands_used || [];
    scriptBrands.forEach((item: any) => {
      if ((item.difficulty === 'hard' || item.difficulty === 'intermediate') && item.pronunciation) {
        const itemName = item.term || item.name;
        if (itemName) {
          pronunciationItems.push({
            name: itemName,
            pronunciation: item.pronunciation,
            type: 'brand'
          });
        }
      }
    });
    
    console.log('[ReaderView DEBUG] pronunciationItems after processing both arrays:', pronunciationItems);
    console.log('[ReaderView DEBUG] Terms found:', scriptTerms.length);
    console.log('[ReaderView DEBUG] Brands found:', scriptBrands.length);
    
    return pronunciationItems.sort((a, b) => a.name.localeCompare(b.name));
  };

  const highlightScriptText = (text: string) => {
    if (!text) return text;
    
    let highlightedText = text;
    const allItems = [...allTerms.map(t => ({ name: t.term, ...t })), ...allBrands];
    
    // Sort by length (longest first) to avoid partial matches
    const sortedItems = allItems.sort((a, b) => b.name.length - a.name.length);
    
    sortedItems.forEach(item => {
      if (item.name && item.pronunciation) {
        const regex = new RegExp(`\\b${item.name}\\b`, 'gi');
        const difficultyClass = item.difficulty === 'hard' ? 'bg-red-100 border-red-400' :
                              item.difficulty === 'intermediate' ? 'bg-yellow-100 border-yellow-400' :
                              'bg-blue-100 border-blue-400';
        
        highlightedText = highlightedText.replace(regex, (match) => {
          return `<span class="difficult-term ${difficultyClass} px-1 py-0.5 rounded-sm border-b-2 relative font-medium cursor-help" data-pronunciation="${item.pronunciation}">${match}</span>`;
        });
      }
    });
    
    return highlightedText;
  };

  const loadJobDetail = async (jobId: string) => {
    try {
      setLoadingJobDetail(true);
      const detail = await apiService.getJobDetail(jobId);
      setJobDetail(detail);
    } catch (err: any) {
      console.error('Failed to load job details:', err);
      setJobDetail(null);
    } finally {
      setLoadingJobDetail(false);
    }
  };

  const updateAssignmentStatus = async (assignmentId: string, status: string, notes?: string) => {
    try {
      await apiService.updateAssignmentStatus(assignmentId, status, notes);
      
      // Refresh assignments after update
      await loadAssignments();
      
      // If this was the selected assignment, update it
      if (selectedAssignment?.assignment_id === assignmentId) {
        const updatedAssignment = assignments.find(a => a.assignment_id === assignmentId);
        if (updatedAssignment) {
          setSelectedAssignment({ ...updatedAssignment, status: status as any });
        }
      }
    } catch (err: any) {
      setError(`Failed to update assignment: ${err.message}`);
    }
  };

  const handleStartRecording = () => {
    // Only control recording interface - no status change
    setRecordingState(prev => ({
      ...prev,
      isRecording: true,
      isPaused: false,
      duration: 0,
    }));
  };

  const handlePauseRecording = () => {
    setRecordingState(prev => ({
      ...prev,
      isPaused: !prev.isPaused,
    }));
  };

  const handleStopRecording = () => {
    // Stop recording and create audio blob (simulated)
    setRecordingState(prev => ({
      ...prev,
      isRecording: false,
      isPaused: false,
      audioBlob: new Blob(['audio-data-placeholder'], { type: 'audio/wav' }) // Placeholder - in real implementation, this would be the actual recording
    }));
  };

  const handleRestartRecording = () => {
    setShowRestartConfirm(true);
  };

  const confirmRestartRecording = () => {
    setRecordingState({
      isRecording: false,
      isPaused: false,
      duration: 0,
      audioBlob: undefined
    });
    setShowRestartConfirm(false);
  };

  const cancelRestartRecording = () => {
    setShowRestartConfirm(false);
  };

  const getAssignmentStatusColor = (status: string) => {
    switch (status) {
      case 'assigned':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'in_progress':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'audio_submitted':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200';
      default:
        return 'bg-gray-100 text-gray-500 border-gray-200';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };


  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading your assignments...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-md p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Error loading assignments</h3>
            <p className="mt-1 text-sm text-red-700">{error}</p>
            <button
              onClick={loadAssignments}
              className="mt-2 bg-red-100 hover:bg-red-200 text-red-800 px-3 py-1 rounded text-sm"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex bg-gray-50">
      {/* Assignments Sidebar */}
      <div className="w-1/3 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">My Assignments</h2>
          <p className="text-sm text-gray-600 mt-1">{assignments.length} scripts assigned</p>
        </div>
        
        <div className="flex-1 overflow-y-auto">
          {assignments.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              <div className="text-4xl mb-2">📝</div>
              <p>No assignments yet</p>
              <p className="text-sm mt-1">Check back later for new scripts to record</p>
            </div>
          ) : (
            <div className="space-y-2 p-4">
              {assignments.map((assignment) => (
                <div
                  key={assignment.assignment_id}
                  onClick={() => {
                    setSelectedAssignment(assignment);
                    loadJobDetail(assignment.job_id);
                  }}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedAssignment?.assignment_id === assignment.assignment_id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-medium text-gray-900 text-sm pr-2 flex-1 break-words">
                      {assignment.script_title || `Script ${String(assignment.script_id || assignment.job_id || 'unknown').slice(0, 8)}...`}
                    </h3>
                    <span className={`px-2 py-1 text-xs rounded-full border ${getAssignmentStatusColor(assignment.status)}`}>
                      {assignment.status.replace('_', ' ')}
                    </span>
                  </div>
                  
                  <div className="text-xs text-gray-600 space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium">Priority:</span> 
                      <span className={`px-1.5 py-0.5 text-xs rounded ${
                        assignment.priority === 3 ? 'bg-red-100 text-red-800 font-medium' :
                        assignment.priority === 2 ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {assignment.priority === 3 ? 'High' :
                         assignment.priority === 2 ? 'Medium' : 'Low'}
                      </span>
                    </div>
                    {assignment.word_count && (
                      <div>
                        <span className="font-medium">Word Count:</span> {assignment.word_count.toLocaleString()}
                      </div>
                    )}
                    {assignment.due_date && (
                      <div>
                        <span className="font-medium">Due:</span> {formatDate(assignment.due_date)}
                      </div>
                    )}
                    <div>
                      <span className="font-medium">Assigned:</span> {formatDate(assignment.created_at)}
                    </div>
                  </div>
                  
                  {/* Blocking indicator */}
                  {assignment.blocked && (
                    <div className="mt-2 p-2 bg-orange-50 border border-orange-200 rounded text-xs text-orange-800">
                      <div className="flex items-center space-x-1">
                        <span className="font-medium">🚫 Blocked:</span>
                      </div>
                      <div className="mt-1">{assignment.blocked_reason}</div>
                    </div>
                  )}
                  
                  {assignment.notes && (
                    <div className="mt-2 text-xs text-gray-700 bg-gray-100 p-2 rounded">
                      {assignment.notes}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col">
        {selectedAssignment ? (
          <>
            {/* Assignment Header */}
            <div className="bg-white border-b border-gray-200 p-6">
              <div className="flex items-start justify-between">
                <div>
                  <h1 className="text-xl font-semibold text-gray-900">
                    {selectedAssignment.script_title || `Script ${String(selectedAssignment.script_id || selectedAssignment.job_id || 'unknown')}`}
                  </h1>
                  <div className="mt-2 flex items-center space-x-4 text-sm text-gray-600">
                    <span className={`px-2 py-1 rounded-full border text-xs ${getAssignmentStatusColor(selectedAssignment.status)}`}>
                      {selectedAssignment.status.replace('_', ' ')}
                    </span>
                    <span>Priority: {selectedAssignment.priority === 3 ? 'High' : selectedAssignment.priority === 2 ? 'Medium' : 'Low'}</span>
                    {selectedAssignment.due_date && (
                      <span>Due: {formatDate(selectedAssignment.due_date)}</span>
                    )}
                  </div>
                </div>
                
              </div>
            </div>

            {/* Recording Controls */}
            <div className="bg-white border-b border-gray-200 p-6">
              <div className="mb-4">
                <h3 className="text-sm font-medium text-gray-900 mb-1">Recording Interface</h3>
                <p className="text-xs text-gray-600">
                  Use these controls to record audio. Recording controls do not change assignment status.
                </p>
              </div>
              
              {selectedAssignment.blocked && (
                <div className="mb-4 p-4 bg-orange-50 border border-orange-200 rounded-lg">
                  <div className="flex items-center space-x-2 text-orange-800">
                    <span className="text-lg">🚫</span>
                    <span className="font-medium">Assignment Blocked</span>
                  </div>
                  <p className="text-sm text-orange-700 mt-2">{selectedAssignment.blocked_reason}</p>
                  <p className="text-xs text-orange-600 mt-1">Complete higher priority assignments first to unlock this one.</p>
                </div>
              )}
              
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  {!recordingState.isRecording ? (
                    <button
                      onClick={handleStartRecording}
                      disabled={selectedAssignment.status === 'completed' || selectedAssignment.blocked}
                      className="flex items-center space-x-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white px-6 py-3 rounded-lg font-medium disabled:cursor-not-allowed"
                    >
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <circle cx="10" cy="10" r="6"/>
                      </svg>
                      <span>
                        {selectedAssignment.blocked ? 'Recording Blocked' : 'Start Recording'}
                      </span>
                    </button>
                  ) : (
                    <div className="flex space-x-2">
                      <button
                        onClick={handlePauseRecording}
                        className="flex items-center space-x-2 bg-yellow-600 hover:bg-yellow-700 text-white px-4 py-3 rounded-lg font-medium"
                      >
                        {recordingState.isPaused ? (
                          <>
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M8 5v10l7-5-7-5z"/>
                            </svg>
                            <span>Resume</span>
                          </>
                        ) : (
                          <>
                            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd"/>
                            </svg>
                            <span>Pause</span>
                          </>
                        )}
                      </button>
                      
                      <button
                        onClick={handleStopRecording}
                        className="flex items-center space-x-2 bg-gray-600 hover:bg-gray-700 text-white px-4 py-3 rounded-lg font-medium"
                      >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd"/>
                        </svg>
                        <span>Stop</span>
                      </button>
                      
                      {recordingState.duration > 0 && (
                        <button
                          onClick={handleRestartRecording}
                          className="flex items-center space-x-2 bg-orange-600 hover:bg-orange-700 text-white px-4 py-3 rounded-lg font-medium"
                        >
                          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd"/>
                          </svg>
                          <span>Restart</span>
                        </button>
                      )}
                    </div>
                  )}
                  
                  {/* Show recording status only when recording */}
                  {recordingState.isRecording && (
                    <div className="flex items-center space-x-3">
                      <div className="flex items-center space-x-2">
                        <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
                        <span className="text-sm text-gray-600">
                          {recordingState.isPaused ? 'Paused' : 'Recording'}
                        </span>
                      </div>
                      <span className="text-sm font-mono text-gray-900">
                        {formatDuration(recordingState.duration)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Finalize Recording - Only show after recording has been done */}
            {recordingState.audioBlob && !recordingState.isRecording && (
              <div className="bg-green-50 border-b border-green-200 p-6">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h3 className="text-sm font-medium text-green-900 mb-2">Recording Complete</h3>
                    <p className="text-xs text-green-700">
                      Recording finished. Click finalize when you're satisfied with the recording.
                    </p>
                  </div>
                  
                  <button
                    onClick={() => {
                      if (selectedAssignment) {
                        updateAssignmentStatus(selectedAssignment.assignment_id, 'completed', 'Recording finalized by reader');
                      }
                    }}
                    className="flex items-center space-x-2 bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg text-sm font-medium"
                  >
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                    </svg>
                    <span>Finalize Recording</span>
                  </button>
                </div>
              </div>
            )}

            {/* Script Content */}
            <div className="flex-1 p-6 overflow-y-auto">
              <div className="max-w-4xl mx-auto space-y-6">
                {loadingJobDetail ? (
                  <div className="bg-white rounded-lg border border-gray-200 p-8">
                    <div className="flex items-center justify-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                      <span className="ml-3 text-gray-600">Loading script details...</span>
                    </div>
                  </div>
                ) : jobDetail ? (
                  <>
                    {/* Pronunciation Guide Section - Show difficult terms and brands */}
                    {(() => {
                      const pronunciationItems = getPronunciationGuideItems();
                      const termsInGuide = pronunciationItems.filter(item => item.type === 'term');
                      const brandsInGuide = pronunciationItems.filter(item => item.type === 'brand');
                      
                      return pronunciationItems.length > 0 ? (
                        <div className="bg-blue-50 rounded-lg border border-blue-200 p-6">
                          <h3 className="text-lg font-semibold text-blue-900 mb-4 flex items-center">
                            <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                            </svg>
                            Pronunciation Guide
                          </h3>
                          
                          <p className="text-blue-800 mb-4 font-medium">
                            Practice these difficult medical terms and brand names before starting your recording.
                          </p>
                          
                          {termsInGuide.length > 0 && (
                            <div className="mb-6">
                              <h4 className="font-medium text-blue-900 mb-3 flex items-center">
                                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                Medical Terms ({termsInGuide.length}):
                              </h4>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {termsInGuide.map((term, index) => (
                                  <div key={`term-${index}`} className="bg-white rounded-lg border border-blue-200 p-3">
                                    <div className="font-medium text-gray-900">{term.name}</div>
                                    <div className="text-sm text-blue-700 font-mono mt-1">{term.pronunciation}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          
                          {brandsInGuide.length > 0 && (
                            <div>
                              <h4 className="font-medium text-blue-900 mb-3 flex items-center">
                                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                                  <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zM14 9a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z" />
                                </svg>
                                Brand Names ({brandsInGuide.length}):
                              </h4>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {brandsInGuide.map((brand, index) => (
                                  <div key={`brand-${index}`} className="bg-white rounded-lg border border-green-200 p-3">
                                    <div className="font-medium text-gray-900">{brand.name}</div>
                                    <div className="text-sm text-green-700 font-mono mt-1">{brand.pronunciation}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ) : null;
                    })()}

                    {/* Script Content */}
                    <div className="bg-white rounded-lg border border-gray-200 p-8">
                      <h3 className="text-lg font-medium text-gray-900 mb-4">Script Content</h3>
                      <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed">
                        {jobDetail.script_content ? (
                          <div 
                            className="whitespace-pre-wrap"
                            dangerouslySetInnerHTML={{ __html: highlightScriptText(jobDetail.script_content) }}
                          />
                        ) : (
                          <p className="italic text-gray-500 text-center py-8">
                            No script content available for this assignment.
                          </p>
                        )}
                      </div>
                      
                      {/* Metadata */}
                      <div className="mt-6 pt-6 border-t border-gray-200">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          {jobDetail.word_count && (
                            <div>
                              <span className="font-medium text-gray-600">Word Count:</span>
                              <div className="text-gray-900">{jobDetail.word_count.toLocaleString()}</div>
                            </div>
                          )}
                          {jobDetail.vertical && (
                            <div>
                              <span className="font-medium text-gray-600">Vertical:</span>
                              <div className="text-gray-900">{jobDetail.vertical}</div>
                            </div>
                          )}
                          {jobDetail.difficulty_level && (
                            <div>
                              <span className="font-medium text-gray-600">Difficulty:</span>
                              <div className="text-gray-900">Level {jobDetail.difficulty_level}</div>
                            </div>
                          )}
                          {jobDetail.metadata?.estimated_reading_time && (
                            <div>
                              <span className="font-medium text-gray-600">Reading Time:</span>
                              <div className="text-gray-900">{jobDetail.metadata.estimated_reading_time}</div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="bg-white rounded-lg border border-gray-200 p-8">
                    <p className="italic text-gray-500 text-center py-8">
                      Script content will be loaded when you select an assignment.
                      <br />
                      Choose a script from the sidebar to begin.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-gray-500">
              <div className="text-4xl mb-4">🎙️</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Select an Assignment</h3>
              <p>Choose a script from the sidebar to begin recording</p>
            </div>
          </div>
        )}
      </div>
      
      {/* Restart Recording Confirmation Modal */}
      {showRestartConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md mx-4">
            <div className="flex items-center mb-4">
              <div className="flex-shrink-0">
                <svg className="w-6 h-6 text-orange-600" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd"/>
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-lg font-medium text-gray-900">Restart Recording?</h3>
              </div>
            </div>
            
            <div className="mb-6">
              <p className="text-sm text-gray-600">
                Are you sure you want to restart the recording? This will reset the timer to 0:00 and 
                discard any current recording progress. <span className="font-semibold text-red-600">This action cannot be undone.</span>
              </p>
            </div>
            
            <div className="flex justify-end space-x-3">
              <button
                onClick={cancelRestartRecording}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Cancel
              </button>
              <button
                onClick={confirmRestartRecording}
                className="px-4 py-2 text-sm font-medium text-white bg-orange-600 border border-transparent rounded-md hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500"
              >
                Restart Recording
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};