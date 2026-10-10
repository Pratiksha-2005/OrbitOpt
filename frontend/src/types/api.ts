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
  execution_status?: PassExecutionStatus;
  is_locked?: boolean;
  actual_start_time?: string;
  actual_end_time?: string;
  actual_data_delivered_gb?: number;
  measured_transfer_rate_mbps?: number;
  estimated_transfer_rate_mbps?: number;
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

export type PassExecutionStatus =
  | 'SCHEDULED'
  | 'ACQUIRING'
  | 'TRANSMITTING'
  | 'COMPLETED'
  | 'MISSED'
  | 'CANCELLED';

export interface PassExecutionTransitionEvent {
  from_status?: string | null;
  to_status: string;
  timestamp: string;
  actual_start_time?: string | null;
  actual_end_time?: string | null;
  actual_data_delivered_gb?: number | null;
  measured_transfer_rate_mbps?: number | null;
  telemetry_source: string;
  notes?: string | null;
}

export interface PassExecutionRead {
  id: string;
  pass_id: string;
  dataset_id?: string;
  schedule_run_id?: string;
  satellite_id: string;
  ground_station_id: string;
  status: PassExecutionStatus;
  is_locked: boolean;
  planned_start_time: string;
  planned_end_time: string;
  planned_data_volume_gb: number;
  estimated_transfer_rate_mbps: number;
  actual_start_time?: string | null;
  actual_end_time?: string | null;
  actual_data_delivered_gb?: number | null;
  measured_transfer_rate_mbps?: number | null;
  telemetry_source: string;
  notes?: string | null;
  transition_history: PassExecutionTransitionEvent[];
  created_at: string;
  updated_at: string;
}

export interface PassTransitionRequest {
  to_status: PassExecutionStatus;
  timestamp?: string;
  actual_start_time?: string;
  actual_end_time?: string;
  actual_data_delivered_gb?: number;
  measured_transfer_rate_mbps?: number;
  telemetry_source?: string;
  notes?: string;
}

export interface PassExecutionSummary {
  total_passes: number;
  scheduled_count: number;
  acquiring_count: number;
  transmitting_count: number;
  completed_count: number;
  missed_count: number;
  cancelled_count: number;
  locked_passes_count: number;
  total_planned_volume_gb: number;
  total_actual_delivered_gb: number;
}

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface MetricDoc {
  name: string;
  units: string;
  formula: string;
  denominator: string;
  handling_missing_data: string;
}

export interface PlannedVsActualData {
  pass_id: string;
  satellite_id: string;
  ground_station_id: string;
  priority: number;
  execution_status: string;
  planned_data_volume_gb: number;
  actual_data_delivered_gb?: number | null;
  telemetry_source: string;
  is_delivered: boolean;
}

export interface StationAvailabilityMetric {
  station_id: string;
  station_name: string;
  horizon_hours: number;
  outage_hours: number;
  available_hours: number;
  availability_percentage: number;
  active_outages_count: number;
}

export interface StationUtilizationMetric {
  station_id: string;
  station_name: string;
  active_transmission_seconds: number;
  total_occupied_seconds_with_buffers: number;
  transmission_utilization_pct: number;
  total_occupancy_pct: number;
}

export interface BenchmarkComparisonMetric {
  baseline_run_id?: string | null;
  baseline_algorithm: string;
  optimized_run_id?: string | null;
  optimized_algorithm: string;
  dataset_id: string;
  baseline_volume_gb: number;
  optimized_volume_gb: number;
  volume_improvement_gb: number;
  volume_improvement_pct: number;
  baseline_objective: number;
  optimized_objective: number;
  objective_improvement_pct: number;
  baseline_scheduled_passes: number;
  optimized_scheduled_passes: number;
  scheduled_passes_delta: number;
  baseline_priority_satisfaction_pct: number;
  optimized_priority_satisfaction_pct: number;
  priority_satisfaction_delta_pct: number;
  baseline_critical_service_rate_pct: number;
  optimized_critical_service_rate_pct: number;
  critical_service_rate_delta_pct: number;
  baseline_runtime_ms: number;
  optimized_runtime_ms: number;
  runtime_ratio: number;
}

export interface OperationalAnalyticsResponse {
  run_id: string;
  dataset_id: string;
  dataset_name: string;
  algorithm: string;
  solver_status: string;
  solver_status_detail?: string | null;
  execution_time_ms: number;
  objective_value: number;
  is_valid: boolean;
  validation_failure_count: number;
  validation_violations: string[];
  created_at: string;
  total_passes: number;
  scheduled_passes_count: number;
  unscheduled_passes_count: number;
  scheduled_percentage: number;
  planned_data_volume_gb: number;
  actual_delivered_data_gb: number;
  confirmed_delivery_ratio_pct?: number | null;
  planned_vs_actual_items: PlannedVsActualData[];
  completed_passes_count: number;
  missed_passes_count: number;
  cancelled_passes_count: number;
  acquiring_passes_count: number;
  transmitting_passes_count: number;
  scheduled_execution_count: number;
  locked_passes_count: number;
  critical_scheduled_count: number;
  critical_total_count: number;
  critical_service_rate_pct: number;
  critical_denominator_definition: string;
  total_evaluated_deadlines: number;
  deadline_satisfied_count: number;
  deadline_missed_count: number;
  deadline_satisfaction_rate_pct: number;
  missed_deadline_rate_pct: number;
  mean_wait_time_seconds?: number | null;
  median_wait_time_seconds?: number | null;
  p90_wait_time_seconds?: number | null;
  p95_wait_time_seconds?: number | null;
  wait_time_basis: string;
  overall_availability_pct: number;
  total_station_horizon_hours: number;
  total_outage_hours: number;
  available_station_hours: number;
  station_availability: StationAvailabilityMetric[];
  transmission_utilization_pct: number;
  total_occupancy_pct: number;
  setup_buffer_seconds_used: number;
  station_utilizations: StationUtilizationMetric[];
  outage_count: number;
  affected_passes_count: number;
  benchmark_comparison?: BenchmarkComparisonMetric | null;
  has_live_backend_data: boolean;
  has_manual_telemetry: boolean;
  has_simulated_telemetry: boolean;
  uncalculated_metrics: string[];
  metric_documentation: Record<string, MetricDoc>;
}

export interface DeadlineRiskItem {
  pass_id: string;
  satellite_id: string;
  ground_station_id: string;
  priority: number;
  deadline: string;
  is_scheduled: boolean;
  scheduled_start_time?: string | null;
  scheduled_end_time?: string | null;
  execution_status: string;
  risk_level: RiskLevel;
  slack_seconds?: number | null;
  has_outage_conflict: boolean;
  explanation: string;
  analysis_method: string;
}

export interface DeadlineRiskSummary {
  run_id: string;
  dataset_id: string;
  evaluated_at: string;
  total_requests: number;
  low_risk_count: number;
  medium_risk_count: number;
  high_risk_count: number;
  critical_risk_count: number;
  method_disclaimer: string;
  items: DeadlineRiskItem[];
}

