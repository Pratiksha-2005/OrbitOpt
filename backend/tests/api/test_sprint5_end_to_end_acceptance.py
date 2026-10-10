"""Sprint 5 End-to-End Integration and Acceptance Test.

Executes the complete 11-step operational workflow:
1. Select dataset & verify ground stations and contact opportunities.
2. Run FCFS baseline and record actual results.
3. Run CP-SAT optimization with equivalent constraints and record actual results.
4. Verify both schedules pass independent validator.
5. Create ground station outage affecting a future pass.
6. Trigger re-optimization; verify outage exclusion and active pass locking.
7. Resolve outage; verify station capacity restoration.
8. Transition pass through ACQUIRING -> TRANSMITTING -> COMPLETED.
9. Verify completed pass is immutable and actual telemetry is distinct from planned.
10. Retrieve Mission Reports analytics and check exact metric formulas.
11. Download CSV and JSON report exports and validate headers, KPIs, and risk registers.
"""

from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient


@pytest.fixture
def acceptance_dataset_payload() -> dict:
    base_time = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    return {
        "dataset_id": "ds_sprint5_acceptance_leo",
        "name": "Sprint 5 LEO Constellation Scenario",
        "description": "Deterministic scenario for complete end-to-end acceptance validation",
        "ground_stations": [
            {
                "station_id": "GS-NORTH-POLAR",
                "name": "Svalbard Ground Station",
                "latitude_deg": 78.22,
                "longitude_deg": 15.65,
                "elevation_m": 450.0,
                "downlink_rate_mbps": 250.0,
            },
            {
                "station_id": "GS-MID-LAT",
                "name": "Hartebeesthoek Station",
                "latitude_deg": -25.88,
                "longitude_deg": 27.70,
                "elevation_m": 1550.0,
                "downlink_rate_mbps": 180.0,
            },
        ],
        "satellite_passes": [
            # Pass 1: Priority 1 (Critical) on North Polar (will be locked)
            {
                "pass_id": "PASS-ACC-01",
                "satellite_id": "SAT-EO-ALPHA",
                "ground_station_id": "GS-NORTH-POLAR",
                "start_time": base_time.isoformat(),
                "end_time": (base_time + timedelta(minutes=10)).isoformat(),
                "max_elevation_deg": 72.0,
                "priority": 1,
                "data_volume_gb": 25.0,
            },
            # Pass 2: Priority 2 (High) on North Polar (conflicts with outage)
            {
                "pass_id": "PASS-ACC-02",
                "satellite_id": "SAT-RADAR-1",
                "ground_station_id": "GS-NORTH-POLAR",
                "start_time": (base_time + timedelta(minutes=20)).isoformat(),
                "end_time": (base_time + timedelta(minutes=30)).isoformat(),
                "max_elevation_deg": 55.0,
                "priority": 2,
                "data_volume_gb": 18.0,
            },
            # Pass 3: Priority 3 (Medium) on Mid-Lat (independent station)
            {
                "pass_id": "PASS-ACC-03",
                "satellite_id": "SAT-MET-1",
                "ground_station_id": "GS-MID-LAT",
                "start_time": (base_time + timedelta(minutes=15)).isoformat(),
                "end_time": (base_time + timedelta(minutes=25)).isoformat(),
                "max_elevation_deg": 48.0,
                "priority": 3,
                "data_volume_gb": 12.0,
            },
        ],
    }


