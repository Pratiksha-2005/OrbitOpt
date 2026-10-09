import pytest
from datetime import datetime, timezone, timedelta
from scheduler.models import (
    Satellite, GroundStation, VisibilityWindow, DownlinkRequest, ScheduledTask, Priority
)
from scheduler.rescheduler import Rescheduler

@pytest.fixture
def base_scenario():
    sat1 = Satellite(id="sat-1", name="Sat 1")
    gs1 = GroundStation(id="gs-1", name="GS 1", downlink_rate_mbps=10.0)
    
    t0 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=20))
    
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.LOW)
    
    # Needs 40 seconds.
    t1 = ScheduledTask(
        id="t1", request_id="r1", visibility_window_id="w1", 
        start_time=t0, end_time=t0+timedelta(seconds=40), data_transmitted_mb=50.0
    )
    
    return {
        "satellites": [sat1],
        "ground_stations": [gs1],
        "windows": [w1],
        "requests": [r1],
        "schedule": [t1],
        "t0": t0
    }

def test_reschedule_preserves_active_task(base_scenario):
    t0 = base_scenario["t0"]
    # Evaluation time is t0 + 20s. The task is currently running.
    t_eval = t0 + timedelta(seconds=20)
    
    # A new request arrives
    r2 = DownlinkRequest(id="r2", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    base_scenario["requests"].append(r2)
    
    rescheduler = Rescheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=base_scenario["windows"],
        requests=base_scenario["requests"],
        current_schedule=base_scenario["schedule"],
        evaluation_time=t_eval
    )
    
    res = rescheduler.reschedule()
    assert res.is_valid
    assert len(res.scheduled_tasks) == 2
    
    t1_new = next(t for t in res.scheduled_tasks if t.request_id == "r1")
    t2_new = next(t for t in res.scheduled_tasks if t.request_id == "r2")
    
    # t1 should be completely untouched
    assert t1_new.start_time == t0
    assert t1_new.end_time == t0 + timedelta(seconds=40)
    
    # t2 should start after t1 because of overlap prevention
    assert t2_new.start_time >= t1_new.end_time

def test_reschedule_invalid_rollback(base_scenario):
    t0 = base_scenario["t0"]
    # t_eval must be >= t0 so the task is treated as a fixed active task
    t_eval = t0 + timedelta(hours=1)
    
    # Make the window invalid
    base_scenario["windows"][0].ground_station_id = "unknown"
    
    rescheduler = Rescheduler(
        satellites=base_scenario["satellites"],
        ground_stations=base_scenario["ground_stations"],
        windows=base_scenario["windows"],
        requests=base_scenario["requests"],
        current_schedule=base_scenario["schedule"],
        evaluation_time=t_eval
    )
    res = rescheduler.reschedule()
    assert not res.is_valid
    # Rolled back to original
    assert res.scheduled_tasks == base_scenario["schedule"]
