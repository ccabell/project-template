/**
 * API service for transcription evaluator.
 */

import axios, { AxiosInstance, AxiosResponse } from 'axios';
import { getCurrentUser } from 'aws-amplify/auth';
import {
  HealthResponse,
  SingleAnalysisRequest,
  AnalysisResponse,
  GroundTruthGenerationRequest,
  GroundTruthResponse,
  GroundTruthJobResponse,
  GroundTruthJobStatus,
  VerticalsResponse,
  DetailedReport,
  Assignment,
  CreateAssignmentRequest,
  AssignmentStats
} from '../types/api';

/**
 * Get User Pool ID token by avoiding fetchAuthSession (which causes 400 Identity Pool errors).
 * Instead, access Amplify's internal token storage directly.
 */
async function getUserPoolIdToken(): Promise<string | null> {
  try {
    // Verify user is authenticated first
    const currentUser = await getCurrentUser();
    console.log('[AUTH] Current user verified:', {
      username: currentUser.username,
      userId: currentUser.userId,
      signInDetails: currentUser.signInDetails
    });

    // Try to get tokens from browser storage first (avoids Identity Pool calls)
    try {
      const storedTokens = await getTokensFromBrowserStorage();
      if (storedTokens) {
        console.log('[AUTH] Retrieved tokens from browser storage');
        return storedTokens;
      }
      
      console.warn('[AUTH] No tokens found in browser storage, falling back to fetchAuthSession');
    } catch (storageError) {
      console.warn('[AUTH] Error accessing browser storage, falling back to fetchAuthSession:', storageError);
    }

    // No fallback to fetchAuthSession to avoid Identity Pool issues
    console.warn('[AUTH] Could not retrieve ID token from browser storage and avoiding fetchAuthSession to prevent Identity Pool errors');
    return null;
    
  } catch (error) {
    console.error('[AUTH] Failed to get User Pool ID token:', error);
    return null;
  }
}

/**
 * Get tokens directly from browser storage (IndexedDB/localStorage).
 */
async function getTokensFromBrowserStorage(): Promise<string | null> {
  try {
    console.log('[AUTH] Searching for tokens in browser storage...');
    
    // List all localStorage keys to debug what's available
    const allKeys = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key) allKeys.push(key);
    }
    console.log('[AUTH] Available localStorage keys:', allKeys);
    
    // Check all localStorage keys for Cognito-related data
    for (const key of allKeys) {
      if (key && (key.includes('Cognito') || key.includes('amplify') || key.includes('aws'))) {
        const value = localStorage.getItem(key);
        console.log(`[AUTH] Found Cognito/Amplify key: ${key}`, value?.substring(0, 100));
      }
    }
    
    // Try the standard Cognito localStorage pattern
    // Note: Cognito stores tokens using CLIENT ID, not User Pool ID
    const clientId = '5sia5bf01l5mg7uacn5aqg4og9';
    const lastAuthUser = localStorage.getItem(`CognitoIdentityServiceProvider.${clientId}.LastAuthUser`);
    
    if (lastAuthUser) {
      console.log('[AUTH] Found LastAuthUser:', lastAuthUser);
      
      const idTokenKey = `CognitoIdentityServiceProvider.${clientId}.${lastAuthUser}.idToken`;
      console.log('[AUTH] Looking for ID token with key:', idTokenKey);
      
      const idToken = localStorage.getItem(idTokenKey);
      
      if (idToken) {
        console.log('[AUTH] Found ID token in localStorage');
        
        // Validate token format
        if (idToken.split('.').length === 3) {
          try {
            const tokenPayload = JSON.parse(atob(idToken.split('.')[1]));
            console.log('[AUTH] ID Token payload from localStorage:', {
              sub: tokenPayload.sub,
              email: tokenPayload.email,
              'cognito:groups': tokenPayload['cognito:groups'],
              'cognito:username': tokenPayload['cognito:username'],
              token_use: tokenPayload.token_use,
              exp: new Date(tokenPayload.exp * 1000).toISOString(),
              aud: tokenPayload.aud,
              iss: tokenPayload.iss
            });
            
            // Validate token issuer matches current user pool
            const expectedIssuer = 'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_O6Ib3izRC';
            if (tokenPayload.iss !== expectedIssuer) {
              console.warn('[AUTH] Token issuer mismatch - clearing stale tokens:', {
                expected: expectedIssuer,
                actual: tokenPayload.iss
              });
              
              // Clear all Cognito tokens for this client
              const keysToRemove = [];
              for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && key.startsWith(`CognitoIdentityServiceProvider.${clientId}.`)) {
                  keysToRemove.push(key);
                }
              }
              
              keysToRemove.forEach(key => {
                localStorage.removeItem(key);
                console.log('[AUTH] Cleared stale token key:', key);
              });
              
              return null;
            }
            
            // Check token expiration
            const now = Math.floor(Date.now() / 1000);
            if (tokenPayload.exp && tokenPayload.exp < now) {
              console.warn('[AUTH] Token expired, clearing tokens');
              
              // Clear expired tokens
              const keysToRemove = [];
              for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key && key.startsWith(`CognitoIdentityServiceProvider.${clientId}.`)) {
                  keysToRemove.push(key);
                }
              }
              
              keysToRemove.forEach(key => {
                localStorage.removeItem(key);
                console.log('[AUTH] Cleared expired token key:', key);
              });
              
              return null;
            }
            
            return idToken;
          } catch (parseError) {
            console.warn('[AUTH] Could not parse ID token from localStorage:', parseError);
          }
        }
      } else {
        console.warn('[AUTH] No ID token found at key:', idTokenKey);
      }
    } else {
      console.warn('[AUTH] No LastAuthUser found for Client ID:', clientId);
    }
    
    return null;
  } catch (error) {
    console.error('[AUTH] Error accessing browser storage:', error);
    return null;
  }
}

