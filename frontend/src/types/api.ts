/**
 * TypeScript Type Definitions for OrbitOpt
 * Derived from docs/API_CONTRACT.md (Backend v1 API Contract)
 */

export type PriorityLevel = 1 | 2 | 3 | 4 | 5;

export type AlgorithmType = 'baseline_fcfs' | 'cp_sat_optimizer' | 'mock_integration';

export type ScheduleStatus = 'completed' | 'failed' | 'running' | 'infeasible' | 'timeout';

export interface GroundStation {
  station_id: string;
  name: string;
  latitude_deg: number;
  longitude_deg: number;
  elevation_mask_deg?: number;
  max_concurrent_passes?: number;
  supported_bands?: string[];
}

export interface SatellitePass {
  pass_id: string;
  satellite_id: string;
  ground_station_id: string;
  start_time: string; // ISO 8601 UTC
  end_time: string;   // ISO 8601 UTC
  max_elevation_deg: number;
  priority: PriorityLevel;
  data_volume_gb: number;
  pending_data_gb?: number;
  effective_data_rate_mbps?: number;
  channel_band?: string;
}

export interface Dataset {
  dataset_id: string;
  name: string;
  description?: string;
  ground_station_count: number;
  satellite_pass_count: number;
  created_at: string;
  ground_stations: GroundStation[];
  satellite_passes: SatellitePass[];
}

export interface DatasetSummary {
  dataset_id: string;
  name: string;
  description?: string;
  ground_station_count: number;
  satellite_pass_count: number;
  created_at: string;
}

export interface DynamicWeights {
  emergency_weight: number;
  urgency_weight: number;
  freshness_weight: number;
  waiting_weight: number;
}

export interface ScoreBreakdown {
  emergency_score: number;
  urgency_score: number;
  freshness_score: number;
  waiting_score: number;
  combined_score: number;
  explanation: string;
}

export interface ScheduledPass {
  pass_id: string;
  satellite_id: string;
  ground_station_id: string;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  data_volume_gb: number;
  transferable_data_gb: number;
  priority: PriorityLevel;
  dynamic_score?: number;
  score_breakdown?: ScoreBreakdown;
}

export interface UnassignedPass {
  pass_id: string;
  satellite_id: string;
  ground_station_id: string;
  start_time: string;
  end_time: string;
  priority: PriorityLevel;
  reason: string;
  dynamic_score?: number;
  score_breakdown?: ScoreBreakdown;
}

export interface ScheduleMetrics {
  total_passes: number;
  scheduled_passes_count: number;
  unassigned_passes_count: number;
  scheduled_percentage: number;
  total_data_downlinked_gb: number;
  total_pending_data_gb: number;
  total_contact_time_seconds: number;
  objective_value: number;
  priority_satisfaction_rate: number;
  priority_breakdown: Record<string, number>;
  ground_station_utilization: Record<string, number>;
  conflicts_detected: number;
  average_dynamic_score?: number;
}

export interface ScheduleRunResponse {
  run_id: string;
  dataset_id: string;
  algorithm: AlgorithmType;
  status: ScheduleStatus;
  is_mock: boolean;
  is_valid: boolean;
  validation_violations: string[];
  solver_status_detail?: string; // 'OPTIMAL' | 'FEASIBLE' | 'INFEASIBLE' | 'TIMEOUT'
  created_at: string;
  execution_time_ms: number;
  scheduled_passes: ScheduledPass[];
  unassigned_passes: UnassignedPass[];
  metrics: ScheduleMetrics;
}

export interface ApiErrorResponse {
  detail: string;
  error_code: string;
  details?: unknown[];
}

export interface HealthCheckResponse {
  status: string;
  version: string;
  timestamp: string;
  environment: string;
  database_connected: boolean;
}

export interface OutageRead {
  id: string;
  station_id: string;
  dataset_id?: string;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  reason: string;
  status: 'active' | 'resolved' | 'cancelled';
  auto_reoptimized: boolean;
  reoptimization_run_id?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface OutageCreate {
  station_id: string;
  start_time: string;
  end_time: string;
  reason: string;
  dataset_id?: string;
  auto_reoptimize?: boolean;
  notes?: string;
}

export interface OutageActionResponse {
  outage: OutageRead;
  affected_pass_ids: string[];
  reoptimized_schedule?: ScheduleRunResponse;
  message: string;
}
