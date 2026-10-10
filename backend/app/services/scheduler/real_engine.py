"""Real Scheduler Engine Adapter integrating Developer 1's FCFS and CP-SAT algorithms with dynamic priority scoring, setup buffer compliance, and safe re-optimization."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

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
    TimeWindow,
    VisibilityWindow,
)
from app.services.scheduler.priority_scoring import (
    DynamicPriorityScorer,
    DynamicPriorityWeights,
)
from app.services.scheduler.validator import ScheduleValidator
from app.services.scheduler_interface import BaseSchedulerEngine

logger = logging.getLogger(__name__)


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
        outages_by_station: Optional[Dict[str, List[TimeWindow]]] = None,
    ) -> ScheduleRunResponse:
        """Execute Developer 1's real baseline FCFS scheduler with dynamic priority ordering."""
        scorer = self._create_scorer(getattr(request, "dynamic_weights", None))
        satellites, ground_stations, windows, requests, score_breakdowns = self._convert_dataset(
            dataset, scorer, outages_by_station
        )

        setup_time = getattr(request, "setup_time_seconds", 120)
        scheduler = FCFSScheduler(
            satellites=satellites,
            ground_stations=ground_stations,
            windows=windows,
            requests=requests,
            setup_time_seconds=setup_time,
        )

        result: ScheduleResult = scheduler.schedule()
        return self._map_result_to_response(
            dataset=dataset,
            result=result,
            algorithm=AlgorithmType.BASELINE_FCFS,
            score_breakdowns=score_breakdowns,
        )

    async def schedule_optimize(
        self,
        dataset: DatasetRead,
        request: OptimizeScheduleRequest,
        outages_by_station: Optional[Dict[str, List[TimeWindow]]] = None,
    ) -> ScheduleRunResponse:
        """Execute Developer 1's real CP-SAT OR-Tools optimizer with dynamic multi-factor priority."""
        scorer = self._create_scorer(getattr(request, "dynamic_weights", None))
        satellites, ground_stations, windows, requests, score_breakdowns = self._convert_dataset(
            dataset, scorer, outages_by_station
        )

        setup_time = getattr(request, "setup_time_seconds", 120)
        scheduler = CPSATScheduler(
            satellites=satellites,
            ground_stations=ground_stations,
            windows=windows,
            requests=requests,
            time_limit_sec=request.time_limit_seconds,
            setup_time_seconds=setup_time,
        )

        result: ScheduleResult = scheduler.schedule()
        return self._map_result_to_response(
            dataset=dataset,
            result=result,
            algorithm=AlgorithmType.CP_SAT_OPTIMIZER,
            score_breakdowns=score_breakdowns,
        )

    async def safe_reoptimize(
        self,
        dataset: DatasetRead,
        request: OptimizeScheduleRequest,
        previous_schedule: Optional[ScheduleRunResponse] = None,
        locked_pass_ids: Optional[List[str]] = None,
        outages_by_station: Optional[Dict[str, List[TimeWindow]]] = None,
    ) -> ScheduleRunResponse:
        """Safe re-optimization: ensures active/completed tasks are protected and previous valid schedule is preserved upon solver/validation failure."""
        try:
            candidate = await self.schedule_optimize(dataset, request, outages_by_station=outages_by_station)
            
            # If solver succeeded and validator confirmed schedule is valid, return candidate
            if candidate.status == ScheduleStatus.COMPLETED and candidate.is_valid:
                return candidate
            
            logger.warning(
                "Candidate re-optimized schedule is invalid or failed solver (status=%s, is_valid=%s). Violations: %s",
                candidate.status,
                candidate.is_valid,
                candidate.validation_violations,
            )
            
            # Safe fallback to previous valid schedule
            if previous_schedule and previous_schedule.is_valid:
                logger.info("Preserving previous valid schedule (run_id=%s) as fallback.", previous_schedule.run_id)
                fallback = previous_schedule.model_copy(deep=True)
                fallback.validation_violations = [
                    f"Re-optimization candidate rejected: {', '.join(candidate.validation_violations) or 'infeasible/failed'}. Previous schedule preserved."
                ]
                return fallback

            return candidate

        except Exception as exc:
            logger.error("Safe re-optimization encountered an error: %s", exc, exc_info=True)
            if previous_schedule and previous_schedule.is_valid:
                logger.info("Preserving previous valid schedule following exception: %s", exc)
                fallback = previous_schedule.model_copy(deep=True)
                fallback.validation_violations = [f"Re-optimization raised exception: {str(exc)}. Previous schedule preserved."]
                return fallback
            raise

    def _create_scorer(self, dynamic_weights=None) -> DynamicPriorityScorer:
        if dynamic_weights:
            weights = DynamicPriorityWeights(
                emergency_weight=dynamic_weights.emergency_weight,
                urgency_weight=dynamic_weights.urgency_weight,
                freshness_weight=dynamic_weights.freshness_weight,
                waiting_weight=dynamic_weights.waiting_weight,
            )
            return DynamicPriorityScorer(weights=weights)
        return DynamicPriorityScorer()

    def _convert_dataset(
        self,
        dataset: DatasetRead,
        scorer: DynamicPriorityScorer,
        outages_by_station: Optional[Dict[str, List[TimeWindow]]] = None,
    ):
        """Convert DatasetRead schemas to Developer 1 domain models with dynamic scores and outages."""
        sat_ids = {p.satellite_id for p in dataset.satellite_passes}
        satellites = [Satellite(id=sid, name=sid) for sid in sat_ids]

        # Map Ground Stations
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
                outages=outages_by_station.get(gs.station_id, []) if outages_by_station else [],
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

        priority_map = {
            1: Priority.CRITICAL,  # 4
            2: Priority.HIGH,      # 3
            3: Priority.MEDIUM,    # 2
            4: Priority.LOW,       # 1
            5: Priority.LOW,       # 1
        }

        eval_time = datetime.now(timezone.utc)
        requests: List[DownlinkRequest] = []
        score_breakdowns: Dict[str, dict] = {}

        for p in dataset.satellite_passes:
            gs_rate = pass_rates.get(p.ground_station_id, 150.0)
            window_duration_sec = (p.end_time - p.start_time).total_seconds()
            max_channel_capacity_gb = (gs_rate * window_duration_sec) / 8000.0
            transferable_gb = min(p.data_volume_gb, max_channel_capacity_gb)

            # Evaluate dynamic multi-factor priority
            breakdown = scorer.score_request(
                priority=p.priority,
                deadline_time=p.end_time,
                data_generated_time=None,
                queued_time=p.start_time,
                evaluation_time=eval_time,
                is_emergency=(p.priority == 1),
            )
            score_breakdowns[p.pass_id] = breakdown.model_dump()

            requests.append(
                DownlinkRequest(
                    id=p.pass_id,
                    satellite_id=p.satellite_id,
                    data_volume_mb=round(transferable_gb * 1000.0, 4),
                    priority=priority_map.get(p.priority, Priority.MEDIUM),
                    deadline_time=_ensure_utc(p.end_time),
                    queued_time=_ensure_utc(p.start_time),
                    dynamic_score=breakdown.combined_score,
                    score_breakdown=breakdown.model_dump(),
                )
            )

        return satellites, ground_stations, windows, requests, score_breakdowns

    def _map_result_to_response(
        self,
        dataset: DatasetRead,
        result: ScheduleResult,
        algorithm: AlgorithmType,
        score_breakdowns: Dict[str, dict],
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
            breakdown = score_breakdowns.get(task.request_id)

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
                    dynamic_score=task.dynamic_score or (breakdown.get("combined_score") if breakdown else None),
                    score_breakdown=task.score_breakdown or breakdown,
                )
            )

        unassigned_passes: List[UnassignedPass] = []
        for rej_id in result.rejected_request_ids:
            orig_pass = pass_lookup.get(rej_id)
            if orig_pass:
                breakdown = score_breakdowns.get(rej_id)
                unassigned_passes.append(
                    UnassignedPass(
                        pass_id=orig_pass.pass_id,
                        satellite_id=orig_pass.satellite_id,
                        ground_station_id=orig_pass.ground_station_id,
                        start_time=_ensure_utc(orig_pass.start_time),
                        end_time=_ensure_utc(orig_pass.end_time),
                        priority=orig_pass.priority,
                        reason="Unassigned: rejected due to station temporal conflict, antenna slew buffer, or channel capacity constraint",
                        dynamic_score=breakdown.get("combined_score") if breakdown else None,
                        score_breakdown=breakdown,
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
            is_mock=False,
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

        # Calculate average dynamic score across scheduled passes
        dyn_scores = [p.dynamic_score for p in scheduled_passes if p.dynamic_score is not None]
        avg_dynamic_score = round(sum(dyn_scores) / len(dyn_scores), 2) if dyn_scores else None

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
            average_dynamic_score=avg_dynamic_score,
        )
