"""SQLAlchemy ORM model for Ground Station Outages."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


def generate_outage_id() -> str:
    return f"outage_{uuid.uuid4().hex[:12]}"


class OutageModel(Base, TimestampMixin):
    """Ground station outage or maintenance window record."""

    __tablename__ = "ground_station_outages"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=generate_outage_id,
    )
    station_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    auto_reoptimized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reoptimization_run_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("schedule_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
