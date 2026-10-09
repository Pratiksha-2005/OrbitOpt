import uuid
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
        
        result = optimizer.schedule()
        
        # 4. Revalidate combined schedule
        combined_tasks = fixed_tasks + result.scheduled_tasks
        
        validator = ScheduleValidator(
            self.satellites, self.ground_stations, self.windows, self.requests
        )
        errors = validator.validate(combined_tasks)
        
        # 5. Handle safely
        if errors:
            return ScheduleResult(
                id=f"reschedule-invalid-{uuid.uuid4().hex[:8]}",
                scheduled_tasks=self.current_schedule, # Roll back to last valid
                rejected_request_ids=[],
                objective_value=0.0,
                runtime_seconds=result.runtime_seconds,
                solver_status=SolverStatus.MODEL_INVALID,
                is_valid=False,
                validation_errors=errors
            )
            
        # Success: Calculate total objective
        total_objective = 0.0
        req_dict = {r.id: r for r in self.requests}
        for t in combined_tasks:
            req = req_dict.get(t.request_id)
            if req:
                total_objective += req.data_volume_mb * req.priority.value
                
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
