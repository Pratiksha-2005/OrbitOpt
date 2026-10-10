"""Tests for application health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health_check(client: AsyncClient) -> None:
    """Verify root GET /health returns 200 with healthy status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"
    assert data["database_connected"] is True
    assert "timestamp" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_api_v1_health_check(client: AsyncClient) -> None:
    """Verify versioned GET /api/v1/health returns 200 with matching schema."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database_connected"] is True
