"""Tests for Dataset management endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_dataset_success(
    client: AsyncClient,
    sample_dataset_payload: dict,
) -> None:
    """Verify creating a valid dataset returns 201 and stores all items."""
    response = await client.post("/api/v1/datasets", json=sample_dataset_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == sample_dataset_payload["name"]
    assert data["ground_station_count"] == 2
    assert data["satellite_pass_count"] == 3
    assert data["dataset_id"].startswith("ds_")
    assert len(data["ground_stations"]) == 2
    assert len(data["satellite_passes"]) == 3


@pytest.mark.asyncio
async def test_get_dataset_by_id(
    client: AsyncClient,
    sample_dataset_payload: dict,
) -> None:
    """Verify retrieving a dataset by ID."""
    create_res = await client.post("/api/v1/datasets", json=sample_dataset_payload)
    dataset_id = create_res.json()["dataset_id"]

    get_res = await client.get(f"/api/v1/datasets/{dataset_id}")
    assert get_res.status_code == 200
    assert get_res.json()["dataset_id"] == dataset_id
    assert get_res.json()["name"] == sample_dataset_payload["name"]


@pytest.mark.asyncio
async def test_get_dataset_not_found(client: AsyncClient) -> None:
    """Verify 404 is returned for non-existent dataset."""
    response = await client.get("/api/v1/datasets/ds_non_existent_12345")
    assert response.status_code == 404
    data = response.json()
    assert data["error_code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_datasets(
    client: AsyncClient,
    sample_dataset_payload: dict,
) -> None:
    """Verify listing datasets."""
    await client.post("/api/v1/datasets", json=sample_dataset_payload)
    response = await client.get("/api/v1/datasets")
    assert response.status_code == 200
    datasets = response.json()
    assert len(datasets) >= 1
    assert "dataset_id" in datasets[0]


@pytest.mark.asyncio
async def test_create_dataset_validation_errors(
    client: AsyncClient,
    sample_dataset_payload: dict,
) -> None:
    """Verify validation errors for corrupted or inconsistent dataset payloads."""
    # 1. Invalid time window (end_time before start_time)
    invalid_payload = dict(sample_dataset_payload)
    invalid_payload["satellite_passes"] = [
        {
            "pass_id": "PASS-BAD-01",
            "satellite_id": "SAT-1",
            "ground_station_id": "GS-SVALBARD",
            "start_time": "2026-10-10T12:00:00Z",
            "end_time": "2026-10-10T11:00:00Z",  # Earlier than start
            "max_elevation_deg": 45.0,
            "priority": 1,
            "data_volume_gb": 10.0,
        }
    ]
    res = await client.post("/api/v1/datasets", json=invalid_payload)
    assert res.status_code == 422

    # 2. Unknown ground station reference
    invalid_payload2 = dict(sample_dataset_payload)
    invalid_payload2["satellite_passes"] = [
        {
            "pass_id": "PASS-BAD-02",
            "satellite_id": "SAT-1",
            "ground_station_id": "GS-UNKNOWN-STATION",
            "start_time": "2026-10-10T12:00:00Z",
            "end_time": "2026-10-10T12:10:00Z",
            "max_elevation_deg": 45.0,
            "priority": 1,
            "data_volume_gb": 10.0,
        }
    ]
    res2 = await client.post("/api/v1/datasets", json=invalid_payload2)
    assert res2.status_code == 422
