import time
import uuid
import math
from typing import List, Dict, Tuple
from datetime import datetime, timezone, timedelta

from ortools.sat.python import cp_model

from scheduler.models import (
    Satellite, GroundStation, VisibilityWindow, DownlinkRequest, 
    ScheduledTask, ScheduleResult, SolverStatus
)
from scheduler.validator import ScheduleValidator

class CPSATScheduler:
    def __init__(
        self,
        satellites: List[Satellite],
        ground_stations: List[GroundStation],
        windows: List[VisibilityWindow],
        requests: List[DownlinkRequest],
        fixed_tasks: List[ScheduledTask] | None = None,
        time_limit_sec: float = 60.0,
        evaluation_time: datetime | None = None
    ):
        self.satellites = {s.id: s for s in satellites}
        self.ground_stations = {gs.id: gs for gs in ground_stations}
        self.windows = {w.id: w for w in windows}
        # Deduplicate requests if they are passed multiple times
        self.requests = {r.id: r for r in requests}
        
        self.raw_satellites = satellites
        self.raw_ground_stations = ground_stations
        self.raw_windows = windows
        self.raw_requests = list(self.requests.values())
        
        self.fixed_tasks = fixed_tasks or []
        self.time_limit_sec = time_limit_sec
        self.evaluation_time = evaluation_time or datetime.now(timezone.utc)
        
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
                validation_errors=[]
            )

        model = cp_model.CpModel()
        
        from collections import defaultdict
        intervals_by_gs = defaultdict(list)
        intervals_by_sat = defaultdict(list)
        
        x_vars = {} # (req_id, window_id) -> bool var
        start_vars = {} # (req_id, window_id) -> int var
        end_vars = {} # (req_id, window_id) -> int var
        
        rejected_request_ids = []
        objective_terms = []
        
        # Add fixed tasks to NoOverlap constraints
        for ft in self.fixed_tasks:
            s_int = self._datetime_to_int(ft.start_time)
            e_int = self._datetime_to_int(ft.end_time)
            interval = model.NewIntervalVar(s_int, e_int - s_int, e_int, f'fixed_{ft.id}')
            
            w = self.windows.get(ft.visibility_window_id)
            if w:
                intervals_by_gs[w.ground_station_id].append(interval)
            
            req = self.requests.get(ft.request_id)
            if req:
                intervals_by_sat[req.satellite_id].append(interval)
            elif w:
                intervals_by_sat[w.satellite_id].append(interval)
                
        # Add GS outages to NoOverlap constraints
        for gs in self.ground_stations.values():
            for outage in gs.outages:
                s_int = self._datetime_to_int(outage.start_time)
                e_int = self._datetime_to_int(outage.end_time)
                outage_id = uuid.uuid4().hex[:8]
                interval = model.NewIntervalVar(s_int, e_int - s_int, e_int, f'outage_{gs.id}_{outage_id}')
                intervals_by_gs[gs.id].append(interval)
        
        from scheduler.priority import get_dynamic_score
        
        for req in self.raw_requests:
            eligible_windows = self._get_eligible_windows(req)
            if not eligible_windows:
                rejected_request_ids.append(req.id)
                continue
                
            r_x_vars = []
            
            for w in eligible_windows:
                gs = self.ground_stations[w.ground_station_id]
                
                # Duration in seconds (conservative integer rounding up to never shorten duration)
                duration_sec = math.ceil((req.data_volume_mb * 8) / gs.downlink_rate_mbps)
                
                # Time bounds and Deadline
                w_start_sec = self._datetime_to_int(w.start_time)
                w_end_sec = self._datetime_to_int(w.end_time)
                if req.deadline:
                    w_end_sec = min(w_end_sec, self._datetime_to_int(req.deadline))
                
                if w_end_sec - w_start_sec < duration_sec:
                    continue # Impossible to fit
                
                x = model.NewBoolVar(f'x_{req.id}_{w.id}')
                s = model.NewIntVar(w_start_sec, w_end_sec, f's_{req.id}_{w.id}')
                e = model.NewIntVar(w_start_sec, w_end_sec, f'e_{req.id}_{w.id}')
                
                interval = model.NewOptionalIntervalVar(s, duration_sec, e, x, f'i_{req.id}_{w.id}')
                
                intervals_by_gs[w.ground_station_id].append(interval)
                intervals_by_sat[w.satellite_id].append(interval)
                
                x_vars[(req.id, w.id)] = x
                start_vars[(req.id, w.id)] = s
                end_vars[(req.id, w.id)] = e
                r_x_vars.append(x)
                
                # Objective coefficient: combine base priority and dynamic score.
                dynamic_score = get_dynamic_score(req, self.evaluation_time)
                
                if req.verified_emergency:
                    # To outrank ANY normal request, we use a massive multiplier.
                    # Max normal score = ~4100. Max realistic data = 1e6 MB. 
                    # 1e11 multiplier ensures even 1MB of emergency data beats 20,000,000 MB of critical data.
                    total_priority = 100_000_000_000.0
                else:
                    # Base priority (1-4) is multiplied by 1000 so it dominates, dynamic score (0-100) acts as tie-breaker.
                    total_priority = req.priority.value * 1000.0 + dynamic_score
                    
                # Multiply by data_volume_mb to prioritize high throughput within tiers.
                coeff = int(round(total_priority * req.data_volume_mb))
                objective_terms.append(x * coeff)
                
            if r_x_vars:
                # Each request is scheduled at most once
                model.AddAtMostOne(r_x_vars)
            else:
                rejected_request_ids.append(req.id)
                
        # No overlap constraints
        for gs_id, intervals in intervals_by_gs.items():
            model.AddNoOverlap(intervals)
            
        for sat_id, intervals in intervals_by_sat.items():
            model.AddNoOverlap(intervals)
            
        # Maximize priority-weighted data volume
        model.Maximize(sum(objective_terms))
        
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_sec
        solver.parameters.random_seed = 42 # Deterministic where practical
        solver.parameters.num_search_workers = 1 # Single worker for true determinism
        
        status_code = solver.Solve(model)
        
        # Map status
        status_map = {
            cp_model.OPTIMAL: SolverStatus.OPTIMAL,
            cp_model.FEASIBLE: SolverStatus.FEASIBLE,
            cp_model.INFEASIBLE: SolverStatus.INFEASIBLE,
            cp_model.MODEL_INVALID: SolverStatus.MODEL_INVALID,
            cp_model.UNKNOWN: SolverStatus.UNKNOWN
        }
        status = status_map.get(status_code, SolverStatus.UNKNOWN)
        
        scheduled_tasks = []
        actual_objective = 0.0
        
        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for req in self.raw_requests:
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
                            data_transmitted_mb=req.data_volume_mb
                        )
                        scheduled_tasks.append(task)
                        
                        dynamic_score = get_dynamic_score(req, self.evaluation_time)
                        if req.verified_emergency:
                            total_priority = 100_000_000_000.0
                        else:
                            total_priority = req.priority.value * 1000.0 + dynamic_score
                            
                        coeff = int(round(total_priority * req.data_volume_mb))
                        actual_objective += coeff
                        
                        scheduled = True
                        break # scheduled at most once
                
                if not scheduled and req.id not in rejected_request_ids:
                    rejected_request_ids.append(req.id)
        else:
            # If completely infeasible or unknown
            for req in self.raw_requests:
                if req.id not in rejected_request_ids:
                    rejected_request_ids.append(req.id)
                    
        runtime = time.time() - start_runtime
        
        validator = ScheduleValidator(
            self.raw_satellites, self.raw_ground_stations, self.raw_windows, self.raw_requests
        )
        errors = validator.validate(scheduled_tasks)
        
        if errors:
            status = SolverStatus.MODEL_INVALID
            
        return ScheduleResult(
            id=f"cpsat-run-{uuid.uuid4().hex[:8]}",
            scheduled_tasks=scheduled_tasks,
            rejected_request_ids=rejected_request_ids,
            objective_value=float(actual_objective),
            runtime_seconds=runtime,
            solver_status=status,
            is_valid=len(errors) == 0,
            validation_errors=errors
        )
