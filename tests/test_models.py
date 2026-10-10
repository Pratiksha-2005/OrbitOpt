import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError
from scheduler.models import (
    Satellite, GroundStation, VisibilityWindow,
    DownlinkRequest, ScheduledTask, ScheduleResult, Priority, SolverStatus
)

def test_valid_satellite():
    sat = Satellite(id="sat-1", name="Sat 1")
    assert sat.id == "sat-1"
    assert sat.name == "Sat 1"

def test_invalid_empty_id():
    with pytest.raises(ValidationError):
        Satellite(id="", name="Sat 1")

def test_valid_ground_station():
    gs = GroundStation(id="gs-1", name="GS 1", downlink_rate_mbps=100.5)
    assert gs.downlink_rate_mbps == 100.5

def test_invalid_ground_station_rate():
    with pytest.raises(ValidationError, match="greater than 0"):
        GroundStation(id="gs-1", name="GS 1", downlink_rate_mbps=-10.0)
    with pytest.raises(ValidationError, match="greater than 0"):
        GroundStation(id="gs-1", name="GS 1", downlink_rate_mbps=0.0)

def test_valid_time_window():
    start = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    end = datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc)
    vw = VisibilityWindow(id="vw-1", satellite_id="s1", ground_station_id="g1", start_time=start, end_time=end)
    assert vw.start_time == start
    assert vw.end_time == end

def test_invalid_time_ordering():
    start = datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc)
    end = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValidationError, match="greater than start_time"):
        VisibilityWindow(id="vw-1", satellite_id="s1", ground_station_id="g1", start_time=start, end_time=end)

def test_naive_datetime():
    start = datetime(2023, 1, 1, 12, 0)
    end = datetime(2023, 1, 1, 12, 10)
    with pytest.raises(ValidationError, match="timezone-aware"):
        VisibilityWindow(id="vw-1", satellite_id="s1", ground_station_id="g1", start_time=start, end_time=end)

def test_non_utc_datetime():
    tz = timezone(timedelta(hours=1))
    start = datetime(2023, 1, 1, 12, 0, tzinfo=tz)
    end = datetime(2023, 1, 1, 12, 10, tzinfo=tz)
    with pytest.raises(ValidationError, match="strictly in UTC"):
        VisibilityWindow(id="vw-1", satellite_id="s1", ground_station_id="g1", start_time=start, end_time=end)

def test_downlink_request():
    req = DownlinkRequest(id="req-1", satellite_id="s1", data_volume_mb=500.0, priority=Priority.HIGH)
    assert req.priority == 3
    
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        DownlinkRequest(id="req-2", satellite_id="s1", data_volume_mb=-1.0, priority=Priority.LOW)
    
    with pytest.raises(ValidationError):
        DownlinkRequest(id="req-3", satellite_id="s1", data_volume_mb=10.0, priority=5)

def test_scheduled_task():
    start = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    end = datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc)
    st = ScheduledTask(id="st-1", request_id="req-1", visibility_window_id="vw-1", start_time=start, end_time=end, data_transmitted_mb=50.0)
    assert st.data_transmitted_mb == 50.0
    
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ScheduledTask(id="st-1", request_id="req-1", visibility_window_id="vw-1", start_time=start, end_time=end, data_transmitted_mb=-5.0)

def test_schedule_result():
    res = ScheduleResult(
        id="res-1",
        scheduled_tasks=[],
        rejected_request_ids=[],
        objective_value=100.5,
        runtime_seconds=1.2,
        solver_status=SolverStatus.OPTIMAL,
        is_valid=True,
        validation_errors=[]
    )
    assert res.solver_status == SolverStatus.OPTIMAL

def test_invalid_runtime():
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ScheduleResult(
            id="res-1", scheduled_tasks=[], rejected_request_ids=[],
            objective_value=100.5, runtime_seconds=-0.5,
            solver_status=SolverStatus.OPTIMAL, is_valid=True
        )
