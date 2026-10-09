"""Temporary mock scheduling service for API integration boundary testing.

NOTE: This mock service is strictly for integration testing while Developer 1's
scheduling engine (FCFS and CP-SAT OR-Tools solver) is under active development.
All results generated here are explicitly flagged with `is_mock=True` so they
are never confused with genuine optimization results.
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.schemas.dataset import DatasetRead
from app.schemas.metrics import ScheduleMetrics
from app.schemas.satellite_pass import SatellitePassRead
from app.schemas.schedule import (
    AlgorithmType,
    BaselineScheduleRequest,
    OptimizeScheduleRequest,
    ScheduledPass,
    ScheduleRunResponse,
    ScheduleStatus,
    UnassignedPass,
)
from app.services.scheduler_interface import BaseSchedulerEngine

DEFAULT_PRIORITY_WEIGHTS = {
    "1": 10.0,
    "2": 5.0,
    "3": 2.0,
    "4": 1.0,
    "5": 0.5,
}


class MockSchedulerEngine(BaseSchedulerEngine):
    """Temporary mock engine for testing frontend and API integration contracts."""

    async def schedule_baseline(
        self,
        dataset: DatasetRead,
        request: BaselineScheduleRequest,
    ) -> ScheduleRunResponse:
        start_exec = time.perf_counter()
        
        # Sort passes chronologically for basic FCFS
        sorted_passes = sorted(dataset.satellite_passes, key=lambda p: p.start_time)
        
        scheduled: List[ScheduledPass] = []
        unassigned: List[UnassignedPass] = []
        station_last_end: Dict[str, datetime] = {}
        conflicts = 0

        for p in sorted_passes:
            last_end = station_last_end.get(p.ground_station_id)
            duration_sec = (p.end_time - p.start_time).total_seconds()
            
            # Check setup time buffer
            if last_end is not None:
                gap_sec = (p.start_time - last_end).total_seconds()
                if gap_sec < request.setup_time_seconds:
                    conflicts += 1
                    unassigned.append(
                        UnassignedPass(
                            pass_id=p.pass_id,
                            satellite_id=p.satellite_id,
                            ground_station_id=p.ground_station_id,
                            start_time=p.start_time,
                            end_time=p.end_time,
                            priority=p.priority,
                            reason=f"Station conflict: requires {request.setup_time_seconds}s buffer; gap was {gap_sec:.1f}s",
                        )
                    )
                    continue

            # Compute transferable data: min(pending_data_gb, effective_data_rate_mbps * duration_sec / 8000.0)
            transferable_gb = p.data_volume_gb
            if p.effective_data_rate_mbps is not None and p.effective_data_rate_mbps > 0:
                channel_capacity_gb = (p.effective_data_rate_mbps * duration_sec) / 8000.0
                transferable_gb = min(p.data_volume_gb, channel_capacity_gb)

            # Allocate pass
            scheduled.append(
                ScheduledPass(
                    pass_id=p.pass_id,
                    satellite_id=p.satellite_id,
                    ground_station_id=p.ground_station_id,
                    start_time=p.start_time,
                    end_time=p.end_time,
                    duration_seconds=duration_sec,
                    data_volume_gb=round(transferable_gb, 4),
                    transferable_data_gb=round(transferable_gb, 4),
                    priority=p.priority,
                )
            )
            station_last_end[p.ground_station_id] = p.end_time

        exec_ms = (time.perf_counter() - start_exec) * 1000.0
        metrics = self._calculate_metrics(
            dataset.satellite_passes,
            scheduled,
            unassigned,
            conflicts,
            priority_weights=DEFAULT_PRIORITY_WEIGHTS,
        )

        return ScheduleRunResponse(
            run_id=f"run_{uuid.uuid4()}",
            dataset_id=dataset.dataset_id,
            algorithm=AlgorithmType.BASELINE_FCFS,
            status=ScheduleStatus.COMPLETED,
            is_mock=True,
            is_valid=True,
            validation_violations=[],
            solver_status_detail="FCFS_COMPLETED",
            created_at=datetime.now(timezone.utc),
            execution_time_ms=round(exec_ms, 2),
            scheduled_passes=scheduled,
            unassigned_passes=unassigned,
            metrics=metrics,
        )

    async def schedule_optimize(
        self,
        dataset: DatasetRead,
        request: OptimizeScheduleRequest,
    ) -> ScheduleRunResponse:
        start_exec = time.perf_counter()

        weights = request.priority_weights or DEFAULT_PRIORITY_WEIGHTS

        # Precalculate transferable data for each pass
        pass_transferable_map = {}
        for p in dataset.satellite_passes:
            duration_sec = (p.end_time - p.start_time).total_seconds()
            transferable = p.data_volume_gb
            if p.effective_data_rate_mbps is not None and p.effective_data_rate_mbps > 0:
                channel_capacity = (p.effective_data_rate_mbps * duration_sec) / 8000.0
                transferable = min(p.data_volume_gb, channel_capacity)
            pass_transferable_map[p.pass_id] = transferable

        # Mock optimization prioritizes higher weighted transferable data volume (Objective: Maximize sum(weight * transferable_data))
        sorted_passes = sorted(
            dataset.satellite_passes,
            key=lambda p: (
                -(weights.get(str(p.priority), 1.0) * pass_transferable_map[p.pass_id]),
                p.start_time,
            ),
        )

        scheduled: List[ScheduledPass] = []
        unassigned: List[UnassignedPass] = []
        station_allocations: Dict[str, List[SatellitePassRead]] = {
            gs.station_id: [] for gs in dataset.ground_stations
        }
        conflicts = 0

        for p in sorted_passes:
            station_passes = station_allocations.get(p.ground_station_id, [])
            has_overlap = False
            duration_sec = (p.end_time - p.start_time).total_seconds()
            transferable_gb = pass_transferable_map[p.pass_id]

            for allocated in station_passes:
                # Check overlap including setup time
                overlap = not (
                    p.end_time.timestamp() + request.setup_time_seconds <= allocated.start_time.timestamp()
                    or p.start_time.timestamp() >= allocated.end_time.timestamp() + request.setup_time_seconds
                )
                if overlap:
                    has_overlap = True
                    conflicts += 1
                    break

            if has_overlap:
                unassigned.append(
                    UnassignedPass(
                        pass_id=p.pass_id,
                        satellite_id=p.satellite_id,
                        ground_station_id=p.ground_station_id,
                        start_time=p.start_time,
                        end_time=p.end_time,
                        priority=p.priority,
                        reason=f"CP-SAT Mock conflict resolution: preempted by higher objective pass on station '{p.ground_station_id}'",
                    )
                )
            else:
                scheduled.append(
                    ScheduledPass(
                        pass_id=p.pass_id,
                        satellite_id=p.satellite_id,
                        ground_station_id=p.ground_station_id,
                        start_time=p.start_time,
                        end_time=p.end_time,
                        duration_seconds=duration_sec,
                        data_volume_gb=round(transferable_gb, 4),
                        transferable_data_gb=round(transferable_gb, 4),
                        priority=p.priority,
                    )
                )
                station_allocations.setdefault(p.ground_station_id, []).append(p)

        # Re-sort scheduled by start_time
        scheduled.sort(key=lambda x: x.start_time)

        exec_ms = (time.perf_counter() - start_exec) * 1000.0
        metrics = self._calculate_metrics(
            dataset.satellite_passes,
            scheduled,
            unassigned,
            conflicts,
            priority_weights=weights,
        )

        return ScheduleRunResponse(
            run_id=f"run_{uuid.uuid4()}",
            dataset_id=dataset.dataset_id,
            algorithm=AlgorithmType.CP_SAT_OPTIMIZER,
            status=ScheduleStatus.COMPLETED,
            is_mock=True,
            is_valid=True,
            validation_violations=[],
            solver_status_detail="CP_SAT_MOCK_OPTIMAL",
            created_at=datetime.now(timezone.utc),
            execution_time_ms=round(exec_ms, 2),
            scheduled_passes=scheduled,
            unassigned_passes=unassigned,
            metrics=metrics,
        )

    def _calculate_metrics(
        self,
        all_passes: List[SatellitePassRead],
        scheduled: List[ScheduledPass],
        unassigned: List[UnassignedPass],
        conflicts: int,
        priority_weights: Dict[str, float],
    ) -> ScheduleMetrics:
        total = len(all_passes)
        sched_count = len(scheduled)
        unassigned_count = len(unassigned)
        sched_pct = (sched_count / total * 100.0) if total > 0 else 0.0

        total_pending = sum(p.data_volume_gb for p in all_passes)
        total_transferable = sum(p.data_volume_gb for p in scheduled)
        total_contact_sec = sum(p.duration_seconds for p in scheduled)

        # Agreed Optimization Objective: Maximize sum(weight * transferable_data)
        objective_val = sum(
            priority_weights.get(str(p.priority), 1.0) * p.data_volume_gb
            for p in scheduled
        )

        # Priority breakdown
        priority_breakdown: Dict[str, int] = {}
        for p in scheduled:
            key = str(p.priority)
            priority_breakdown[key] = priority_breakdown.get(key, 0) + 1

        # Priority satisfaction: weighted sum percentage
        max_score = sum(priority_weights.get(str(p.priority), 1.0) * p.data_volume_gb for p in all_passes)
        priority_sat_rate = (objective_val / max_score * 100.0) if max_score > 0 else 100.0

        # Ground station utilization count
        gs_counts: Dict[str, int] = {}
        for p in scheduled:
            gs_counts[p.ground_station_id] = gs_counts.get(p.ground_station_id, 0) + 1
        
        gs_utilization: Dict[str, float] = {
            gs_id: round((cnt / total * 100.0), 2) if total > 0 else 0.0
            for gs_id, cnt in gs_counts.items()
        }

        return ScheduleMetrics(
            total_passes=total,
            scheduled_passes_count=sched_count,
            unassigned_passes_count=unassigned_count,
            scheduled_percentage=round(sched_pct, 2),
            total_data_downlinked_gb=round(total_transferable, 2),
            total_pending_data_gb=round(total_pending, 2),
            total_contact_time_seconds=round(total_contact_sec, 2),
            objective_value=round(objective_val, 2),
            priority_satisfaction_rate=round(priority_sat_rate, 2),
            priority_breakdown=priority_breakdown,
            ground_station_utilization=gs_utilization,
            conflicts_detected=conflicts,
        )
