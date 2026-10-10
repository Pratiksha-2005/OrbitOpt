from typing import List
from collections import defaultdict

from scheduler.models import (
    Satellite, GroundStation, VisibilityWindow, DownlinkRequest, ScheduledTask
)

class ScheduleValidator:
    def __init__(
        self,
        satellites: List[Satellite],
        ground_stations: List[GroundStation],
        windows: List[VisibilityWindow],
        requests: List[DownlinkRequest]
    ):
        self.satellites = {s.id: s for s in satellites}
        self.ground_stations = {gs.id: gs for gs in ground_stations}
        self.windows = {w.id: w for w in windows}
        self.requests = {r.id: r for r in requests}
        
    def validate(self, tasks: List[ScheduledTask]) -> List[str]:
        errors = []
        seen_requests = set()
        
        # for overlap checking
        tasks_by_gs = defaultdict(list)
        tasks_by_sat = defaultdict(list)
        
        for task in tasks:
            req = self.requests.get(task.request_id)
            if not req:
                errors.append(f"Task {task.id} references unknown request {task.request_id}")
            else:
                if req.id in seen_requests:
                    errors.append(f"Request {req.id} is scheduled multiple times")
                seen_requests.add(req.id)
                if req.satellite_id not in self.satellites:
                    errors.append(f"Request {req.id} references unknown satellite {req.satellite_id}")
            
            window = self.windows.get(task.visibility_window_id)
            if not window:
                errors.append(f"Task {task.id} references unknown window {task.visibility_window_id}")
            else:
                if window.satellite_id not in self.satellites:
                    errors.append(f"Window {window.id} references unknown satellite {window.satellite_id}")
                if window.ground_station_id not in self.ground_stations:
                    errors.append(f"Window {window.id} references unknown ground station {window.ground_station_id}")
            
            # If basic references are missing, skip logical checks for this task to avoid crashes
            if not req or not window:
                continue
                
            gs = self.ground_stations.get(window.ground_station_id)
            if not gs:
                continue

            # 2. Satellite Compatibility
            if req.satellite_id != window.satellite_id:
                errors.append(f"Task {task.id}: Request satellite {req.satellite_id} does not match Window satellite {window.satellite_id}")
                
            # 3. Time bounds & Deadlines
            if task.start_time < window.start_time or task.end_time > window.end_time:
                errors.append(f"Task {task.id} is scheduled outside its visibility window {window.id}")
            if req.deadline and task.end_time > req.deadline:
                errors.append(f"Task {task.id} end time exceeds request deadline {req.deadline}")
                
            # GS Outages
            for outage in gs.outages:
                if task.start_time < outage.end_time and task.end_time > outage.start_time:
                    errors.append(f"Task {task.id} overlaps with an outage on ground station {gs.id}")
                
            # 4. Duration & Data Volume MVP
            # Using 1e-5 as a documented small floating-point tolerance
            EPSILON = 1e-5
            if abs(task.data_transmitted_mb - req.data_volume_mb) > EPSILON:
                errors.append(f"Task {task.id} data_transmitted_mb ({task.data_transmitted_mb}) does not match request data_volume_mb ({req.data_volume_mb})")
            
            task_duration_sec = (task.end_time - task.start_time).total_seconds()
            required_sec = (req.data_volume_mb * 8) / gs.downlink_rate_mbps
            if task_duration_sec < required_sec - EPSILON:
                errors.append(f"Task {task.id} duration {task_duration_sec:.2f}s is insufficient for {req.data_volume_mb}MB at {gs.downlink_rate_mbps}Mbps (needs {required_sec:.2f}s)")
            
            # Record for overlap checks
            tasks_by_gs[window.ground_station_id].append(task)
            tasks_by_sat[req.satellite_id].append(task)
            
        # 5. Overlap Checks (GS and Satellite)
        self._check_overlaps(tasks_by_gs, "Ground Station", errors)
        self._check_overlaps(tasks_by_sat, "Satellite", errors)
        
        return errors
        
    def _check_overlaps(self, task_groups: dict, group_name: str, errors: List[str]):
        for group_id, group_tasks in task_groups.items():
            sorted_tasks = sorted(group_tasks, key=lambda t: t.start_time)
            for i in range(1, len(sorted_tasks)):
                prev_task = sorted_tasks[i-1]
                curr_task = sorted_tasks[i]
                # Using half-open intervals [start, end), adjacent tasks are allowed. Overlap is when prev_end > curr_start.
                if prev_task.end_time > curr_task.start_time:
                    errors.append(f"{group_name} {group_id} has overlapping tasks {prev_task.id} and {curr_task.id}")
