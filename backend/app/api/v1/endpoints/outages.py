"""Ground Station Outages and Event-Driven Rescheduling API endpoints."""

from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_outage_service
from app.schemas.outage import (
    OutageActionResponse,
    OutageCreate,
    OutageRead,
    OutageStatus,
)
from app.services.outage_service import OutageService

router = APIRouter(prefix="/outages", tags=["Outages"])


@router.post(
    "",
    response_model=OutageActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Ground Station Outage",
    description="Registers an outage/maintenance window on a ground station and triggers safe event-driven schedule re-optimization.",
)
async def create_outage(
    payload: OutageCreate,
    service: Annotated[OutageService, Depends(get_outage_service)],
) -> OutageActionResponse:
    """Create ground station outage and trigger re-optimization."""
    return await service.create_outage(payload)


@router.get(
    "",
    response_model=List[OutageRead],
    summary="List Ground Station Outages",
    description="Retrieves registered outages, with optional filters for station, dataset, or status.",
)
async def list_outages(
    service: Annotated[OutageService, Depends(get_outage_service)],
    station_id: Optional[str] = Query(default=None, description="Filter by ground station ID"),
    dataset_id: Optional[str] = Query(default=None, description="Filter by scenario dataset ID"),
    status: Optional[OutageStatus] = Query(default=None, description="Filter by status (active/resolved/cancelled)"),
) -> List[OutageRead]:
    """List outages."""
    status_str = status.value if status else None
    return await service.list_outages(
        station_id=station_id,
        dataset_id=dataset_id,
        status=status_str,
    )


@router.get(
    "/{outage_id}",
    response_model=OutageRead,
    summary="Get Outage Details",
    description="Retrieves a specific outage record by ID.",
)
async def get_outage(
    outage_id: str,
    service: Annotated[OutageService, Depends(get_outage_service)],
) -> OutageRead:
    """Get single outage record."""
    return await service.get_outage(outage_id)


@router.post(
    "/{outage_id}/resolve",
    response_model=OutageActionResponse,
    summary="Resolve and Close Outage",
    description="Marks an active outage as resolved, restoring station availability and re-optimizing the schedule.",
)
async def resolve_outage(
    outage_id: str,
    service: Annotated[OutageService, Depends(get_outage_service)],
    auto_reoptimize: bool = Query(default=True, description="Whether to trigger schedule re-optimization upon resolution"),
) -> OutageActionResponse:
    """Resolve ground station outage."""
    return await service.resolve_outage(outage_id, auto_reoptimize=auto_reoptimize)


@router.delete(
    "/{outage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Outage Record",
    description="Deletes an outage record.",
)
async def delete_outage(
    outage_id: str,
    service: Annotated[OutageService, Depends(get_outage_service)],
) -> None:
    """Delete outage."""
    await service.delete_outage(outage_id)
