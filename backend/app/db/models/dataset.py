"""SQLAlchemy ORM models for Datasets, Ground Stations, and Passes."""

import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


def generate_dataset_id() -> str:
    return f"ds_{uuid.uuid4()}"


class DatasetModel(Base, TimestampMixin):
    """Scenario dataset container."""

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_dataset_id,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ground_stations: Mapped[List["GroundStationModel"]] = relationship(
        "GroundStationModel",
        back_populates="dataset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    satellite_passes: Mapped[List["SatellitePassModel"]] = relationship(
        "SatellitePassModel",
        back_populates="dataset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    schedule_runs: Mapped[List["ScheduleRunModel"]] = relationship(
        "ScheduleRunModel",
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


class GroundStationModel(Base, TimestampMixin):
    """Ground station configuration associated with a dataset."""

    __tablename__ = "ground_stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    station_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    latitude_deg: Mapped[float] = mapped_column(Float, nullable=False)
    longitude_deg: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_mask_deg: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    max_concurrent_passes: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    supported_bands: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    dataset: Mapped["DatasetModel"] = relationship(
        "DatasetModel",
        back_populates="ground_stations",
    )


class SatellitePassModel(Base, TimestampMixin):
    """Satellite pass opportunity associated with a dataset."""

    __tablename__ = "satellite_passes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pass_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    satellite_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ground_station_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    max_elevation_deg: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False, index=True)
    data_volume_gb: Mapped[float] = mapped_column(Float, nullable=False)
    required_bandwidth_mbps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    channel_band: Mapped[Optional[str]] = mapped_column(String(32), default="X-band", nullable=True)

    dataset: Mapped["DatasetModel"] = relationship(
        "DatasetModel",
        back_populates="satellite_passes",
    )
