"""Satellite Pass (Contact Opportunity) schemas."""

from datetime import datetime
from typing import Optional
from pydantic import Field, model_validator
from .common import OrbitOptBaseModel


class SatellitePassBase(OrbitOptBaseModel):
    """Core satellite pass window attributes."""

    pass_id: str = Field(
        ...,
        description="Unique identifier for the pass opportunity (e.g. 'PASS-SAT01-001')",
        min_length=1,
        max_length=64,
        examples=["PASS-SAT01-001"],
    )
    satellite_id: str = Field(
        ...,
        description="Satellite identifier (e.g. 'SAT-EARTHOBS-1')",
        min_length=1,
        max_length=64,
        examples=["SAT-EARTHOBS-1"],
    )
    ground_station_id: str = Field(
        ...,
        description="Target Ground Station ID for this contact window",
        min_length=1,
        max_length=64,
        examples=["GS-SVALBARD"],
    )
    start_time: datetime = Field(
        ...,
        description="Pass start timestamp in UTC (ISO 8601)",
        examples=["2026-10-10T08:00:00Z"],
    )
    end_time: datetime = Field(
        ...,
        description="Pass end timestamp in UTC (ISO 8601)",
        examples=["2026-10-10T08:12:00Z"],
    )
    max_elevation_deg: float = Field(
        ...,
        description="Maximum elevation angle during the pass in degrees [0.0, 90.0]",
        ge=0.0,
        le=90.0,
        examples=[48.5],
    )
    priority: int = Field(
        default=3,
        description="Priority of the pass (1 = Highest Priority, 5 = Lowest Priority)",
        ge=1,
        le=5,
        examples=[1],
    )
    data_volume_gb: float = Field(
        default=0.0,
        description="Pending/transferable data volume in Gigabytes (GB) available for downlink",
        ge=0.0,
        examples=[42.5],
    )
    pending_data_gb: Optional[float] = Field(
        default=None,
        description="Explicit pending data volume on satellite in GB (alias for data_volume_gb)",
        ge=0.0,
        examples=[42.5],
    )
    effective_data_rate_mbps: Optional[float] = Field(
        default=None,
        description="Effective transmission data rate in Mbps (used for transferable data computation: transferable = min(pending, rate * duration / 8000))",
        gt=0.0,
        examples=[150.0],
    )
    required_bandwidth_mbps: Optional[float] = Field(
        default=None,
        description="Required downlink bandwidth in Mbps (alias for effective_data_rate_mbps)",
        gt=0.0,
        examples=[150.0],
    )
    channel_band: Optional[str] = Field(
        default="X-band",
        description="Frequency band required for communication (e.g., 'X-band', 'S-band')",
        examples=["X-band"],
    )

    @model_validator(mode="after")
    def validate_and_sync_fields(self) -> "SatellitePassBase":
        if self.end_time <= self.start_time:
            raise ValueError(
                f"end_time ({self.end_time.isoformat()}) must be strictly after start_time ({self.start_time.isoformat()})"
            )
        
        # Check for conflicting pending data volume values
        if self.pending_data_gb is not None and self.data_volume_gb > 0.0:
            if abs(self.pending_data_gb - self.data_volume_gb) > 1e-4:
                raise ValueError(
                    f"Conflicting values provided for 'pending_data_gb' ({self.pending_data_gb} GB) "
                    f"and 'data_volume_gb' ({self.data_volume_gb} GB). Please provide matching values or specify only one."
                )

        # Synchronize pending_data_gb and data_volume_gb
        if self.pending_data_gb is not None and self.data_volume_gb == 0.0:
            self.data_volume_gb = self.pending_data_gb
        elif self.pending_data_gb is None and self.data_volume_gb > 0.0:
            self.pending_data_gb = self.data_volume_gb

        if self.data_volume_gb <= 0.0:
            raise ValueError("Pass data volume (or pending_data_gb) must be greater than 0.0 GB")

        # Check for conflicting data rate values
        if self.effective_data_rate_mbps is not None and self.required_bandwidth_mbps is not None:
            if abs(self.effective_data_rate_mbps - self.required_bandwidth_mbps) > 1e-4:
                raise ValueError(
                    f"Conflicting values provided for 'effective_data_rate_mbps' ({self.effective_data_rate_mbps} Mbps) "
                    f"and 'required_bandwidth_mbps' ({self.required_bandwidth_mbps} Mbps). Please specify matching values or only one."
                )

        # Synchronize data rate fields
        if self.effective_data_rate_mbps is not None and self.required_bandwidth_mbps is None:
            self.required_bandwidth_mbps = self.effective_data_rate_mbps
        elif self.required_bandwidth_mbps is not None and self.effective_data_rate_mbps is None:
            self.effective_data_rate_mbps = self.required_bandwidth_mbps

        return self


class SatellitePassCreate(SatellitePassBase):
    """Pass creation schema."""
    pass


class SatellitePassRead(SatellitePassBase):
    """Pass response schema."""
    pass
