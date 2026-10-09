"""Solvers and Validator for the SatNet NASA Deep Space Network Scheduling Problem."""

import math
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

from ortools.sat.python import cp_model

from .models import (
    SatNetCandidateWindow,
    SatNetMaintenanceInterval,
    SatNetMetrics,
    SatNetRequest,
    SatNetScenario,
    SatNetScheduleResult,
    SatNetScheduledTask,
    SatNetSolverStatus,
)


class SatNetValidator:
    """Validates scheduled allocations against SatNet constraints."""

    def __init__(self, scenario: SatNetScenario):
        self.scenario = scenario
        self.request_lookup = {r.track_id: r for r in scenario.requests}
        self.maint_by_antenna = defaultdict(list)
        for m in scenario.maintenance_intervals:
            self.maint_by_antenna[m.antenna].append(m)

    def validate(self, tasks: List[SatNetScheduledTask]) -> List[str]:
        violations: List[str] = []
        seen_requests: Set[str] = set()
        intervals_by_dish: Dict[str, List[Tuple[int, int, str]]] = defaultdict(list)

        # Pre-populate maintenance intervals on physical dishes
        for ant, maint_list in self.maint_by_antenna.items():
            for m in maint_list:
                intervals_by_dish[ant].append((m.start_sec, m.end_sec, f"MAINTENANCE:{m.interval_id}"))

        for task in tasks:
            req = self.request_lookup.get(task.track_id)
            if not req:
                violations.append(f"Task {task.task_id} references unknown track_id '{task.track_id}'")
                continue

            # 1. At-most-one check
            if task.track_id in seen_requests:
                violations.append(f"Request '{task.track_id}' scheduled multiple times")
            seen_requests.add(task.track_id)

            # 2. Duration bounds check
            min_sec = int(round(req.duration_min_hours * 3600))
            req_sec = int(round(req.duration_hours * 3600))
            task_sec = task.end_sec - task.start_sec

            if task_sec < min_sec:
                violations.append(
                    f"Task '{task.task_id}' duration {task_sec}s is less than minimum required {min_sec}s ({req.duration_min_hours}h)"
                )
            if task_sec > req_sec + 1:  # Allow 1s rounding
                violations.append(
                    f"Task '{task.task_id}' duration {task_sec}s exceeds requested {req_sec}s ({req.duration_hours}h)"
                )

            # 3. Time window bounds check
            if task.start_sec < req.time_window_start_sec or task.end_sec > req.time_window_end_sec:
                violations.append(
                    f"Task '{task.task_id}' [{task.start_sec}, {task.end_sec}] outside time window [{req.time_window_start_sec}, {req.time_window_end_sec}]"
                )

            # 4. View period bounds check
            # Find matching candidate window
            matched_vp = False
            for cw in req.candidate_windows:
                if cw.resource_id == task.resource_id:
                    if task.start_sec >= cw.vp_start_sec and task.end_sec <= cw.vp_end_sec:
                        matched_vp = True
                        break
            if not matched_vp:
                violations.append(
                    f"Task '{task.task_id}' on '{task.resource_id}' [{task.start_sec}, {task.end_sec}] not within any valid view period for this resource"
                )

            # 5. Setup and teardown margins check
            setup_sec = req.setup_time_minutes * 60
            teardown_sec = req.teardown_time_minutes * 60

            if task.setup_start_sec != task.start_sec - setup_sec:
                violations.append(f"Task '{task.task_id}' setup start mismatch: expected {task.start_sec - setup_sec}, got {task.setup_start_sec}")
            if task.teardown_end_sec != task.end_sec + teardown_sec:
                violations.append(f"Task '{task.task_id}' teardown end mismatch: expected {task.end_sec + teardown_sec}, got {task.teardown_end_sec}")

            # 6. Physical antenna occupancy registration
            for ant in task.constituent_antennas:
                intervals_by_dish[ant].append(
                    (task.setup_start_sec, task.teardown_end_sec, f"TASK:{task.task_id}:{task.track_id}")
                )

        # 7. Check for physical dish overlaps
        for dish, intervals in intervals_by_dish.items():
            sorted_intervals = sorted(intervals, key=lambda x: x[0])
            for i in range(1, len(sorted_intervals)):
                prev = sorted_intervals[i - 1]
                curr = sorted_intervals[i]
                # Overlap if previous end > current start
                if prev[1] > curr[0]:
                    violations.append(
                        f"Overlap on physical antenna '{dish}': '{prev[2]}' [{prev[0]}, {prev[1]}] overlaps with '{curr[2]}' [{curr[0]}, {curr[1]}]"
                    )

        return violations


