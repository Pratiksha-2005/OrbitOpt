import uuid
import math
from typing import List
from datetime import datetime, timezone

from scheduler.models import (
    Satellite, GroundStation, VisibilityWindow, DownlinkRequest, 
    ScheduledTask, ScheduleResult, SolverStatus
)
from scheduler.cpsat import CPSATScheduler
from scheduler.validator import ScheduleValidator

class Rescheduler:
    def __init__(
        self,
        satellites: List[Satellite],
        ground_stations: List[GroundStation],
        windows: List[VisibilityWindow],
        requests: List[DownlinkRequest],
        current_schedule: List[ScheduledTask],
        evaluation_time: datetime | None = None
    ):
        self.satellites = satellites
        self.ground_stations = ground_stations
        self.windows = windows
        self.requests = requests
        self.current_schedule = current_schedule
        self.evaluation_time = evaluation_time or datetime.now(timezone.utc)
        
    def _create_rollback_result(self, status: SolverStatus, errors: List[str], runtime: float) -> ScheduleResult:
        total_objective = 0.0
        req_dict = {r.id: r for r in self.requests}
        scheduled_req_ids = {t.request_id for t in self.current_schedule}
        
        from scheduler.priority import get_base_coefficient, get_emergency_bonus, validate_objective_bounds
        
        validate_objective_bounds(self.requests)
        emergency_bonus = get_emergency_bonus(self.requests)
        
        for t in self.current_schedule:
            req = req_dict.get(t.request_id)
            if req:
                base_coeff = get_base_coefficient(req, self.evaluation_time)
                if req.verified_emergency:
                    coeff = emergency_bonus + base_coeff
                else:
                    coeff = base_coeff
                total_objective += coeff
                
        all_rejected_ids = [r.id for r in self.requests if r.id not in scheduled_req_ids]
        
        return ScheduleResult(
            id=f"reschedule-rollback-{uuid.uuid4().hex[:8]}",
            scheduled_tasks=self.current_schedule,
            rejected_request_ids=all_rejected_ids,
            objective_value=float(total_objective),
            runtime_seconds=runtime,
            solver_status=status,
            is_valid=False if errors else True,
            validation_errors=errors
        )

    def reschedule(self) -> ScheduleResult:
        fixed_tasks = []
        fixed_req_ids = set()
        
        # 1. Preserve already-started or completed tasks
        for task in self.current_schedule:
            if task.start_time <= self.evaluation_time:
                fixed_tasks.append(task)
                fixed_req_ids.add(task.request_id)
                
        # 2. Filter requests to exclude those already fixed
        future_requests = []
        for req in self.requests:
            if req.id not in fixed_req_ids:
                future_requests.append(req)
                
        # 3. Use CPSATScheduler to re-optimize eligible future work
        optimizer = CPSATScheduler(
            satellites=self.satellites,
            ground_stations=self.ground_stations,
            windows=self.windows,
            requests=future_requests,
            fixed_tasks=fixed_tasks,
            evaluation_time=self.evaluation_time
        )
        
        try:
            result = optimizer.schedule()
        except Exception as e:
            return self._create_rollback_result(
                status=SolverStatus.UNKNOWN,
                errors=[f"Optimization threw an exception: {str(e)}"],
                runtime=0.0
            )
            
        if result.solver_status in (SolverStatus.INFEASIBLE, SolverStatus.UNKNOWN, SolverStatus.MODEL_INVALID):
            return self._create_rollback_result(
                status=result.solver_status,
                errors=["Optimization failed or timed out. Rolled back."],
                runtime=result.runtime_seconds
            )
        
        # 4. Revalidate combined schedule
        combined_tasks = fixed_tasks + result.scheduled_tasks
        
        validator = ScheduleValidator(
            self.satellites, self.ground_stations, self.windows, self.requests
        )
        errors = validator.validate(combined_tasks)
        
        # 5. Handle safely
        if errors:
            return self._create_rollback_result(
                status=SolverStatus.MODEL_INVALID,
                errors=errors,
                runtime=result.runtime_seconds
            )
            
        # Success: Calculate total objective
        total_objective = 0.0
        req_dict = {r.id: r for r in self.requests}
        from scheduler.priority import get_base_coefficient, get_emergency_bonus, validate_objective_bounds
        
        validate_objective_bounds(self.requests)
        emergency_bonus = get_emergency_bonus(self.requests)
        
        for t in combined_tasks:
            req = req_dict.get(t.request_id)
            if req:
                base_coeff = get_base_coefficient(req, self.evaluation_time)
                if req.verified_emergency:
                    coeff = emergency_bonus + base_coeff
                else:
                    coeff = base_coeff
                total_objective += coeff
                
        # Any request not in combined_tasks is rejected
        scheduled_req_ids = {t.request_id for t in combined_tasks}
        all_rejected_ids = [r.id for r in self.requests if r.id not in scheduled_req_ids]
        
        return ScheduleResult(
            id=f"reschedule-run-{uuid.uuid4().hex[:8]}",
            scheduled_tasks=combined_tasks,
            rejected_request_ids=all_rejected_ids,
            objective_value=float(total_objective),
            runtime_seconds=result.runtime_seconds,
            solver_status=result.solver_status,
            is_valid=True,
            validation_errors=[]
        )
