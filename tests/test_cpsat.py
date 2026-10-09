import pytest
from datetime import datetime, timezone, timedelta

from scheduler.models import (
    Satellite, GroundStation, VisibilityWindow, DownlinkRequest, Priority, SolverStatus
)
from scheduler.cpsat import CPSATScheduler
from scheduler.fcfs import FCFSScheduler

@pytest.fixture
def base_scenario():
    sat1 = Satellite(id="sat-1", name="Sat 1")
    sat2 = Satellite(id="sat-2", name="Sat 2")
    
    gs1 = GroundStation(id="gs-1", name="GS 1", downlink_rate_mbps=10.0)
    gs2 = GroundStation(id="gs-2", name="GS 2", downlink_rate_mbps=100.0)
    
    t0 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    
    return {
        "satellites": [sat1, sat2],
        "ground_stations": [gs1, gs2],
        "t0": t0
    }

def test_cpsat_basic_feasible(base_scenario):
    t0 = base_scenario["t0"]
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=10))
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    
    scheduler = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[r1]
    )
    result = scheduler.schedule()
    
    assert result.is_valid
    assert len(result.scheduled_tasks) == 1
    assert result.solver_status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE)
    assert not result.rejected_request_ids

def test_cpsat_competing_requests(base_scenario):
    t0 = base_scenario["t0"]
    # 50 second window. 
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(seconds=50))
    
    # Needs 40 seconds
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.MEDIUM)
    # Needs 40 seconds
    r2 = DownlinkRequest(id="r2", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    
    # Both cannot fit in 50 seconds. R2 should win because of higher priority.
    scheduler = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[r1, r2]
    )
    result = scheduler.schedule()
    
    assert result.is_valid
    assert len(result.scheduled_tasks) == 1
    assert result.scheduled_tasks[0].request_id == "r2"
    assert "r1" in result.rejected_request_ids

def test_cpsat_emergency_outranks_normal(base_scenario):
    t0 = base_scenario["t0"]
    # 40s window
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(seconds=40))
    
    # r_normal: CRITICAL, 50MB (needs 40s)
    r_normal = DownlinkRequest(id="r_normal", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.CRITICAL)
    # r_emergency: LOW, 5MB (needs 4s), but verified_emergency=True
    r_emergency = DownlinkRequest(id="r_emergency", satellite_id="sat-1", data_volume_mb=5.0, priority=Priority.LOW, verified_emergency=True)
    
    # Only one can fit. The tiny emergency task should completely dwarf the massive critical normal task.
    scheduler = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[r_normal, r_emergency]
    )
    result = scheduler.schedule()
    
    assert result.is_valid
    assert len(result.scheduled_tasks) == 1
    assert result.scheduled_tasks[0].request_id == "r_emergency"

def test_cpsat_emergency_outranks_massive_normal(base_scenario):
    t0 = base_scenario["t0"]
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(seconds=40))
    
    requests = []
    # 100 normal requests, 1000MB each. Total = 100,000MB.
    # Priority is CRITICAL (4). They require way more time than 40s.
    for i in range(100):
        requests.append(DownlinkRequest(
            id=f"r_norm_{i}", satellite_id="sat-1", data_volume_mb=1000.0, priority=Priority.CRITICAL
        ))
        
    # r_emergency: LOW, 1MB (needs 0.8s), verified_emergency=True
    r_emergency = DownlinkRequest(id="r_emergency", satellite_id="sat-1", data_volume_mb=1.0, priority=Priority.LOW, verified_emergency=True)
    requests.append(r_emergency)
    
    scheduler = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=requests
    )
    result = scheduler.schedule()
    
    assert result.is_valid
    # The emergency task MUST be scheduled, despite the presence of 100 massive critical tasks.
    assert any(t.request_id == "r_emergency" for t in result.scheduled_tasks)
    
def test_cpsat_infeasible_emergency(base_scenario):
    t0 = base_scenario["t0"]
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(seconds=10))
    
    # 10s window. Normal fits.
    r_norm = DownlinkRequest(id="r_norm", satellite_id="sat-1", data_volume_mb=5.0, priority=Priority.MEDIUM)
    
    # Emergency needs 100s, so it is mathematically infeasible.
    r_emergency = DownlinkRequest(id="r_emergency", satellite_id="sat-1", data_volume_mb=100.0, priority=Priority.LOW, verified_emergency=True)
    
    scheduler = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[r_norm, r_emergency]
    )
    res = scheduler.schedule()
    
    assert res.is_valid
    assert len(res.scheduled_tasks) == 1
    assert res.scheduled_tasks[0].request_id == "r_norm"
    assert "r_emergency" in res.rejected_request_ids

def test_cpsat_multiple_emergencies_count_priority(base_scenario):
    t0 = base_scenario["t0"]
    # 20s window.
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(seconds=20))
    
    # E1 needs 16s (20MB)
    e1 = DownlinkRequest(id="e1", satellite_id="sat-1", data_volume_mb=20.0, priority=Priority.CRITICAL, verified_emergency=True)
    # E2 needs 8s (10MB)
    e2 = DownlinkRequest(id="e2", satellite_id="sat-1", data_volume_mb=10.0, priority=Priority.LOW, verified_emergency=True)
    # E3 needs 8s (10MB)
    e3 = DownlinkRequest(id="e3", satellite_id="sat-1", data_volume_mb=10.0, priority=Priority.LOW, verified_emergency=True)
    
    # E1 has double the data volume (and base score) of E2+E3 combined.
    # However, E2+E3 yields a count of 2 emergencies.
    # The lexicographic rule dictates we must schedule 2 emergencies over 1, regardless of their data volume tie-breaker.
    scheduler = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[e1, e2, e3]
    )
    res = scheduler.schedule()
    assert res.is_valid
    assert len(res.scheduled_tasks) == 2
    scheduled_ids = {t.request_id for t in res.scheduled_tasks}
    assert "e2" in scheduled_ids and "e3" in scheduled_ids
    assert "e1" not in scheduled_ids