class TranscriptionEvaluatorAPI {
  private client: AxiosInstance;

  constructor(baseURL: string = process.env.REACT_APP_API_URL || 'http://localhost:8000') {
    this.client = axios.create({
      baseURL,
      timeout: 60000, // Increased for async operations
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for authentication and logging
    this.client.interceptors.request.use(
      async (config) => {
        console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
        
        // Define public endpoints that don't require authentication
        const publicEndpoints = [
          '/health', 
          '/analyze/single'
        ];
        
        // Check if this is a public endpoint
        const isPublicEndpoint = publicEndpoints.some(endpoint => 
          config.url?.includes(endpoint)
        );
        
        // All protected endpoints require Cognito authentication:
        // - /api/generate/ground-truth (job creation)
        // - /api/jobs/* (user job management)
        // - /api/user/* (user profile)
        // - /api/scripts/* (user scripts)
        // - /api/recordings/* (user recordings)
        
        if (!isPublicEndpoint) {
          try {
            console.log('[API] Protected endpoint - getting User Pool token');
            
            // Use our direct token extraction method
            const idToken = await getUserPoolIdToken();
            
            if (idToken) {
              config.headers.Authorization = `Bearer ${idToken}`;
              console.log('[API] Added User Pool ID token to request');
            } else {
              console.warn('[API] No User Pool ID token available for protected endpoint');
              // Don't throw error immediately - let the API return 401 and handle it properly
            }
          } catch (error) {
            console.error('[API] Authentication error:', error);
            // Don't throw error here - let the API request proceed and handle auth errors in response interceptor
          }
        } else {
          console.log('[API] Public endpoint - no authentication required:', config.url);
        }
        
        return config;
      },
      (error) => {
        console.error('[API] Request error:', error);
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('[API] Response error:', error);
        
        // Handle specific HTTP status codes
        if (error.response?.status === 401) {
          throw new Error('Authentication failed - please sign in again');
        } else if (error.response?.status === 403) {
          throw new Error('Access denied - insufficient permissions');
        } else if (error.response?.status === 404) {
          throw new Error('Resource not found');
        }
        
        if (error.response?.data?.detail) {
          throw new Error(error.response.data.detail);
        }
        
        if (error.response?.data?.message) {
          throw new Error(error.response.data.message);
        }
        
        if (error.response?.data?.error) {
          throw new Error(error.response.data.error);
        }
        
        if (error.code === 'ECONNABORTED') {
          throw new Error('Request timeout - please try again');
        }
        
        throw new Error(error.message || 'An unexpected error occurred');
      }
    );
  }

  async healthCheck(): Promise<HealthResponse> {
    const response: AxiosResponse<HealthResponse> = await this.client.get('/health');
    return response.data;
  }

  async analyzeSingle(request: SingleAnalysisRequest): Promise<AnalysisResponse> {
    const response: AxiosResponse<AnalysisResponse> = await this.client.post(
      '/analyze/single',
      request
    );
    return response.data;
  }

  async generateGroundTruth(
    request: GroundTruthGenerationRequest
  ): Promise<GroundTruthJobResponse> {
    const response: AxiosResponse<GroundTruthJobResponse> = await this.client.post(
      '/generate/ground-truth',
      request
    );
    return response.data;
  }

  async getJobStatus(jobId: string): Promise<GroundTruthJobStatus> {
    const response: AxiosResponse<any> = await this.client.get(`/api/jobs/${jobId}`);
    return {
      job_id: response.data.job_id,
      status: response.data.status,
      updated_at: response.data.updated_at,
      error: response.data.error_message,
      result: response.data.result_path ? {
        success: true,
        script_id: response.data.job_id,
        content: response.data.result?.content || '',
        word_count: response.data.result?.word_count || 0,
        storage_path: response.data.result_path,
        metadata: response.data.metadata || {},
        message: response.data.message || 'Ground truth generation completed'
      } : undefined
    };
  }

  async getUserJobs(): Promise<{user_id: string; jobs: any[]; total_count: number}> {
    try {
      // Call /api/jobs - backend automatically filters by authenticated user via JWT token
      const response: AxiosResponse<any> = await this.client.get(`/api/jobs`);
      console.log('[API DEBUG] getUserJobs raw response:', response.data);
      console.log('[API DEBUG] Sample job data:', response.data.jobs?.[0]);
      return {
        user_id: response.data.user_id,
        jobs: response.data.jobs.map((job: any) => {
          console.log('[API DEBUG] Processing job:', job.job_id, 'hasResult:', !!job.result);
          return {
            job_id: job.job_id,
            user_id: job.user_id,
            status: job.status,
            created_at: job.created_at,
            updated_at: job.updated_at,
            result_path: job.result_path,
            error_message: job.error_message,
            metadata: job.metadata,
            request_data: job.request_data || {},
            result: job.result,
            script_title: job.script_title
          };
        }),
        total_count: response.data.total_count
      };
    } catch (error) {
      console.warn('Failed to load user jobs:', error);
      return { user_id: '', jobs: [], total_count: 0 };
    }
  }

  async getJobDetail(jobId: string): Promise<any> {
    const response: AxiosResponse<any> = await this.client.get(`/jobs/${jobId}`);
    return response.data;
  }

  async getAvailableVerticals(): Promise<VerticalsResponse> {
    const response: AxiosResponse<VerticalsResponse> = await this.client.get(
      '/generate/verticals'
    );
    return response.data;
  }

  async getReport(reportPath: string): Promise<DetailedReport> {
    const response: AxiosResponse<DetailedReport> = await this.client.get(
      `/analyze/report/${encodeURIComponent(reportPath)}`
    );
    return response.data;
  }

  async getBrands(vertical?: string): Promise<{brands: string[]; total_count: number}> {
    const params = vertical ? { vertical } : {};
    const response: AxiosResponse<any> = await this.client.get('/api/brands', { params });
    return {
      brands: response.data.brands,
      total_count: response.data.total_count
    };
  }

  async addBrand(name: string, vertical?: string, phonetic?: string, difficulty?: string): Promise<{success: boolean; message: string}> {
    const response: AxiosResponse<any> = await this.client.post('/api/brands', {
      name,
      vertical,
      phonetic,
      difficulty
    });
    return {
      success: response.data.success,
      message: response.data.message
    };
  }

  async deleteBrand(name: string): Promise<{success: boolean; message: string}> {
    const response: AxiosResponse<any> = await this.client.delete(`/api/brands/${encodeURIComponent(name)}`);
    return {
      success: response.data.success,
      message: response.data.message
    };
  }

  async getTerms(vertical?: string): Promise<{terms: string[]; total_count: number}> {
    const params = vertical ? { vertical } : {};
    const response: AxiosResponse<any> = await this.client.get('/api/terms', { params });
    return {
      terms: response.data.terms,
      total_count: response.data.total_count
    };
  }

  async addTerm(name: string, vertical?: string, phonetic?: string, difficulty?: string): Promise<{success: boolean; message: string}> {
    const response: AxiosResponse<any> = await this.client.post('/api/terms', {
      name,
      vertical,
      phonetic,
      difficulty
    });
    return {
      success: response.data.success,
      message: response.data.message
    };
  }

  async deleteTerm(name: string): Promise<{success: boolean; message: string}> {
    const response: AxiosResponse<any> = await this.client.delete(`/api/terms/${encodeURIComponent(name)}`);
    return {
      success: response.data.success,
      message: response.data.message
    };
  }

  // Assignment service methods
  async getMyAssignments(statusFilter?: string, assignmentTypeFilter?: string, limit: number = 50): Promise<Assignment[]> {
    const params = new URLSearchParams();
    if (statusFilter) params.append('status_filter', statusFilter);
    if (assignmentTypeFilter) params.append('assignment_type_filter', assignmentTypeFilter);
    params.append('limit', limit.toString());
    
    const response: AxiosResponse<Assignment[]> = await this.client.get(
      `/assignments/my?${params.toString()}`
    );
    return response.data;
  }

  async createAssignment(assignment: CreateAssignmentRequest): Promise<{success: boolean; assignment: Assignment; message: string}> {
    const response: AxiosResponse<any> = await this.client.post('/assignments/', assignment);
    return response.data;
  }

  async updateAssignmentStatus(assignmentId: string, status: string, notes?: string): Promise<{success: boolean; message: string}> {
    const response: AxiosResponse<any> = await this.client.put(`/assignments/${assignmentId}/status`, {
      status,
      notes
    });
    return response.data;
  }

  async getAssignmentStats(): Promise<AssignmentStats> {
    const response: AxiosResponse<AssignmentStats> = await this.client.get('/assignments/stats/my');
    return response.data;
  }

  async getPendingAssignments(limit: number = 100): Promise<Assignment[]> {
    const response: AxiosResponse<Assignment[]> = await this.client.get(`/assignments/pending?limit=${limit}`);
    return response.data;
  }

  async getOverdueAssignments(limit: number = 100): Promise<Assignment[]> {
    const response: AxiosResponse<Assignment[]> = await this.client.get(`/assignments/overdue?limit=${limit}`);
    return response.data;
  }

  async getUserInfo(): Promise<{username: string; groups: string[]; email?: string}> {
    const response: AxiosResponse<{username: string; groups: string[]; email?: string}> = await this.client.get('/auth/me');
    return response.data;
  }

  async getAvailableReaders(): Promise<{cognito_id: string; email: string; name: string; is_active: boolean}[]> {
    const response: AxiosResponse<{cognito_id: string; email: string; name: string; is_active: boolean}[]> = await this.client.get('/assignments/readers');
    return response.data;
  }

  async getAllAssignments(): Promise<Assignment[]> {
    const response: AxiosResponse<Assignment[]> = await this.client.get('/assignments/all');
    return response.data;
  }

  async updateAssignmentPriority(assignmentId: string, priority: number): Promise<{success: boolean; message: string}> {
    const response: AxiosResponse<any> = await this.client.put(`/assignments/${assignmentId}/priority`, {
      priority
    });
    return response.data;
  }

  async updateAssignmentReader(assignmentId: string, readerId: string): Promise<{success: boolean; message: string}> {
    const response: AxiosResponse<any> = await this.client.put(`/assignments/${assignmentId}/reader`, {
      assigned_to_cognito_id: readerId
    });
    return response.data;
  }

  async deleteAssignment(assignmentId: string): Promise<{success: boolean; message: string}> {
    const response: AxiosResponse<any> = await this.client.delete(`/assignments/${assignmentId}`);
    return response.data;
  }

  async updateScript(jobId: string, title: string, content: string): Promise<{success: boolean; message: string}> {
    const wordCount = content.trim().split(/\s+/).length;
    const response: AxiosResponse<any> = await this.client.put(`/api/jobs/${jobId}/script`, {
      script_title: title,
      content: content,
      word_count: wordCount
    });
    return response.data;
  }
}

// Export singleton instance
export const apiService = new TranscriptionEvaluatorAPI();

// Export class for testing or custom instances
export { TranscriptionEvaluatorAPI };