/**
 * API types for transcription evaluator service.
 */

export interface HealthResponse {
  status: string;
  timestamp: string;
  version: string;
}

export interface SingleAnalysisRequest {
  consultation_id: string;
  original_text: string;
  corrected_text: string;
  ground_truth_text: string;
  backend: string;
  confidence_threshold?: number;
}

export interface AnalysisResponse {
  success: boolean;
  analysis_id: string;
  report_path?: string;
  summary_statistics?: {
    false_positive_count: number;
    false_negative_count: number;
    accuracy: number;
    character_error_rate: number;
  };
  message: string;
}

export interface GroundTruthGenerationRequest {
  medical_vertical?: string;
  language?: string;
  target_word_count?: number;
  seed_term_density?: number;
  difficulty_level?: string;
  include_product_names?: boolean;
  encounter_type?: string;
  selected_brands?: string[];
  selected_terms?: string[];
}

export interface GroundTruthJobResponse {
  job_id: string;
  status: string;
  message: string;
  poll_url: string;
  estimated_completion_time: string;
}

export interface GroundTruthJobStatus {
  job_id: string;
  script_title?: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  updated_at: string;
  error?: string;
  result?: GroundTruthResponse;
}

export interface GroundTruthResponse {
  success: boolean;
  script_id: string;
  script_title?: string;
  content: string;
  word_count: number;
  storage_path: string;
  metadata: {
    script_url: string;
    metadata_url: string;
    generation_id: string;
    seed_terms_used: string[];
    brand_names_used: string[];
    difficulty_score: number;
    transcription_challenge_score: number;
    reader_challenge_score: number;
  };
  message: string;
}

export interface VerticalsResponse {
  verticals: Array<{
    id: string;
    name: string;
    description: string;
  }>;
}

export interface DetailedReport {
  consultation_id: string;
  timestamp: string;
  false_positive_count: number;
  false_negative_count: number;
  false_positives: Array<{
    term: string;
    error_type: string;
    confidence: number;
    medical_vertical: string;
  }>;
  false_negatives: Array<{
    term: string;
    error_type: string;
    confidence: number;
    medical_vertical: string;
  }>;
  accuracy_metrics: {
    accuracy: number;
    character_error_rate: number;
    improvement_over_original: number;
  };
  summary: {
    total_errors: number;
    accuracy: number;
    character_error_rate: number;
    improvement_over_original: number;
  };
}

// Assignment related types
export interface Assignment {
  assignment_id: string;
  job_id: string;
  script_id?: string;
  script_title?: string;
  script_difficulty?: number;
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
  // Enhanced fields from priority-based API
  word_count?: number;
  blocked?: boolean;
  blocked_reason?: string;
}

export interface CreateAssignmentRequest {
  script_id: string;
  assigned_to_cognito_id: string;
  assignment_type: 'record' | 'evaluate' | 'review';
  priority?: number;
  due_date?: string;
  notes?: string;
}

export interface AssignmentStats {
  total_assignments: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  by_priority: Record<number, number>;
  overdue_count: number;
  completed_this_week: number;
  average_completion_time_hours?: number;
}