def test_cpsat_extreme_values(base_scenario):
    t0 = base_scenario["t0"]
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(seconds=20))
    
    # Exabyte dataset to see if it overflows Python's int math or CPSAT
    # 1 Exabyte = 1e12 MB
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=1e12, priority=Priority.CRITICAL)
    # Emergency 
    r2 = DownlinkRequest(id="r2", satellite_id="sat-1", data_volume_mb=1.0, priority=Priority.LOW, verified_emergency=True)
    
    # They both obviously can't fit in 20s. But testing the objective bounding logic.
    scheduler = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[r1, r2]
    )
    # Will fail validation initially because duration > 20s. 
    # But it shouldn't crash during objective building.
    res = scheduler.schedule()
    # E is 1MB, so it fits (needs 0.8s). R1 is 1e12 MB, needs 8e11s.
    # E will be scheduled.
    assert res.is_valid
    assert len(res.scheduled_tasks) == 1
    assert res.scheduled_tasks[0].request_id == "r2"

def test_cpsat_objective_bound_validation(base_scenario):
    # This dataset creates an objective sum that exceeds 64-bit limits.
    # 9.22e18 is the limit. 
    # If we have one request with data_volume_mb = 3e15, max base score is 3e15 * 4100 = 1.23e19.
    # This exceeds 9.2e18.
    
    r_massive = DownlinkRequest(id="r_massive", satellite_id="sat-1", data_volume_mb=3e15, priority=Priority.CRITICAL)
    
    scheduler = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[],
        requests=[r_massive]
    )
    
    with pytest.raises(ValueError, match="exceeds CP-SAT 64-bit signed integer limit"):
        scheduler.schedule()

def test_fractional_data_volumes(base_scenario):
    t0 = base_scenario["t0"]
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(seconds=20))
    
    # Fractional boundaries
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=0.0001, priority=Priority.LOW, verified_emergency=True)
    r2 = DownlinkRequest(id="r2", satellite_id="sat-1", data_volume_mb=100.5, priority=Priority.MEDIUM)
    
    scheduler = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[r1, r2]
    )
    res = scheduler.schedule()
    assert res.is_valid
    # The tiny fractional emergency should easily be scheduled and outrank despite small roundoff
    scheduled_ids = {t.request_id for t in res.scheduled_tasks}
    assert "r1" in scheduled_ids

def test_cpsat_compare_fcfs(base_scenario):
    t0 = base_scenario["t0"]
    # We want a scenario where FCFS is suboptimal.
    # Let w1 for sat-1 on gs-1 be T=0 to T=60.
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(seconds=60))
    # Let w2 for sat-2 on gs-1 be T=10 to T=70.
    w2 = VisibilityWindow(id="w2", satellite_id="sat-2", ground_station_id="gs-1", start_time=t0+timedelta(seconds=10), end_time=t0+timedelta(seconds=70))
    
    # r1 is MEDIUM, uses sat-1. Needs 40s.
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.MEDIUM)
    # r2 is CRITICAL, uses sat-2. Needs 40s.
    r2 = DownlinkRequest(id="r2", satellite_id="sat-2", data_volume_mb=50.0, priority=Priority.CRITICAL)
    
    fcfs = FCFSScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1, w2],
        requests=[r1, r2]
    )
    fcfs_res = fcfs.schedule()
    
    cpsat = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1, w2],
        requests=[r1, r2]
    )
    cpsat_res = cpsat.schedule()
    
    assert fcfs_res.scheduled_tasks[0].request_id == "r1"
    assert "r2" in fcfs_res.rejected_request_ids
    
    assert cpsat_res.scheduled_tasks[0].request_id == "r2"
    assert "r1" in cpsat_res.rejected_request_ids
    
    assert cpsat_res.objective_value > fcfs_res.objective_value

def test_cpsat_empty_input(base_scenario):
    scheduler = CPSATScheduler(base_scenario["satellites"], base_scenario["ground_stations"], [], [])
    result = scheduler.schedule()
    assert result.is_valid
    assert len(result.scheduled_tasks) == 0

def test_cpsat_no_eligible_window(base_scenario):
    t0 = base_scenario["t0"]
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    scheduler = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[],
        requests=[r1]
    )
    result = scheduler.schedule()
    assert len(result.scheduled_tasks) == 0
    assert result.rejected_request_ids == ["r1"]

def test_cpsat_sat_overlap_prevention(base_scenario):
    t0 = base_scenario["t0"]
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(seconds=50))
    w2 = VisibilityWindow(id="w2", satellite_id="sat-1", ground_station_id="gs-2", start_time=t0, end_time=t0+timedelta(seconds=50))
    
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    r2 = DownlinkRequest(id="r2", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.MEDIUM)
    
    # 50MB needs 40s on gs-1, 4s on gs-2. Total sequentially is 44s.
    # It fits sequentially on the same satellite across two ground stations.
    scheduler = CPSATScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1, w2],
        requests=[r1, r2]
    )
    result = scheduler.schedule()
    assert result.is_valid
    assert len(result.scheduled_tasks) == 2
