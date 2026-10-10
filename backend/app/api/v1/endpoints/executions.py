"""Pass Execution Tracking and State Machine API Endpoints."""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_execution_service, get_schedule_service
from app.schemas.execution import (
    PassExecutionRead,
    PassExecutionStatus,
    PassExecutionSummary,
    PassTransitionRequest,
)
from app.services.execution_service import ExecutionService
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/executions", tags=["Executions"])


@router.get(
    "",
    response_model=List[PassExecutionRead],
    summary="List Pass Execution States",
    description="Retrieves scheduled passes and their execution state machine states, lock status, and telemetry.",
)
async def list_executions(
    service: Annotated[ExecutionService, Depends(get_execution_service)],
    dataset_id: Optional[str] = Query(default=None, description="Filter by scenario dataset ID"),
    schedule_run_id: Optional[str] = Query(default=None, description="Filter by schedule run ID"),
    status: Optional[PassExecutionStatus] = Query(default=None, description="Filter by execution status"),
    is_locked: Optional[bool] = Query(default=None, description="Filter by lock status"),
) -> List[PassExecutionRead]:
    """List pass execution tracking records."""
    status_str = status.value if status else None
    return await service.list_executions(
        dataset_id=dataset_id,
        schedule_run_id=schedule_run_id,
        status=status_str,
        is_locked=is_locked,
    )


@router.get(
    "/summary",
    response_model=PassExecutionSummary,
    summary="Get Execution State Machine Summary",
    description="Calculates state machine aggregates (counts per state, locked count, planned vs delivered data volume).",
)
async def get_execution_summary(
    service: Annotated[ExecutionService, Depends(get_execution_service)],
    dataset_id: Optional[str] = Query(default=None, description="Filter summary by dataset ID"),
) -> PassExecutionSummary:
    """Retrieve execution state summary."""
    return await service.get_execution_summary(dataset_id=dataset_id)


@router.get(
    "/{pass_id}",
    response_model=PassExecutionRead,
    summary="Get Pass Execution History",
    description="Retrieves a pass's execution state, transition audit history, planned vs actual data, and measurements.",
)
async def get_execution(
    pass_id: str,
    service: Annotated[ExecutionService, Depends(get_execution_service)],
) -> PassExecutionRead:
    """Get single pass execution record."""
    return await service.get_execution(pass_id)


@router.post(
    "/{pass_id}/transition",
    response_model=PassExecutionRead,
    summary="Transition Pass Execution State",
    description="Transitions a satellite pass to a new execution state machine status, validating legality and recording telemetry measurements.",
)
async def transition_pass(
    pass_id: str,
    payload: PassTransitionRequest,
    service: Annotated[ExecutionService, Depends(get_execution_service)],
) -> PassExecutionRead:
    """Validate and execute a state transition for a scheduled pass."""
    return await service.transition_execution(pass_id=pass_id, request=payload)


@router.post(
    "/sync-schedule/{run_id}",
    response_model=List[PassExecutionRead],
    summary="Synchronize Executions from Schedule Run",
    description="Populates or updates execution state machine records from a completed schedule run.",
)
async def sync_schedule_executions(
    run_id: str,
    schedule_service: Annotated[ScheduleService, Depends(get_schedule_service)],
    execution_service: Annotated[ExecutionService, Depends(get_execution_service)],
) -> List[PassExecutionRead]:
    """Sync execution records from an existing run ID."""
    run = await schedule_service.get_schedule_run(run_id)
    await execution_service.sync_executions_from_run(run)
    return await execution_service.list_executions(schedule_run_id=run_id)
