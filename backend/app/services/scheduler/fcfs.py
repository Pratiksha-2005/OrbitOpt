"""Developer 1 Baseline First-Come-First-Served Scheduler with setup time support."""

import time
import uuid
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta

from app.services.scheduler.models import (
    Satellite,
    GroundStation,
    VisibilityWindow,
    DownlinkRequest,
    ScheduledTask,
    ScheduleResult,
    SolverStatus,
)
from app.services.scheduler.validator import ScheduleValidator


class FCFSScheduler:
    """Deterministic Baseline FCFS heuristic with physical antenna slew buffer constraints."""

    def __init__(
        self,
        satellites: List[Satellite],
        ground_stations: List[GroundStation],
        windows: List[VisibilityWindow],
        requests: List[DownlinkRequest],
        setup_time_seconds: int = 0,
    ):
        self.satellites = {s.id: s for s in satellites}
        self.ground_stations = {gs.id: gs for gs in ground_stations}
        self.windows = {w.id: w for w in windows}
        self.requests = {r.id: r for r in requests}
        
        self.raw_satellites = satellites
        self.raw_ground_stations = ground_stations
        self.raw_windows = windows
        self.raw_requests = list(self.requests.values())
        self.setup_time_seconds = max(0, setup_time_seconds)
        
        # Track scheduled tasks for overlap & setup checks
        self.gs_tasks: Dict[str, List[ScheduledTask]] = {gs.id: [] for gs in ground_stations}
        self.sat_tasks: Dict[str, List[ScheduledTask]] = {s.id: [] for s in satellites}
        
    def _get_eligible_windows(self, request: DownlinkRequest) -> List[VisibilityWindow]:
        eligible = []
        for w in self.windows.values():
            if w.satellite_id == request.satellite_id and w.ground_station_id in self.ground_stations:
                eligible.append(w)
        return eligible

    def _find_earliest_start(self, request: DownlinkRequest) -> datetime:
        windows = self._get_eligible_windows(request)
        if not windows:
            return datetime.max.replace(tzinfo=timezone.utc)
        return min(w.start_time for w in windows)
        
    def _is_sat_overlap(self, task_start: datetime, task_end: datetime, tasks: List[ScheduledTask]) -> bool:
        for t in tasks:
            if max(task_start, t.start_time) < min(task_end, t.end_time):
                return True
        return False

    def _is_gs_conflict(self, task_start: datetime, task_end: datetime, tasks: List[ScheduledTask]) -> bool:
        setup_delta = timedelta(seconds=self.setup_time_seconds)
        for t in tasks:
            # Overlap with task duration + required antenna setup buffers
            if max(task_start, t.start_time) < min(task_end, t.end_time):
                return True
            if self.setup_time_seconds > 0:
                # Must not start before previous task end + setup
                if task_start < t.end_time + setup_delta and task_end > t.start_time - setup_delta:
                    return True
        return False

    def _is_outage_conflict(self, task_start: datetime, task_end: datetime, outages: list) -> bool:
        setup_delta = timedelta(seconds=self.setup_time_seconds)
        for out in outages:
            if max(task_start, out.start_time) < min(task_end, out.end_time):
                return True
            if self.setup_time_seconds > 0:
                if task_start < out.end_time + setup_delta and task_end > out.start_time - setup_delta:
                    return True
        return False
        
    def schedule(self) -> ScheduleResult:
        start_runtime = time.time()
        scheduled_tasks: List[ScheduledTask] = []
        rejected_request_ids: List[str] = []
        
        # 1. Sort requests deterministically
        # Tie-breaking rules:
        # 1. Earliest eligible visibility-window start time (ascending)
        # 2. Dynamic Priority Score (descending) / Priority (descending)
        # 3. Data volume (descending)
        # 4. Request ID (ascending)
        sorted_reqs = sorted(
            self.raw_requests,
            key=lambda r: (
                self._find_earliest_start(r),
                -(r.dynamic_score if r.dynamic_score is not None else float(r.priority.value * 25.0)),
                -r.data_volume_mb,
                r.id,
            ),
        )
        
        for req in sorted_reqs:
            windows = self._get_eligible_windows(req)
            if not windows:
                rejected_request_ids.append(req.id)
                continue
                
            # Sort eligible windows deterministically:
            # 1. Start time (ascending)
            # 2. GS rate (descending)
            # 3. Window ID (ascending)
            sorted_windows = sorted(
                windows,
                key=lambda w: (
                    w.start_time,
                    -self.ground_stations[w.ground_station_id].downlink_rate_mbps,
                    w.id,
                ),
            )
            
            task_scheduled = False
            for w in sorted_windows:
                gs = self.ground_stations[w.ground_station_id]
                duration_sec = (req.data_volume_mb * 8.0) / gs.downlink_rate_mbps
                duration = timedelta(seconds=duration_sec)
                setup_delta = timedelta(seconds=self.setup_time_seconds)
                
                # Gather potential earliest start points
                potential_starts = [w.start_time]
                for t in self.gs_tasks[w.ground_station_id]:
                    candidate = t.end_time + setup_delta
                    if w.start_time <= candidate <= w.end_time:
                        potential_starts.append(candidate)
                for t in self.sat_tasks[req.satellite_id]:
                    candidate = t.end_time
                    if w.start_time <= candidate <= w.end_time:
                        potential_starts.append(candidate)
                for out in getattr(gs, "outages", []):
                    candidate = out.end_time + setup_delta if self.setup_time_seconds > 0 else out.end_time
                    if w.start_time <= candidate <= w.end_time:
                        potential_starts.append(candidate)
                        
                potential_starts = sorted(list(set(potential_starts)))
                
                for t_start in potential_starts:
                    t_end = t_start + duration
                    
                    if t_end > w.end_time:
                        continue  # Window boundary constraint
                        
                    if self._is_gs_conflict(t_start, t_end, self.gs_tasks[w.ground_station_id]):
                        continue
                    if self._is_sat_overlap(t_start, t_end, self.sat_tasks[req.satellite_id]):
                        continue
                    if self._is_outage_conflict(t_start, t_end, getattr(gs, "outages", [])):
                        continue
                        
                    # Allocated
                    task = ScheduledTask(
                        id=f"task-{req.id}-{w.id}-{uuid.uuid4().hex[:8]}",
                        request_id=req.id,
                        visibility_window_id=w.id,
                        start_time=t_start,
                        end_time=t_end,
                        data_transmitted_mb=req.data_volume_mb,
                        dynamic_score=req.dynamic_score,
                    )
                    
                    scheduled_tasks.append(task)
                    self.gs_tasks[w.ground_station_id].append(task)
                    self.sat_tasks[req.satellite_id].append(task)
                    task_scheduled = True
                    break
                    
                if task_scheduled:
                    break
                    
            if not task_scheduled:
                rejected_request_ids.append(req.id)
                
        # Calculate objective (priority * data_volume_mb)
        objective_value = sum(
            self.requests[t.request_id].data_volume_mb * self.requests[t.request_id].priority.value 
            for t in scheduled_tasks
        )

        # Average dynamic priority score
        avg_dynamic_score = None
        if scheduled_tasks:
            scores = [t.dynamic_score for t in scheduled_tasks if t.dynamic_score is not None]
            if scores:
                avg_dynamic_score = round(sum(scores) / len(scores), 2)
        
        runtime = time.time() - start_runtime
        
        validator = ScheduleValidator(
            self.raw_satellites,
            self.raw_ground_stations,
            self.raw_windows,
            self.raw_requests,
            setup_time_seconds=self.setup_time_seconds,
        )
        errors = validator.validate(scheduled_tasks)
        
        status = SolverStatus.FEASIBLE
        if errors:
            status = SolverStatus.MODEL_INVALID
            
        return ScheduleResult(
            id=f"fcfs-run-{uuid.uuid4().hex[:8]}",
            scheduled_tasks=scheduled_tasks,
            rejected_request_ids=rejected_request_ids,
            objective_value=float(objective_value),
            runtime_seconds=runtime,
            solver_status=status,
            is_valid=len(errors) == 0,
            validation_errors=errors,
            average_dynamic_score=avg_dynamic_score,
        )
