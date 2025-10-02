import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import toast from 'react-hot-toast';

interface Reader {
  cognito_id: string;
  email: string;
  name: string;
  is_active: boolean;
}

interface AssignmentWithDetails {
  assignment_id: string;
  job_id: string;
  script_id?: string;
  script_title?: string;
  assigned_to_cognito_id: string;
  assigned_to_name?: string;
  assigned_by_cognito_id: string;
  assigned_by_name?: string;
  assignment_type: 'record' | 'evaluate' | 'review';
  status: 'assigned' | 'in_progress' | 'audio_submitted' | 'completed' | 'skipped';
  priority: number;
  due_date?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  word_count?: number;
  blocked?: boolean;
  blocked_reason?: string;
}

interface CompletedJob {
  job_id: string;
  script_title?: string;
  status: string;
  created_at: string;
  result?: {
    content: string;
    word_count: number;
    metadata?: any;
  };
  request_data?: {
    medical_vertical?: string;
    target_word_count?: number;
  };
}

export const ScriptAssignment: React.FC = () => {
  const [completedJobs, setCompletedJobs] = useState<CompletedJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showingScript, setShowingScript] = useState<CompletedJob | null>(null);
  const [assignmentModal, setAssignmentModal] = useState<CompletedJob | null>(null);
  const [readers, setReaders] = useState<Reader[]>([]);
  const [expandedPreviews, setExpandedPreviews] = useState<Set<string>>(new Set());
  
  // Assignment management state
  const [currentView, setCurrentView] = useState<'scripts' | 'assignments'>('scripts');
  const [allAssignments, setAllAssignments] = useState<AssignmentWithDetails[]>([]);
  const [assignmentsLoading, setAssignmentsLoading] = useState(false);
  const [editingAssignment, setEditingAssignment] = useState<(AssignmentWithDetails & { action: 'priority' | 'reader' | 'delete' }) | null>(null);
  
  // Script editing state
  const [editingScript, setEditingScript] = useState<CompletedJob | null>(null);

  const togglePreview = (jobId: string) => {
    const newExpanded = new Set(expandedPreviews);
    if (newExpanded.has(jobId)) {
      newExpanded.delete(jobId);
    } else {
      newExpanded.add(jobId);
    }
    setExpandedPreviews(newExpanded);
  };

  const renderScriptPreview = (job: CompletedJob) => {
    const content = job.result?.content || 'No content available';
    const isExpanded = expandedPreviews.has(job.job_id);
    const shortPreview = content.substring(0, 300);
    const shouldTruncate = content.length > 300;
    
    return (
      <div className="space-y-2">
        <div className="text-sm text-gray-900 whitespace-pre-wrap leading-relaxed">
          {isExpanded ? content : shortPreview}
          {!isExpanded && shouldTruncate && '...'}
        </div>
        {shouldTruncate && (
          <button
            onClick={() => togglePreview(job.job_id)}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            {isExpanded ? 'Show less' : 'Read more'}
          </button>
        )}
      </div>
    );
  };

  useEffect(() => {
    loadCompletedJobs();
    loadReaders();
  }, []);

  useEffect(() => {
    if (currentView === 'assignments') {
      loadAllAssignments();
    }
  }, [currentView]);

  const loadCompletedJobs = async () => {
    try {
      setLoading(true);
      const [jobsData, assignments] = await Promise.all([
        apiService.getUserJobs(),
        apiService.getAllAssignments().catch(() => []) // Don't fail if assignments fail to load
      ]);
      
      // Get job IDs that already have assignments
      const assignedJobIds = new Set(assignments.map((assignment: any) => assignment.job_id));
      
      // Filter for completed jobs that have actual script content and are not already assigned
      const completed = jobsData.jobs.filter(job => 
        job.status === 'completed' && 
        job.result && 
        job.result.content &&
        !assignedJobIds.has(job.job_id) // Exclude already assigned jobs
      );
      
      setCompletedJobs(completed);
    } catch (err) {
      console.error('Failed to load completed jobs:', err);
      setError('Failed to load completed scripts');
    } finally {
      setLoading(false);
    }
  };

  const loadReaders = async () => {
    try {
      console.log('[ScriptAssignment] Loading readers...');
      const readersList = await apiService.getAvailableReaders();
      console.log('[ScriptAssignment] Loaded readers:', readersList);
      setReaders(readersList);
    } catch (err) {
      console.error('Failed to load readers:', err);
      console.error('Error details:', (err as any).response?.data || (err as any).message);
      // Set a default fallback to prevent UI errors
      setReaders([]);
    }
  };

  const loadAllAssignments = async () => {
    try {
      setAssignmentsLoading(true);
      console.log('[ScriptAssignment] Loading all assignments...');
      const assignments = await apiService.getAllAssignments();
      console.log('[ScriptAssignment] Loaded assignments:', assignments);
      setAllAssignments(assignments);
    } catch (err) {
      console.error('Failed to load assignments:', err);
      toast.error('Failed to load assignment details');
      setAllAssignments([]);
    } finally {
      setAssignmentsLoading(false);
    }
  };

  const handleAssignScript = (job: CompletedJob) => {
    setAssignmentModal(job);
  };

  const handleViewScript = (job: CompletedJob) => {
    setShowingScript(job);
  };

  const handleEditScript = (job: CompletedJob) => {
    setEditingScript(job);
  };

  const handleDownloadScript = (job: CompletedJob) => {
    let result = job.result;
    // Parse result if it's a string
    if (typeof result === 'string') {
      try {
        result = JSON.parse(result);
      } catch (e) {
        result = job.result;
      }
    }
    
    const content = `Ground Truth Script
Generated: ${new Date(job.created_at).toLocaleDateString()}
Job ID: ${job.job_id}
Word Count: ${result?.word_count || 'Unknown'}
Medical Vertical: ${job.request_data?.medical_vertical || 'Unknown'}

${result?.content || 'No content available'}`;

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ground-truth-${job.job_id.substring(0, 8)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleCreateAssignment = async (jobId: string, readerCognitoId: string, priority: string, notes: string) => {
    try {
      const priorityMap: Record<string, number> = { low: 1, medium: 2, high: 3 };
      
      await apiService.createAssignment({
        script_id: jobId,
        assigned_to_cognito_id: readerCognitoId,
        assignment_type: 'record',
        priority: priorityMap[priority] || 2,
        notes
      });
      
      setAssignmentModal(null);
      // Refresh both available scripts and assignments after creating assignment
      loadCompletedJobs(); // Remove assigned script from available list
      if (currentView === 'assignments') {
        loadAllAssignments();
      }
      // Assignment created successfully - no popup for better batch UX
    } catch (err) {
      console.error('Failed to create assignment:', err);
      toast.error('Failed to create assignment. Please try again.');
    }
  };

  // Helper functions for assignment status display
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
      case 'skipped':
        return 'bg-gray-100 text-gray-800 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-500 border-gray-200';
    }
  };

  const getPriorityColor = (priority: number) => {
    switch (priority) {
      case 3:
        return 'bg-red-100 text-red-800 border-red-200';
      case 2:
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 1:
        return 'bg-gray-100 text-gray-800 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-500 border-gray-200';
    }
  };

  const getPriorityText = (priority: number) => {
    switch (priority) {
      case 3: return 'High';
      case 2: return 'Medium';
      case 1: return 'Low';
      default: return 'Unknown';
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

  if (loading) {
    return (
      <div className="p-8">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded mb-4"></div>
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <div className="text-red-400 text-xl mr-3">⚠️</div>
            <div>
              <h3 className="text-red-800 font-medium">Error Loading Scripts</h3>
              <p className="text-red-700 mt-1">{error}</p>
              <button
                onClick={loadCompletedJobs}
                className="mt-3 text-red-600 hover:text-red-500 underline"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <div className="flex-1 flex flex-col min-h-0 overflow-y-auto">
        <div className="p-8 flex-1 flex flex-col">
          <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Script Assignment</h2>
        <p className="text-gray-600">
          Assign completed ground truth scripts to readers for recording.
        </p>
        
        {/* View Toggle Tabs */}
        <div className="mt-4 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setCurrentView('scripts')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                currentView === 'scripts'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Available Scripts
            </button>
            <button
              onClick={() => setCurrentView('assignments')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                currentView === 'assignments'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Assignment Management
            </button>
          </nav>
        </div>
      </div>

          {/* Conditional View Content */}
          {currentView === 'scripts' ? (
        // Scripts View
        completedJobs.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">📝</div>
            <h3 className="text-xl font-medium text-gray-900 mb-2">No Completed Scripts</h3>
            <p className="text-gray-600 mb-4">
              Generate some ground truth scripts first to see them here for assignment.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Refresh
            </button>
          </div>
        ) : (
          <div className="space-y-4 max-h-[70vh] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100 pr-2">
            {completedJobs.map((job) => (
            <div key={job.job_id} className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h3 className="text-lg font-medium text-gray-900">
                    {job.script_title || `Script ${job.job_id.substring(0, 8)}`}
                  </h3>
                  <p className="text-sm text-gray-500">
                    Created: {new Date(job.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                  Ready for Assignment
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div>
                  <span className="text-sm font-medium text-gray-500">Medical Vertical</span>
                  <p className="text-sm text-gray-900 capitalize">
                    {job.request_data?.medical_vertical?.replace('_', ' ') || 'Unknown'}
                  </p>
                </div>
                <div>
                  <span className="text-sm font-medium text-gray-500">Word Count</span>
                  <p className="text-sm text-gray-900">
                    {(() => {
                      let result = job.result;
                      // Parse result if it's a string
                      if (typeof result === 'string') {
                        try {
                          result = JSON.parse(result);
                        } catch (e) {
                          result = job.result;
                        }
                      }
                      return result?.word_count || job.request_data?.target_word_count || 'Unknown';
                    })()} words
                  </p>
                </div>
                <div>
                  <span className="text-sm font-medium text-gray-500">Script Preview</span>
                  {renderScriptPreview(job)}
                </div>
              </div>

              <div className="flex space-x-3">
                <button 
                  onClick={() => handleAssignScript(job)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Assign to Reader
                </button>
                <button 
                  onClick={() => handleEditScript(job)}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                >
                  Edit Script
                </button>
                <button 
                  onClick={() => handleViewScript(job)}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  View Full Script
                </button>
                <button 
                  onClick={() => handleDownloadScript(job)}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  Download
                </button>
              </div>
            </div>
          ))}
        </div>
            )
          ) : (
            // Assignments Management View
        <div className="space-y-6">
          {assignmentsLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <span className="ml-3 text-gray-600">Loading assignments...</span>
            </div>
          ) : allAssignments.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-6xl mb-4">📋</div>
              <h3 className="text-xl font-medium text-gray-900 mb-2">No Assignments Found</h3>
              <p className="text-gray-600">
                No script assignments have been created yet. Assign scripts from the "Available Scripts" tab.
              </p>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">Assignment Overview</h3>
                <p className="text-sm text-gray-600 mt-1">
                  {allAssignments.length} assignments found
                </p>
              </div>
              
              <div className="divide-y divide-gray-200 max-h-[60vh] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
                {allAssignments.map((assignment) => (
                  <div key={assignment.assignment_id} className="p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1">
                        <h4 className="text-lg font-medium text-gray-900 mb-2">
                          {assignment.script_title || `Script ${assignment.job_id.substring(0, 8)}`}
                        </h4>
                        <div className="flex items-center space-x-4 text-sm text-gray-600">
                          <span className={`px-2 py-1 rounded-full border text-xs font-medium ${getAssignmentStatusColor(assignment.status)}`}>
                            {assignment.status.replace('_', ' ')}
                          </span>
                          <span className={`px-2 py-1 rounded-full border text-xs font-medium ${getPriorityColor(assignment.priority)}`}>
                            {getPriorityText(assignment.priority)} Priority
                          </span>
                          <span>Type: {assignment.assignment_type}</span>
                        </div>
                      </div>
                      <div className="text-right text-sm text-gray-500">
                        <div>ID: {assignment.assignment_id.substring(0, 16)}...</div>
                        <div className="mt-1">Created: {formatDate(assignment.created_at)}</div>
                        
                        {/* Assignment Actions */}
                        <div className="mt-3 flex space-x-2">
                          <button
                            onClick={() => setEditingAssignment({
                              ...assignment,
                              action: 'priority'
                            })}
                            className="px-3 py-1 text-xs bg-blue-50 text-blue-600 border border-blue-200 rounded hover:bg-blue-100 transition-colors"
                            title="Edit Priority"
                          >
                            📝 Priority
                          </button>
                          <button
                            onClick={() => setEditingAssignment({
                              ...assignment,
                              action: 'reader'
                            })}
                            className="px-3 py-1 text-xs bg-green-50 text-green-600 border border-green-200 rounded hover:bg-green-100 transition-colors"
                            title="Change Reader"
                          >
                            👤 Reader
                          </button>
                          <button
                            onClick={() => setEditingAssignment({
                              ...assignment,
                              action: 'delete'
                            })}
                            className="px-3 py-1 text-xs bg-red-50 text-red-600 border border-red-200 rounded hover:bg-red-100 transition-colors"
                            title="Delete Assignment"
                          >
                            🗑️ Delete
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      {/* Reader Information */}
                      <div>
                        <h5 className="font-medium text-gray-900 mb-2">Assigned Reader</h5>
                        <div className="text-sm text-gray-600">
                          <div className="font-medium text-gray-900">
                            {assignment.assigned_to_name || 'Name not available'}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            ID: {assignment.assigned_to_cognito_id.substring(0, 8)}...
                          </div>
                        </div>
                      </div>

                      {/* Assignment Details */}
                      <div>
                        <h5 className="font-medium text-gray-900 mb-2">Assignment Details</h5>
                        <div className="text-sm text-gray-600 space-y-1">
                          {assignment.word_count && (
                            <div>Word Count: {assignment.word_count.toLocaleString()}</div>
                          )}
                          {assignment.due_date && (
                            <div>Due: {formatDate(assignment.due_date)}</div>
                          )}
                          {assignment.completed_at && (
                            <div className="text-green-600">
                              Completed: {formatDate(assignment.completed_at)}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Notes and Status */}
                      <div>
                        <h5 className="font-medium text-gray-900 mb-2">Notes & Status</h5>
                        <div className="text-sm text-gray-600">
                          {assignment.blocked && (
                            <div className="mb-2 p-2 bg-orange-50 border border-orange-200 rounded text-xs text-orange-800">
                              <div className="font-medium">🚫 Blocked</div>
                              <div>{assignment.blocked_reason}</div>
                            </div>
                          )}
                          {assignment.notes ? (
                            <div className="text-xs bg-gray-100 p-2 rounded">{assignment.notes}</div>
                          ) : (
                            <div className="text-xs text-gray-400 italic">No notes</div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Progress Timeline */}
                    <div className="mt-4 pt-4 border-t border-gray-100">
                      <div className="flex items-center space-x-2 text-xs text-gray-500">
                        <span>Assigned: {formatDate(assignment.created_at)}</span>
                        {assignment.updated_at !== assignment.created_at && (
                          <>
                            <span>•</span>
                            <span>Updated: {formatDate(assignment.updated_at)}</span>
                          </>
                        )}
                        {assignment.completed_at && (
                          <>
                            <span>•</span>
                            <span>Completed: {formatDate(assignment.completed_at)}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
            </div>
          )}

          {/* Script Viewer Modal */}
      {showingScript && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-4xl max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-gray-900">
                {showingScript.script_title || `Script ${showingScript.job_id.substring(0, 8)}`}
              </h2>
              <button
                onClick={() => setShowingScript(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                <span className="sr-only">Close</span>
                ✕
              </button>
            </div>

            <div className="mb-6 bg-gray-50 p-4 rounded-lg">
              <h4 className="text-lg font-medium text-gray-900 mb-2">Script Details</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="font-medium text-gray-600">Medical Vertical:</span>
                  <div className="text-gray-900">{showingScript.request_data?.medical_vertical?.replace('_', ' ') || 'Unknown'}</div>
                </div>
                <div>
                  <span className="font-medium text-gray-600">Word Count:</span>
                  <div className="text-gray-900">{(() => {
                    let result = showingScript.result;
                    // Parse result if it's a string
                    if (typeof result === 'string') {
                      try {
                        result = JSON.parse(result);
                      } catch (e) {
                        result = showingScript.result;
                      }
                    }
                    return result?.word_count || 'Unknown';
                  })()}</div>
                </div>
                <div>
                  <span className="font-medium text-gray-600">Created:</span>
                  <div className="text-gray-900">{new Date(showingScript.created_at).toLocaleDateString()}</div>
                </div>
                <div>
                  <span className="font-medium text-gray-600">Status:</span>
                  <div className="text-green-600 font-medium">Completed</div>
                </div>
              </div>
            </div>

            <div className="mb-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Script Content</h4>
              <div className="bg-gray-50 p-6 rounded-lg border min-h-96 max-h-[60vh] overflow-y-auto overflow-x-hidden scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
                <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono leading-relaxed">
                  {showingScript.result?.content || 'No content available'}
                </pre>
              </div>
            </div>

            <div className="flex justify-end space-x-3">
              <button
                onClick={() => handleDownloadScript(showingScript)}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
              >
                Download Script
              </button>
              <button
                onClick={() => {
                  setShowingScript(null);
                  setEditingScript(showingScript);
                }}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
              >
                Edit Script
              </button>
              <button
                onClick={() => {
                  setShowingScript(null);
                  setAssignmentModal(showingScript);
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Assign to Reader
              </button>
              <button
                onClick={() => setShowingScript(null)}
                className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Assignment Modal */}
      {assignmentModal && (
        <AssignmentModal
          job={assignmentModal}
          readers={readers}
          onClose={() => setAssignmentModal(null)}
          onAssign={handleCreateAssignment}
        />
      )}

      {/* Edit Assignment Modal */}
      {editingAssignment && (
        <EditAssignmentModal
          assignment={editingAssignment}
          readers={readers}
          onClose={() => setEditingAssignment(null)}
          onUpdate={(updatedAssignment) => {
            setEditingAssignment(null);
            loadAllAssignments(); // Refresh assignments list
          }}
        />
      )}

      {/* Script Editing Modal */}
      {editingScript && (
        <ScriptEditModal
          job={editingScript}
          onClose={() => setEditingScript(null)}
          onSave={(updatedJob) => {
            setEditingScript(null);
            loadCompletedJobs(); // Refresh scripts list
          }}
        />
      )}
        </div>
      </div>
    </div>
  );
};

// Assignment Modal Component
interface AssignmentModalProps {
  job: CompletedJob;
  readers: Reader[];
  onClose: () => void;
  onAssign: (jobId: string, readerCognitoId: string, priority: string, notes: string) => void;
}

const AssignmentModal: React.FC<AssignmentModalProps> = ({ job, readers, onClose, onAssign }) => {
  const [selectedReaderId, setSelectedReaderId] = useState('');
  const [priority, setPriority] = useState('medium');
  const [notes, setNotes] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReaderId.trim()) {
      toast.error('Please select a reader');
      return;
    }
    onAssign(job.job_id, selectedReaderId, priority, notes);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-gray-900">Assign Script</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Reader
            </label>
            <select
              value={selectedReaderId}
              onChange={(e) => setSelectedReaderId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            >
              <option value="">Select a reader...</option>
              {readers.map((reader) => (
                <option key={reader.cognito_id} value={reader.cognito_id}>
                  {reader.name} ({reader.email})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Priority
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Notes (Optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Additional instructions for the reader..."
              rows={3}
            />
          </div>

          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Create Assignment
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// Edit Assignment Modal Component
interface EditAssignmentModalProps {
  assignment: AssignmentWithDetails & { action: 'priority' | 'reader' | 'delete' };
  readers: Reader[];
  onClose: () => void;
  onUpdate: (assignment: AssignmentWithDetails) => void;
}

const EditAssignmentModal: React.FC<EditAssignmentModalProps> = ({
  assignment,
  readers,
  onClose,
  onUpdate
}) => {
  const [priority, setPriority] = useState(assignment.priority.toString());
  const [selectedReader, setSelectedReader] = useState(assignment.assigned_to_cognito_id);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (assignment.action === 'priority') {
        const priorityMap: Record<string, number> = { '1': 1, '2': 2, '3': 3 };
        await apiService.updateAssignmentPriority(
          assignment.assignment_id,
          priorityMap[priority]
        );
        toast.success('Assignment priority updated successfully');
      } else if (assignment.action === 'reader') {
        await apiService.updateAssignmentReader(
          assignment.assignment_id,
          selectedReader
        );
        toast.success('Assignment reader updated successfully');
      } else if (assignment.action === 'delete') {
        await apiService.deleteAssignment(assignment.assignment_id);
        toast.success('Assignment deleted successfully');
      }

      onUpdate(assignment);
    } catch (err) {
      console.error('Failed to update assignment:', err);
      toast.error(`Failed to ${assignment.action} assignment. Please try again.`);
    } finally {
      setLoading(false);
    }
  };

  const getModalTitle = () => {
    switch (assignment.action) {
      case 'priority': return 'Edit Priority';
      case 'reader': return 'Change Reader';
      case 'delete': return 'Delete Assignment';
      default: return 'Edit Assignment';
    }
  };

  const getButtonText = () => {
    switch (assignment.action) {
      case 'priority': return 'Update Priority';
      case 'reader': return 'Change Reader';
      case 'delete': return 'Delete Assignment';
      default: return 'Update';
    }
  };

  const getButtonClass = () => {
    switch (assignment.action) {
      case 'priority': return 'px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50';
      case 'reader': return 'px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50';
      case 'delete': return 'px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50';
      default: return 'px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50';
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">{getModalTitle()}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="mb-4 text-sm text-gray-600">
          <div className="font-medium">{assignment.script_title || `Script ${assignment.job_id.substring(0, 8)}`}</div>
          <div>Assignment ID: {assignment.assignment_id.substring(0, 16)}...</div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {assignment.action === 'priority' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Priority Level
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              >
                <option value="1">Low (1)</option>
                <option value="2">Medium (2)</option>
                <option value="3">High (3)</option>
              </select>
            </div>
          )}

          {assignment.action === 'reader' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Assign to Reader
              </label>
              <select
                value={selectedReader}
                onChange={(e) => setSelectedReader(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                required
              >
                {readers.map((reader) => (
                  <option key={reader.cognito_id} value={reader.cognito_id}>
                    {reader.name} ({reader.email})
                  </option>
                ))}
              </select>
            </div>
          )}

          {assignment.action === 'delete' && (
            <div className="bg-red-50 border border-red-200 rounded-md p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-red-800">Delete Assignment</h3>
                  <p className="mt-1 text-sm text-red-700">
                    Are you sure you want to delete this assignment? This action cannot be undone.
                    The script will become available for reassignment.
                  </p>
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={getButtonClass()}
              disabled={loading}
            >
              {loading ? 'Processing...' : getButtonText()}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// Script Edit Modal Component
interface ScriptEditModalProps {
  job: CompletedJob;
  onClose: () => void;
  onSave: (updatedJob: CompletedJob) => void;
}

const ScriptEditModal: React.FC<ScriptEditModalProps> = ({ job, onClose, onSave }) => {
  const [editedContent, setEditedContent] = useState('');
  const [editedTitle, setEditedTitle] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Initialize with current content
    let result = job.result;
    if (typeof result === 'string') {
      try {
        result = JSON.parse(result);
      } catch (e) {
        result = job.result;
      }
    }
    setEditedContent(result?.content || '');
    setEditedTitle(job.script_title || `Script ${job.job_id.substring(0, 8)}`);
  }, [job]);

  const handleSave = async () => {
    setLoading(true);
    try {
      // Save changes via API
      await apiService.updateScript(job.job_id, editedTitle, editedContent);

      // Create updated job object with edited content
      let updatedResult = job.result;
      if (typeof updatedResult === 'string') {
        try {
          updatedResult = JSON.parse(updatedResult);
        } catch (e) {
          updatedResult = { content: '', word_count: 0 };
        }
      }

      // Update the result with edited content
      const newResult = {
        ...updatedResult,
        content: editedContent,
        word_count: editedContent.split(' ').filter(word => word.trim().length > 0).length
      };

      const updatedJob: CompletedJob = {
        ...job,
        script_title: editedTitle,
        result: newResult
      };

      toast.success('Script updated successfully');
      onSave(updatedJob);
    } catch (error) {
      console.error('Failed to save script changes:', error);
      toast.error('Failed to save changes. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const wordCount = editedContent.split(' ').filter(word => word.trim().length > 0).length;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-6xl max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Edit Script</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <span className="sr-only">Close</span>
            ✕
          </button>
        </div>

        <div className="space-y-6">
          {/* Script Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Script Title
            </label>
            <input
              type="text"
              value={editedTitle}
              onChange={(e) => setEditedTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Enter script title..."
            />
          </div>

          {/* Script Content */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Script Content
              </label>
              <span className="text-sm text-gray-500">
                {wordCount.toLocaleString()} words
              </span>
            </div>
            <textarea
              value={editedContent}
              onChange={(e) => setEditedContent(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
              rows={20}
              placeholder="Enter script content..."
            />
          </div>

          {/* Script Details */}
          <div className="bg-gray-50 p-4 rounded-lg">
            <h4 className="text-lg font-medium text-gray-900 mb-2">Script Details</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="font-medium text-gray-600">Job ID:</span>
                <div className="text-gray-900">{job.job_id.substring(0, 8)}...</div>
              </div>
              <div>
                <span className="font-medium text-gray-600">Medical Vertical:</span>
                <div className="text-gray-900">{job.request_data?.medical_vertical?.replace('_', ' ') || 'Unknown'}</div>
              </div>
              <div>
                <span className="font-medium text-gray-600">Original Word Count:</span>
                <div className="text-gray-900">{(() => {
                  let result = job.result;
                  if (typeof result === 'string') {
                    try {
                      result = JSON.parse(result);
                    } catch (e) {
                      result = job.result;
                    }
                  }
                  return result?.word_count || 'Unknown';
                })()}</div>
              </div>
              <div>
                <span className="font-medium text-gray-600">Created:</span>
                <div className="text-gray-900">{new Date(job.created_at).toLocaleDateString()}</div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end space-x-3 pt-6 border-t border-gray-200 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
            disabled={loading}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            disabled={loading || !editedContent.trim() || !editedTitle.trim()}
          >
            {loading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
};