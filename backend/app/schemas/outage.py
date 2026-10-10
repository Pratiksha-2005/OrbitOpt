"""Pydantic schemas for Ground Station Outages and Event-Driven Rescheduling."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import Field, model_validator
from .common import OrbitOptBaseModel
from .schedule import ScheduleRunResponse


class OutageStatus(str, Enum):
    """Lifecycle status of a ground station outage."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class OutageCreate(OrbitOptBaseModel):
    """Payload for creating and registering a ground station outage."""

    station_id: str = Field(..., min_length=1, description="Ground station identifier (e.g. 'GS-01')")
    start_time: datetime = Field(..., description="Outage window start time in UTC")
    end_time: datetime = Field(..., description="Outage window end time in UTC")
    reason: str = Field(..., min_length=1, max_length=255, description="Reason for outage (e.g. 'Hardware Maintenance')")
    dataset_id: Optional[str] = Field(default=None, description="Optional target scenario dataset ID")
    auto_reoptimize: bool = Field(
        default=True,
        description="Whether to automatically trigger safe re-optimization on affected schedules",
    )
    notes: Optional[str] = Field(default=None, description="Additional operator or technician notes")

    @model_validator(mode="after")
    def validate_interval_and_timezone(self) -> "OutageCreate":
        st = _ensure_utc(self.start_time)
        et = _ensure_utc(self.end_time)
        if et <= st:
            raise ValueError(
                f"Outage end_time ({et.isoformat()}) must be strictly after start_time ({st.isoformat()})"
            )
        object.__setattr__(self, "start_time", st)
        object.__setattr__(self, "end_time", et)
        return self


class OutageUpdate(OrbitOptBaseModel):
    """Payload for updating an outage record."""

    status: Optional[OutageStatus] = Field(default=None, description="Updated outage status")
    reason: Optional[str] = Field(default=None, description="Updated reason")
    end_time: Optional[datetime] = Field(default=None, description="Adjusted end time in UTC")
    notes: Optional[str] = Field(default=None, description="Updated technician notes")

    @model_validator(mode="after")
    def validate_utc(self) -> "OutageUpdate":
        if self.end_time is not None:
            object.__setattr__(self, "end_time", _ensure_utc(self.end_time))
        return self


class OutageRead(OrbitOptBaseModel):
    """Public representation of a ground station outage."""

    id: str = Field(..., description="Unique outage record identifier")
    station_id: str = Field(..., description="Ground station identifier")
    dataset_id: Optional[str] = Field(default=None, description="Associated dataset ID")
    start_time: datetime = Field(..., description="Outage start time in UTC")
    end_time: datetime = Field(..., description="Outage end time in UTC")
    duration_seconds: float = Field(..., description="Total outage duration in seconds")
    reason: str = Field(..., description="Outage justification")
    status: OutageStatus = Field(..., description="Current status (active/resolved/cancelled)")
    auto_reoptimized: bool = Field(default=False, description="Whether automatic re-optimization was performed")
    reoptimization_run_id: Optional[str] = Field(default=None, description="ID of generated re-optimized schedule run")
    notes: Optional[str] = Field(default=None, description="Technician notes")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


class OutageActionResponse(OrbitOptBaseModel):
    """Response returned when an outage is created, modified, or resolved."""

    outage: OutageRead = Field(..., description="The created or modified outage record")
    affected_pass_ids: List[str] = Field(default_factory=list, description="IDs of contact passes directly overlapping the outage")
    reoptimized_schedule: Optional[ScheduleRunResponse] = Field(
        default=None,
        description="The safe re-optimized schedule run outcome, if automatic re-optimization was triggered",
    )
    message: str = Field(..., description="Summary status message for operators")
