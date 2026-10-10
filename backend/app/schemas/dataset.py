"""Dataset schemas for scenario configuration and validation."""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import Field, model_validator
from .common import OrbitOptBaseModel
from .ground_station import GroundStationCreate, GroundStationRead
from .satellite_pass import SatellitePassCreate, SatellitePassRead


class DatasetCreate(OrbitOptBaseModel):
    """Schema for creating and registering a scenario dataset."""

    dataset_id: Optional[str] = Field(
        default=None,
        description="Optional custom unique identifier for deterministic scenario registration",
        max_length=64,
        examples=["ds_priority_contention_benchmark"],
    )
    name: str = Field(
        ...,
        description="Descriptive name of the scheduling dataset scenario",
        min_length=1,
        max_length=128,
        examples=["LEO Constellation 24h Scenario"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional detailed overview of scenario objectives and constraints",
        max_length=512,
        examples=["Global multi-satellite downlink scenario across 5 polar and equatorial stations."],
    )
    ground_stations: List[GroundStationCreate] = Field(
        ...,
        description="List of ground stations participating in the scenario",
        min_length=1,
    )
    satellite_passes: List[SatellitePassCreate] = Field(
        ...,
        description="List of satellite contact pass opportunities",
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_ground_station_references(self) -> "DatasetCreate":
        station_ids = {gs.station_id for gs in self.ground_stations}
        
        # Check for duplicate station IDs
        if len(station_ids) != len(self.ground_stations):
            raise ValueError("Duplicate station_id detected in ground_stations list.")

        # Check for duplicate pass IDs
        pass_ids = {p.pass_id for p in self.satellite_passes}
        if len(pass_ids) != len(self.satellite_passes):
            raise ValueError("Duplicate pass_id detected in satellite_passes list.")

        # Ensure all passes refer to existing stations in the dataset
        for p in self.satellite_passes:
            if p.ground_station_id not in station_ids:
                raise ValueError(
                    f"Pass '{p.pass_id}' references unknown ground_station_id '{p.ground_station_id}'. "
                    f"Available stations: {sorted(list(station_ids))}"
                )

        return self


class DatasetRead(OrbitOptBaseModel):
    """Schema for reading a dataset with full details."""

    dataset_id: str = Field(..., description="Unique dataset identifier")
    name: str = Field(..., description="Scenario name")
    description: Optional[str] = Field(default=None, description="Scenario description")
    ground_station_count: int = Field(..., description="Total ground stations in dataset")
    satellite_pass_count: int = Field(..., description="Total satellite passes in dataset")
    created_at: datetime = Field(..., description="Creation timestamp in UTC")
    ground_stations: List[GroundStationRead] = Field(default_factory=list)
    satellite_passes: List[SatellitePassRead] = Field(default_factory=list)


class DatasetSummary(OrbitOptBaseModel):
    """Compact summary of a dataset for list views."""

    dataset_id: str
    name: str
    description: Optional[str] = None
    ground_station_count: int
    satellite_pass_count: int
    created_at: datetime
