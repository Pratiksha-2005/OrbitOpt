import pytest
from datetime import datetime, timezone, timedelta
from scheduler.models import (
    Satellite, GroundStation, VisibilityWindow, DownlinkRequest, ScheduledTask, Priority
)
from scheduler.validator import ScheduleValidator

@pytest.fixture
def base_scenario():
    sat1 = Satellite(id="sat-1", name="Sat 1")
    sat2 = Satellite(id="sat-2", name="Sat 2")
    
    gs1 = GroundStation(id="gs-1", name="GS 1", downlink_rate_mbps=10.0)
    gs2 = GroundStation(id="gs-2", name="GS 2", downlink_rate_mbps=100.0)
    
    t0 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=10))
    w2 = VisibilityWindow(id="w2", satellite_id="sat-2", ground_station_id="gs-2", start_time=t0, end_time=t0+timedelta(minutes=10))
    
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    r2 = DownlinkRequest(id="r2", satellite_id="sat-2", data_volume_mb=200.0, priority=Priority.MEDIUM)
    
    return {
        "satellites": [sat1, sat2],
        "ground_stations": [gs1, gs2],
        "windows": [w1, w2],
        "requests": [r1, r2],
        "t0": t0
    }

def test_valid_schedule(base_scenario):
    t0 = base_scenario["t0"]
    # req 1: 50 MB = 400 Mb. Rate gs1 = 10 Mbps. Needed = 40s.
    t1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w1", 
                       start_time=t0, end_time=t0+timedelta(seconds=40), data_transmitted_mb=50.0)
    # req 2: 200 MB = 1600 Mb. Rate gs2 = 100 Mbps. Needed = 16s.
    t2 = ScheduledTask(id="t2", request_id="r2", visibility_window_id="w2",
                       start_time=t0, end_time=t0+timedelta(seconds=16), data_transmitted_mb=200.0)
    
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1, t2])
    assert not errors

def test_missing_references(base_scenario):
    t0 = base_scenario["t0"]
    t1 = ScheduledTask(id="t1", request_id="unknown_req", visibility_window_id="w1", 
                       start_time=t0, end_time=t0+timedelta(seconds=40), data_transmitted_mb=50.0)
    t2 = ScheduledTask(id="t2", request_id="r2", visibility_window_id="unknown_window",
                       start_time=t0, end_time=t0+timedelta(seconds=16), data_transmitted_mb=200.0)
    
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1, t2])
    assert len(errors) == 2
    assert any("unknown request" in e for e in errors)
    assert any("unknown window" in e for e in errors)

def test_satellite_mismatch(base_scenario):
    t0 = base_scenario["t0"]
    t1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w2",
                       start_time=t0, end_time=t0+timedelta(seconds=40), data_transmitted_mb=50.0)
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1])
    assert any("does not match Window satellite" in e for e in errors)

def test_out_of_bounds(base_scenario):
    t0 = base_scenario["t0"]
    t1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w1", 
                       start_time=t0 - timedelta(seconds=1), end_time=t0+timedelta(seconds=40), data_transmitted_mb=50.0)
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1])
    assert any("outside its visibility window" in e for e in errors)

def test_insufficient_duration(base_scenario):
    t0 = base_scenario["t0"]
    t1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w1", 
                       start_time=t0, end_time=t0+timedelta(seconds=39), data_transmitted_mb=50.0)
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1])
    assert any("insufficient" in e for e in errors)

def test_data_mismatch(base_scenario):
    t0 = base_scenario["t0"]
    t1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w1", 
                       start_time=t0, end_time=t0+timedelta(seconds=40), data_transmitted_mb=49.0)
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1])
    assert any("does not match request data_volume_mb" in e for e in errors)

def test_duplicate_request(base_scenario):
    t0 = base_scenario["t0"]
    t1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w1", 
                       start_time=t0, end_time=t0+timedelta(seconds=40), data_transmitted_mb=50.0)
    t2 = ScheduledTask(id="t2", request_id="r1", visibility_window_id="w1", 
                       start_time=t0+timedelta(seconds=40), end_time=t0+timedelta(seconds=80), data_transmitted_mb=50.0)
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1, t2])
    assert any("scheduled multiple times" in e for e in errors)

def test_gs_overlap(base_scenario):
    t0 = base_scenario["t0"]
    w3 = VisibilityWindow(id="w3", satellite_id="sat-2", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=10))
    base_scenario["windows"].append(w3)
    
    t1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w1", 
                       start_time=t0, end_time=t0+timedelta(seconds=40), data_transmitted_mb=50.0)
    t2 = ScheduledTask(id="t2", request_id="r2", visibility_window_id="w3", 
                       start_time=t0+timedelta(seconds=20), end_time=t0+timedelta(seconds=36), data_transmitted_mb=200.0)
    
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1, t2])
    assert any("Ground Station gs-1 has overlapping tasks" in e for e in errors)

def test_satellite_overlap(base_scenario):
    t0 = base_scenario["t0"]
    w4 = VisibilityWindow(id="w4", satellite_id="sat-1", ground_station_id="gs-2", start_time=t0, end_time=t0+timedelta(minutes=10))
    base_scenario["windows"].append(w4)
    
    r3 = DownlinkRequest(id="r3", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.HIGH)
    base_scenario["requests"].append(r3)
    
    t1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w1", 
                       start_time=t0, end_time=t0+timedelta(seconds=40), data_transmitted_mb=50.0)
    t2 = ScheduledTask(id="t2", request_id="r3", visibility_window_id="w4", 
                       start_time=t0+timedelta(seconds=20), end_time=t0+timedelta(seconds=60), data_transmitted_mb=50.0)
    
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1, t2])
    assert any("Satellite sat-1 has overlapping tasks" in e for e in errors)

def test_exact_adjacency(base_scenario):
    t0 = base_scenario["t0"]
    w3 = VisibilityWindow(id="w3", satellite_id="sat-2", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=10))
    base_scenario["windows"].append(w3)
    
    t1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w1", 
                       start_time=t0, end_time=t0+timedelta(seconds=40), data_transmitted_mb=50.0)
    t2 = ScheduledTask(id="t2", request_id="r2", visibility_window_id="w3", 
                       start_time=t0+timedelta(seconds=40), end_time=t0+timedelta(seconds=200), data_transmitted_mb=200.0)
    
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1, t2])
    assert not errors

def test_missing_sat_or_gs(base_scenario):
    t0 = base_scenario["t0"]
    w3 = VisibilityWindow(id="w3", satellite_id="unknown_sat", ground_station_id="unknown_gs", start_time=t0, end_time=t0+timedelta(minutes=10))
    base_scenario["windows"].append(w3)
    
    r3 = DownlinkRequest(id="r3", satellite_id="unknown_sat", data_volume_mb=50.0, priority=Priority.HIGH)
    base_scenario["requests"].append(r3)
    
    t1 = ScheduledTask(id="t1", request_id="r3", visibility_window_id="w3", 
                       start_time=t0, end_time=t0+timedelta(seconds=40), data_transmitted_mb=50.0)
    
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1])
    
    assert any("references unknown satellite unknown_sat" in e for e in errors)
    assert any("references unknown ground station unknown_gs" in e for e in errors)
    
def test_multiple_errors_one_schedule(base_scenario):
    t0 = base_scenario["t0"]
    t1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w2", 
                       start_time=t0 - timedelta(seconds=5), 
                       end_time=t0 - timedelta(seconds=3), 
                       data_transmitted_mb=10.0)
    
    validator = ScheduleValidator(**{k:v for k,v in base_scenario.items() if k != "t0"})
    errors = validator.validate([t1])
    assert len(errors) >= 4
