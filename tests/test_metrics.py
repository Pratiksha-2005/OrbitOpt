import pytest
from datetime import datetime, timezone, timedelta

from scheduler.models import (
    Satellite, GroundStation, VisibilityWindow, DownlinkRequest, Priority, TimeWindow,
    ScheduleResult, ScheduledTask, SolverStatus
)
from scheduler.metrics import calculate_station_utilization, calculate_improvement_over_fcfs

def test_calculate_station_utilization_basic():
    t0 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    gs1 = GroundStation(id="gs-1", name="GS 1", downlink_rate_mbps=10.0)
    # Two windows that overlap: 
    # w1: t0 to t0+30m
    # w2: t0+15m to t0+45m
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=30))
    w2 = VisibilityWindow(id="w2", satellite_id="sat-2", ground_station_id="gs-1", start_time=t0+timedelta(minutes=15), end_time=t0+timedelta(minutes=45))
    
    # Available time should be 45 minutes (2700 seconds)
    
    task1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w1", start_time=t0, end_time=t0+timedelta(minutes=10), data_transmitted_mb=10)
    task2 = ScheduledTask(id="t2", request_id="r2", visibility_window_id="w2", start_time=t0+timedelta(minutes=30), end_time=t0+timedelta(minutes=40), data_transmitted_mb=10)
    # Used time is 10 + 10 = 20 minutes (1200 seconds)
    
    result = ScheduleResult(
        id="res", scheduled_tasks=[task1, task2], rejected_request_ids=[], 
        objective_value=1.0, runtime_seconds=1.0, solver_status=SolverStatus.OPTIMAL, is_valid=True
    )
    
    utils = calculate_station_utilization(result, [gs1], [w1, w2])
    # 20 / 45 = 44.444...%
    assert abs(utils["gs-1"] - 44.44444) < 1e-4
    
def test_calculate_station_utilization_with_outage():
    t0 = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    # Outage exactly blocks 10 minutes of the window
    outage = TimeWindow(start_time=t0+timedelta(minutes=10), end_time=t0+timedelta(minutes=20))
    gs1 = GroundStation(id="gs-1", name="GS 1", downlink_rate_mbps=10.0, outages=[outage])
    w1 = VisibilityWindow(id="w1", satellite_id="sat-1", ground_station_id="gs-1", start_time=t0, end_time=t0+timedelta(minutes=30))
    
    # Available time = 30m - 10m = 20 minutes
    task1 = ScheduledTask(id="t1", request_id="r1", visibility_window_id="w1", start_time=t0, end_time=t0+timedelta(minutes=10), data_transmitted_mb=10)
    
    result = ScheduleResult(
        id="res", scheduled_tasks=[task1], rejected_request_ids=[], 
        objective_value=1.0, runtime_seconds=1.0, solver_status=SolverStatus.OPTIMAL, is_valid=True
    )
    
    utils = calculate_station_utilization(result, [gs1], [w1])
    # 10 / 20 = 50%
    assert utils["gs-1"] == 50.0

def test_improvement_over_fcfs():
    res_fcfs = ScheduleResult(id="1", scheduled_tasks=[], rejected_request_ids=[], objective_value=100.0, runtime_seconds=1.0, solver_status=SolverStatus.FEASIBLE, is_valid=True)
    res_cpsat = ScheduleResult(id="2", scheduled_tasks=[], rejected_request_ids=[], objective_value=150.0, runtime_seconds=1.0, solver_status=SolverStatus.OPTIMAL, is_valid=True)
    
    imp = calculate_improvement_over_fcfs(res_cpsat, res_fcfs)
    assert imp == 50.0
    
def test_improvement_zero_fcfs():
    res_fcfs = ScheduleResult(id="1", scheduled_tasks=[], rejected_request_ids=[], objective_value=0.0, runtime_seconds=1.0, solver_status=SolverStatus.FEASIBLE, is_valid=True)
    res_cpsat = ScheduleResult(id="2", scheduled_tasks=[], rejected_request_ids=[], objective_value=50.0, runtime_seconds=1.0, solver_status=SolverStatus.OPTIMAL, is_valid=True)
    
    imp = calculate_improvement_over_fcfs(res_cpsat, res_fcfs)
    assert imp == 100.0
    
    res_cpsat_zero = ScheduleResult(id="3", scheduled_tasks=[], rejected_request_ids=[], objective_value=0.0, runtime_seconds=1.0, solver_status=SolverStatus.OPTIMAL, is_valid=True)
    imp2 = calculate_improvement_over_fcfs(res_cpsat_zero, res_fcfs)
    assert imp2 == 0.0
