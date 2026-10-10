import pytest
from datetime import datetime, timezone, timedelta
from scheduler.models import (
    Satellite, GroundStation, VisibilityWindow, DownlinkRequest, Priority
)
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

def test_fcfs_fits_in_window(base_scenario):
    t0 = base_scenario["t0"]
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=10))
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    
    scheduler = FCFSScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[r1]
    )
    result = scheduler.schedule()
    
    assert result.is_valid
    assert len(result.scheduled_tasks) == 1
    assert not result.rejected_request_ids
    assert result.scheduled_tasks[0].start_time == t0
    # 50MB * 8 / 10Mbps = 40s
    assert result.scheduled_tasks[0].end_time == t0 + timedelta(seconds=40)
    assert result.objective_value == 50.0 * 3 # HIGH priority

def test_fcfs_does_not_fit(base_scenario):
    t0 = base_scenario["t0"]
    # 1 minute window, needs 40s
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(seconds=30))
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    
    scheduler = FCFSScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[r1]
    )
    result = scheduler.schedule()
    
    assert result.is_valid
    assert len(result.scheduled_tasks) == 0
    assert result.rejected_request_ids == ["r1"]

def test_fcfs_satellite_mismatch(base_scenario):
    t0 = base_scenario["t0"]
    w1 = VisibilityWindow(id="w1", satellite_id="sat-2", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=10))
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    
    scheduler = FCFSScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[r1]
    )
    result = scheduler.schedule()
    assert len(result.scheduled_tasks) == 0
    assert result.rejected_request_ids == ["r1"]

def test_fcfs_exact_adjacency_and_gs_conflict(base_scenario):
    t0 = base_scenario["t0"]
    # Two requests for different satellites but same window/GS.
    # r1: 50MB @ 10Mbps = 40s
    # r2: 50MB @ 10Mbps = 40s
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=10))
    w2 = VisibilityWindow(id="w2", satellite_id="sat-2", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=10))
    
    # Priority tie breaker: r1 is CRITICAL, r2 is HIGH
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.CRITICAL)
    r2 = DownlinkRequest(id="r2", satellite_id="sat-2", data_volume_mb=50.0, priority=Priority.HIGH)
    
    scheduler = FCFSScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1, w2],
        requests=[r1, r2]
    )
    result = scheduler.schedule()
    assert result.is_valid
    assert len(result.scheduled_tasks) == 2
    
    t_r1 = next(t for t in result.scheduled_tasks if t.request_id == "r1")
    t_r2 = next(t for t in result.scheduled_tasks if t.request_id == "r2")
    
    assert t_r1.start_time == t0
    assert t_r1.end_time == t0 + timedelta(seconds=40)
    
    # Adjacency: r2 should start exactly when r1 ends
    assert t_r2.start_time == t0 + timedelta(seconds=40)
    assert t_r2.end_time == t0 + timedelta(seconds=80)

def test_fcfs_empty(base_scenario):
    scheduler = FCFSScheduler(base_scenario["satellites"], base_scenario["ground_stations"], [], [])
    result = scheduler.schedule()
    assert result.is_valid
    assert len(result.scheduled_tasks) == 0

def test_fcfs_missing_refs(base_scenario):
    t0 = base_scenario["t0"]
    # Window references unknown GS
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="unknown", start_time=t0, end_time=t0+timedelta(minutes=10))
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    scheduler = FCFSScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[r1]
    )
    result = scheduler.schedule()
    assert len(result.scheduled_tasks) == 0
    assert result.rejected_request_ids == ["r1"]

def test_fcfs_duplicate_requests(base_scenario):
    t0 = base_scenario["t0"]
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=10))
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    # Give the scheduler the same request twice
    scheduler = FCFSScheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=[w1],
        requests=[r1, r1]
    )
    result = scheduler.schedule()
    
    # Should only schedule it once because they have the same ID.
    assert len(result.scheduled_tasks) == 1
    assert result.rejected_request_ids == []
