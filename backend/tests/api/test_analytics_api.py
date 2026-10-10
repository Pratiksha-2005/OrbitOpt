"""API integration tests for /analytics endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_analytics_api_endpoints(
    client: AsyncClient,
    sample_dataset_payload: dict,
):
    """Verify operational analytics, deadline risks, and export endpoints via HTTP."""
    # 1. Create dataset
    ds_res = await client.post("/api/v1/datasets", json=sample_dataset_payload)
    assert ds_res.status_code == 201
    dataset_id = ds_res.json()["dataset_id"]

    # 2. Run baseline schedule
    sched_res = await client.post(
        "/api/v1/schedules/baseline",
        json={"dataset_id": dataset_id, "setup_time_seconds": 120},
    )
    assert sched_res.status_code == 200
    run_id = sched_res.json()["run_id"]

    # 3. GET /api/v1/analytics/runs/{run_id}
    analytics_res = await client.get(f"/api/v1/analytics/runs/{run_id}")
    assert analytics_res.status_code == 200
    data = analytics_res.json()
    assert data["run_id"] == run_id
    assert data["dataset_id"] == dataset_id
    assert "planned_data_volume_gb" in data
    assert "actual_delivered_data_gb" in data
    assert "critical_service_rate_pct" in data
    assert "overall_availability_pct" in data
    assert "transmission_utilization_pct" in data
    assert "metric_documentation" in data

    # 4. GET /api/v1/analytics/runs/{run_id}/deadline-risks
    risks_res = await client.get(f"/api/v1/analytics/runs/{run_id}/deadline-risks")
    assert risks_res.status_code == 200
    risk_data = risks_res.json()
    assert risk_data["run_id"] == run_id
    assert risk_data["total_requests"] >= 1
    assert "method_disclaimer" in risk_data
    assert len(risk_data["items"]) >= 1

    # 5. GET /api/v1/analytics/runs/{run_id}/export (format=json)
    json_export = await client.get(f"/api/v1/analytics/runs/{run_id}/export?format=json")
    assert json_export.status_code == 200
    assert "report_metadata" in json_export.json()

    # 6. GET /api/v1/analytics/runs/{run_id}/export (format=csv)
    csv_export = await client.get(f"/api/v1/analytics/runs/{run_id}/export?format=csv")
    assert csv_export.status_code == 200
    assert "text/csv" in csv_export.headers["content-type"]
    assert f'filename="mission_report_{run_id}.csv"' in csv_export.headers["content-disposition"]
    assert "# ORBITOPT MISSION EXECUTION REPORT" in csv_export.text

    # 7. Unknown run ID -> 404
    bad_res = await client.get("/api/v1/analytics/runs/run_invalid_999")
    assert bad_res.status_code == 404
