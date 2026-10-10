"""Pydantic schemas and state machine definitions for Pass Execution Tracking."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import Field, model_validator
from .common import OrbitOptBaseModel


class PassExecutionStatus(str, Enum):
    """Execution state machine states for scheduled satellite passes."""

    SCHEDULED = "SCHEDULED"
    ACQUIRING = "ACQUIRING"
    TRANSMITTING = "TRANSMITTING"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"


# Explicitly defined legal state transitions
# Key: from_status -> Set[to_status]
LEGAL_STATE_TRANSITIONS: Dict[PassExecutionStatus, Set[PassExecutionStatus]] = {
    PassExecutionStatus.SCHEDULED: {
        PassExecutionStatus.ACQUIRING,
        PassExecutionStatus.MISSED,
        PassExecutionStatus.CANCELLED,
    },
    PassExecutionStatus.ACQUIRING: {
        PassExecutionStatus.TRANSMITTING,
        PassExecutionStatus.MISSED,
        PassExecutionStatus.CANCELLED,
    },
    PassExecutionStatus.TRANSMITTING: {
        PassExecutionStatus.COMPLETED,
        PassExecutionStatus.MISSED,
        PassExecutionStatus.CANCELLED,
    },
    # Terminal states have NO outgoing legal transitions
    PassExecutionStatus.COMPLETED: set(),
    PassExecutionStatus.MISSED: set(),
    PassExecutionStatus.CANCELLED: set(),
}

# Passes in these states are locked against ordinary re-optimization and emergency preemption
LOCKED_EXECUTION_STATES: Set[PassExecutionStatus] = {
    PassExecutionStatus.ACQUIRING,
    PassExecutionStatus.TRANSMITTING,
    PassExecutionStatus.COMPLETED,
}


def is_legal_transition(from_status: PassExecutionStatus, to_status: PassExecutionStatus) -> bool:
    """Check if state transition is mathematically valid according to the state machine graph."""
    allowed = LEGAL_STATE_TRANSITIONS.get(from_status, set())
    return to_status in allowed


def is_status_locked(status: PassExecutionStatus) -> bool:
    """Check if given execution status requires locking against rescheduling."""
    return status in LOCKED_EXECUTION_STATES


class PassExecutionTransitionEvent(OrbitOptBaseModel):
    """Log record of a state transition."""

    from_status: Optional[str] = Field(default=None, description="Previous execution state")
    to_status: str = Field(..., description="Target execution state")
    timestamp: datetime = Field(..., description="UTC timestamp of the transition")
    actual_start_time: Optional[datetime] = Field(default=None, description="Actual start time if recorded")
    actual_end_time: Optional[datetime] = Field(default=None, description="Actual end time if recorded")
    actual_data_delivered_gb: Optional[float] = Field(default=None, description="Delivered data in GB")
    measured_transfer_rate_mbps: Optional[float] = Field(default=None, description="Measured rate in Mbps")
    telemetry_source: str = Field(default="simulated", description="Source of update (simulated/manual/etc)")
    notes: Optional[str] = Field(default=None, description="Operator or subsystem notes")


class PassTransitionRequest(OrbitOptBaseModel):
    """Payload to request an execution state machine transition."""

    to_status: PassExecutionStatus = Field(..., description="Target state to transition pass into")
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Transition event timestamp in UTC (defaults to current time)",
    )
    actual_start_time: Optional[datetime] = Field(
        default=None,
        description="Actual contact / downlink acquisition start time in UTC",
    )
    actual_end_time: Optional[datetime] = Field(
        default=None,
        description="Actual contact / transmission completion time in UTC",
    )
    actual_data_delivered_gb: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Actual measured delivered data volume in GB",
    )
    measured_transfer_rate_mbps: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Actual measured transfer rate in Mbps",
    )
    telemetry_source: str = Field(
        default="operator_manual",
        description="Source/provenance of telemetry update (e.g. 'operator_manual', 'simulated')",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Operational context or justification",
    )

    @model_validator(mode="after")
    def validate_timestamp_ordering(self) -> "PassTransitionRequest":
        if self.actual_start_time and self.actual_end_time:
            if self.actual_end_time < self.actual_start_time:
                raise ValueError("actual_end_time cannot be earlier than actual_start_time")
        return self


class PassExecutionRead(OrbitOptBaseModel):
    """Read representation of a pass execution lifecycle record."""

    id: str = Field(..., description="Unique execution record ID")
    pass_id: str = Field(..., description="Target pass identifier")
    dataset_id: Optional[str] = Field(default=None, description="Associated scenario dataset ID")
    schedule_run_id: Optional[str] = Field(default=None, description="Origin schedule run ID")
    satellite_id: str = Field(..., description="Satellite identifier")
    ground_station_id: str = Field(..., description="Ground station identifier")
    status: PassExecutionStatus = Field(..., description="Current state machine execution status")
    is_locked: bool = Field(..., description="Whether pass is locked against rescheduling")

    # Planned values
    planned_start_time: datetime = Field(..., description="Planned contact start time")
    planned_end_time: datetime = Field(..., description="Planned contact end time")
    planned_data_volume_gb: float = Field(..., description="Planned data volume in GB")
    estimated_transfer_rate_mbps: float = Field(..., description="Estimated downlink transfer rate in Mbps")

    # Actual telemetry measurements
    actual_start_time: Optional[datetime] = Field(default=None, description="Actual pass start time")
    actual_end_time: Optional[datetime] = Field(default=None, description="Actual pass end time")
    actual_data_delivered_gb: Optional[float] = Field(default=None, description="Actual delivered data volume in GB")
    measured_transfer_rate_mbps: Optional[float] = Field(default=None, description="Actual measured transfer rate in Mbps")

    telemetry_source: str = Field(default="simulated", description="Source of telemetry update")
    notes: Optional[str] = Field(default=None, description="Operational notes")
    transition_history: List[PassExecutionTransitionEvent] = Field(
        default_factory=list,
        description="Audit log of state transitions",
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


class PassExecutionSummary(OrbitOptBaseModel):
    """High-level summary of execution states across an active schedule."""

    total_passes: int
    scheduled_count: int
    acquiring_count: int
    transmitting_count: int
    completed_count: int
    missed_count: int
    cancelled_count: int
    locked_passes_count: int
    total_planned_volume_gb: float
    total_actual_delivered_gb: float
