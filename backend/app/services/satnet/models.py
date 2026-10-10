"""Domain data models for the SatNet NASA Deep Space Network dataset."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set


class SatNetSolverStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    MODEL_INVALID = "MODEL_INVALID"
    UNKNOWN = "UNKNOWN"


@dataclass
class SatNetCandidateWindow:
    """A specific candidate tracking opportunity on a resource during a view period."""

    window_id: str
    track_id: str
    resource_id: str
    constituent_antennas: List[str]
    start_time: datetime
    end_time: datetime
    vp_start_sec: int
    vp_end_sec: int
    duration_hours: float


@dataclass
class SatNetMaintenanceInterval:
    """A planned downtime block for a specific DSN antenna dish."""

    interval_id: str
    antenna: str
    start_time: datetime
    end_time: datetime
    start_sec: int
    end_sec: int
    week: int
    year: int


@dataclass
class SatNetRequest:
    """A customer mission tracking request from SatNet."""

    track_id: str
    subject: int
    user: str
    week: int
    year: int
    duration_hours: float
    duration_min_hours: float
    setup_time_minutes: int
    teardown_time_minutes: int
    time_window_start_sec: int
    time_window_end_sec: int
    time_window_start: datetime
    time_window_end: datetime
    candidate_resources: List[str] = field(default_factory=list)
    candidate_windows: List[SatNetCandidateWindow] = field(default_factory=list)


@dataclass
class SatNetScenario:
    """A normalized weekly scheduling problem scenario parsed from SatNet."""

    name: str
    week_key: str
    week_number: int
    year: int
    week_start_epoch: datetime
    requests: List[SatNetRequest] = field(default_factory=list)
    maintenance_intervals: List[SatNetMaintenanceInterval] = field(default_factory=list)
    single_antennas: Set[str] = field(default_factory=set)
    array_antennas: Dict[str, List[str]] = field(default_factory=dict)
    all_resources: Set[str] = field(default_factory=set)


@dataclass
class SatNetScheduledTask:
    """An allocated tracking activity on a DSN resource."""

    task_id: str
    track_id: str
    subject: int
    resource_id: str
    constituent_antennas: List[str]
    start_time: datetime
    end_time: datetime
    start_sec: int
    end_sec: int
    scheduled_duration_hours: float
    setup_start_time: datetime
    teardown_end_time: datetime
    setup_start_sec: int
    teardown_end_sec: int


@dataclass
class SatNetMetrics:
    """Evaluation metrics for SatNet scheduling runs (no artificial GB or priority weights)."""

    total_requests: int
    scheduled_requests_count: int
    unassigned_requests_count: int
    request_satisfaction_rate: float
    total_requested_hours: float
    total_scheduled_hours: float
    hours_completion_rate: float
    maintenance_intervals_enforced: int
    antenna_utilization_hours: Dict[str, float] = field(default_factory=dict)
    mission_allocation_hours: Dict[str, float] = field(default_factory=dict)


@dataclass
class SatNetScheduleResult:
    """Complete scheduling execution outcome for a SatNet scenario."""

    run_id: str
    scenario_name: str
    algorithm: str
    solver_status: SatNetSolverStatus
    is_valid: bool
    validation_violations: List[str]
    runtime_seconds: float
    scheduled_tasks: List[SatNetScheduledTask] = field(default_factory=list)
    rejected_track_ids: List[str] = field(default_factory=list)
    metrics: Optional[SatNetMetrics] = None
