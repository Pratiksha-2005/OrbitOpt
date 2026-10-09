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

def get_base_coefficient(request: DownlinkRequest, evaluation_time: datetime) -> int:
    """
    Calculates the exact integer objective coefficient for a normal request.
    This strictly evaluates: int(round((priority_value * 1000 + dynamic_score) * data_volume_mb))
    """
    dynamic_score = get_dynamic_score(request, evaluation_time)
    total_priority = request.priority.value * 1000.0 + dynamic_score
    return int(round(total_priority * request.data_volume_mb))

def get_emergency_bonus(requests: list[DownlinkRequest]) -> int:
    """
    Calculates the strict mathematical lexicographic bonus that guarantees an
    emergency outranks ANY combination of normal requests and secondary constraints.
    Max total_priority = 4000 (CRITICAL) + 100 (Max dynamic score) = 4100.0
    """
    max_possible_base_score = 0
    for req in requests:
        max_possible_base_score += int(round(4100.0 * req.data_volume_mb))
    return max_possible_base_score + 1

def validate_objective_bounds(requests: list[DownlinkRequest]) -> None:
    """
    Verifies that the sum of the absolute theoretical maximum objective coefficients 
    (including emergency bonuses) cannot exceed the signed 64-bit limit of CP-SAT.
    Throws ValueError if the dataset is unsafe.
    """
    MAX_CPSAT_INT = (1 << 63) - 1
    emergency_bonus = get_emergency_bonus(requests)
    
    max_total_objective = 0
    for req in requests:
        base_coeff_bound = int(round(4100.0 * req.data_volume_mb))
        if req.verified_emergency:
            max_total_objective += emergency_bonus + base_coeff_bound
        else:
            max_total_objective += base_coeff_bound
            
    if max_total_objective > MAX_CPSAT_INT:
        raise ValueError(
            f"Dataset total objective potential ({max_total_objective}) exceeds "
            f"CP-SAT 64-bit signed integer limit ({MAX_CPSAT_INT})."
        )