class SatNetFCFSEngine:
    """First-Come-First-Served baseline scheduler for SatNet scenarios."""

    def __init__(self, scenario: SatNetScenario):
        self.scenario = scenario

    def solve(self) -> SatNetScheduleResult:
        start_time = time.time()
        # Sort requests chronologically by time_window_start
        sorted_requests = sorted(
            self.scenario.requests,
            key=lambda r: (r.time_window_start_sec, r.track_id),
        )

        # Track occupied intervals per physical antenna dish: List of (start_sec, end_sec)
        dish_occupancy: Dict[str, List[Tuple[int, int]]] = defaultdict(list)

        # Pre-reserve maintenance intervals
        for m in self.scenario.maintenance_intervals:
            dish_occupancy[m.antenna].append((m.start_sec, m.end_sec))

        scheduled_tasks: List[SatNetScheduledTask] = []
        rejected_track_ids: List[str] = []

        epoch = self.scenario.week_start_epoch

        for req in sorted_requests:
            setup_sec = req.setup_time_minutes * 60
            teardown_sec = req.teardown_time_minutes * 60
            dur_req_sec = int(round(req.duration_hours * 3600))
            dur_min_sec = int(round(req.duration_min_hours * 3600))

            scheduled = False

            # Sort candidate windows chronologically
            sorted_windows = sorted(req.candidate_windows, key=lambda w: w.vp_start_sec)

            for cw in sorted_windows:
                # Feasible tracking interval must be within both view period and request time window
                valid_earliest_track = max(cw.vp_start_sec, req.time_window_start_sec)
                valid_latest_track = min(cw.vp_end_sec, req.time_window_end_sec)

                # Need at least dur_min_sec
                if valid_latest_track - valid_earliest_track < dur_min_sec:
                    continue

                # Attempt requested duration first, then shrink to minimum if needed
                for dur_sec in (dur_req_sec, dur_min_sec):
                    if valid_latest_track - valid_earliest_track < dur_sec:
                        continue

                    # Try placing at earliest possible start time
                    track_start = valid_earliest_track
                    track_end = track_start + dur_sec

                    # Scan for a clash-free placement in small steps or shift
                    placed = False
                    while track_end <= valid_latest_track:
                        block_start = track_start - setup_sec
                        block_end = track_end + teardown_sec

                        # Check collision against all constituent antennas
                        has_clash = False
                        clash_latest_end = track_start

                        for ant in cw.constituent_antennas:
                            for occ_s, occ_e in dish_occupancy[ant]:
                                if not (block_end <= occ_s or block_start >= occ_e):
                                    has_clash = True
                                    clash_latest_end = max(clash_latest_end, occ_e + setup_sec)

                        if not has_clash:
                            # Found valid clash-free allocation
                            task = SatNetScheduledTask(
                                task_id=f"task_{req.track_id}_{cw.resource_id}_{len(scheduled_tasks)}",
                                track_id=req.track_id,
                                subject=req.subject,
                                resource_id=cw.resource_id,
                                constituent_antennas=cw.constituent_antennas,
                                start_time=epoch + timedelta(seconds=track_start),
                                end_time=epoch + timedelta(seconds=track_end),
                                start_sec=track_start,
                                end_sec=track_end,
                                scheduled_duration_hours=round(dur_sec / 3600.0, 4),
                                setup_start_time=epoch + timedelta(seconds=block_start),
                                teardown_end_time=epoch + timedelta(seconds=block_end),
                                setup_start_sec=block_start,
                                teardown_end_sec=block_end,
                            )
                            scheduled_tasks.append(task)
                            # Lock dishes
                            for ant in cw.constituent_antennas:
                                dish_occupancy[ant].append((block_start, block_end))
                            placed = True
                            scheduled = True
                            break
                        else:
                            # Advance past the clash
                            track_start = max(track_start + 60, clash_latest_end)
                            track_end = track_start + dur_sec

                    if placed:
                        break

                if scheduled:
                    break

            if not scheduled:
                rejected_track_ids.append(req.track_id)

        runtime = time.time() - start_time
        validator = SatNetValidator(self.scenario)
        violations = validator.validate(scheduled_tasks)

        metrics = self._calculate_metrics(scheduled_tasks, rejected_track_ids)

        return SatNetScheduleResult(
            run_id=f"satnet_fcfs_{uuid.uuid4().hex[:8]}",
            scenario_name=self.scenario.name,
            algorithm="SatNet_FCFS_Baseline",
            solver_status=SatNetSolverStatus.FEASIBLE if not violations else SatNetSolverStatus.MODEL_INVALID,
            is_valid=len(violations) == 0,
            validation_violations=violations,
            runtime_seconds=runtime,
            scheduled_tasks=scheduled_tasks,
            rejected_track_ids=rejected_track_ids,
            metrics=metrics,
        )

    def _calculate_metrics(
        self,
        scheduled: List[SatNetScheduledTask],
        rejected: List[str],
    ) -> SatNetMetrics:
        total_reqs = len(self.scenario.requests)
        sched_count = len(scheduled)
        total_req_hrs = sum(r.duration_hours for r in self.scenario.requests)
        total_sched_hrs = sum(t.scheduled_duration_hours for t in scheduled)

        ant_util: Dict[str, float] = defaultdict(float)
        mission_util: Dict[str, float] = defaultdict(float)

        for t in scheduled:
            for ant in t.constituent_antennas:
                ant_util[ant] += t.scheduled_duration_hours
            mission_util[str(t.subject)] += t.scheduled_duration_hours

        return SatNetMetrics(
            total_requests=total_reqs,
            scheduled_requests_count=sched_count,
            unassigned_requests_count=len(rejected),
            request_satisfaction_rate=round((sched_count / total_reqs * 100.0) if total_reqs else 0.0, 2),
            total_requested_hours=round(total_req_hrs, 2),
            total_scheduled_hours=round(total_sched_hrs, 2),
            hours_completion_rate=round((total_sched_hrs / total_req_hrs * 100.0) if total_req_hrs else 0.0, 2),
            maintenance_intervals_enforced=len(self.scenario.maintenance_intervals),
            antenna_utilization_hours=dict(sorted(ant_util.items())),
            mission_allocation_hours=dict(sorted(mission_util.items())),
        )


