/**
 * OrbitOpt API Service Layer
 * Strictly adheres to docs/API_CONTRACT.md contracts.
 * Connects to FastAPI backend via Vite proxy or direct base URL.
 */

import axios, { AxiosError } from 'axios';
import type {
  Dataset,
  DatasetSummary,
  GroundStation,
  SatellitePass,
  ScheduleRunResponse,
  ScheduleMetrics,
  HealthCheckResponse,
  ApiErrorResponse,
  PassExecutionRead,
  PassTransitionRequest,
  PassExecutionSummary,
  OperationalAnalyticsResponse,
  DeadlineRiskSummary,
} from '../types/api';


const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Check backend health status and DB connectivity
 */
export const checkHealth = async (): Promise<HealthCheckResponse> => {
  try {
    const response = await apiClient.get<HealthCheckResponse>('/health');
    return response.data;
  } catch {
    // Also try root health endpoint via root proxy
    const fallbackResponse = await axios.get<HealthCheckResponse>('/health', { timeout: 3000 });
    return fallbackResponse.data;
  }
};

/**
 * List all dataset scenarios available on backend
 */
export const listDatasets = async (skip = 0, limit = 50): Promise<DatasetSummary[]> => {
  const response = await apiClient.get<DatasetSummary[]>('/datasets', {
    params: { skip, limit },
  });
  return response.data;
};

/**
 * Retrieve a specific scenario dataset by ID
 */
export const getDataset = async (datasetId: string): Promise<Dataset> => {
  const response = await apiClient.get<Dataset>(`/datasets/${datasetId}`);
  return response.data;
};

/**
 * Create a new dataset scenario
 */
export const createDataset = async (
  data: {
    dataset_id?: string;
    name: string;
    description?: string;
    ground_stations: GroundStation[];
    satellite_passes: SatellitePass[];
  }
): Promise<Dataset> => {
  const response = await apiClient.post<Dataset>('/datasets', data);
  return response.data;
};

/**
 * Execute baseline First-Come-First-Served (FCFS) scheduling
 */
export const runBaseline = async (
  datasetId: string,
  setupTimeSeconds = 60
): Promise<ScheduleRunResponse> => {
  const response = await apiClient.post<ScheduleRunResponse>('/schedules/baseline', {
    dataset_id: datasetId,
    setup_time_seconds: setupTimeSeconds,
  });
  return response.data;
};

/**
 * Execute OR-Tools CP-SAT multi-satellite optimization
 */
export const runOptimize = async (
  datasetId: string,
  timeLimitSeconds = 30.0,
  priorityWeights?: Record<string, number>,
  maximizeDataVolume = true
): Promise<ScheduleRunResponse> => {
  const response = await apiClient.post<ScheduleRunResponse>('/schedules/optimize', {
    dataset_id: datasetId,
    time_limit_seconds: timeLimitSeconds,
    priority_weights: priorityWeights || {
      '1': 10.0,
      '2': 5.0,
      '3': 2.0,
      '4': 1.0,
      '5': 0.5,
    },
    maximize_data_volume: maximizeDataVolume,
  });
  return response.data;
};

/**
 * Retrieve previous schedule run details and timeline
 */
export const getScheduleRun = async (runId: string): Promise<ScheduleRunResponse> => {
  const response = await apiClient.get<ScheduleRunResponse>(`/schedules/${runId}`);
  return response.data;
};

/**
 * Retrieve metrics and KPIs for a specific run
 */
export const getScheduleMetrics = async (runId: string): Promise<ScheduleMetrics> => {
  const response = await apiClient.get<ScheduleMetrics>(`/schedules/${runId}/metrics`);
  return response.data;
};

/**
 * Register a ground station outage and trigger event-driven re-optimization
 */
export const createOutage = async (payload: {
  station_id: string;
  start_time: string;
  end_time: string;
  reason: string;
  dataset_id?: string;
  auto_reoptimize?: boolean;
  notes?: string;
}) => {
  const response = await apiClient.post('/outages', payload);
  return response.data;
};

/**
 * List ground station outages
 */
export const listOutages = async (params?: {
  station_id?: string;
  dataset_id?: string;
  status?: string;
}) => {
  const response = await apiClient.get('/outages', { params });
  return response.data;
};

/**
 * Resolve/close an outage and restore station scheduling capacity
 */
export const resolveOutage = async (outageId: string, autoReoptimize = true) => {
  const response = await apiClient.post(`/outages/${outageId}/resolve`, null, {
    params: { auto_reoptimize: autoReoptimize },
  });
  return response.data;
};

/**
 * List pass execution tracking records
 */
export const listExecutions = async (params?: {
  dataset_id?: string;
  schedule_run_id?: string;
  status?: string;
  is_locked?: boolean;
}): Promise<PassExecutionRead[]> => {
  const response = await apiClient.get<PassExecutionRead[]>('/executions', { params });
  return response.data;
};

/**
 * Get single pass execution record
 */
export const getExecution = async (passId: string): Promise<PassExecutionRead> => {
  const response = await apiClient.get<PassExecutionRead>(`/executions/${passId}`);
  return response.data;
};

/**
 * Transition a pass to a new execution state
 */
export const transitionPassExecution = async (
  passId: string,
  req: PassTransitionRequest
): Promise<PassExecutionRead> => {
  const response = await apiClient.post<PassExecutionRead>(`/executions/${passId}/transition`, req);
  return response.data;
};

/**
 * Get execution summary metrics across a scenario
 */
export const getExecutionSummary = async (datasetId?: string): Promise<PassExecutionSummary> => {
  const response = await apiClient.get<PassExecutionSummary>('/executions/summary', {
    params: { dataset_id: datasetId },
  });
  return response.data;
};

/**
 * Get comprehensive operational analytics for a schedule run
 */
export const getOperationalAnalytics = async (
  runId: string
): Promise<OperationalAnalyticsResponse> => {
  const response = await apiClient.get<OperationalAnalyticsResponse>(`/analytics/runs/${runId}`);
  return response.data;
};

/**
 * Get deterministic rule-based deadline risk analysis for a schedule run
 */
export const getDeadlineRisks = async (
  runId: string
): Promise<DeadlineRiskSummary> => {
  const response = await apiClient.get<DeadlineRiskSummary>(`/analytics/runs/${runId}/deadline-risks`);
  return response.data;
};

/**
 * Download real mission schedule report in CSV or JSON format
 */
export const downloadMissionReport = async (
  runId: string,
  format: 'json' | 'csv'
): Promise<void> => {
  const response = await apiClient.get(`/analytics/runs/${runId}/export`, {
    params: { format },
    responseType: format === 'csv' ? 'blob' : 'json',
  });

  const blob =
    format === 'csv'
      ? (response.data as Blob)
      : new Blob([JSON.stringify(response.data, null, 2)], {
          type: 'application/json',
        });

  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `mission_report_${runId}.${format}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};


/**
 * Helper to parse backend error details cleanly
 */
export const getApiErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const serverError = error as AxiosError<ApiErrorResponse>;
    if (serverError.response?.data?.detail) {
      return serverError.response.data.detail;
    }
    if (serverError.message) {
      return serverError.message;
    }
  }
  return 'Network or server communication failure.';
};
