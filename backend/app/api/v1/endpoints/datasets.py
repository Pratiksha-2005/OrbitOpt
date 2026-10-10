"""Dataset management endpoints."""

from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_dataset_service
from app.schemas.dataset import (
    DatasetCreate,
    DatasetRead,
    DatasetSummary,
)
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.post(
    "",
    response_model=DatasetRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create and validate a scheduling scenario dataset",
    description="Registers a new dataset scenario containing Ground Stations and Satellite Pass opportunities.",
)
async def create_dataset(
    data: DatasetCreate,
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetRead:
    """Create and persist a new dataset."""
    return await service.create_dataset(data)


@router.get(
    "",
    response_model=List[DatasetSummary],
    summary="List all dataset scenarios",
    description="Returns compact summary metadata for all registered datasets.",
)
async def list_datasets(
    service: Annotated[DatasetService, Depends(get_dataset_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> List[DatasetSummary]:
    """List datasets with pagination."""
    return await service.list_datasets(skip=skip, limit=limit)


@router.get(
    "/{dataset_id}",
    response_model=DatasetRead,
    summary="Retrieve dataset by ID",
    description="Fetches full scenario dataset details including ground stations and contact passes.",
)
async def get_dataset(
    dataset_id: str,
    service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> DatasetRead:
    """Retrieve full dataset details."""
    return await service.get_dataset(dataset_id)
