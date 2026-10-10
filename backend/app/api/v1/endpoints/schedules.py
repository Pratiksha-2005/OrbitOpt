"""Scheduling and Optimization execution endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends, status

from app.api.deps import get_schedule_service
from app.schemas.metrics import ScheduleMetrics
from app.schemas.schedule import (
    BaselineScheduleRequest,
    OptimizeScheduleRequest,
    ScheduleRunResponse,
)
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/schedules", tags=["Schedules"])


@router.post(
    "/baseline",
    response_model=ScheduleRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Baseline FCFS Scheduling",
    description="Runs the baseline First-Come-First-Served scheduling algorithm against the given dataset.",
)
async def run_baseline_schedule(
    request: BaselineScheduleRequest,
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> ScheduleRunResponse:
    """Execute baseline FCFS schedule run."""
    return await service.execute_baseline(request)


@router.post(
    "/optimize",
    response_model=ScheduleRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute CP-SAT Multi-Satellite Optimization",
    description="Runs the CP-SAT constraint programming optimizer to maximize downlink throughput and priority satisfaction.",
)
async def run_optimize_schedule(
    request: OptimizeScheduleRequest,
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> ScheduleRunResponse:
    """Execute CP-SAT optimizer run."""
    return await service.execute_optimize(request)


@router.get(
    "/{run_id}",
    response_model=ScheduleRunResponse,
    summary="Retrieve Schedule Run Details",
    description="Fetches full allocation timeline, unassigned passes, and summary metrics for a previous run.",
)
async def get_schedule_run(
    run_id: str,
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> ScheduleRunResponse:
    """Retrieve schedule run by ID."""
    return await service.get_schedule_run(run_id)


@router.get(
    "/{run_id}/metrics",
    response_model=ScheduleMetrics,
    summary="Retrieve Schedule Run Metrics",
    description="Retrieves comparative KPIs, priority satisfaction, and ground station utilization metrics for a run.",
)
async def get_schedule_metrics(
    run_id: str,
    service: Annotated[ScheduleService, Depends(get_schedule_service)],
) -> ScheduleMetrics:
    """Retrieve schedule run metrics."""
    return await service.get_schedule_metrics(run_id)
