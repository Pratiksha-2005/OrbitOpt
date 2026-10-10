"""SQLAlchemy ORM models for Schedule Runs and Allocations."""

import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy import (
    Boolean,
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


def generate_run_id() -> str:
    return f"run_{uuid.uuid4()}"


class ScheduleRunModel(Base, TimestampMixin):
    """Execution record of a scheduling run."""

    __tablename__ = "schedule_runs"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_run_id,
    )
    dataset_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validation_violations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    solver_status_detail: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    unassigned_passes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    dataset: Mapped["DatasetModel"] = relationship(
        "DatasetModel",
        back_populates="schedule_runs",
    )
    scheduled_passes: Mapped[List["ScheduledAllocationModel"]] = relationship(
        "ScheduledAllocationModel",
        back_populates="schedule_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ScheduledAllocationModel(Base, TimestampMixin):
    """Allocated satellite pass assignment in a schedule run."""

    __tablename__ = "scheduled_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("schedule_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pass_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    satellite_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ground_station_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    data_volume_gb: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)

    schedule_run: Mapped["ScheduleRunModel"] = relationship(
        "ScheduleRunModel",
        back_populates="scheduled_passes",
    )
