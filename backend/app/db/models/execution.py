"""SQLAlchemy ORM model for Pass Execution Tracking and State Machine."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


def generate_execution_id() -> str:
    return f"exec_{uuid.uuid4().hex[:12]}"


class PassExecutionModel(Base, TimestampMixin):
    """Lifecycle and execution tracking record for a scheduled satellite pass."""

    __tablename__ = "pass_executions"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_execution_id,
    )
    pass_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    schedule_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    satellite_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ground_station_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # State machine status: SCHEDULED, ACQUIRING, TRANSMITTING, COMPLETED, MISSED, CANCELLED
    status: Mapped[str] = mapped_column(String(32), default="SCHEDULED", nullable=False, index=True)

    # Whether the pass is currently protected from re-optimization/preemption
    # Locked when status is ACQUIRING, TRANSMITTING, or COMPLETED
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Planned parameters
    planned_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_data_volume_gb: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_transfer_rate_mbps: Mapped[float] = mapped_column(Float, default=150.0, nullable=False)

    # Actual telemetry/execution measurements
    actual_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_data_delivered_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    measured_transfer_rate_mbps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Telemetry source description: e.g. "simulated", "operator_manual", "external_api"
    telemetry_source: Mapped[str] = mapped_column(String(64), default="simulated", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Chronological transition history: list of {from, to, timestamp, measurements, notes, ...}
    transition_history: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
