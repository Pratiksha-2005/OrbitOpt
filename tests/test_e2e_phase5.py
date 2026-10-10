import pytest
from datetime import datetime, timezone, timedelta

from scheduler.models import (
    Satellite, GroundStation, VisibilityWindow, DownlinkRequest, Priority, TimeWindow
)
from scheduler.cpsat import CPSATScheduler
from scheduler.rescheduler import Rescheduler
from scheduler.fcfs import FCFSScheduler

def test_e2e_scenario():
    # Setup base scenario
    t0 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    
    sat1 = Satellite(id="sat-1", name="Sat 1")
    sat2 = Satellite(id="sat-2", name="Sat 2")
    
    # gs1 has an outage from t0+10m to t0+15m
    outage = TimeWindow(start_time=t0+timedelta(minutes=10), end_time=t0+timedelta(minutes=15))
    gs1 = GroundStation(id="gs-1", name="GS 1", downlink_rate_mbps=10.0, outages=[outage])
    
    # Visibility windows
    # sat-1 on gs-1 from t0 to t0+30m
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=30))
    # sat-2 on gs-1 from t0 to t0+30m
    w2 = VisibilityWindow(id="w2", satellite_id="sat-2", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=30))
    
    satellites = [sat1, sat2]
    ground_stations = [gs1]
    windows = [w1, w2]
    
    # Request 1 (sat-1): Normal request, 50MB (needs 40s), priority MEDIUM
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=50.0, priority=Priority.MEDIUM, created_at=t0-timedelta(hours=2))
    
    # Request 2 (sat-2): Routine request, 100MB (needs 80s), priority LOW
    r2 = DownlinkRequest(id="r2", satellite_id="sat-2", data_volume_mb=100.0, priority=Priority.LOW, created_at=t0-timedelta(hours=1))
    
    # 1. Run Initial CPSAT Schedule
    requests_initial = [r1, r2]
    optimizer = CPSATScheduler(satellites, ground_stations, windows, requests_initial, evaluation_time=t0)
    res_initial = optimizer.schedule()
    
    assert res_initial.is_valid
    assert len(res_initial.scheduled_tasks) == 2
    
    # Evaluate at t0 + 5 minutes
    # Task r1 or r2 are already completed or running since they take < 2 minutes total and were scheduled at t0.
    t_eval = t0 + timedelta(minutes=5)
    
    # 2. Introduce verified emergency (sat-1), 5MB (needs 4s), deadline is t0+12m (which is during outage!)
    # Actually, outage is 10m to 15m. Deadline is 12m. It must be scheduled before 10m.
    r_emergency = DownlinkRequest(
        id="r_emergency", satellite_id="sat-1", data_volume_mb=5.0, priority=Priority.LOW,
        created_at=t_eval, verified_emergency=True, deadline=t0+timedelta(minutes=12)
    )
    
    requests_new = [r1, r2, r_emergency]
    
    # 3. Reschedule
    rescheduler = Rescheduler(
        satellites=satellites,
        ground_stations=ground_stations,
        windows=windows,
        requests=requests_new,
        current_schedule=res_initial.scheduled_tasks,
        evaluation_time=t_eval
    )
    
    res_final = rescheduler.reschedule()
    assert res_final.is_valid
    
    # Check that emergency was scheduled
    t_emerg = next((t for t in res_final.scheduled_tasks if t.request_id == "r_emergency"), None)
    assert t_emerg is not None
    assert t_emerg.end_time <= r_emergency.deadline
    
    # Verify no tasks overlap the outage
    for t in res_final.scheduled_tasks:
        overlap_outage = max(t.start_time, outage.start_time) < min(t.end_time, outage.end_time)
        assert not overlap_outage
            
    # Verify active tasks were preserved
    t1_orig = next(t for t in res_initial.scheduled_tasks if t.request_id == "r1")
    t1_final = next(t for t in res_final.scheduled_tasks if t.request_id == "r1")
    assert t1_orig.start_time == t1_final.start_time
    assert t1_orig.end_time == t1_final.end_time
    
    # Verify FCFS produces a valid schedule as well
    fcfs = FCFSScheduler(satellites, ground_stations, windows, requests_new)
    res_fcfs = fcfs.schedule()
    assert res_fcfs.is_valid
    for t in res_fcfs.scheduled_tasks:
        overlap_outage = max(t.start_time, outage.start_time) < min(t.end_time, outage.end_time)
        assert not overlap_outage

def test_fcfs_respects_deadline():
    t0 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    sat1 = Satellite(id="sat-1", name="Sat 1")
    gs1 = GroundStation(id="gs-1", name="GS 1", downlink_rate_mbps=10.0)
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=30))
    
    # Needs 80s, but deadline is 50s. It cannot fit.
    r1 = DownlinkRequest(id="r1", satellite_id="sat-1", data_volume_mb=100.0, priority=Priority.LOW, deadline=t0+timedelta(seconds=50))
    
    fcfs = FCFSScheduler([sat1], [gs1], [w1], [r1])
    res = fcfs.schedule()
    assert len(res.scheduled_tasks) == 0
    assert "r1" in res.rejected_request_ids
