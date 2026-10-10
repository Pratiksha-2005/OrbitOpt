"""End-to-End API and Persistence Verification Tests for OrbitOpt Scheduler.

Exercises the complete lifecycle:
1. Dataset creation and retrieval
2. Real FCFS baseline schedule execution
3. Real CP-SAT schedule optimization
4. Database persistence and query verification
5. Metrics calculation and mathematical objective validation
6. ScheduleValidator invocation and constraint enforcement
"""

from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.schedule import ScheduledAllocationModel, ScheduleRunModel
from app.db.models.dataset import DatasetModel


@pytest.fixture
def multi_satellite_e2e_dataset_payload() -> dict:
    """Realistic multi-satellite, multi-station scenario with concurrent pass opportunities:
    Ground Stations (150 Mbps standard downlink rate):
      - GS-NORTH (150 Mbps, max 1 pass concurrently)
      - GS-SOUTH (150 Mbps, max 1 pass concurrently)

    Passes (600s window duration each, 12:00:00 - 12:10:00 UTC):
      - PASS-1: SAT-1, GS-NORTH, Priority 1 (weight 10.0), 4.0 GB (needs 213.3s -> 40.0 objective)
      - PASS-2: SAT-2, GS-NORTH, Priority 5 (weight 0.5),  4.0 GB (needs 213.3s -> 2.0 objective)
      - PASS-3: SAT-1, GS-SOUTH, Priority 2 (weight 5.0),  3.0 GB (needs 160.0s -> 15.0 objective)
      - PASS-4: SAT-3, GS-SOUTH, Priority 2 (weight 5.0),  5.0 GB (needs 266.7s -> 25.0 objective)

    Optimal CP-SAT Packing:
      - GS-NORTH: PASS-1 (214s) + PASS-2 (214s) = 428s <= 600s
      - GS-SOUTH: PASS-3 (160s) + PASS-4 (267s) = 427s <= 600s
      - SAT-1: PASS-1 (GS-NORTH, 214s) + PASS-3 (GS-SOUTH, 160s) = 374s <= 600s (no antenna conflict)
      - SAT-2: PASS-2 (GS-NORTH, 214s) <= 600s
      - SAT-3: PASS-4 (GS-SOUTH, 267s) <= 600s
      - Total Objective = 40.0 + 2.0 + 15.0 + 25.0 = 82.0
    """
    return {
        "name": "E2E Multi-Satellite Scheduling Scenario",
        "description": "Deterministic dataset for end-to-end API and solver verification",
        "ground_stations": [
            {
                "station_id": "GS-NORTH",
                "name": "Arctic Ground Station",
                "latitude_deg": 75.0,
                "longitude_deg": 15.0,
                "elevation_mask_deg": 5.0,
                "max_concurrent_passes": 1,
                "supported_bands": ["X-band"],
            },
            {
                "station_id": "GS-SOUTH",
                "name": "Antarctic Ground Station",
                "latitude_deg": -70.0,
                "longitude_deg": 30.0,
                "elevation_mask_deg": 5.0,
                "max_concurrent_passes": 1,
                "supported_bands": ["X-band"],
            },
        ],
        "satellite_passes": [
            {
                "pass_id": "PASS-1",
                "satellite_id": "SAT-1",
                "ground_station_id": "GS-NORTH",
                "start_time": "2026-10-10T12:00:00Z",
                "end_time": "2026-10-10T12:10:00Z",
                "max_elevation_deg": 60.0,
                "priority": 1,
                "data_volume_gb": 4.0,
                "channel_band": "X-band",
            },
            {
                "pass_id": "PASS-2",
                "satellite_id": "SAT-2",
                "ground_station_id": "GS-NORTH",
                "start_time": "2026-10-10T12:00:00Z",
                "end_time": "2026-10-10T12:10:00Z",
                "max_elevation_deg": 40.0,
                "priority": 5,
                "data_volume_gb": 4.0,
                "channel_band": "X-band",
            },
            {
                "pass_id": "PASS-3",
                "satellite_id": "SAT-1",
                "ground_station_id": "GS-SOUTH",
                "start_time": "2026-10-10T12:00:00Z",
                "end_time": "2026-10-10T12:10:00Z",
                "max_elevation_deg": 45.0,
                "priority": 2,
                "data_volume_gb": 3.0,
                "channel_band": "X-band",
            },
            {
                "pass_id": "PASS-4",
                "satellite_id": "SAT-3",
                "ground_station_id": "GS-SOUTH",
                "start_time": "2026-10-10T12:00:00Z",
                "end_time": "2026-10-10T12:10:00Z",
                "max_elevation_deg": 70.0,
                "priority": 2,
                "data_volume_gb": 5.0,
                "channel_band": "X-band",
            },
        ],
    }


