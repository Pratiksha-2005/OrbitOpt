"""Developer 1 Independent Schedule Validator with physical constraints and setup time enforcement."""

from datetime import timedelta
from typing import List
from collections import defaultdict

from app.services.scheduler.models import (
    Satellite,
    GroundStation,
    VisibilityWindow,
    DownlinkRequest,
    ScheduledTask,
)


class ScheduleValidator:
    """Independent mathematical validator verifying conflict-freedom and physical feasibility."""

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
        self.setup_time_seconds = max(0, setup_time_seconds)

    def validate(self, tasks: List[ScheduledTask]) -> List[str]:
        errors: List[str] = []
        seen_requests = set()

        tasks_by_gs = defaultdict(list)
        tasks_by_sat = defaultdict(list)

        for task in tasks:
            req = self.requests.get(task.request_id)
            if not req:
                errors.append(f"Task {task.id} references unknown request {task.request_id}")
            else:
                if req.id in seen_requests:
                    errors.append(f"Request {req.id} is scheduled multiple times (duplicate allocation)")
                seen_requests.add(req.id)
                if req.satellite_id not in self.satellites:
                    errors.append(f"Request {req.id} references unknown satellite {req.satellite_id}")

            window = self.windows.get(task.visibility_window_id)
            if not window:
                errors.append(f"Task {task.id} references unknown visibility window {task.visibility_window_id}")
            else:
                if window.satellite_id not in self.satellites:
                    errors.append(f"Window {window.id} references unknown satellite {window.satellite_id}")
                if window.ground_station_id not in self.ground_stations:
                    errors.append(f"Window {window.id} references unknown ground station {window.ground_station_id}")

            if not req or not window:
                continue

            gs = self.ground_stations.get(window.ground_station_id)
            if not gs:
                continue

            # 1. Satellite Compatibility
            if req.satellite_id != window.satellite_id:
                errors.append(
                    f"Task {task.id}: Request satellite {req.satellite_id} does not match Window satellite {window.satellite_id}"
                )

            # 2. Hard Visibility Window Bounds
            if task.start_time < window.start_time or task.end_time > window.end_time:
                errors.append(
                    f"Task {task.id} [{task.start_time.isoformat()} - {task.end_time.isoformat()}] is scheduled outside its visibility window {window.id} [{window.start_time.isoformat()} - {window.end_time.isoformat()}]"
                )

            # 3. Transmission Duration & Channel Capacity
            EPSILON = 1e-4
            if abs(task.data_transmitted_mb - req.data_volume_mb) > EPSILON:
                errors.append(
                    f"Task {task.id} data_transmitted_mb ({task.data_transmitted_mb}) does not match request data_volume_mb ({req.data_volume_mb})"
                )

            task_duration_sec = (task.end_time - task.start_time).total_seconds()
            required_sec = (req.data_volume_mb * 8.0) / gs.downlink_rate_mbps
            if task_duration_sec < required_sec - EPSILON:
                errors.append(
                    f"Task {task.id} duration {task_duration_sec:.2f}s is insufficient for {req.data_volume_mb}MB at {gs.downlink_rate_mbps}Mbps (needs {required_sec:.2f}s)"
                )

            tasks_by_gs[window.ground_station_id].append(task)
            tasks_by_sat[req.satellite_id].append(task)

        # 4. Satellite Overlap Checks (a satellite can only downlink to one antenna at a time)
        self._check_satellite_overlaps(tasks_by_sat, errors)

        # 5. Ground Station Overlap and Setup Buffer Checks
        self._check_ground_station_constraints(tasks_by_gs, errors)

        return errors

    def _check_satellite_overlaps(self, sat_tasks: dict, errors: List[str]) -> None:
        for sat_id, tasks in sat_tasks.items():
            sorted_tasks = sorted(tasks, key=lambda t: t.start_time)
            for i in range(1, len(sorted_tasks)):
                prev_task = sorted_tasks[i - 1]
                curr_task = sorted_tasks[i]
                if prev_task.end_time > curr_task.start_time:
                    errors.append(
                        f"Satellite {sat_id} has overlapping passes: Task {prev_task.id} (ends {prev_task.end_time.isoformat()}) overlaps with Task {curr_task.id} (starts {curr_task.start_time.isoformat()})"
                    )

    def _check_ground_station_constraints(self, gs_tasks: dict, errors: List[str]) -> None:
        setup_delta = timedelta(seconds=self.setup_time_seconds)
        for gs_id, tasks in gs_tasks.items():
            sorted_tasks = sorted(tasks, key=lambda t: t.start_time)
            for i in range(1, len(sorted_tasks)):
                prev_task = sorted_tasks[i - 1]
                curr_task = sorted_tasks[i]

                # Direct overlap check
                if prev_task.end_time > curr_task.start_time:
                    errors.append(
                        f"Ground Station {gs_id} has overlapping passes: Task {prev_task.id} (ends {prev_task.end_time.isoformat()}) overlaps with Task {curr_task.id} (starts {curr_task.start_time.isoformat()})"
                    )
                # Antenna slew / setup buffer check
                elif self.setup_time_seconds > 0 and curr_task.start_time < prev_task.end_time + setup_delta:
                    actual_gap = (curr_task.start_time - prev_task.end_time).total_seconds()
                    errors.append(
                        f"Ground Station {gs_id} setup-time violation: Gap between Task {prev_task.id} and Task {curr_task.id} is {actual_gap:.1f}s, but required antenna slew buffer is {self.setup_time_seconds}s"
                    )

        # Outage and maintenance window collision checks
        for gs_id, tasks in gs_tasks.items():
            gs = self.ground_stations.get(gs_id)
            if not gs or not getattr(gs, "outages", None):
                continue
            for outage in gs.outages:
                for task in tasks:
                    if task.start_time < outage.end_time and task.end_time > outage.start_time:
                        errors.append(
                            f"Task {task.id} overlaps with an outage on ground station {gs.id} ({outage.start_time.isoformat()} to {outage.end_time.isoformat()})"
                        )
