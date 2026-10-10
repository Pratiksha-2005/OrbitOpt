"""API integration tests for Ground Station Outages and Re-optimization endpoints."""

from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_outage_unknown_station_returns_404(client: AsyncClient):
    t0 = datetime.now(timezone.utc)
    payload = {
        "station_id": "UNKNOWN_STATION_999",
        "start_time": t0.isoformat(),
        "end_time": (t0 + timedelta(hours=2)).isoformat(),
        "reason": "Antenna motor failure",
    }
    response = await client.post("/api/v1/outages", json=payload)
    assert response.status_code == 404
    body = response.json()
    assert "not found" in body.get("detail", "").lower()


@pytest.mark.asyncio
async def test_create_outage_invalid_interval_returns_422(client: AsyncClient):
    t0 = datetime.now(timezone.utc)
    payload = {
        "station_id": "GS-01",
        "start_time": (t0 + timedelta(hours=2)).isoformat(),
        "end_time": t0.isoformat(),  # End before start
        "reason": "Invalid time window",
    }
    response = await client.post("/api/v1/outages", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_outage_lifecycle_create_list_resolve(client: AsyncClient, sample_dataset_payload: dict):
    # 1. Create a dataset to guarantee valid ground station in test db
    ds_resp = await client.post("/api/v1/datasets", json=sample_dataset_payload)
    assert ds_resp.status_code == 201
    created_ds = ds_resp.json()
    target_ds_id = created_ds["dataset_id"]
    station_id = created_ds["ground_stations"][0]["station_id"]

    # 2. Register outage with auto-reoptimization
    t0 = datetime.now(timezone.utc)
    create_payload = {
        "station_id": station_id,
        "dataset_id": target_ds_id,
        "start_time": t0.isoformat(),
        "end_time": (t0 + timedelta(hours=4)).isoformat(),
        "reason": "Feed horn replacement",
        "auto_reoptimize": True,
    }

    create_resp = await client.post("/api/v1/outages", json=create_payload)
    assert create_resp.status_code == 201
    action_body = create_resp.json()
    assert action_body["outage"]["station_id"] == station_id
    assert action_body["outage"]["status"] == "active"
    outage_id = action_body["outage"]["id"]

    # 3. List outages
    list_resp = await client.get(f"/api/v1/outages?station_id={station_id}")
    assert list_resp.status_code == 200
    outages_list = list_resp.json()
    assert any(o["id"] == outage_id for o in outages_list)

    # 4. Duplicate trigger test: repeated outage registration returns existing without error
    dup_resp = await client.post("/api/v1/outages", json=create_payload)
    assert dup_resp.status_code == 201
    assert "Duplicate active outage detected" in dup_resp.json()["message"]

    # 5. Resolve outage
    resolve_resp = await client.post(f"/api/v1/outages/{outage_id}/resolve?auto_reoptimize=true")
    assert resolve_resp.status_code == 200
    resolve_body = resolve_resp.json()
    assert resolve_body["outage"]["status"] == "resolved"
    assert "RESOLVED" in resolve_body["message"]
