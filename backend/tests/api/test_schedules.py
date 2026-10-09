"""Tests for Scheduling execution, retrieval and error endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_scheduler_engine
from app.db.models.schedule import ScheduledAllocationModel, ScheduleRunModel
from app.main import app
from app.schemas.dataset import DatasetRead
from app.schemas.schedule import (
    BaselineScheduleRequest,
    OptimizeScheduleRequest,
    ScheduleRunResponse,
)
from app.services.scheduler_interface import BaseSchedulerEngine


class FailingSchedulerEngine(BaseSchedulerEngine):
    """Engine fixture that simulates unexpected solver crash."""

    async def schedule_baseline(
        self,
        dataset: DatasetRead,
        request: BaselineScheduleRequest,
    ) -> ScheduleRunResponse:
        raise RuntimeError("Simulated baseline engine failure")

    async def schedule_optimize(
        self,
        dataset: DatasetRead,
        request: OptimizeScheduleRequest,
    ) -> ScheduleRunResponse:
        raise RuntimeError("Simulated CP-SAT solver crash")


@pytest.mark.asyncio
async def test_baseline_schedule_execution(
    client: AsyncClient,
    sample_dataset_payload: dict,
    db_session: AsyncSession,
) -> None:
    """Verify running baseline schedule against a dataset and check DB persistence."""
    create_res = await client.post("/api/v1/datasets", json=sample_dataset_payload)
    dataset_id = create_res.json()["dataset_id"]

    req = {
        "dataset_id": dataset_id,
        "setup_time_seconds": 120,
    }
    response = await client.post("/api/v1/schedules/baseline", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["algorithm"] == "baseline_fcfs"
    assert data["status"] == "completed"
    assert data["is_mock"] is False
    assert "metrics" in data
    assert data["metrics"]["total_passes"] == 3
    assert data["metrics"]["objective_value"] > 0
    assert len(data["scheduled_passes"]) + len(data["unassigned_passes"]) == 3
    assert data["run_id"].startswith("run_")

    # Verify directly in database tables
    run_stmt = select(ScheduleRunModel).where(ScheduleRunModel.id == data["run_id"])
    run_row = (await db_session.execute(run_stmt)).scalar_one_or_none()
    assert run_row is not None
    assert run_row.algorithm == "baseline_fcfs"
    assert run_row.dataset_id == dataset_id

    alloc_stmt = select(ScheduledAllocationModel).where(
        ScheduledAllocationModel.schedule_run_id == data["run_id"]
    )
    alloc_rows = (await db_session.execute(alloc_stmt)).scalars().all()
    assert len(alloc_rows) == len(data["scheduled_passes"])


@pytest.mark.asyncio
async def test_optimize_schedule_execution(
    client: AsyncClient,
    sample_dataset_payload: dict,
) -> None:
    """Verify running optimization algorithm with custom objective weights against a dataset."""
    create_res = await client.post("/api/v1/datasets", json=sample_dataset_payload)
    dataset_id = create_res.json()["dataset_id"]

    req = {
        "dataset_id": dataset_id,
        "time_limit_seconds": 15.0,
        "setup_time_seconds": 120,
        "priority_weights": {
            "1": 10.0,
            "2": 5.0,
            "3": 2.0,
            "4": 1.0,
            "5": 0.5,
        },
        "maximize_data_volume": True,
    }
    response = await client.post("/api/v1/schedules/optimize", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["algorithm"] == "cp_sat_optimizer"
    assert data["status"] == "completed"
    assert data["is_mock"] is False
    assert data["metrics"]["scheduled_passes_count"] >= 1
    assert data["metrics"]["objective_value"] > 0


@pytest.mark.asyncio
async def test_schedule_non_existent_dataset(client: AsyncClient) -> None:
    """Verify 404 returned when scheduling non-existent dataset."""
    res_base = await client.post(
        "/api/v1/schedules/baseline",
        json={"dataset_id": "ds_does_not_exist_999", "setup_time_seconds": 120},
    )
    assert res_base.status_code == 404
    assert res_base.json()["error_code"] == "RESOURCE_NOT_FOUND"

    res_opt = await client.post(
        "/api/v1/schedules/optimize",
        json={"dataset_id": "ds_does_not_exist_999", "time_limit_seconds": 10.0},
    )
    assert res_opt.status_code == 404
    assert res_opt.json()["error_code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_schedule_run_and_metrics_not_found(client: AsyncClient) -> None:
    """Verify 404 for missing run IDs."""
    res_run = await client.get("/api/v1/schedules/run_does_not_exist_999")
    assert res_run.status_code == 404
    assert res_run.json()["error_code"] == "RESOURCE_NOT_FOUND"

    res_metrics = await client.get("/api/v1/schedules/run_does_not_exist_999/metrics")
    assert res_metrics.status_code == 404
    assert res_metrics.json()["error_code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_scheduler_engine_failure_handling(
    client: AsyncClient,
    sample_dataset_payload: dict,
) -> None:
    """Verify graceful 500 response when the scheduling engine fails."""
    create_res = await client.post("/api/v1/datasets", json=sample_dataset_payload)
    dataset_id = create_res.json()["dataset_id"]

    # Override scheduler engine with a failing mock
    app.dependency_overrides[get_scheduler_engine] = lambda: FailingSchedulerEngine()

    try:
        res = await client.post(
            "/api/v1/schedules/optimize",
            json={"dataset_id": dataset_id, "time_limit_seconds": 10.0},
        )
        assert res.status_code == 500
        data = res.json()
        assert data["error_code"] == "SCHEDULING_ENGINE_ERROR"
        assert "CP-SAT optimization solver failed" in data["detail"]
    finally:
        app.dependency_overrides.pop(get_scheduler_engine, None)
