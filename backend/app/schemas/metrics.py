"""Metrics and KPI evaluation schemas for scheduling runs."""

from typing import Dict, List, Optional
from pydantic import Field
from .common import OrbitOptBaseModel


class ScheduleMetrics(OrbitOptBaseModel):
    """Comparative and operational metrics calculated for a scheduling run."""

    total_passes: int = Field(..., description="Total input contact opportunities")
    scheduled_passes_count: int = Field(..., description="Number of successfully scheduled passes")
    unassigned_passes_count: int = Field(..., description="Number of unassigned/dropped passes")
    scheduled_percentage: float = Field(..., description="Percentage of passes scheduled [0.0 - 100.0]")
    
    total_data_downlinked_gb: float = Field(..., description="Total data volume scheduled for downlink in GB")
    total_pending_data_gb: float = Field(
        default=0.0,
        description="Total pending data volume across all input passes in GB",
    )
    total_contact_time_seconds: float = Field(..., description="Total scheduled contact duration in seconds")
    
    objective_value: float = Field(
        ...,
        description="Agreed optimization objective: sum of priority weight multiplied by transferable data (GB) for all scheduled passes",
    )
    priority_satisfaction_rate: float = Field(
        ...,
        description="Weighted priority satisfaction score [0.0 - 100.0]",
    )
    priority_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of scheduled passes grouped by priority level (e.g., {'1': 5, '2': 3})",
    )
    ground_station_utilization: Dict[str, float] = Field(
        default_factory=dict,
        description="Utilization percentage per ground station [0.0 - 100.0]",
    )
    conflicts_detected: int = Field(
        default=0,
        description="Number of ground station or antenna temporal conflicts detected/resolved",
    )
