"""Developer 1 Baseline First-Come-First-Served Scheduler."""

import time
import uuid
from typing import List, Dict
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
    def __init__(
        self,
        satellites: List[Satellite],
        ground_stations: List[GroundStation],
        windows: List[VisibilityWindow],
        requests: List[DownlinkRequest],
    ):
        # Deterministic unique mapping via dict
        self.satellites = {s.id: s for s in satellites}
        self.ground_stations = {gs.id: gs for gs in ground_stations}
        self.windows = {w.id: w for w in windows}
        self.requests = {r.id: r for r in requests}
        
        self.raw_satellites = satellites
        self.raw_ground_stations = ground_stations
        self.raw_windows = windows
        # Use the deduped requests as the baseline raw requests
        self.raw_requests = list(self.requests.values())
        
        # Track scheduled tasks for overlap checking during generation
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
        
    def _is_overlap(self, task_start: datetime, task_end: datetime, tasks: List[ScheduledTask]) -> bool:
        for t in tasks:
            # Half-open interval overlap check: max(start) < min(end)
            if max(task_start, t.start_time) < min(task_end, t.end_time):
                return True
        return False
        
    def schedule(self) -> ScheduleResult:
        start_runtime = time.time()
        scheduled_tasks: List[ScheduledTask] = []
        rejected_request_ids: List[str] = []
        
        # 1. Sort requests deterministically
        # Tie-breaking rules:
        # 1. Earliest eligible visibility-window start time (ascending)
        # 2. Priority (descending)
        # 3. Data volume (descending - try to fit big ones first if same priority)
        # 4. Request ID (ascending)
        sorted_reqs = sorted(
            self.raw_requests,
            key=lambda r: (
                self._find_earliest_start(r),
                -r.priority.value,
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
            # 2. GS rate (descending - prefer faster links)
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
                duration_sec = (req.data_volume_mb * 8) / gs.downlink_rate_mbps
                duration = timedelta(seconds=duration_sec)
                
                # Gather all potential start times in this window
                potential_starts = [w.start_time]
                for t in self.gs_tasks[w.ground_station_id]:
                    if w.start_time <= t.end_time <= w.end_time:
                        potential_starts.append(t.end_time)
                for t in self.sat_tasks[req.satellite_id]:
                    if w.start_time <= t.end_time <= w.end_time:
                        potential_starts.append(t.end_time)
                        
                potential_starts.sort()
                
                for t_start in potential_starts:
                    t_end = t_start + duration
                    
                    if t_end > w.end_time:
                        continue # Does not fit in window bounds
                        
                    # Check for overlaps (exact adjacency is allowed by _is_overlap logic)
                    if self._is_overlap(t_start, t_end, self.gs_tasks[w.ground_station_id]):
                        continue
                    if self._is_overlap(t_start, t_end, self.sat_tasks[req.satellite_id]):
                        continue
                        
                    # Found a valid slot
                    task = ScheduledTask(
                        id=f"task-{req.id}-{w.id}-{uuid.uuid4().hex[:8]}",
                        request_id=req.id,
                        visibility_window_id=w.id,
                        start_time=t_start,
                        end_time=t_end,
                        data_transmitted_mb=req.data_volume_mb,
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
        
        runtime = time.time() - start_runtime
        
        validator = ScheduleValidator(
            self.raw_satellites, self.raw_ground_stations, self.raw_windows, self.raw_requests
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
        )
