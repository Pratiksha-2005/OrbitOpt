from typing import List, Dict
from scheduler.models import (
    ScheduleResult, GroundStation, VisibilityWindow
)

def calculate_station_utilization(
    result: ScheduleResult, 
    ground_stations: List[GroundStation], 
    windows: List[VisibilityWindow]
) -> Dict[str, float]:
    """
    Calculates the utilization percentage (0.0 to 100.0) for each ground station.
    Utilization = (total scheduled task duration) / (total available visibility window duration minus outages)
    """
    total_available_sec = {gs.id: 0.0 for gs in ground_stations}
    total_used_sec = {gs.id: 0.0 for gs in ground_stations}
    
    # Helper to merge intervals
    def merge_intervals(intervals):
        if not intervals:
            return []
        sorted_intervals = sorted(intervals, key=lambda x: x[0])
        merged = [sorted_intervals[0]]
        for current in sorted_intervals[1:]:
            previous = merged[-1]
            if current[0] <= previous[1]:
                merged[-1] = (previous[0], max(previous[1], current[1]))
            else:
                merged.append(current)
        return merged
        
    for gs in ground_stations:
        # Get all windows for this GS
        gs_windows = [w for w in windows if w.ground_station_id == gs.id]
        raw_intervals = [(w.start_time.timestamp(), w.end_time.timestamp()) for w in gs_windows]
        merged_windows = merge_intervals(raw_intervals)
        
        available_sec = sum(end - start for start, end in merged_windows)
        
        # Subtract outages (intersection with merged windows)
        for outage in gs.outages:
            o_start = outage.start_time.timestamp()
            o_end = outage.end_time.timestamp()
            for w_start, w_end in merged_windows:
                overlap_start = max(o_start, w_start)
                overlap_end = min(o_end, w_end)
                if overlap_start < overlap_end:
                    available_sec -= (overlap_end - overlap_start)
                    
        total_available_sec[gs.id] = max(available_sec, 0.0)

    for task in result.scheduled_tasks:
        w = next((w for w in windows if w.id == task.visibility_window_id), None)
        if w and w.ground_station_id in total_used_sec:
            duration = (task.end_time - task.start_time).total_seconds()
            total_used_sec[w.ground_station_id] += duration
            
    utilization = {}
    for gs_id in total_available_sec:
        avail = total_available_sec[gs_id]
        if avail > 0:
            utilization[gs_id] = min((total_used_sec[gs_id] / avail) * 100.0, 100.0)
        else:
            utilization[gs_id] = 0.0
            
    return utilization

def calculate_improvement_over_fcfs(cpsat_result: ScheduleResult, fcfs_result: ScheduleResult) -> float:
    """
    Calculates the percentage improvement of CP-SAT over FCFS based on the objective value.
    """
    if fcfs_result.objective_value <= 0:
        if cpsat_result.objective_value > 0:
            return 100.0
        return 0.0
    
    improvement = ((cpsat_result.objective_value - fcfs_result.objective_value) / fcfs_result.objective_value) * 100.0
    return improvement
