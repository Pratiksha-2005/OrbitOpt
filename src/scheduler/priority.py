from datetime import datetime
from scheduler.models import DownlinkRequest

def calculate_waiting_time_score(request: DownlinkRequest, evaluation_time: datetime) -> float:
    """
    Normalizes waiting time from 0 to 100.
    Assuming 24 hours (86400 seconds) maxes out the waiting score to 100.
    """
    if not request.created_at:
        return 0.0
        
    wait_seconds = max(0.0, (evaluation_time - request.created_at).total_seconds())
    score = (wait_seconds / 86400.0) * 100.0
    return min(100.0, score)

def get_dynamic_score(request: DownlinkRequest, evaluation_time: datetime) -> float:
    """
    Calculates the dynamic priority score based on:
    score = 0.40 * emergency_severity + 0.25 * deadline_urgency + 0.15 * data_freshness + 0.20 * waiting_time
    """
    wait_score = calculate_waiting_time_score(request, evaluation_time)
    
    score = (
        0.40 * request.emergency_severity +
        0.25 * request.deadline_urgency +
        0.15 * request.data_freshness +
        0.20 * wait_score
    )
    
    return score
