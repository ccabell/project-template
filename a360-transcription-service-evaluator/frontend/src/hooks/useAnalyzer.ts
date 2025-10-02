/**
 * React hook for transcript analysis functionality.
 */

import { useState, useCallback } from 'react';
import { apiService } from '../services/api';
import {
  SingleAnalysisRequest,
  AnalysisResponse,
  DetailedReport
} from '../types/api';

interface UseAnalyzerResult {
  analyzing: boolean;
  analysis: AnalysisResponse | null;
  detailedReport: DetailedReport | null;
  error: string | null;
  analyzeTranscript: (request: SingleAnalysisRequest) => Promise<void>;
  getDetailedReport: (reportPath: string) => Promise<void>;
  clearAnalysis: () => void;
  clearError: () => void;
}

export const useAnalyzer = (): UseAnalyzerResult => {
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [detailedReport, setDetailedReport] = useState<DetailedReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const analyzeTranscript = useCallback(async (request: SingleAnalysisRequest) => {
    setAnalyzing(true);
    setError(null);
    setAnalysis(null);
    setDetailedReport(null);

    try {
      const result = await apiService.analyzeSingle(request);
      setAnalysis(result);

      // Automatically fetch detailed report if available
      if (result.report_path) {
        try {
          const report = await apiService.getReport(result.report_path);
          setDetailedReport(report);
        } catch (reportError) {
          console.warn('Failed to fetch detailed report:', reportError);
          // Don't set error here as the main analysis succeeded
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  }, []);

  const getDetailedReport = useCallback(async (reportPath: string) => {
    setError(null);

    try {
      const report = await apiService.getReport(reportPath);
      setDetailedReport(report);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch report');
    }
  }, []);

  const clearAnalysis = useCallback(() => {
    setAnalysis(null);
    setDetailedReport(null);
    setError(null);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    analyzing,
    analysis,
    detailedReport,
    error,
    analyzeTranscript,
    getDetailedReport,
    clearAnalysis,
    clearError,
  };
};