class SatNetCPSATEngine:
    """OR-Tools CP-SAT Integer Programming Optimizer for SatNet scenarios."""

    def __init__(self, scenario: SatNetScenario, time_limit_seconds: float = 30.0):
        self.scenario = scenario
        self.time_limit_seconds = time_limit_seconds

    def solve(self) -> SatNetScheduleResult:
        start_time = time.time()
        model = cp_model.CpModel()

        # Decision variables
        # For each request r and candidate window w:
        # x_{r,w} = 1 if window w is chosen for request r
        x_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}
        start_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}
        end_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}
        dur_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}

        # Intervals on physical dishes (includes setup and teardown)
        intervals_by_dish: Dict[str, List[cp_model.IntervalVar]] = defaultdict(list)

        objective_terms = []

        # 1. Add fixed maintenance intervals on physical dishes
        for m in self.scenario.maintenance_intervals:
            m_dur = m.end_sec - m.start_sec
            if m_dur <= 0:
                continue
            m_interval = model.NewFixedSizeIntervalVar(
                m.start_sec, m_dur, f"maint_{m.antenna}_{m.start_sec}"
            )
            intervals_by_dish[m.antenna].append(m_interval)

        # 2. Build tracking interval variables for each candidate window
        for req in self.scenario.requests:
            setup_sec = req.setup_time_minutes * 60
            teardown_sec = req.teardown_time_minutes * 60
            dur_req_sec = int(round(req.duration_hours * 3600))
            dur_min_sec = int(round(req.duration_min_hours * 3600))

            req_x_vars = []

            for cw in req.candidate_windows:
                valid_earliest_track = max(cw.vp_start_sec, req.time_window_start_sec)
                valid_latest_track = min(cw.vp_end_sec, req.time_window_end_sec)

                if valid_latest_track - valid_earliest_track < dur_min_sec:
                    continue  # Infeasible for this window

                key = (req.track_id, cw.window_id)
                x = model.NewBoolVar(f"x_{req.track_id}_{cw.window_id}")
                req_x_vars.append(x)
                x_vars[key] = x

                # Track start and end within valid window
                # Total block on dish: [block_start, block_end] where block_start = track_start - setup, block_end = track_end + teardown
                # total_block_dur = dur + setup + teardown
                dur_var = model.NewIntVar(dur_min_sec, dur_req_sec, f"dur_{req.track_id}_{cw.window_id}")
                dur_vars[key] = dur_var

                track_start_var = model.NewIntVar(
                    valid_earliest_track, valid_latest_track - dur_min_sec, f"s_{req.track_id}_{cw.window_id}"
                )
                track_end_var = model.NewIntVar(
                    valid_earliest_track + dur_min_sec, valid_latest_track, f"e_{req.track_id}_{cw.window_id}"
                )
                start_vars[key] = track_start_var
                end_vars[key] = track_end_var

                # Link track_end == track_start + dur
                model.Add(track_end_var == track_start_var + dur_var)

                # Total block on dish including setup and teardown
                block_start_var = model.NewIntVar(
                    valid_earliest_track - setup_sec, valid_latest_track - dur_min_sec - setup_sec, f"bs_{req.track_id}_{cw.window_id}"
                )
                block_end_var = model.NewIntVar(
                    valid_earliest_track + dur_min_sec + teardown_sec, valid_latest_track + teardown_sec, f"be_{req.track_id}_{cw.window_id}"
                )
                model.Add(block_start_var == track_start_var - setup_sec)
                model.Add(block_end_var == track_end_var + teardown_sec)

                block_dur_var = model.NewIntVar(
                    dur_min_sec + setup_sec + teardown_sec, dur_req_sec + setup_sec + teardown_sec, f"bdur_{req.track_id}_{cw.window_id}"
                )
                model.Add(block_dur_var == dur_var + (setup_sec + teardown_sec))

                # Create optional interval for each constituent physical antenna dish
                for ant in cw.constituent_antennas:
                    dish_interval = model.NewOptionalIntervalVar(
                        block_start_var,
                        block_dur_var,
                        block_end_var,
                        x,
                        f"dish_int_{ant}_{req.track_id}_{cw.window_id}",
                    )
                    intervals_by_dish[ant].append(dish_interval)

                # Objective: Maximize total scheduled contact hours (in seconds / 60)
                # Primary term: dur_var, plus small incentive per scheduled request
                objective_terms.append(x * 1000 + dur_var)

            # At most one window allocated per request
            if req_x_vars:
                model.AddAtMostOne(req_x_vars)

        # 3. No-overlap constraint on every physical antenna dish
        for dish, intervals in intervals_by_dish.items():
            model.AddNoOverlap(intervals)

        # 4. Objective function
        model.Maximize(sum(objective_terms))

        # 5. Solver configuration
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        solver.parameters.random_seed = 42
        solver.parameters.num_search_workers = 4

        status_code = solver.Solve(model)

        status_map = {
            cp_model.OPTIMAL: SatNetSolverStatus.OPTIMAL,
            cp_model.FEASIBLE: SatNetSolverStatus.FEASIBLE,
            cp_model.INFEASIBLE: SatNetSolverStatus.INFEASIBLE,
            cp_model.MODEL_INVALID: SatNetSolverStatus.MODEL_INVALID,
            cp_model.UNKNOWN: SatNetSolverStatus.UNKNOWN,
        }
        solver_status = status_map.get(status_code, SatNetSolverStatus.UNKNOWN)

        scheduled_tasks: List[SatNetScheduledTask] = []
        rejected_track_ids: List[str] = []
        epoch = self.scenario.week_start_epoch

        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for req in self.scenario.requests:
                scheduled = False
                setup_sec = req.setup_time_minutes * 60
                teardown_sec = req.teardown_time_minutes * 60

                for cw in req.candidate_windows:
                    key = (req.track_id, cw.window_id)
                    if key in x_vars and solver.Value(x_vars[key]):
                        s_val = int(solver.Value(start_vars[key]))
                        e_val = int(solver.Value(end_vars[key]))
                        dur_sec = e_val - s_val
                        bs_val = s_val - setup_sec
                        be_val = e_val + teardown_sec

                        task = SatNetScheduledTask(
                            task_id=f"cpsat_task_{req.track_id}_{cw.resource_id}",
                            track_id=req.track_id,
                            subject=req.subject,
                            resource_id=cw.resource_id,
                            constituent_antennas=cw.constituent_antennas,
                            start_time=epoch + timedelta(seconds=s_val),
                            end_time=epoch + timedelta(seconds=e_val),
                            start_sec=s_val,
                            end_sec=e_val,
                            scheduled_duration_hours=round(dur_sec / 3600.0, 4),
                            setup_start_time=epoch + timedelta(seconds=bs_val),
                            teardown_end_time=epoch + timedelta(seconds=be_val),
                            setup_start_sec=bs_val,
                            teardown_end_sec=be_val,
                        )
                        scheduled_tasks.append(task)
                        scheduled = True
                        break

                if not scheduled:
                    rejected_track_ids.append(req.track_id)
        else:
            rejected_track_ids = [r.track_id for r in self.scenario.requests]

        runtime = time.time() - start_time
        validator = SatNetValidator(self.scenario)
        violations = validator.validate(scheduled_tasks)

        if violations:
            solver_status = SatNetSolverStatus.MODEL_INVALID

        # Calculate SatNet-native metrics
        total_reqs = len(self.scenario.requests)
        sched_count = len(scheduled_tasks)
        total_req_hrs = sum(r.duration_hours for r in self.scenario.requests)
        total_sched_hrs = sum(t.scheduled_duration_hours for t in scheduled_tasks)

        ant_util: Dict[str, float] = defaultdict(float)
        mission_util: Dict[str, float] = defaultdict(float)

        for t in scheduled_tasks:
            for ant in t.constituent_antennas:
                ant_util[ant] += t.scheduled_duration_hours
            mission_util[str(t.subject)] += t.scheduled_duration_hours

        metrics = SatNetMetrics(
            total_requests=total_reqs,
            scheduled_requests_count=sched_count,
            unassigned_requests_count=len(rejected_track_ids),
            request_satisfaction_rate=round((sched_count / total_reqs * 100.0) if total_reqs else 0.0, 2),
            total_requested_hours=round(total_req_hrs, 2),
            total_scheduled_hours=round(total_sched_hrs, 2),
            hours_completion_rate=round((total_sched_hrs / total_req_hrs * 100.0) if total_req_hrs else 0.0, 2),
            maintenance_intervals_enforced=len(self.scenario.maintenance_intervals),
            antenna_utilization_hours=dict(sorted(ant_util.items())),
            mission_allocation_hours=dict(sorted(mission_util.items())),
        )

        return SatNetScheduleResult(
            run_id=f"satnet_cpsat_{uuid.uuid4().hex[:8]}",
            scenario_name=self.scenario.name,
            algorithm="SatNet_CP_SAT_Optimizer",
            solver_status=solver_status,
            is_valid=len(violations) == 0,
            validation_violations=violations,
            runtime_seconds=runtime,
            scheduled_tasks=scheduled_tasks,
            rejected_track_ids=rejected_track_ids,
            metrics=metrics,
        )
