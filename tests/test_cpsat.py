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
