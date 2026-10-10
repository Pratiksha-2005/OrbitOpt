"""Ground Station schemas for data validation and API serialization."""

from typing import List
from pydantic import Field
from .common import OrbitOptBaseModel


class GroundStationBase(OrbitOptBaseModel):
    """Core Ground Station attributes."""

    station_id: str = Field(
        ...,
        description="Unique identifier for the ground station (e.g. 'GS-SVALBARD')",
        min_length=1,
        max_length=64,
        examples=["GS-SVALBARD"],
    )
    name: str = Field(
        ...,
        description="Human-readable ground station location/name",
        min_length=1,
        max_length=128,
        examples=["Svalbard Ground Station"],
    )
    latitude_deg: float = Field(
        ...,
        description="Latitude in degrees [-90.0, 90.0]",
        ge=-90.0,
        le=90.0,
        examples=[78.2297],
    )
    longitude_deg: float = Field(
        ...,
        description="Longitude in degrees [-180.0, 180.0]",
        ge=-180.0,
        le=180.0,
        examples=[15.4077],
    )
    elevation_mask_deg: float = Field(
        default=5.0,
        description="Minimum horizon elevation angle in degrees for contact visibility [0.0, 90.0]",
        ge=0.0,
        le=90.0,
        examples=[5.0],
    )
    max_concurrent_passes: int = Field(
        default=1,
        description="Maximum concurrent satellite passes supported by this ground station (e.g., number of antennas)",
        ge=1,
        examples=[1],
    )
    supported_bands: List[str] = Field(
        default_factory=lambda: ["S-band", "X-band"],
        description="Radio frequency bands supported by the ground station antennas",
        examples=[["S-band", "X-band", "Ka-band"]],
    )


class GroundStationCreate(GroundStationBase):
    """Schema for ground station creation input."""
    pass


class GroundStationRead(GroundStationBase):
    """Schema for ground station retrieval response."""
    pass
