"""Abstract interface for scheduling engines (Developer 1 integration contract)."""

from abc import ABC, abstractmethod
from app.schemas.dataset import DatasetRead
from app.schemas.schedule import (
    BaselineScheduleRequest,
    OptimizeScheduleRequest,
    ScheduleRunResponse,
)


class BaseSchedulerEngine(ABC):
    """Abstract contract for scheduling algorithms.
    
    Developer 1 will provide the concrete implementation containing:
    - First-Come-First-Served (FCFS) Baseline
    - OR-Tools CP-SAT Multi-Satellite Optimizer
    - Conflict Detection & Validation logic
    """

    @abstractmethod
    async def schedule_baseline(
        self,
        dataset: DatasetRead,
        request: BaselineScheduleRequest,
    ) -> ScheduleRunResponse:
        """Execute baseline FCFS scheduling on the given dataset."""
        pass

    @abstractmethod
    async def schedule_optimize(
        self,
        dataset: DatasetRead,
        request: OptimizeScheduleRequest,
    ) -> ScheduleRunResponse:
        """Execute CP-SAT multi-satellite optimization on the given dataset."""
        pass
