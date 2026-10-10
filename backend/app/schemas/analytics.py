"""Operational Analytics, Metrics, and Mission Report schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field
from .common import OrbitOptBaseModel
from .schedule import AlgorithmType, ScheduleStatus


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MetricDoc(OrbitOptBaseModel):
    """Documentation for a specific calculated operational metric."""
    name: str
    units: str
    formula: str
    denominator: str
    handling_missing_data: str


class PlannedVsActualData(OrbitOptBaseModel):
    pass_id: str
    satellite_id: str
    ground_station_id: str
    priority: int
    execution_status: str
    planned_data_volume_gb: float
    actual_data_delivered_gb: Optional[float] = None
    telemetry_source: str
    is_delivered: bool


class StationAvailabilityMetric(OrbitOptBaseModel):
    station_id: str
    station_name: str
    horizon_hours: float
    outage_hours: float
    available_hours: float
    availability_percentage: float
    active_outages_count: int


class StationUtilizationMetric(OrbitOptBaseModel):
    station_id: str
    station_name: str
    active_transmission_seconds: float
    total_occupied_seconds_with_buffers: float
    transmission_utilization_pct: float
    total_occupancy_pct: float


class BenchmarkComparisonMetric(OrbitOptBaseModel):
    baseline_run_id: Optional[str] = None
    baseline_algorithm: str = "baseline_fcfs"
    optimized_run_id: Optional[str] = None
    optimized_algorithm: str = "cp_sat_optimizer"
    dataset_id: str
    
    # Volume metrics
    baseline_volume_gb: float
    optimized_volume_gb: float
    volume_improvement_gb: float
    volume_improvement_pct: float
    
    # Objective value
    baseline_objective: float
    optimized_objective: float
    objective_improvement_pct: float
    
    # Pass counts
    baseline_scheduled_passes: int
    optimized_scheduled_passes: int
    scheduled_passes_delta: int
    
    # Priority satisfaction
    baseline_priority_satisfaction_pct: float
    optimized_priority_satisfaction_pct: float
    priority_satisfaction_delta_pct: float

    # Critical request service rate
    baseline_critical_service_rate_pct: float
    optimized_critical_service_rate_pct: float
    critical_service_rate_delta_pct: float
    
    # Runtime
    baseline_runtime_ms: float
    optimized_runtime_ms: float
    runtime_ratio: float


class OperationalAnalyticsResponse(OrbitOptBaseModel):
    """Integrated operational analytics and mission performance metrics."""

    run_id: str
    dataset_id: str
    dataset_name: str
    algorithm: AlgorithmType
    solver_status: str
    solver_status_detail: Optional[str] = None
    execution_time_ms: float
    objective_value: float
    is_valid: bool
    validation_failure_count: int
    validation_violations: List[str] = Field(default_factory=list)
    created_at: datetime

    # 1. Pass allocation metrics
    total_passes: int
    scheduled_passes_count: int
    unscheduled_passes_count: int
    scheduled_percentage: float

    # 2. Planned vs Actually Delivered Data
    planned_data_volume_gb: float
    actual_delivered_data_gb: float
    confirmed_delivery_ratio_pct: Optional[float] = None
    planned_vs_actual_items: List[PlannedVsActualData] = Field(default_factory=list)

    # 3. Execution state machine counts
    completed_passes_count: int
    missed_passes_count: int
    cancelled_passes_count: int
    acquiring_passes_count: int
    transmitting_passes_count: int
    scheduled_execution_count: int
    locked_passes_count: int

    # 4. Critical priority service rate
    critical_scheduled_count: int
    critical_total_count: int
    critical_service_rate_pct: float
    critical_denominator_definition: str = (
        "Total priority 1 (Critical) contact opportunities submitted in scenario dataset"
    )

    # 5. Deadline satisfaction
    total_evaluated_deadlines: int
    deadline_satisfied_count: int
    deadline_missed_count: int
    deadline_satisfaction_rate_pct: float
    missed_deadline_rate_pct: float

    # 6. Waiting time metrics (seconds from availability/queue to transmission start)
    mean_wait_time_seconds: Optional[float] = None
    median_wait_time_seconds: Optional[float] = None
    p90_wait_time_seconds: Optional[float] = None
    p95_wait_time_seconds: Optional[float] = None
    wait_time_basis: str = (
        "Elapsed duration from pass window start to scheduled transmission start"
    )

    # 7. Ground station availability after outages
    overall_availability_pct: float
    total_station_horizon_hours: float
    total_outage_hours: float
    available_station_hours: float
    station_availability: List[StationAvailabilityMetric] = Field(default_factory=list)

    # 8. Transmission utilization and resource occupancy (including setup buffers)
    transmission_utilization_pct: float
    total_occupancy_pct: float
    setup_buffer_seconds_used: float
    station_utilizations: List[StationUtilizationMetric] = Field(default_factory=list)

    # 9. Outage impact metrics
    outage_count: int
    affected_passes_count: int

    # 10. FCFS vs CP-SAT Benchmark comparison (if comparable run available)
    benchmark_comparison: Optional[BenchmarkComparisonMetric] = None

    # 11. Data quality & provenance flags
    has_live_backend_data: bool = True
    has_manual_telemetry: bool = False
    has_simulated_telemetry: bool = True
    uncalculated_metrics: List[str] = Field(default_factory=list)

    # 12. Documentation of formulas and denominators
    metric_documentation: Dict[str, MetricDoc] = Field(default_factory=dict)


class DeadlineRiskItem(OrbitOptBaseModel):
    """Deterministic rule-based deadline risk evaluation for an individual pass."""

    pass_id: str
    satellite_id: str
    ground_station_id: str
    priority: int
    deadline: datetime
    is_scheduled: bool
    scheduled_start_time: Optional[datetime] = None
    scheduled_end_time: Optional[datetime] = None
    execution_status: str
    risk_level: RiskLevel
    slack_seconds: Optional[float] = None
    has_outage_conflict: bool
    explanation: str
    analysis_method: str = "RULE_BASED_DETERMINISTIC"


class DeadlineRiskSummary(OrbitOptBaseModel):
    """Aggregated deadline risk summary and itemized risk register."""

    run_id: str
    dataset_id: str
    evaluated_at: datetime
    total_requests: int
    low_risk_count: int
    medium_risk_count: int
    high_risk_count: int
    critical_risk_count: int
    method_disclaimer: str = (
        "Rule-based deterministic deadline risk analysis based on remaining time, contact duration, "
        "antenna setup margins, and station outages. Not machine-learning prediction."
    )
    items: List[DeadlineRiskItem] = Field(default_factory=list)
