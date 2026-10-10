import pytest
from datetime import datetime, timezone, timedelta
from scheduler.models import DownlinkRequest, Priority
from scheduler.priority import get_dynamic_score, calculate_waiting_time_score

def test_priority_score_calculation():
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    t_eval = t0 + timedelta(hours=12) # Wait score = 50.0
    
    req = DownlinkRequest(
        id="r1", satellite_id="s1", data_volume_mb=10, priority=Priority.LOW,
        created_at=t0, emergency_severity=50.0, deadline_urgency=20.0, data_freshness=100.0
    )
    
    # 0.40 * 50 = 20
    # 0.25 * 20 = 5
    # 0.15 * 100 = 15
    # 0.20 * 50 = 10
    # Total = 50.0
    
    score = get_dynamic_score(req, t_eval)
    assert abs(score - 50.0) < 1e-5

def test_verified_emergency_dynamic_score():
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    req = DownlinkRequest(
        id="r1", satellite_id="s1", data_volume_mb=10, priority=Priority.LOW,
        emergency_severity=100.0, verified_emergency=True
    )
    # The pure dynamic score is computed normally (0.40 * 100 = 40.0). 
    # CPSAT intercept and outrank behavior is tested separately.
    score = get_dynamic_score(req, t0)
    assert score == 40.0

def test_missing_factors():
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    req = DownlinkRequest(id="r1", satellite_id="s1", data_volume_mb=10, priority=Priority.LOW)
    # Default fields: 0.0, no created_at
    score = get_dynamic_score(req, t0)
    assert score == 0.0

def test_max_waiting_time():
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    t_eval = t0 + timedelta(hours=48)
    req = DownlinkRequest(id="r1", satellite_id="s1", data_volume_mb=10, priority=Priority.LOW, created_at=t0)
    
    score = calculate_waiting_time_score(req, t_eval)
    assert score == 100.0 # capped at 100