@pytest.mark.asyncio
async def test_complete_end_to_end_lifecycle(
    client: AsyncClient,
    multi_satellite_e2e_dataset_payload: dict,
    db_session: AsyncSession,
) -> None:
    """Verify all 9 stages of the end-to-end scheduling lifecycle against live API and DB."""

    # 1. Create dataset
    create_res = await client.post("/api/v1/datasets", json=multi_satellite_e2e_dataset_payload)
    assert create_res.status_code == 201
    dataset_data = create_res.json()
    dataset_id = dataset_data["dataset_id"]
    assert dataset_data["ground_station_count"] == 2
    assert dataset_data["satellite_pass_count"] == 4

    # 2. Retrieve dataset
    get_res = await client.get(f"/api/v1/datasets/{dataset_id}")
    assert get_res.status_code == 200
    retrieved_dataset = get_res.json()
    assert retrieved_dataset["dataset_id"] == dataset_id
    assert len(retrieved_dataset["satellite_passes"]) == 4

    # 3. Run real FCFS baseline endpoint
    fcfs_req = {
        "dataset_id": dataset_id,
        "setup_time_seconds": 60,
    }
    fcfs_res = await client.post("/api/v1/schedules/baseline", json=fcfs_req)
    assert fcfs_res.status_code == 200
    fcfs_data = fcfs_res.json()

    # Verify FCFS properties
    assert fcfs_data["algorithm"] == "baseline_fcfs"
    assert fcfs_data["status"] == "completed"
    assert fcfs_data["is_mock"] is False
    assert fcfs_data["is_valid"] is True
    assert fcfs_data["validation_violations"] == []
    assert fcfs_data["solver_status_detail"] in ("FEASIBLE", "OPTIMAL")
    assert fcfs_data["execution_time_ms"] >= 0.0
    fcfs_run_id = fcfs_data["run_id"]

    # 4. Run real CP-SAT optimization endpoint
    opt_req = {
        "dataset_id": dataset_id,
        "time_limit_seconds": 15.0,
        "setup_time_seconds": 60,
        "priority_weights": {
            "1": 10.0,
            "2": 5.0,
            "3": 2.0,
            "4": 1.0,
            "5": 0.5,
        },
        "maximize_data_volume": True,
    }
    opt_res = await client.post("/api/v1/schedules/optimize", json=opt_req)
    assert opt_res.status_code == 200
    opt_data = opt_res.json()

    # Verify CP-SAT properties
    assert opt_data["algorithm"] == "cp_sat_optimizer"
    assert opt_data["status"] == "completed"
    assert opt_data["is_mock"] is False
    assert opt_data["is_valid"] is True
    assert opt_data["validation_violations"] == []
    assert opt_data["solver_status_detail"] in ("OPTIMAL", "FEASIBLE")
    assert opt_data["execution_time_ms"] >= 0.0
    opt_run_id = opt_data["run_id"]

    # 5. Retrieve both schedule runs via GET /api/v1/schedules/{run_id}
    get_fcfs_run = await client.get(f"/api/v1/schedules/{fcfs_run_id}")
    assert get_fcfs_run.status_code == 200
    assert get_fcfs_run.json()["run_id"] == fcfs_run_id
    assert get_fcfs_run.json()["is_mock"] is False

    get_opt_run = await client.get(f"/api/v1/schedules/{opt_run_id}")
    assert get_opt_run.status_code == 200
    assert get_opt_run.json()["run_id"] == opt_run_id
    assert get_opt_run.json()["is_mock"] is False

    # 6. Retrieve metrics via GET /api/v1/schedules/{run_id}/metrics
    get_fcfs_metrics = await client.get(f"/api/v1/schedules/{fcfs_run_id}/metrics")
    assert get_fcfs_metrics.status_code == 200
    fcfs_metrics = get_fcfs_metrics.json()
    assert fcfs_metrics["total_passes"] == 4
    assert fcfs_metrics["objective_value"] > 0

    get_opt_metrics = await client.get(f"/api/v1/schedules/{opt_run_id}/metrics")
    assert get_opt_metrics.status_code == 200
    opt_metrics = get_opt_metrics.json()
    assert opt_metrics["total_passes"] == 4
    assert opt_metrics["objective_value"] > 0

    # 7 & 8. Verify database persistence matches API responses directly
    # Check ScheduleRunModel in database
    fcfs_db = (
        await db_session.execute(
            select(ScheduleRunModel).where(ScheduleRunModel.id == fcfs_run_id)
        )
    ).scalar_one_or_none()
    assert fcfs_db is not None
    assert fcfs_db.dataset_id == dataset_id
    assert fcfs_db.algorithm == "baseline_fcfs"
    assert fcfs_db.is_mock is False
    assert fcfs_db.is_valid is True

    opt_db = (
        await db_session.execute(
            select(ScheduleRunModel).where(ScheduleRunModel.id == opt_run_id)
        )
    ).scalar_one_or_none()
    assert opt_db is not None
    assert opt_db.dataset_id == dataset_id
    assert opt_db.algorithm == "cp_sat_optimizer"
    assert opt_db.is_mock is False
    assert opt_db.is_valid is True

    # Check ScheduledAllocationModel rows in database
    opt_allocs = (
        await db_session.execute(
            select(ScheduledAllocationModel).where(
                ScheduledAllocationModel.schedule_run_id == opt_run_id
            )
        )
    ).scalars().all()
    assert len(opt_allocs) == len(opt_data["scheduled_passes"])

    # 9. Verify mathematical objective and constraint enforcement
    # CP-SAT optimizes sequential pass schedules across both stations without overlap:
    # PASS-1: 10.0 * 4.0 = 40.0
    # PASS-2: 0.5 * 4.0 = 2.0
    # PASS-3: 5.0 * 3.0 = 15.0
    # PASS-4: 5.0 * 5.0 = 25.0
    # Total optimal objective = 82.0
    opt_sched_ids = {p["pass_id"] for p in opt_data["scheduled_passes"]}
    assert "PASS-1" in opt_sched_ids
    assert "PASS-2" in opt_sched_ids
    assert "PASS-3" in opt_sched_ids
    assert "PASS-4" in opt_sched_ids
    assert opt_data["metrics"]["objective_value"] == 82.0
    assert opt_data["metrics"]["scheduled_passes_count"] == 4
    assert opt_data["metrics"]["unassigned_passes_count"] == 0


