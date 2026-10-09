"""Common schema components and base models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class OrbitOptBaseModel(BaseModel):
    """Base Pydantic model with default configuration for OrbitOpt."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        from_attributes=True,
    )


class HealthResponse(OrbitOptBaseModel):
    """Health check endpoint response payload."""

    status: str = Field(..., description="Operational status, e.g. 'healthy'")
    version: str = Field(..., description="Application semantic version")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Current UTC timestamp")
    environment: str = Field(..., description="Active environment name (e.g. development, production)")
    database_connected: bool = Field(..., description="True if database connectivity is verified")


class ErrorResponse(OrbitOptBaseModel):
    """Standard error response format."""

    detail: str = Field(..., description="Human-readable error explanation")
    error_code: str = Field(..., description="Machine-readable error classification code")
    details: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional granular error metadata")