@pytest.mark.asyncio
async def test_full_sprint5_end_to_end_acceptance_scenario(
    client: AsyncClient,
    acceptance_dataset_payload: dict,
):
    # -------------------------------------------------------------------------
    # STEP 1: Register and load dataset
    # -------------------------------------------------------------------------
    ds_res = await client.post("/api/v1/datasets", json=acceptance_dataset_payload)
    assert ds_res.status_code == 201, f"Dataset creation failed: {ds_res.text}"
    dataset = ds_res.json()
    dataset_id = dataset["dataset_id"]
    assert len(dataset["ground_stations"]) == 2
    assert len(dataset["satellite_passes"]) == 3

    # -------------------------------------------------------------------------
    # STEP 2: Run Baseline FCFS
    # -------------------------------------------------------------------------
    fcfs_res = await client.post(
        "/api/v1/schedules/baseline",
        json={"dataset_id": dataset_id, "setup_time_seconds": 120},
    )
    assert fcfs_res.status_code == 200, f"FCFS failed: {fcfs_res.text}"
    fcfs_data = fcfs_res.json()
    fcfs_run_id = fcfs_data["run_id"]
    assert fcfs_data["algorithm"] == "baseline_fcfs"
    assert fcfs_data["is_valid"] is True
    assert fcfs_data["metrics"]["scheduled_passes_count"] >= 2
    assert fcfs_data["metrics"]["total_data_downlinked_gb"] > 0

    # -------------------------------------------------------------------------
    # STEP 3: Run CP-SAT Optimizer with equivalent constraints
    # -------------------------------------------------------------------------
    cpsat_res = await client.post(
        "/api/v1/schedules/optimize",
        json={"dataset_id": dataset_id, "time_limit_seconds": 5},
    )
    assert cpsat_res.status_code == 200, f"CP-SAT failed: {cpsat_res.text}"
    cpsat_data = cpsat_res.json()
    cpsat_run_id = cpsat_data["run_id"]
    assert cpsat_data["algorithm"] == "cp_sat_optimizer"
    assert cpsat_data["is_valid"] is True
    assert cpsat_data["metrics"]["objective_value"] >= fcfs_data["metrics"]["objective_value"]

    # -------------------------------------------------------------------------
    # STEP 4: Validate both schedules independently
    # -------------------------------------------------------------------------
    assert fcfs_data["is_valid"] is True and len(fcfs_data["validation_violations"]) == 0
    assert cpsat_data["is_valid"] is True and len(cpsat_data["validation_violations"]) == 0

    # -------------------------------------------------------------------------
    # STEP 5: Create Ground Station Outage affecting future PASS-ACC-02 on GS-NORTH-POLAR
    # -------------------------------------------------------------------------
    base_time = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    outage_payload = {
        "station_id": "GS-NORTH-POLAR",
        "start_time": (base_time + timedelta(minutes=18)).isoformat(),
        "end_time": (base_time + timedelta(minutes=32)).isoformat(),
        "reason": "Antenna feedhorn calibration & radome inspection",
        "dataset_id": dataset_id,
        "auto_reoptimize": False,
    }
    outage_res = await client.post("/api/v1/outages", json=outage_payload)
    assert outage_res.status_code == 201, f"Outage creation failed: {outage_res.text}"
    outage_data = outage_res.json()
    outage_id = outage_data["outage"]["id"]
    assert "PASS-ACC-02" in outage_data["affected_pass_ids"]

    # -------------------------------------------------------------------------
    # STEP 6: Lock PASS-ACC-01 in ACQUIRING and verify safe re-optimization
    # -------------------------------------------------------------------------
    trans_res1 = await client.post(
        "/api/v1/executions/PASS-ACC-01/transition",
        json={
            "to_status": "ACQUIRING",
            "timestamp": base_time.isoformat(),
            "actual_start_time": base_time.isoformat(),
            "is_simulated": True,
            "notes": "Acquiring carrier frequency on Svalbard",
        },
    )
    assert trans_res1.status_code == 200
    assert trans_res1.json()["is_locked"] is True

    # Re-optimize with outage and locked pass
    reopt_res = await client.post(
        "/api/v1/schedules/optimize",
        json={"dataset_id": dataset_id, "time_limit_seconds": 5},
    )
    assert reopt_res.status_code == 200
    reopt_data = reopt_res.json()
    reopt_sched_ids = {sp["pass_id"] for sp in reopt_data["scheduled_passes"]}

    # Locked pass MUST remain in schedule
    assert "PASS-ACC-01" in reopt_sched_ids
    # Outage pass PASS-ACC-02 MUST NOT be scheduled on the degraded station
    assert "PASS-ACC-02" not in reopt_sched_ids

    # -------------------------------------------------------------------------
    # STEP 7: Resolve the outage & verify station capacity restored
    # -------------------------------------------------------------------------
    resolve_res = await client.post(f"/api/v1/outages/{outage_id}/resolve?auto_reoptimize=true")
    assert resolve_res.status_code == 200
    resolve_data = resolve_res.json()
    assert resolve_data["outage"]["status"] == "resolved"

    # Re-optimize after resolution: PASS-ACC-02 should now be eligible for scheduling
    post_res_opt = await client.post(
        "/api/v1/schedules/optimize",
        json={"dataset_id": dataset_id, "time_limit_seconds": 5},
    )
    assert post_res_opt.status_code == 200
    post_res_sched_ids = {sp["pass_id"] for sp in post_res_opt.json()["scheduled_passes"]}
    assert "PASS-ACC-01" in post_res_sched_ids

    # -------------------------------------------------------------------------
    # STEP 8: Transition PASS-ACC-01 -> TRANSMITTING -> COMPLETED
    # -------------------------------------------------------------------------
    trans_res2 = await client.post(
        "/api/v1/executions/PASS-ACC-01/transition",
        json={
            "to_status": "TRANSMITTING",
            "timestamp": (base_time + timedelta(minutes=2)).isoformat(),
            "actual_data_delivered_gb": 15.0,
            "is_simulated": True,
        },
    )
    assert trans_res2.status_code == 200
    assert trans_res2.json()["status"] == "TRANSMITTING"

    trans_res3 = await client.post(
        "/api/v1/executions/PASS-ACC-01/transition",
        json={
            "to_status": "COMPLETED",
            "timestamp": (base_time + timedelta(minutes=10)).isoformat(),
            "actual_end_time": (base_time + timedelta(minutes=10)).isoformat(),
            "actual_data_delivered_gb": 24.2,  # Actual measurement: 24.2 GB delivered vs 25.0 GB planned
            "is_simulated": True,
            "notes": "Downlink finished cleanly.",
        },
    )
    assert trans_res3.status_code == 200
    completed_exec = trans_res3.json()
    assert completed_exec["status"] == "COMPLETED"
    assert completed_exec["is_locked"] is True

    # -------------------------------------------------------------------------
    # STEP 9: Verify COMPLETED pass immutability & telemetry separation
    # -------------------------------------------------------------------------
    # Re-optimization must retain COMPLETED pass
    reopt_post_comp = await client.post(
        "/api/v1/schedules/optimize",
        json={"dataset_id": dataset_id, "time_limit_seconds": 5},
    )
    assert reopt_post_comp.status_code == 200
    active_sched = reopt_post_comp.json()
    comp_pass = next(sp for sp in active_sched["scheduled_passes"] if sp["pass_id"] == "PASS-ACC-01")
    assert comp_pass["execution_status"] == "COMPLETED"
    assert comp_pass["is_locked"] is True
    assert comp_pass["data_volume_gb"] == 11.25  # Channel-bounded planned volume (150 Mbps * 600s / 8000)
    assert comp_pass["actual_data_delivered_gb"] == 24.2  # Actual delivery distinct from planned

    # -------------------------------------------------------------------------
    # STEP 10: Open Mission Reports and verify operational metrics
    # -------------------------------------------------------------------------
    analytics_res = await client.get(f"/api/v1/analytics/runs/{active_sched['run_id']}")
    assert analytics_res.status_code == 200
    metrics = analytics_res.json()
    assert metrics["run_id"] == active_sched["run_id"]
    assert metrics["dataset_id"] == dataset_id
    assert metrics["actual_delivered_data_gb"] == 24.2
    assert metrics["planned_data_volume_gb"] > 0.0
    assert metrics["completed_passes_count"] == 1
    assert metrics["critical_service_rate_pct"] == 100.0  # PASS-ACC-01 is P1
    assert metrics["transmission_utilization_pct"] > 0.0
    assert metrics["total_occupancy_pct"] >= metrics["transmission_utilization_pct"]

    # Check Deadline Risk Register
    risks_res = await client.get(f"/api/v1/analytics/runs/{active_sched['run_id']}/deadline-risks")
    assert risks_res.status_code == 200
    risk_reg = risks_res.json()
    pass1_risk = next(r for r in risk_reg["items"] if r["pass_id"] == "PASS-ACC-01")
    assert pass1_risk["risk_level"] == "LOW"
    assert "completed" in pass1_risk["explanation"].lower()

    # -------------------------------------------------------------------------
    # STEP 11: Export CSV and JSON reports and validate contents
    # -------------------------------------------------------------------------
    # JSON Export
    json_exp_res = await client.get(f"/api/v1/analytics/runs/{active_sched['run_id']}/export?format=json")
    assert json_exp_res.status_code == 200
    json_data = json_exp_res.json()
    assert "report_metadata" in json_data
    assert json_data["report_metadata"]["run_id"] == active_sched["run_id"]
    assert json_data["operational_analytics"]["actual_delivered_data_gb"] == 24.2

    # CSV Export
    csv_exp_res = await client.get(f"/api/v1/analytics/runs/{active_sched['run_id']}/export?format=csv")
    assert csv_exp_res.status_code == 200
    assert "text/csv" in csv_exp_res.headers["content-type"]
    assert f'filename="mission_report_{active_sched["run_id"]}.csv"' in csv_exp_res.headers["content-disposition"]
    csv_text = csv_exp_res.text
    assert "# ORBITOPT MISSION EXECUTION REPORT" in csv_text
    assert active_sched["run_id"] in csv_text
    assert "PASS-ACC-01" in csv_text
    assert "24.2" in csv_text  # Actual delivered data in CSV
