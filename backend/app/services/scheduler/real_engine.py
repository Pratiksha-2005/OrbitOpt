"""Real Scheduler Engine Adapter integrating Developer 1's FCFS and CP-SAT algorithms."""

import math
from datetime import datetime, timezone
from typing import Dict, List

from app.schemas.dataset import DatasetRead
from app.schemas.metrics import ScheduleMetrics
from app.schemas.schedule import (
    AlgorithmType,
    BaselineScheduleRequest,
    OptimizeScheduleRequest,
    ScheduledPass,
    ScheduleRunResponse,
    ScheduleStatus,
    UnassignedPass,
)
from app.services.scheduler.cpsat import CPSATScheduler
from app.services.scheduler.fcfs import FCFSScheduler
from app.services.scheduler.models import (
    DownlinkRequest,
    GroundStation,
    Priority,
    Satellite,
    ScheduleResult,
    SolverStatus,
    VisibilityWindow,
)
from app.services.scheduler_interface import BaseSchedulerEngine


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class RealSchedulerEngine(BaseSchedulerEngine):
    """Production scheduler engine adapter wrapping Developer 1's FCFS and CP-SAT modules."""

    async def schedule_baseline(
        self,
        dataset: DatasetRead,
        request: BaselineScheduleRequest,
    ) -> ScheduleRunResponse:
        """Execute Developer 1's real baseline FCFS scheduler."""
        satellites, ground_stations, windows, requests = self._convert_dataset(dataset)

        scheduler = FCFSScheduler(
            satellites=satellites,
            ground_stations=ground_stations,
            windows=windows,
            requests=requests,
        )

        result: ScheduleResult = scheduler.schedule()
        return self._map_result_to_response(
            dataset=dataset,
            result=result,
            algorithm=AlgorithmType.BASELINE_FCFS,
        )

    async def schedule_optimize(
        self,
        dataset: DatasetRead,
        request: OptimizeScheduleRequest,
    ) -> ScheduleRunResponse:
        """Execute Developer 1's real CP-SAT OR-Tools optimizer."""
        satellites, ground_stations, windows, requests = self._convert_dataset(dataset)

        scheduler = CPSATScheduler(
            satellites=satellites,
            ground_stations=ground_stations,
            windows=windows,
            requests=requests,
            time_limit_sec=request.time_limit_seconds,
        )

        result: ScheduleResult = scheduler.schedule()
        return self._map_result_to_response(
            dataset=dataset,
            result=result,
            algorithm=AlgorithmType.CP_SAT_OPTIMIZER,
        )

    def _convert_dataset(
        self,
        dataset: DatasetRead,
    ):
        """Convert DatasetRead schemas to Developer 1 domain models."""
        sat_ids = {p.satellite_id for p in dataset.satellite_passes}
        satellites = [Satellite(id=sid, name=sid) for sid in sat_ids]

        # Map Ground Stations (extract downlink rate from pass or default to 150 Mbps)
        pass_rates = {
            p.ground_station_id: p.effective_data_rate_mbps
            for p in dataset.satellite_passes
            if p.effective_data_rate_mbps is not None
        }

        ground_stations = [
            GroundStation(
                id=gs.station_id,
                name=gs.name,
                downlink_rate_mbps=pass_rates.get(gs.station_id, 150.0),
            )
            for gs in dataset.ground_stations
        ]

        # Map Visibility Windows
        windows = [
            VisibilityWindow(
                id=p.pass_id,
                satellite_id=p.satellite_id,
                ground_station_id=p.ground_station_id,
                start_time=_ensure_utc(p.start_time),
                end_time=_ensure_utc(p.end_time),
            )
            for p in dataset.satellite_passes
        ]

        # Map Downlink Requests (1 GB = 1000 MB decimal)
        priority_map = {
            1: Priority.CRITICAL,  # 4
            2: Priority.HIGH,      # 3
            3: Priority.MEDIUM,    # 2
            4: Priority.LOW,       # 1
            5: Priority.LOW,       # 1
        }

        requests = []
        for p in dataset.satellite_passes:
            gs_rate = pass_rates.get(p.ground_station_id, 150.0)
            window_duration_sec = (p.end_time - p.start_time).total_seconds()
            max_channel_capacity_gb = (gs_rate * window_duration_sec) / 8000.0
            transferable_gb = min(p.data_volume_gb, max_channel_capacity_gb)
            requests.append(
                DownlinkRequest(
                    id=p.pass_id,
                    satellite_id=p.satellite_id,
                    data_volume_mb=round(transferable_gb * 1000.0, 4),
                    priority=priority_map.get(p.priority, Priority.MEDIUM),
                )
            )

        return satellites, ground_stations, windows, requests

    def _map_result_to_response(
        self,
        dataset: DatasetRead,
        result: ScheduleResult,
        algorithm: AlgorithmType,
    ) -> ScheduleRunResponse:
        """Transform Developer 1 ScheduleResult to API ScheduleRunResponse."""
        pass_lookup = {p.pass_id: p for p in dataset.satellite_passes}

        scheduled_passes: List[ScheduledPass] = []
        for task in result.scheduled_tasks:
            orig_pass = pass_lookup.get(task.request_id)
            if not orig_pass:
                continue

            duration_sec = (task.end_time - task.start_time).total_seconds()
            data_vol_gb = round(task.data_transmitted_mb / 1000.0, 4)

            scheduled_passes.append(
                ScheduledPass(
                    pass_id=orig_pass.pass_id,
                    satellite_id=orig_pass.satellite_id,
                    ground_station_id=orig_pass.ground_station_id,
                    start_time=_ensure_utc(task.start_time),
                    end_time=_ensure_utc(task.end_time),
                    duration_seconds=duration_sec,
                    data_volume_gb=data_vol_gb,
                    transferable_data_gb=data_vol_gb,
                    priority=orig_pass.priority,
                )
            )

        unassigned_passes: List[UnassignedPass] = []
        for rej_id in result.rejected_request_ids:
            orig_pass = pass_lookup.get(rej_id)
            if orig_pass:
                unassigned_passes.append(
                    UnassignedPass(
                        pass_id=orig_pass.pass_id,
                        satellite_id=orig_pass.satellite_id,
                        ground_station_id=orig_pass.ground_station_id,
                        start_time=_ensure_utc(orig_pass.start_time),
                        end_time=_ensure_utc(orig_pass.end_time),
                        priority=orig_pass.priority,
                        reason="Unassigned: rejected due to overlap or duration constraint violation",
                    )
                )

        status_map = {
            SolverStatus.OPTIMAL: ScheduleStatus.COMPLETED,
            SolverStatus.FEASIBLE: ScheduleStatus.COMPLETED,
            SolverStatus.INFEASIBLE: ScheduleStatus.INFEASIBLE,
            SolverStatus.UNKNOWN: ScheduleStatus.FAILED,
            SolverStatus.MODEL_INVALID: ScheduleStatus.FAILED,
        }
        api_status = status_map.get(result.solver_status, ScheduleStatus.COMPLETED)

        # Compute summary metrics
        metrics = self._calculate_metrics(dataset.satellite_passes, scheduled_passes, unassigned_passes)

        return ScheduleRunResponse(
            run_id=f"run_{result.id}",
            dataset_id=dataset.dataset_id,
            algorithm=algorithm,
            status=api_status,
            is_mock=False, # Real optimizer execution!
            is_valid=result.is_valid,
            validation_violations=result.validation_errors,
            solver_status_detail=result.solver_status.value,
            created_at=datetime.now(timezone.utc),
            execution_time_ms=round(result.runtime_seconds * 1000.0, 2),
            scheduled_passes=scheduled_passes,
            unassigned_passes=unassigned_passes,
            metrics=metrics,
        )

    def _calculate_metrics(
        self,
        all_passes,
        scheduled_passes: List[ScheduledPass],
        unassigned_passes: List[UnassignedPass],
    ) -> ScheduleMetrics:
        total = len(all_passes)
        sched_count = len(scheduled_passes)
        unassigned_count = len(unassigned_passes)
        sched_pct = (sched_count / total * 100.0) if total > 0 else 0.0

        total_pending = sum(p.data_volume_gb for p in all_passes)
        total_transferable = sum(p.data_volume_gb for p in scheduled_passes)
        total_contact_sec = sum(p.duration_seconds for p in scheduled_passes)

        priority_weights = {1: 10.0, 2: 5.0, 3: 2.0, 4: 1.0, 5: 0.5}
        objective_val = sum(
            priority_weights.get(p.priority, 1.0) * p.data_volume_gb
            for p in scheduled_passes
        )

        priority_breakdown: Dict[str, int] = {}
        for p in scheduled_passes:
            key = str(p.priority)
            priority_breakdown[key] = priority_breakdown.get(key, 0) + 1

        max_score = sum(priority_weights.get(p.priority, 1.0) * p.data_volume_gb for p in all_passes)
        priority_sat_rate = (objective_val / max_score * 100.0) if max_score > 0 else 100.0

        gs_counts: Dict[str, int] = {}
        for p in scheduled_passes:
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
            conflicts_detected=unassigned_count,
        )
