"""API Integration tests for Pass Execution Tracking endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestExecutionsAPI:
    """Test REST API endpoints for /api/v1/executions."""

    async def test_execution_api_lifecycle_and_transition(self, client: AsyncClient, sample_dataset_payload: dict):
        """Test full API lifecycle: create dataset -> optimize schedule -> sync -> transition pass."""
        # 1. Create dataset
        ds_resp = await client.post("/api/v1/datasets", json=sample_dataset_payload)
        assert ds_resp.status_code == 201
        dataset_id = ds_resp.json()["dataset_id"]

        # 2. Run optimize schedule
        opt_resp = await client.post(
            "/api/v1/schedules/optimize",
            json={"dataset_id": dataset_id, "time_limit_seconds": 10.0},
        )
        assert opt_resp.status_code == 200
        run_data = opt_resp.json()
        assert len(run_data["scheduled_passes"]) > 0

        target_pass = run_data["scheduled_passes"][0]
        pass_id = target_pass["pass_id"]

        # 3. List executions (auto-synced upon run persist)
        list_resp = await client.get(f"/api/v1/executions?dataset_id={dataset_id}")
        assert list_resp.status_code == 200
        executions = list_resp.json()
        assert len(executions) > 0
        matched = next((e for e in executions if e["pass_id"] == pass_id), None)
        assert matched is not None
        assert matched["status"] == "SCHEDULED"
        assert matched["is_locked"] is False

        # 4. Transition: SCHEDULED -> ACQUIRING
        t1_resp = await client.post(
            f"/api/v1/executions/{pass_id}/transition",
            json={
                "to_status": "ACQUIRING",
                "telemetry_source": "operator_manual",
                "notes": "Acquisition sequence started",
            },
        )
        assert t1_resp.status_code == 200
        t1_data = t1_resp.json()
        assert t1_data["status"] == "ACQUIRING"
        assert t1_data["is_locked"] is True
        assert t1_data["telemetry_source"] == "operator_manual"

        # 5. Illegal transition: cannot go directly from ACQUIRING -> COMPLETED
        illegal_resp = await client.post(
            f"/api/v1/executions/{pass_id}/transition",
            json={"to_status": "COMPLETED"},
        )
        assert illegal_resp.status_code == 400
        err_data = illegal_resp.json()
        assert err_data["error_code"] == "INVALID_STATE_TRANSITION"

        # 6. Legal transition: ACQUIRING -> TRANSMITTING
        t2_resp = await client.post(
            f"/api/v1/executions/{pass_id}/transition",
            json={"to_status": "TRANSMITTING", "notes": "Signal confirmed"},
        )
        assert t2_resp.status_code == 200
        assert t2_resp.json()["status"] == "TRANSMITTING"
        assert t2_resp.json()["is_locked"] is True

        # 7. Legal transition: TRANSMITTING -> COMPLETED (with telemetry measurements)
        t3_resp = await client.post(
            f"/api/v1/executions/{pass_id}/transition",
            json={
                "to_status": "COMPLETED",
                "actual_data_delivered_gb": 48.0,
                "measured_transfer_rate_mbps": 390.0,
                "telemetry_source": "operator_manual",
                "notes": "Transfer complete",
            },
        )
        assert t3_resp.status_code == 200
        completed_data = t3_resp.json()
        assert completed_data["status"] == "COMPLETED"
        assert completed_data["is_locked"] is True
        assert completed_data["actual_data_delivered_gb"] == 48.0
        assert completed_data["measured_transfer_rate_mbps"] == 390.0
        assert len(completed_data["transition_history"]) == 4

        # 8. Check execution summary endpoint
        summary_resp = await client.get(f"/api/v1/executions/summary?dataset_id={dataset_id}")
        assert summary_resp.status_code == 200
        summary_data = summary_resp.json()
        assert summary_data["completed_count"] >= 1
        assert summary_data["locked_passes_count"] >= 1
        assert summary_data["total_actual_delivered_gb"] >= 48.0

        # 9. Duplicate transition rejection: COMPLETED -> COMPLETED
        dup_resp = await client.post(
            f"/api/v1/executions/{pass_id}/transition",
            json={"to_status": "COMPLETED"},
        )
        assert dup_resp.status_code == 400
        assert dup_resp.json()["error_code"] == "INVALID_STATE_TRANSITION"

    async def test_execution_not_found(self, client: AsyncClient):
        """Querying or updating non-existent pass ID returns 404."""
        resp = await client.get("/api/v1/executions/NON_EXISTENT_PASS")
        assert resp.status_code == 404

        post_resp = await client.post(
            "/api/v1/executions/NON_EXISTENT_PASS/transition",
            json={"to_status": "ACQUIRING"},
        )
        assert post_resp.status_code == 404
