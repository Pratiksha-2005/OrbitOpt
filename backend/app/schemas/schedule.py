"""Schedule request, allocation, and response schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import Field, model_validator
from .common import OrbitOptBaseModel
from .metrics import ScheduleMetrics


class AlgorithmType(str, Enum):
    """Supported scheduling algorithm types."""

    BASELINE_FCFS = "baseline_fcfs"
    CP_SAT_OPTIMIZER = "cp_sat_optimizer"
    MOCK_INTEGRATION = "mock_integration"


class ScheduleStatus(str, Enum):
    """Execution status of a scheduling run."""

    COMPLETED = "completed"
    FAILED = "failed"
    RUNNING = "running"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"


class ScheduledPass(OrbitOptBaseModel):
    """Allocated pass in the scheduled timeline."""

    pass_id: str = Field(..., description="Unique ID of the scheduled pass")
    satellite_id: str = Field(..., description="Satellite identifier")
    ground_station_id: str = Field(..., description="Ground station assigned")
    start_time: datetime = Field(..., description="Pass start time in UTC")
    end_time: datetime = Field(..., description="Pass end time in UTC")
    duration_seconds: float = Field(..., description="Contact duration in seconds")
    data_volume_gb: float = Field(..., description="Downlinked data volume in GB")
    transferable_data_gb: Optional[float] = Field(
        default=None,
        description="Transferable data in GB: min(pending_data, effective_data_rate * duration)",
    )
    priority: int = Field(..., description="Pass priority level [1-5]")
    dynamic_score: Optional[float] = Field(
        default=None,
        description="Multi-factor dynamic priority score [0.0 - 100.0] combining E, U, F, W",
    )
    score_breakdown: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Breakdown of individual factor scores (emergency, urgency, freshness, waiting) and rationale",
    )
    execution_status: str = Field(
        default="SCHEDULED",
        description="Pass execution lifecycle status (SCHEDULED, ACQUIRING, TRANSMITTING, COMPLETED, MISSED, CANCELLED)",
    )
    is_locked: bool = Field(
        default=False,
        description="Whether pass is locked against ordinary re-optimization and emergency preemption",
    )
    actual_start_time: Optional[datetime] = Field(
        default=None,
        description="Actual execution start time in UTC",
    )
    actual_end_time: Optional[datetime] = Field(
        default=None,
        description="Actual execution end time in UTC",
    )
    actual_data_delivered_gb: Optional[float] = Field(
        default=None,
        description="Actual measured delivered data volume in GB",
    )
    measured_transfer_rate_mbps: Optional[float] = Field(
        default=None,
        description="Actual measured transfer rate in Mbps",
    )
    estimated_transfer_rate_mbps: Optional[float] = Field(
        default=None,
        description="Estimated transfer rate in Mbps",
    )

    @model_validator(mode="after")
    def sync_transferable_data(self) -> "ScheduledPass":
        if self.transferable_data_gb is None:
            object.__setattr__(self, "transferable_data_gb", self.data_volume_gb)
        return self



class UnassignedPass(OrbitOptBaseModel):
    """Details of a pass that could not be scheduled due to conflicts or constraints."""

    pass_id: str = Field(..., description="Unique ID of the unassigned pass")
    satellite_id: str = Field(..., description="Satellite identifier")
    ground_station_id: str = Field(..., description="Conflicted Ground station")
    start_time: datetime = Field(..., description="Pass start time in UTC")
    end_time: datetime = Field(..., description="Pass end time in UTC")
    priority: int = Field(..., description="Pass priority level")
    reason: str = Field(..., description="Explanation why the pass could not be scheduled (e.g., 'Station overlap with PASS-001')")
    dynamic_score: Optional[float] = Field(
        default=None,
        description="Multi-factor dynamic priority score [0.0 - 100.0]",
    )
    score_breakdown: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Breakdown of individual factor scores",
    )


class DynamicWeightsInput(OrbitOptBaseModel):
    """Configurable weights for dynamic multi-factor scoring (E+U+F+W = 1.0)."""

    emergency_weight: float = Field(default=0.40, ge=0.0, le=1.0, description="Emergency tier weight (E)")
    urgency_weight: float = Field(default=0.30, ge=0.0, le=1.0, description="Deadline urgency weight (U)")
    freshness_weight: float = Field(default=0.10, ge=0.0, le=1.0, description="Data freshness weight (F)")
    waiting_weight: float = Field(default=0.20, ge=0.0, le=1.0, description="Waiting anti-starvation weight (W)")

    @model_validator(mode="after")
    def validate_sum(self) -> "DynamicWeightsInput":
        total = self.emergency_weight + self.urgency_weight + self.freshness_weight + self.waiting_weight
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"Dynamic weights must sum to 1.0, got {total:.4f}")
        return self


class BaselineScheduleRequest(OrbitOptBaseModel):
    """Request payload for running FCFS baseline schedule."""

    dataset_id: str = Field(..., description="Dataset ID to execute baseline on")
    setup_time_seconds: int = Field(
        default=120,
        description="Required re-pointing/calibration buffer between passes at the same station (seconds)",
        ge=0,
    )
    dynamic_weights: Optional[DynamicWeightsInput] = Field(
        default=None,
        description="Optional weights for dynamic priority calculation",
    )


class OptimizeScheduleRequest(OrbitOptBaseModel):
    """Request payload for running CP-SAT optimization."""

    dataset_id: str = Field(..., description="Dataset ID to optimize")
    time_limit_seconds: float = Field(
        default=30.0,
        description="Maximum solver execution time limit in seconds",
        gt=0.0,
        le=300.0,
    )
    setup_time_seconds: int = Field(
        default=120,
        description="Antenna slew and re-configuration buffer time in seconds",
        ge=0,
    )
    priority_weights: Optional[Dict[str, float]] = Field(
        default_factory=lambda: {
            "1": 10.0,
            "2": 5.0,
            "3": 2.0,
            "4": 1.0,
            "5": 0.5,
        },
        description="Custom weights assigned to priority levels 1-5 (1=Highest priority)",
    )
    dynamic_weights: Optional[DynamicWeightsInput] = Field(
        default=None,
        description="Weights for dynamic multi-factor scoring (Emergency, Urgency, Freshness, Waiting)",
    )
    maximize_data_volume: bool = Field(
        default=True,
        description="Whether objective function prioritizes total downlinked data volume alongside pass count",
    )


class ScheduleRunResponse(OrbitOptBaseModel):
    """Standardized response schema for scheduling runs."""

    run_id: str = Field(..., description="Unique identifier of this scheduling run")
    dataset_id: str = Field(..., description="ID of the dataset evaluated")
    algorithm: AlgorithmType = Field(..., description="Algorithm used for this run")
    status: ScheduleStatus = Field(..., description="Execution status")
    is_mock: bool = Field(
        default=False,
        description="Flag indicating if results were generated by the integration mock boundary rather than Developer 1's solver",
    )
    is_valid: bool = Field(
        default=True,
        description="Independent schedule validation flag (True if conflict-free and setup-time compliant)",
    )
    validation_violations: List[str] = Field(
        default_factory=list,
        description="List of detected schedule violations from the independent validator (empty if valid)",
    )
    solver_status_detail: Optional[str] = Field(
        default=None,
        description="Detailed CP-SAT solver status (e.g., 'OPTIMAL', 'FEASIBLE', 'INFEASIBLE', 'MODEL_INVALID')",
    )
    created_at: datetime = Field(..., description="Timestamp when schedule was run in UTC")
    execution_time_ms: float = Field(..., description="Algorithm execution time in milliseconds")
    scheduled_passes: List[ScheduledPass] = Field(default_factory=list, description="Allocated passes")
    unassigned_passes: List[UnassignedPass] = Field(default_factory=list, description="Unallocated passes")
    metrics: ScheduleMetrics = Field(..., description="KPI and summary metrics for this run")