@pytest.mark.asyncio
async def test_end_to_end_hard_conflict_resolution(
    client: AsyncClient,
) -> None:
    """Verify that CP-SAT optimizer correctly rejects low priority pass in a hard conflict."""
    payload = {
        "name": "Hard Conflict Scenario",
        "ground_stations": [
            {
                "station_id": "GS-SINGLE",
                "name": "Single Station",
                "latitude_deg": 0.0,
                "longitude_deg": 0.0,
                "elevation_mask_deg": 5.0,
                "max_concurrent_passes": 1,
                "supported_bands": ["X-band"],
            }
        ],
        "satellite_passes": [
            {
                "pass_id": "PASS-HIGH",
                "satellite_id": "SAT-1",
                "ground_station_id": "GS-SINGLE",
                "start_time": "2026-10-10T08:00:00Z",
                "end_time": "2026-10-10T08:05:00Z",  # 300s window
                "max_elevation_deg": 60.0,
                "priority": 1,
                "data_volume_gb": 4.0,  # Needs ~213.3s at 150 Mbps
                "channel_band": "X-band",
            },
            {
                "pass_id": "PASS-LOW",
                "satellite_id": "SAT-2",
                "ground_station_id": "GS-SINGLE",
                "start_time": "2026-10-10T08:00:00Z",
                "end_time": "2026-10-10T08:05:00Z",  # 300s window
                "max_elevation_deg": 40.0,
                "priority": 5,
                "data_volume_gb": 4.0,  # Needs ~213.3s at 150 Mbps
                "channel_band": "X-band",
            },
        ],
    }

    create_res = await client.post("/api/v1/datasets", json=payload)
    assert create_res.status_code == 201
    dataset_id = create_res.json()["dataset_id"]

    opt_res = await client.post(
        "/api/v1/schedules/optimize",
        json={
            "dataset_id": dataset_id,
            "time_limit_seconds": 10.0,
            "priority_weights": {"1": 10.0, "5": 0.5},
        },
    )
    assert opt_res.status_code == 200
    data = opt_res.json()

    assert data["is_mock"] is False
    assert data["status"] == "completed"
    assert data["is_valid"] is True
    assert data["metrics"]["scheduled_passes_count"] == 1
    assert data["metrics"]["unassigned_passes_count"] == 1
    assert data["scheduled_passes"][0]["pass_id"] == "PASS-HIGH"
    assert data["unassigned_passes"][0]["pass_id"] == "PASS-LOW"
    assert data["metrics"]["objective_value"] == 40.0  # 10.0 * 4.0

