"""Database service for creating, retrieving, and listing datasets."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ResourceNotFoundError
from app.db.models.dataset import (
    DatasetModel,
    GroundStationModel,
    SatellitePassModel,
)
from app.schemas.dataset import DatasetCreate, DatasetRead, DatasetSummary
from app.schemas.ground_station import GroundStationRead
from app.schemas.satellite_pass import SatellitePassRead


class DatasetService:
    """Service layer for dataset lifecycle and persistence."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_dataset(self, data: DatasetCreate) -> DatasetRead:
        """Persist a new dataset with its ground stations and passes."""
        dataset = DatasetModel(
            name=data.name,
            description=data.description,
        )

        for gs in data.ground_stations:
            dataset.ground_stations.append(
                GroundStationModel(
                    station_id=gs.station_id,
                    name=gs.name,
                    latitude_deg=gs.latitude_deg,
                    longitude_deg=gs.longitude_deg,
                    elevation_mask_deg=gs.elevation_mask_deg,
                    max_concurrent_passes=gs.max_concurrent_passes,
                    supported_bands=gs.supported_bands,
                )
            )

        for p in data.satellite_passes:
            dataset.satellite_passes.append(
                SatellitePassModel(
                    pass_id=p.pass_id,
                    satellite_id=p.satellite_id,
                    ground_station_id=p.ground_station_id,
                    start_time=p.start_time,
                    end_time=p.end_time,
                    max_elevation_deg=p.max_elevation_deg,
                    priority=p.priority,
                    data_volume_gb=p.data_volume_gb,
                    required_bandwidth_mbps=p.required_bandwidth_mbps,
                    channel_band=p.channel_band,
                )
            )

        self.db.add(dataset)
        await self.db.commit()
        await self.db.refresh(dataset)

        return self._to_read_schema(dataset)

    async def get_dataset(self, dataset_id: str) -> DatasetRead:
        """Fetch a dataset by ID or raise ResourceNotFoundError."""
        stmt = (
            select(DatasetModel)
            .where(DatasetModel.id == dataset_id)
            .options(
                selectinload(DatasetModel.ground_stations),
                selectinload(DatasetModel.satellite_passes),
            )
        )
        result = await self.db.execute(stmt)
        dataset = result.scalar_one_or_none()

        if not dataset:
            raise ResourceNotFoundError(resource="Dataset", resource_id=dataset_id)

        return self._to_read_schema(dataset)

    async def list_datasets(self, skip: int = 0, limit: int = 50) -> List[DatasetSummary]:
        """List summary info for stored datasets."""
        stmt = (
            select(DatasetModel)
            .options(
                selectinload(DatasetModel.ground_stations),
                selectinload(DatasetModel.satellite_passes),
            )
            .offset(skip)
            .limit(limit)
            .order_by(DatasetModel.created_at.desc())
        )
        result = await self.db.execute(stmt)
        datasets = result.scalars().all()

        return [
            DatasetSummary(
                dataset_id=d.id,
                name=d.name,
                description=d.description,
                ground_station_count=len(d.ground_stations),
                satellite_pass_count=len(d.satellite_passes),
                created_at=d.created_at,
            )
            for d in datasets
        ]

    def _to_read_schema(self, dataset: DatasetModel) -> DatasetRead:
        return DatasetRead(
            dataset_id=dataset.id,
            name=dataset.name,
            description=dataset.description,
            ground_station_count=len(dataset.ground_stations),
            satellite_pass_count=len(dataset.satellite_passes),
            created_at=dataset.created_at,
            ground_stations=[
                GroundStationRead(
                    station_id=gs.station_id,
                    name=gs.name,
                    latitude_deg=gs.latitude_deg,
                    longitude_deg=gs.longitude_deg,
                    elevation_mask_deg=gs.elevation_mask_deg,
                    max_concurrent_passes=gs.max_concurrent_passes,
                    supported_bands=gs.supported_bands,
                )
                for gs in dataset.ground_stations
            ],
            satellite_passes=[
                SatellitePassRead(
                    pass_id=p.pass_id,
                    satellite_id=p.satellite_id,
                    ground_station_id=p.ground_station_id,
                    start_time=p.start_time,
                    end_time=p.end_time,
                    max_elevation_deg=p.max_elevation_deg,
                    priority=p.priority,
                    data_volume_gb=p.data_volume_gb,
                    pending_data_gb=p.data_volume_gb,
                    effective_data_rate_mbps=p.required_bandwidth_mbps,
                    required_bandwidth_mbps=p.required_bandwidth_mbps,
                    channel_band=p.channel_band,
                )
                for p in dataset.satellite_passes
            ],
        )
