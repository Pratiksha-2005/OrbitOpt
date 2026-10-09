from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import List
from pydantic import BaseModel, Field, model_validator

class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class SolverStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"

def _validate_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("Datetime must be timezone-aware")
    if dt.tzinfo.utcoffset(dt).total_seconds() != 0:
        raise ValueError("Datetime must be strictly in UTC")
    return dt

class TimeWindow(BaseModel):
    start_time: datetime
    end_time: datetime

    @model_validator(mode='after')
    def check_time_ordering_and_utc(self) -> 'TimeWindow':
        # validate_utc ensures the datetime objects have timezone info and it is UTC
        self.start_time = _validate_utc(self.start_time)
        self.end_time = _validate_utc(self.end_time)
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be strictly greater than start_time")
        return self

class Satellite(BaseModel):
    id: str = Field(..., min_length=1)
    name: str

class GroundStation(BaseModel):
    """
    Ground station details.
    Rates are given in Megabits per second (Mbps).
    Volumes are typically given in Megabytes (MB).
    To calculate time from volume: (volume_mb * 8) / downlink_rate_mbps
    """
    id: str = Field(..., min_length=1)
    name: str
    downlink_rate_mbps: float = Field(..., gt=0.0)

class VisibilityWindow(TimeWindow):
    id: str = Field(..., min_length=1)
    satellite_id: str = Field(..., min_length=1)
    ground_station_id: str = Field(..., min_length=1)

class DownlinkRequest(BaseModel):
    id: str = Field(..., min_length=1)
    satellite_id: str = Field(..., min_length=1)
    data_volume_mb: float = Field(..., ge=0.0)
    priority: Priority
    
    # Phase 5: Dynamic Priority Factors (Backward compatible defaults)
    created_at: datetime | None = None
    emergency_severity: float = Field(0.0, ge=0.0, le=100.0)
    deadline_urgency: float = Field(0.0, ge=0.0, le=100.0)
    data_freshness: float = Field(0.0, ge=0.0, le=100.0)
    verified_emergency: bool = False

class ScheduledTask(TimeWindow):
    id: str = Field(..., min_length=1)
    request_id: str = Field(..., min_length=1)
    visibility_window_id: str = Field(..., min_length=1)
    data_transmitted_mb: float = Field(..., ge=0.0)

class ScheduleResult(BaseModel):
    id: str = Field(..., min_length=1)
    scheduled_tasks: List[ScheduledTask]
    rejected_request_ids: List[str]
    objective_value: float = Field(..., description="Priority-weighted data objective.")
    runtime_seconds: float = Field(..., ge=0.0)
    solver_status: SolverStatus
    is_valid: bool
    validation_errors: List[str] = Field(default_factory=list)
