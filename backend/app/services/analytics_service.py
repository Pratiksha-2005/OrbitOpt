"""Operational Analytics, Reporting, and Deterministic Deadline-Risk Service."""

import csv
import io
import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ResourceNotFoundError
from app.db.models.execution import PassExecutionModel
from app.db.models.outage import OutageModel
from app.db.models.schedule import ScheduleRunModel
from app.schemas.analytics import (
    BenchmarkComparisonMetric,
    DeadlineRiskItem,
    DeadlineRiskSummary,
    MetricDoc,
    OperationalAnalyticsResponse,
    PlannedVsActualData,
    RiskLevel,
    StationAvailabilityMetric,
    StationUtilizationMetric,
)
from app.schemas.schedule import AlgorithmType, ScheduledPass, ScheduleRunResponse
from app.services.dataset_service import DatasetService
from app.services.schedule_service import ScheduleService

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _percentile(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


class AnalyticsService:
    """Service generating operational KPIs, deterministic risk analysis, and exportable mission reports."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.dataset_service = DatasetService(db)

    async def get_operational_analytics(self, run_id: str) -> OperationalAnalyticsResponse:
        """Calculate comprehensive operational metrics for a specific schedule run."""
        # 1. Fetch Schedule Run
        stmt = (
            select(ScheduleRunModel)
            .where(ScheduleRunModel.id == run_id)
            .options(selectinload(ScheduleRunModel.scheduled_passes))
        )
        result = await self.db.execute(stmt)
        run_model = result.scalar_one_or_none()
        if not run_model:
            raise ResourceNotFoundError(resource="Schedule Run", resource_id=run_id)

        # 2. Fetch Dataset (Source of truth for all contact opportunities)
        dataset = await self.dataset_service.get_dataset(run_model.dataset_id)

        # 3. Fetch Execution Records
        exec_stmt = select(PassExecutionModel).where(
            PassExecutionModel.dataset_id == run_model.dataset_id
        )
        exec_rows = (await self.db.execute(exec_stmt)).scalars().all()
        exec_map: Dict[str, PassExecutionModel] = {em.pass_id: em for em in exec_rows}

        # 4. Fetch Outages for participating stations
        station_ids = [gs.station_id for gs in dataset.ground_stations]
        outage_stmt = select(OutageModel).where(
            OutageModel.station_id.in_(station_ids),
            OutageModel.status.in_(["active", "ACTIVE"]),
        )
        outages = (await self.db.execute(outage_stmt)).scalars().all()

        # 5. Extract Scheduled and Dataset Passes
        scheduled_allocs = run_model.scheduled_passes
        scheduled_pass_ids = {sp.pass_id for sp in scheduled_allocs}
        dataset_pass_map = {p.pass_id: p for p in dataset.satellite_passes}
        total_passes = len(dataset.satellite_passes)
        scheduled_count = len(scheduled_allocs)
        unscheduled_count = max(0, total_passes - scheduled_count)
        scheduled_percentage = (
            round((scheduled_count / total_passes * 100.0), 2) if total_passes > 0 else 0.0
        )

        # 6. Planned vs. Actually Delivered Data Volume
        planned_data_volume_gb = round(sum(sp.data_volume_gb for sp in scheduled_allocs), 2)
        actual_delivered_data_gb = 0.0
        planned_vs_actual_items: List[PlannedVsActualData] = []
        has_manual = False
        has_simulated = False

        for sp in scheduled_allocs:
            em = exec_map.get(sp.pass_id)
            actual_vol = em.actual_data_delivered_gb if em else None
            status_val = em.status if em else "SCHEDULED"
            telemetry_src = em.telemetry_source if em else "unrecorded"
            if em:
                if em.telemetry_source == "operator_manual":
                    has_manual = True
                elif em.telemetry_source == "simulated":
                    has_simulated = True

            if actual_vol is not None and actual_vol > 0.0:
                actual_delivered_data_gb += actual_vol

            planned_vs_actual_items.append(
                PlannedVsActualData(
                    pass_id=sp.pass_id,
                    satellite_id=sp.satellite_id,
                    ground_station_id=sp.ground_station_id,
                    priority=sp.priority,
                    execution_status=status_val,
                    planned_data_volume_gb=sp.data_volume_gb,
                    actual_data_delivered_gb=actual_vol,
                    telemetry_source=telemetry_src,
                    is_delivered=(actual_vol is not None and actual_vol > 0.0 and status_val == "COMPLETED"),
                )
            )

        actual_delivered_data_gb = round(actual_delivered_data_gb, 2)
        confirmed_delivery_ratio_pct = (
            round((actual_delivered_data_gb / planned_data_volume_gb * 100.0), 2)
            if planned_data_volume_gb > 0
            else 0.0
        )

        # 7. Execution State Machine Counts
        completed_count = sum(1 for em in exec_rows if em.status == "COMPLETED")
        missed_count = sum(1 for em in exec_rows if em.status == "MISSED")
        cancelled_count = sum(1 for em in exec_rows if em.status == "CANCELLED")
        acquiring_count = sum(1 for em in exec_rows if em.status == "ACQUIRING")
        transmitting_count = sum(1 for em in exec_rows if em.status == "TRANSMITTING")
        scheduled_exec_count = sum(1 for em in exec_rows if em.status == "SCHEDULED")
        locked_passes_count = sum(1 for em in exec_rows if em.is_locked)

        # 8. Critical Priority Service Rate
        # Denominator: total passes in input dataset with priority == 1
        critical_in_dataset = [p for p in dataset.satellite_passes if p.priority == 1]
        critical_total_count = len(critical_in_dataset)
        critical_scheduled_count = sum(1 for sp in scheduled_allocs if sp.priority == 1)
        critical_service_rate_pct = (
            round((critical_scheduled_count / critical_total_count * 100.0), 2)
            if critical_total_count > 0
            else 100.0
        )

        # 9. Deadline Satisfaction Rate
        deadline_satisfied_count = 0
        deadline_missed_count = 0
        total_deadlines = total_passes

        for p in dataset.satellite_passes:
            deadline = _ensure_utc(p.end_time)
            if p.pass_id in scheduled_pass_ids:
                # Find matching allocation
                alloc = next((sp for sp in scheduled_allocs if sp.pass_id == p.pass_id), None)
                if alloc and _ensure_utc(alloc.end_time) <= deadline:
                    em = exec_map.get(p.pass_id)
                    if em and em.status in ("MISSED", "CANCELLED"):
                        deadline_missed_count += 1
                    else:
                        deadline_satisfied_count += 1
                else:
                    deadline_missed_count += 1
            else:
                deadline_missed_count += 1

        deadline_satisfaction_rate_pct = (
            round((deadline_satisfied_count / total_deadlines * 100.0), 2)
            if total_deadlines > 0
            else 100.0
        )
        missed_deadline_rate_pct = round(100.0 - deadline_satisfaction_rate_pct, 2)

        # 10. Waiting Time Metrics (Seconds from availability/window start to transmission start)
        wait_times: List[float] = []
        for sp in scheduled_allocs:
            orig = dataset_pass_map.get(sp.pass_id)
            if orig:
                em = exec_map.get(sp.pass_id)
                actual_start = _ensure_utc(em.actual_start_time) if (em and em.actual_start_time) else _ensure_utc(sp.start_time)
                avail_time = _ensure_utc(orig.start_time)
                wait_sec = max(0.0, (actual_start - avail_time).total_seconds())
                wait_times.append(wait_sec)

        mean_wait = round(sum(wait_times) / len(wait_times), 1) if wait_times else None
        median_wait = round(_percentile(wait_times, 50.0), 1) if wait_times else None
        p90_wait = round(_percentile(wait_times, 90.0), 1) if wait_times else None
        p95_wait = round(_percentile(wait_times, 95.0), 1) if wait_times else None

        # 11. Ground Station Availability After Outages
        pass_starts = [_ensure_utc(p.start_time) for p in dataset.satellite_passes]
        pass_ends = [_ensure_utc(p.end_time) for p in dataset.satellite_passes]
        horizon_start = min(pass_starts) if pass_starts else datetime.now(timezone.utc)
        horizon_end = max(pass_ends) if pass_ends else datetime.now(timezone.utc)
        horizon_seconds = max(1.0, (horizon_end - horizon_start).total_seconds())
        horizon_hours = round(horizon_seconds / 3600.0, 2)

        station_avail_list: List[StationAvailabilityMetric] = []
        total_outage_sec = 0.0

        for gs in dataset.ground_stations:
            gs_outages = [o for o in outages if o.station_id == gs.station_id]
            outage_sec_gs = 0.0
            for o in gs_outages:
                o_start = max(horizon_start, _ensure_utc(o.start_time))
                o_end = min(horizon_end, _ensure_utc(o.end_time))
                if o_end > o_start:
                    outage_sec_gs += (o_end - o_start).total_seconds()

            avail_sec_gs = max(0.0, horizon_seconds - outage_sec_gs)
            avail_pct_gs = round((avail_sec_gs / horizon_seconds * 100.0), 2)
            total_outage_sec += outage_sec_gs

            station_avail_list.append(
                StationAvailabilityMetric(
                    station_id=gs.station_id,
                    station_name=gs.name,
                    horizon_hours=horizon_hours,
                    outage_hours=round(outage_sec_gs / 3600.0, 2),
                    available_hours=round(avail_sec_gs / 3600.0, 2),
                    availability_percentage=avail_pct_gs,
                    active_outages_count=len(gs_outages),
                )
            )

        total_station_horizon_sec = horizon_seconds * max(1, len(dataset.ground_stations))
        available_station_sec = max(0.0, total_station_horizon_sec - total_outage_sec)
        overall_availability_pct = round(
            (available_station_sec / total_station_horizon_sec * 100.0), 2
        )

        # 12. Transmission Utilization and Total Resource Occupancy (including setup buffers)
        setup_time_sec = float(run_model.parameters.get("setup_time_seconds", 120))
        total_active_tx_sec = sum(sp.duration_seconds for sp in scheduled_allocs)
        total_setup_buffer_sec = setup_time_sec * len(scheduled_allocs)
        total_occupied_sec = total_active_tx_sec + total_setup_buffer_sec

        transmission_utilization_pct = round(
            (total_active_tx_sec / total_station_horizon_sec * 100.0), 2
        )
        total_occupancy_pct = round(
            (total_occupied_sec / total_station_horizon_sec * 100.0), 2
        )

        station_utils: List[StationUtilizationMetric] = []
        for gs in dataset.ground_stations:
            gs_allocs = [sp for sp in scheduled_allocs if sp.ground_station_id == gs.station_id]
            gs_tx_sec = sum(sp.duration_seconds for sp in gs_allocs)
            gs_occ_sec = gs_tx_sec + (setup_time_sec * len(gs_allocs))
            station_utils.append(
                StationUtilizationMetric(
                    station_id=gs.station_id,
                    station_name=gs.name,
                    active_transmission_seconds=round(gs_tx_sec, 1),
                    total_occupied_seconds_with_buffers=round(gs_occ_sec, 1),
                    transmission_utilization_pct=round((gs_tx_sec / horizon_seconds * 100.0), 2),
                    total_occupancy_pct=round((gs_occ_sec / horizon_seconds * 100.0), 2),
                )
            )

        # 13. Outage Impact (Affected passes)
        affected_pass_count = 0
        for p in dataset.satellite_passes:
            p_start = _ensure_utc(p.start_time)
            p_end = _ensure_utc(p.end_time)
            for o in outages:
                if o.station_id == p.ground_station_id:
                    o_start = _ensure_utc(o.start_time)
                    o_end = _ensure_utc(o.end_time)
                    if max(p_start, o_start) < min(p_end, o_end):
                        affected_pass_count += 1
                        break

        # 14. FCFS vs CP-SAT Benchmark Comparison (Look for matching baseline or optimized run)
        benchmark_comp = await self._find_or_compute_benchmark(run_model, dataset)

        # 15. Documentation dictionary
        doc_dict = self._get_metric_documentation()

        return OperationalAnalyticsResponse(
            run_id=run_model.id,
            dataset_id=dataset.dataset_id,
            dataset_name=dataset.name,
            algorithm=AlgorithmType(run_model.algorithm),
            solver_status=run_model.status,
            solver_status_detail=run_model.solver_status_detail,
            execution_time_ms=run_model.execution_time_ms,
            objective_value=float(run_model.metrics.get("objective_value", 0.0)),
            is_valid=run_model.is_valid,
            validation_failure_count=len(run_model.validation_violations or []),
            validation_violations=run_model.validation_violations or [],
            created_at=_ensure_utc(run_model.created_at),
            total_passes=total_passes,
            scheduled_passes_count=scheduled_count,
            unscheduled_passes_count=unscheduled_count,
            scheduled_percentage=scheduled_percentage,
            planned_data_volume_gb=planned_data_volume_gb,
            actual_delivered_data_gb=actual_delivered_data_gb,
            confirmed_delivery_ratio_pct=confirmed_delivery_ratio_pct,
            planned_vs_actual_items=planned_vs_actual_items,
            completed_passes_count=completed_count,
            missed_passes_count=missed_count,
            cancelled_passes_count=cancelled_count,
            acquiring_passes_count=acquiring_count,
            transmitting_passes_count=transmitting_count,
            scheduled_execution_count=scheduled_exec_count,
            locked_passes_count=locked_passes_count,
            critical_scheduled_count=critical_scheduled_count,
            critical_total_count=critical_total_count,
            critical_service_rate_pct=critical_service_rate_pct,
            total_evaluated_deadlines=total_deadlines,
            deadline_satisfied_count=deadline_satisfied_count,
            deadline_missed_count=deadline_missed_count,
            deadline_satisfaction_rate_pct=deadline_satisfaction_rate_pct,
            missed_deadline_rate_pct=missed_deadline_rate_pct,
            mean_wait_time_seconds=mean_wait,
            median_wait_time_seconds=median_wait,
            p90_wait_time_seconds=p90_wait,
            p95_wait_time_seconds=p95_wait,
            overall_availability_pct=overall_availability_pct,
            total_station_horizon_hours=round(total_station_horizon_sec / 3600.0, 2),
            total_outage_hours=round(total_outage_sec / 3600.0, 2),
            available_station_hours=round(available_station_sec / 3600.0, 2),
            station_availability=station_avail_list,
            transmission_utilization_pct=transmission_utilization_pct,
            total_occupancy_pct=total_occupancy_pct,
            setup_buffer_seconds_used=total_setup_buffer_sec,
            station_utilizations=station_utils,
            outage_count=len(outages),
            affected_passes_count=affected_pass_count,
            benchmark_comparison=benchmark_comp,
            has_live_backend_data=True,
            has_manual_telemetry=has_manual,
            has_simulated_telemetry=has_simulated or not has_manual,
            uncalculated_metrics=[],
            metric_documentation=doc_dict,
        )

    async def get_deadline_risk_analysis(self, run_id: str) -> DeadlineRiskSummary:
        """Deterministic, rule-based deadline risk evaluation across all passes in scenario."""
        stmt = (
            select(ScheduleRunModel)
            .where(ScheduleRunModel.id == run_id)
            .options(selectinload(ScheduleRunModel.scheduled_passes))
        )
        run_model = (await self.db.execute(stmt)).scalar_one_or_none()
        if not run_model:
            raise ResourceNotFoundError(resource="Schedule Run", resource_id=run_id)

        dataset = await self.dataset_service.get_dataset(run_model.dataset_id)
        exec_stmt = select(PassExecutionModel).where(
            PassExecutionModel.dataset_id == run_model.dataset_id
        )
        exec_rows = (await self.db.execute(exec_stmt)).scalars().all()
        exec_map: Dict[str, PassExecutionModel] = {em.pass_id: em for em in exec_rows}

        station_ids = [gs.station_id for gs in dataset.ground_stations]
        outage_stmt = select(OutageModel).where(
            OutageModel.station_id.in_(station_ids),
            OutageModel.status == "ACTIVE",
        )
        outages = (await self.db.execute(outage_stmt)).scalars().all()

        alloc_map = {sp.pass_id: sp for sp in run_model.scheduled_passes}
        items: List[DeadlineRiskItem] = []
        low_count = 0
        med_count = 0
        high_count = 0
        crit_count = 0

        for p in dataset.satellite_passes:
            deadline = _ensure_utc(p.end_time)
            alloc = alloc_map.get(p.pass_id)
            em = exec_map.get(p.pass_id)
            status_val = em.status if em else ("SCHEDULED" if alloc else "UNSCHEDULED")

            # Check if assigned station has active outage during pass
            has_outage = False
            for o in outages:
                if o.station_id == p.ground_station_id:
                    o_start = _ensure_utc(o.start_time)
                    o_end = _ensure_utc(o.end_time)
                    p_start = _ensure_utc(p.start_time)
                    p_end = _ensure_utc(p.end_time)
                    if max(p_start, o_start) < min(p_end, o_end):
                        has_outage = True
                        break

            if alloc:
                sched_start = _ensure_utc(alloc.start_time)
                sched_end = _ensure_utc(alloc.end_time)
                slack_sec = (deadline - sched_end).total_seconds()

                if status_val == "COMPLETED":
                    level = RiskLevel.LOW
                    expl = "Pass successfully completed and confirmed delivered within deadline."
                elif status_val in ("MISSED", "CANCELLED"):
                    level = RiskLevel.CRITICAL
                    expl = f"Pass execution reached terminal failed state: {status_val}."
                elif has_outage:
                    level = RiskLevel.HIGH
                    expl = f"Assigned ground station '{p.ground_station_id}' has an active outage overlapping pass window."
                elif slack_sec < 0:
                    level = RiskLevel.CRITICAL
                    expl = f"Scheduled completion time exceeds pass deadline by {abs(slack_sec):.0f}s."
                elif slack_sec < 300:  # < 5 mins
                    level = RiskLevel.MEDIUM
                    expl = f"Tight completion slack of {slack_sec:.0f}s before deadline."
                else:
                    level = RiskLevel.LOW
                    expl = f"Scheduled with healthy completion slack of {slack_sec:.0f}s."

                items.append(
                    DeadlineRiskItem(
                        pass_id=p.pass_id,
                        satellite_id=p.satellite_id,
                        ground_station_id=p.ground_station_id,
                        priority=p.priority,
                        deadline=deadline,
                        is_scheduled=True,
                        scheduled_start_time=sched_start,
                        scheduled_end_time=sched_end,
                        execution_status=status_val,
                        risk_level=level,
                        slack_seconds=slack_sec,
                        has_outage_conflict=has_outage,
                        explanation=expl,
                    )
                )
            else:
                # Unscheduled pass
                # Deterministic rule: check if alternative future windows exist for this satellite
                future_windows = [
                    cand for cand in dataset.satellite_passes
                    if cand.satellite_id == p.satellite_id
                    and cand.pass_id != p.pass_id
                    and _ensure_utc(cand.start_time) < deadline
                ]

                if not future_windows:
                    level = RiskLevel.CRITICAL
                    expl = "Unscheduled request with zero available contact opportunities before deadline."
                elif has_outage:
                    level = RiskLevel.HIGH
                    expl = "Unscheduled request; primary target ground station is degraded by active outage."
                elif p.priority == 1:
                    level = RiskLevel.HIGH
                    expl = "High-priority critical request unallocated in current schedule run."
                else:
                    level = RiskLevel.MEDIUM
                    expl = f"Unallocated in current schedule; {len(future_windows)} alternate candidate windows exist before deadline."

                items.append(
                    DeadlineRiskItem(
                        pass_id=p.pass_id,
                        satellite_id=p.satellite_id,
                        ground_station_id=p.ground_station_id,
                        priority=p.priority,
                        deadline=deadline,
                        is_scheduled=False,
                        scheduled_start_time=None,
                        scheduled_end_time=None,
                        execution_status="UNSCHEDULED",
                        risk_level=level,
                        slack_seconds=None,
                        has_outage_conflict=has_outage,
                        explanation=expl,
                    )
                )

            if items[-1].risk_level == RiskLevel.LOW:
                low_count += 1
            elif items[-1].risk_level == RiskLevel.MEDIUM:
                med_count += 1
            elif items[-1].risk_level == RiskLevel.HIGH:
                high_count += 1
            elif items[-1].risk_level == RiskLevel.CRITICAL:
                crit_count += 1

        return DeadlineRiskSummary(
            run_id=run_model.id,
            dataset_id=dataset.dataset_id,
            evaluated_at=datetime.now(timezone.utc),
            total_requests=len(items),
            low_risk_count=low_count,
            medium_risk_count=med_count,
            high_risk_count=high_count,
            critical_risk_count=crit_count,
            items=items,
        )

    async def export_mission_report(
        self,
        run_id: str,
        export_format: str = "json",
    ) -> Union[dict, str]:
        """Export full mission analytics report in JSON or CSV format."""
        analytics = await self.get_operational_analytics(run_id)
        risks = await self.get_deadline_risk_analysis(run_id)

        if export_format.lower() == "json":
            return {
                "report_metadata": {
                    "run_id": analytics.run_id,
                    "dataset_id": analytics.dataset_id,
                    "dataset_name": analytics.dataset_name,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "format": "json",
                    "provenance": "OrbitOpt Operational Analytics Engine (Sprint 4)",
                },
                "operational_analytics": analytics.model_dump(mode="json"),
                "deadline_risk_analysis": risks.model_dump(mode="json"),
            }

        # CSV format generation
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")

        # 1. Mission Header
        writer.writerow(["# ORBITOPT MISSION EXECUTION REPORT"])
        writer.writerow(["Run ID", analytics.run_id])
        writer.writerow(["Dataset ID", analytics.dataset_id])
        writer.writerow(["Dataset Name", analytics.dataset_name])
        writer.writerow(["Algorithm", analytics.algorithm.value])
        writer.writerow(["Solver Status", analytics.solver_status])
        writer.writerow(["Solver Detail", analytics.solver_status_detail or "N/A"])
        writer.writerow(["Runtime (ms)", analytics.execution_time_ms])
        writer.writerow(["Objective Value", analytics.objective_value])
        writer.writerow(["Is Valid", analytics.is_valid])
        writer.writerow(["Validation Failure Count", analytics.validation_failure_count])
        writer.writerow(["Exported At (UTC)", datetime.now(timezone.utc).isoformat()])
        writer.writerow([])

        # 2. Key Operational Metrics Summary
        writer.writerow(["# OPERATIONAL KPIS & METRICS SUMMARY"])
        writer.writerow(["Metric Name", "Value", "Units", "Formula / Denominator"])
        writer.writerow(["Total Passes", analytics.total_passes, "passes", "Input contact opportunities in dataset"])
        writer.writerow(["Scheduled Passes", analytics.scheduled_passes_count, "passes", "Allocated passes in schedule"])
        writer.writerow(["Unscheduled Passes", analytics.unscheduled_passes_count, "passes", "Dropped or unallocated passes"])
        writer.writerow(["Schedule Percentage", f"{analytics.scheduled_percentage}%", "%", "Scheduled passes / Total passes * 100"])
        writer.writerow(["Planned Data Volume", f"{analytics.planned_data_volume_gb}", "GB", "Sum of planned data volume of scheduled passes"])
        writer.writerow(["Actual Delivered Data", f"{analytics.actual_delivered_data_gb}", "GB", "Sum of verified delivered volume from execution records"])
        writer.writerow(["Confirmed Delivery Ratio", f"{analytics.confirmed_delivery_ratio_pct}%", "%", "Actual delivered GB / Planned GB * 100"])
        writer.writerow(["Completed Passes", analytics.completed_passes_count, "passes", "Passes in COMPLETED state"])
        writer.writerow(["Missed Passes", analytics.missed_passes_count, "passes", "Passes in MISSED state"])
        writer.writerow(["Cancelled Passes", analytics.cancelled_passes_count, "passes", "Passes in CANCELLED state"])
        writer.writerow(["Active Transmitting/Acquiring", analytics.transmitting_passes_count + analytics.acquiring_passes_count, "passes", "Passes in active execution"])
        writer.writerow(["Critical Service Rate", f"{analytics.critical_service_rate_pct}%", "%", "Critical scheduled / Total critical in dataset * 100"])
        writer.writerow(["Deadline Satisfaction Rate", f"{analytics.deadline_satisfaction_rate_pct}%", "%", "Satisfied deadlines / Total opportunities * 100"])
        writer.writerow(["Mean Wait Time", f"{analytics.mean_wait_time_seconds or 'N/A'}", "seconds", "Mean duration from pass start to scheduled transmission start"])
        writer.writerow(["Median Wait Time", f"{analytics.median_wait_time_seconds or 'N/A'}", "seconds", "50th percentile wait time"])
        writer.writerow(["P90 Wait Time", f"{analytics.p90_wait_time_seconds or 'N/A'}", "seconds", "90th percentile wait time"])
        writer.writerow(["Overall Station Availability", f"{analytics.overall_availability_pct}%", "%", "Available horizon hours / Total horizon hours * 100"])
        writer.writerow(["Transmission Utilization", f"{analytics.transmission_utilization_pct}%", "%", "Total active tx seconds / Total station horizon seconds * 100"])
        writer.writerow(["Total Occupancy (inc. Buffers)", f"{analytics.total_occupancy_pct}%", "%", "(Active tx seconds + setup buffers) / Total station horizon seconds * 100"])
        writer.writerow([])

        # 3. Ground Station Availability Breakdown
        writer.writerow(["# GROUND STATION AVAILABILITY AFTER OUTAGES"])
        writer.writerow(["Station ID", "Station Name", "Horizon (hrs)", "Outage (hrs)", "Available (hrs)", "Availability %", "Active Outages"])
        for sa in analytics.station_availability:
            writer.writerow([sa.station_id, sa.station_name, sa.horizon_hours, sa.outage_hours, sa.available_hours, f"{sa.availability_percentage}%", sa.active_outages_count])
        writer.writerow([])

        # 4. Scheduled Pass Allocations & Telemetry
        writer.writerow(["# SCHEDULED PASS ALLOCATIONS & EXECUTION TELEMETRY"])
        writer.writerow(["Pass ID", "Satellite ID", "Ground Station ID", "Priority", "Execution Status", "Planned Vol (GB)", "Actual Delivered (GB)", "Telemetry Source", "Is Delivered"])
        for item in analytics.planned_vs_actual_items:
            writer.writerow([
                item.pass_id,
                item.satellite_id,
                item.ground_station_id,
                item.priority,
                item.execution_status,
                item.planned_data_volume_gb,
                item.actual_data_delivered_gb if item.actual_data_delivered_gb is not None else "N/A",
                item.telemetry_source,
                item.is_delivered,
            ])
        writer.writerow([])

        # 5. Deterministic Deadline Risk Register
        writer.writerow(["# DETERMINISTIC DEADLINE RISK REGISTER (RULE-BASED)"])
        writer.writerow(["Pass ID", "Satellite ID", "Station ID", "Priority", "Is Scheduled", "Deadline (UTC)", "Execution Status", "Risk Level", "Slack (s)", "Outage Conflict", "Explanation"])
        for r in risks.items:
            writer.writerow([
                r.pass_id,
                r.satellite_id,
                r.ground_station_id,
                r.priority,
                r.is_scheduled,
                r.deadline.isoformat(),
                r.execution_status,
                r.risk_level.value,
                f"{r.slack_seconds:.1f}" if r.slack_seconds is not None else "N/A",
                r.has_outage_conflict,
                r.explanation,
            ])

        return output.getvalue()

    async def _find_or_compute_benchmark(
        self,
        current_run: ScheduleRunModel,
        dataset,
    ) -> Optional[BenchmarkComparisonMetric]:
        """Find a comparable counterpart run (FCFS or CP-SAT) for the same dataset."""
        is_cpsat = current_run.algorithm == "cp_sat_optimizer"
        target_algo = "baseline_fcfs" if is_cpsat else "cp_sat_optimizer"

        stmt = (
            select(ScheduleRunModel)
            .where(
                ScheduleRunModel.dataset_id == current_run.dataset_id,
                ScheduleRunModel.algorithm == target_algo,
            )
            .order_by(ScheduleRunModel.created_at.desc())
        )
        target_run = (await self.db.execute(stmt)).scalars().first()
        if not target_run:
            return None

        base_run = target_run if is_cpsat else current_run
        opt_run = current_run if is_cpsat else target_run

        base_vol = float(base_run.metrics.get("total_data_downlinked_gb", 0.0))
        opt_vol = float(opt_run.metrics.get("total_data_downlinked_gb", 0.0))
        vol_imp_gb = round(opt_vol - base_vol, 2)
        vol_imp_pct = round(((opt_vol - base_vol) / base_vol * 100.0), 2) if base_vol > 0 else 0.0

        base_obj = float(base_run.metrics.get("objective_value", 0.0))
        opt_obj = float(opt_run.metrics.get("objective_value", 0.0))
        obj_imp_pct = round(((opt_obj - base_obj) / base_obj * 100.0), 2) if base_obj > 0 else 0.0

        base_sched = int(base_run.metrics.get("scheduled_passes_count", 0))
        opt_sched = int(opt_run.metrics.get("scheduled_passes_count", 0))

        base_sat = float(base_run.metrics.get("priority_satisfaction_rate", 0.0))
        opt_sat = float(opt_run.metrics.get("priority_satisfaction_rate", 0.0))

        # Critical rate comparison
        crit_passes = [p for p in dataset.satellite_passes if p.priority == 1]
        crit_denom = len(crit_passes)
        base_crit_count = sum(1 for p in base_run.scheduled_passes if p.priority == 1)
        opt_crit_count = sum(1 for p in opt_run.scheduled_passes if p.priority == 1)
        base_crit_rate = round(base_crit_count / crit_denom * 100.0, 2) if crit_denom > 0 else 100.0
        opt_crit_rate = round(opt_crit_count / crit_denom * 100.0, 2) if crit_denom > 0 else 100.0

        runtime_ratio = (
            round(opt_run.execution_time_ms / base_run.execution_time_ms, 2)
            if base_run.execution_time_ms > 0
            else 1.0
        )

        return BenchmarkComparisonMetric(
            baseline_run_id=base_run.id,
            baseline_algorithm=base_run.algorithm,
            optimized_run_id=opt_run.id,
            optimized_algorithm=opt_run.algorithm,
            dataset_id=dataset.dataset_id,
            baseline_volume_gb=base_vol,
            optimized_volume_gb=opt_vol,
            volume_improvement_gb=vol_imp_gb,
            volume_improvement_pct=vol_imp_pct,
            baseline_objective=base_obj,
            optimized_objective=opt_obj,
            objective_improvement_pct=obj_imp_pct,
            baseline_scheduled_passes=base_sched,
            optimized_scheduled_passes=opt_sched,
            scheduled_passes_delta=opt_sched - base_sched,
            baseline_priority_satisfaction_pct=base_sat,
            optimized_priority_satisfaction_pct=opt_sat,
            priority_satisfaction_delta_pct=round(opt_sat - base_sat, 2),
            baseline_critical_service_rate_pct=base_crit_rate,
            optimized_critical_service_rate_pct=opt_crit_rate,
            critical_service_rate_delta_pct=round(opt_crit_rate - base_crit_rate, 2),
            baseline_runtime_ms=base_run.execution_time_ms,
            optimized_runtime_ms=opt_run.execution_time_ms,
            runtime_ratio=runtime_ratio,
        )

    def _get_metric_documentation(self) -> Dict[str, MetricDoc]:
        return {
            "scheduled_percentage": MetricDoc(
                name="Pass Allocation Rate",
                units="Percentage [0.0 - 100.0]",
                formula="(scheduled_passes_count / total_passes) * 100.0",
                denominator="Total input contact opportunities in the selected dataset scenario",
                handling_missing_data="Evaluates to 0.0% if total_passes is 0.",
            ),
            "critical_service_rate_pct": MetricDoc(
                name="Critical Priority Service Rate",
                units="Percentage [0.0 - 100.0]",
                formula="(critical_scheduled_count / critical_total_count) * 100.0",
                denominator="Total passes in dataset with Priority = 1 (Critical)",
                handling_missing_data="Evaluates to 100.0% if dataset contains zero priority 1 passes.",
            ),
            "confirmed_delivery_ratio_pct": MetricDoc(
                name="Confirmed Delivered Volume Ratio",
                units="Percentage [0.0 - 100.0]",
                formula="(actual_delivered_data_gb / planned_data_volume_gb) * 100.0",
                denominator="Total planned data volume of scheduled passes",
                handling_missing_data="Evaluates to 0.0% if no execution measurements have been recorded.",
            ),
            "deadline_satisfaction_rate_pct": MetricDoc(
                name="Deadline Satisfaction Rate",
                units="Percentage [0.0 - 100.0]",
                formula="(deadline_satisfied_count / total_evaluated_deadlines) * 100.0",
                denominator="Total contact opportunities in dataset (using pass window end as deadline)",
                handling_missing_data="Evaluates to 100.0% if zero deadlines are evaluated.",
            ),
            "transmission_utilization_pct": MetricDoc(
                name="Time-Based Transmission Utilization",
                units="Percentage [0.0 - 100.0]",
                formula="(total_active_transmission_seconds / total_station_horizon_seconds) * 100.0",
                denominator="Sum of scenario horizon duration across all ground stations (never pass counts)",
                handling_missing_data="Evaluates to 0.0% if no passes are scheduled or horizon is zero.",
            ),
            "total_occupancy_pct": MetricDoc(
                name="Total Resource Occupancy (with Antenna Setup Buffers)",
                units="Percentage [0.0 - 100.0]",
                formula="((total_active_tx_sec + total_setup_buffer_sec) / total_station_horizon_seconds) * 100.0",
                denominator="Sum of scenario horizon duration across all ground stations",
                handling_missing_data="Evaluates to 0.0% if no passes are scheduled.",
            ),
            "overall_availability_pct": MetricDoc(
                name="Ground Station Availability Post-Outages",
                units="Percentage [0.0 - 100.0]",
                formula="((total_station_horizon_sec - total_outage_sec) / total_station_horizon_sec) * 100.0",
                denominator="Total horizon duration multiplied by number of ground stations",
                handling_missing_data="Defaults to 100.0% if no outages are active.",
            ),
        }
