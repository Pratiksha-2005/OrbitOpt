"""Developer 1 CP-SAT Multi-Satellite Optimizer with antenna setup time and dynamic priority scoring."""

import time
import uuid
import math
from datetime import datetime, timezone
from typing import List, Optional
from ortools.sat.python import cp_model

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


class CPSATScheduler:
    """Constraint Programming (OR-Tools CP-SAT) Multi-Satellite ground network optimizer."""

    def __init__(
        self,
        satellites: List[Satellite],
        ground_stations: List[GroundStation],
        windows: List[VisibilityWindow],
        requests: List[DownlinkRequest],
        time_limit_sec: float = 60.0,
        setup_time_seconds: int = 0,
        locked_tasks: Optional[List[ScheduledTask]] = None,
    ):
        self.satellites = {s.id: s for s in satellites}
        self.ground_stations = {gs.id: gs for gs in ground_stations}
        self.windows = {w.id: w for w in windows}
        self.requests = {r.id: r for r in requests}
        
        self.raw_satellites = satellites
        self.raw_ground_stations = ground_stations
        self.raw_windows = windows
        self.raw_requests = list(self.requests.values())
        
        self.time_limit_sec = max(0.5, float(time_limit_sec))
        self.setup_time_seconds = max(0, int(setup_time_seconds))
        self.locked_tasks = locked_tasks or []

        
    def _get_eligible_windows(self, request: DownlinkRequest) -> List[VisibilityWindow]:
        eligible = []
        for w in self.windows.values():
            if w.satellite_id == request.satellite_id and w.ground_station_id in self.ground_stations:
                eligible.append(w)
        return eligible

    def _datetime_to_int(self, dt: datetime) -> int:
        return int(dt.timestamp())

    def _int_to_datetime(self, ts: int) -> datetime:
        return datetime.fromtimestamp(ts, tz=timezone.utc)

    def schedule(self) -> ScheduleResult:
        start_runtime = time.time()
        
        # Fast exit if no requests
        if not self.raw_requests:
            return ScheduleResult(
                id=f"cpsat-run-{uuid.uuid4().hex[:8]}",
                scheduled_tasks=[],
                rejected_request_ids=[],
                objective_value=0.0,
                runtime_seconds=time.time() - start_runtime,
                solver_status=SolverStatus.FEASIBLE,
                is_valid=True,
                validation_errors=[],
            )

        model = cp_model.CpModel()
        
        from collections import defaultdict
        intervals_by_gs = defaultdict(list)
        intervals_by_sat = defaultdict(list)

        # Add ground station outage windows to NoOverlap intervals
        for gs in self.ground_stations.values():
            for outage in getattr(gs, "outages", []):
                s_int = self._datetime_to_int(outage.start_time)
                e_int = self._datetime_to_int(outage.end_time)
                if e_int <= s_int:
                    continue
                outage_dur = e_int - s_int
                outage_id = uuid.uuid4().hex[:8]
                outage_interval = model.NewIntervalVar(
                    s_int, outage_dur, e_int, f"outage_{gs.id}_{outage_id}"
                )
                intervals_by_gs[gs.id].append(outage_interval)

        locked_req_ids = {lt.request_id for lt in self.locked_tasks}

        # Add locked tasks as fixed intervals on ground station and satellite
        for lt in self.locked_tasks:
            win = self.windows.get(lt.visibility_window_id)
            gs_id = win.ground_station_id if win else None
            sat_id = win.satellite_id if win else None
            if not sat_id and lt.request_id in self.requests:
                sat_id = self.requests[lt.request_id].satellite_id

            s_int = self._datetime_to_int(lt.start_time)
            e_int = self._datetime_to_int(lt.end_time)
            dur = e_int - s_int
            if dur <= 0:
                continue

            if sat_id:
                sat_interval = model.NewIntervalVar(
                    s_int, dur, e_int, f"locked_sat_{lt.id}"
                )
                intervals_by_sat[sat_id].append(sat_interval)

            if gs_id:
                if self.setup_time_seconds > 0:
                    gs_dur = dur + self.setup_time_seconds
                    gs_interval = model.NewIntervalVar(
                        s_int, gs_dur, s_int + gs_dur, f"locked_gs_{lt.id}"
                    )
                    intervals_by_gs[gs_id].append(gs_interval)
                else:
                    gs_interval = model.NewIntervalVar(
                        s_int, dur, e_int, f"locked_gs_{lt.id}"
                    )
                    intervals_by_gs[gs_id].append(gs_interval)
        
        x_vars = {}       # (req_id, window_id) -> bool var
        start_vars = {}   # (req_id, window_id) -> int var
        end_vars = {}     # (req_id, window_id) -> int var
        
        rejected_request_ids = []
        objective_terms = []
        
        for req in self.raw_requests:
            if req.id in locked_req_ids:
                # Locked tasks are already locked into fixed intervals and protected
                continue

            eligible_windows = self._get_eligible_windows(req)

            if not eligible_windows:
                rejected_request_ids.append(req.id)
                continue
                
            r_x_vars = []
            
            for w in eligible_windows:
                gs = self.ground_stations[w.ground_station_id]
                
                # Duration in seconds (conservative integer rounding up to never shorten duration)
                duration_sec = math.ceil((req.data_volume_mb * 8.0) / gs.downlink_rate_mbps)
                
                # Time bounds
                w_start_sec = self._datetime_to_int(w.start_time)
                w_end_sec = self._datetime_to_int(w.end_time)
                
                if w_end_sec - w_start_sec < duration_sec:
                    continue  # Impossible to fit within physical visibility bounds
                
                x = model.NewBoolVar(f"x_{req.id}_{w.id}")
                s = model.NewIntVar(w_start_sec, w_end_sec - duration_sec, f"s_{req.id}_{w.id}")
                e = model.NewIntVar(w_start_sec + duration_sec, w_end_sec, f"e_{req.id}_{w.id}")
                
                # Satellite physical interval (pure transmission duration)
                sat_interval = model.NewOptionalIntervalVar(
                    s, duration_sec, e, x, f"i_sat_{req.id}_{w.id}"
                )
                intervals_by_sat[w.satellite_id].append(sat_interval)
                
                # Ground Station interval (includes antenna slew/setup buffer if configured)
                if self.setup_time_seconds > 0:
                    gs_duration_sec = duration_sec + self.setup_time_seconds
                    e_gs = model.NewIntVar(
                        w_start_sec + gs_duration_sec,
                        w_end_sec + self.setup_time_seconds,
                        f"e_gs_{req.id}_{w.id}",
                    )
                    model.Add(e_gs == s + gs_duration_sec).OnlyEnforceIf(x)
                    gs_interval = model.NewOptionalIntervalVar(
                        s, gs_duration_sec, e_gs, x, f"i_gs_{req.id}_{w.id}"
                    )
                    intervals_by_gs[w.ground_station_id].append(gs_interval)
                else:
                    intervals_by_gs[w.ground_station_id].append(sat_interval)
                
                x_vars[(req.id, w.id)] = x
                start_vars[(req.id, w.id)] = s
                end_vars[(req.id, w.id)] = e
                r_x_vars.append(x)
                
                # Dynamic Priority Weighted Objective Term:
                # Uses dynamic multi-factor score (0-100) or priority tier (1-4)
                if req.dynamic_score is not None:
                    weight_factor = req.dynamic_score
                else:
                    weight_factor = float(req.priority.value * 25.0)

                # Integer objective coefficient: weight_factor * data_volume_mb
                coeff = int(round(weight_factor * req.data_volume_mb))
                objective_terms.append(x * coeff)
                
            if r_x_vars:
                # Each request is allocated at most once globally
                model.AddAtMostOne(r_x_vars)
            else:
                rejected_request_ids.append(req.id)
                
        # Ground Station antenna exclusivity constraint (no overlapping allocations)
        for gs_id, intervals in intervals_by_gs.items():
            model.AddNoOverlap(intervals)
            
        # Satellite transmitter exclusivity constraint (satellite can only downlink to one antenna at a time)
        for sat_id, intervals in intervals_by_sat.items():
            model.AddNoOverlap(intervals)
            
        # Maximize total priority-weighted data volume
        if objective_terms:
            model.Maximize(sum(objective_terms))
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_sec
        solver.parameters.random_seed = 42
        solver.parameters.num_search_workers = 1  # Deterministic execution
        
        status_code = solver.Solve(model)
        
        # Map CP-SAT status
        status_map = {
            cp_model.OPTIMAL: SolverStatus.OPTIMAL,
            cp_model.FEASIBLE: SolverStatus.FEASIBLE,
            cp_model.INFEASIBLE: SolverStatus.INFEASIBLE,
            cp_model.MODEL_INVALID: SolverStatus.MODEL_INVALID,
            cp_model.UNKNOWN: SolverStatus.UNKNOWN,
        }
        status = status_map.get(status_code, SolverStatus.UNKNOWN)
        
        scheduled_tasks: List[ScheduledTask] = list(self.locked_tasks)
        actual_objective = 0.0
        for lt in self.locked_tasks:
            req = self.requests.get(lt.request_id)
            if req:
                actual_objective += req.data_volume_mb * req.priority.value
            else:
                actual_objective += lt.data_transmitted_mb * 3.0
        
        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for req in self.raw_requests:
                if req.id in locked_req_ids:
                    continue
                scheduled = False
                for w in self._get_eligible_windows(req):
                    key = (req.id, w.id)
                    if key in x_vars and solver.Value(x_vars[key]):
                        s_val = solver.Value(start_vars[key])
                        e_val = solver.Value(end_vars[key])
                        
                        task = ScheduledTask(
                            id=f"task-{req.id}-{uuid.uuid4().hex[:8]}",
                            request_id=req.id,
                            visibility_window_id=w.id,
                            start_time=self._int_to_datetime(s_val),
                            end_time=self._int_to_datetime(e_val),
                            data_transmitted_mb=req.data_volume_mb,
                            dynamic_score=req.dynamic_score,
                            is_locked=False,
                            execution_status="SCHEDULED",
                        )
                        scheduled_tasks.append(task)
                        actual_objective += req.data_volume_mb * req.priority.value
                        scheduled = True
                        break
                
                if not scheduled and req.id not in rejected_request_ids:
                    rejected_request_ids.append(req.id)
        else:
            for req in self.raw_requests:
                if req.id not in locked_req_ids and req.id not in rejected_request_ids:
                    rejected_request_ids.append(req.id)
                    
        runtime = time.time() - start_runtime
        
        validator = ScheduleValidator(
            self.raw_satellites,
            self.raw_ground_stations,
            self.raw_windows,
            self.raw_requests,
            setup_time_seconds=self.setup_time_seconds,
        )
        errors = validator.validate(scheduled_tasks, locked_request_ids=locked_req_ids)

        
        if errors:
            status = SolverStatus.MODEL_INVALID

        avg_dynamic_score = None
        if scheduled_tasks:
            scores = [t.dynamic_score for t in scheduled_tasks if t.dynamic_score is not None]
            if scores:
                avg_dynamic_score = round(sum(scores) / len(scores), 2)
            
        return ScheduleResult(
            id=f"cpsat-run-{uuid.uuid4().hex[:8]}",
            scheduled_tasks=scheduled_tasks,
            rejected_request_ids=rejected_request_ids,
            objective_value=float(actual_objective),
            runtime_seconds=runtime,
            solver_status=status,
            is_valid=len(errors) == 0,
            validation_errors=errors,
            average_dynamic_score=avg_dynamic_score,
        )
