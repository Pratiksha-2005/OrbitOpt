"""Unit tests for Sprint 4 Operational Analytics, Formulas, Edge Cases, and Reports."""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ResourceNotFoundError
from app.db.models.execution import PassExecutionModel
from app.db.models.outage import OutageModel
from app.db.models.schedule import ScheduleRunModel, ScheduledAllocationModel
from app.schemas.analytics import RiskLevel
from app.schemas.dataset import DatasetCreate
from app.schemas.execution import PassTransitionRequest
from app.schemas.ground_station import GroundStationCreate
from app.schemas.outage import OutageCreate
from app.schemas.satellite_pass import SatellitePassCreate
from app.schemas.schedule import AlgorithmType, BaselineScheduleRequest, OptimizeScheduleRequest
from app.services.analytics_service import AnalyticsService
from app.services.dataset_service import DatasetService
from app.services.execution_service import ExecutionService
from app.services.outage_service import OutageService
from app.services.schedule_service import ScheduleService
from app.services.scheduler.real_engine import RealSchedulerEngine


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 10, 10, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def analytics_dataset(db_session: AsyncSession, base_time: datetime):
    ds_service = DatasetService(db_session)
    dataset_payload = DatasetCreate(
        dataset_id="ds_sprint4_analytics_test",
        name="Sprint 4 Analytics Scenario",
        description="Scenario for validating metrics, deadline risks, and reports",
        ground_stations=[
            GroundStationCreate(
                station_id="GS-NORTH",
                name="North Station",
                latitude_deg=68.0,
                longitude_deg=14.0,
                elevation_m=50.0,
                downlink_rate_mbps=200.0,
            ),
            GroundStationCreate(
                station_id="GS-SOUTH",
                name="South Station",
                latitude_deg=-33.0,
                longitude_deg=18.0,
                elevation_m=25.0,
                downlink_rate_mbps=150.0,
            ),
        ],
        satellite_passes=[
            # Pass 1: Priority 1 (Critical)
            SatellitePassCreate(
                pass_id="PASS-AN-01",
                satellite_id="SAT-EO-1",
                ground_station_id="GS-NORTH",
                start_time=base_time,
                end_time=base_time + timedelta(minutes=10),
                max_elevation_deg=65.0,
                priority=1,
                data_volume_gb=20.0,
            ),
            # Pass 2: Priority 3 (Medium)
            SatellitePassCreate(
                pass_id="PASS-AN-02",
                satellite_id="SAT-EO-2",
                ground_station_id="GS-SOUTH",
                start_time=base_time + timedelta(minutes=15),
                end_time=base_time + timedelta(minutes=25),
                max_elevation_deg=45.0,
                priority=3,
                data_volume_gb=15.0,
            ),
            # Pass 3: Priority 2 (High) overlapping Pass 1 on North station (forces contention)
            SatellitePassCreate(
                pass_id="PASS-AN-03",
                satellite_id="SAT-COMM-1",
                ground_station_id="GS-NORTH",
                start_time=base_time + timedelta(minutes=5),
                end_time=base_time + timedelta(minutes=12),
                max_elevation_deg=50.0,
                priority=2,
                data_volume_gb=10.0,
            ),
        ],
    )
    return await ds_service.create_dataset(dataset_payload)


@pytest.mark.asyncio
async def test_metric_formulas_and_volume_separation(
    db_session: AsyncSession,
    analytics_dataset,
    base_time: datetime,
):
    """Verify planned vs actually delivered volume separation, critical service rate, and formula units."""
    engine = RealSchedulerEngine()
    schedule_service = ScheduleService(db_session, engine)
    analytics_service = AnalyticsService(db_session)
    execution_service = ExecutionService(db_session)

    # 1. Run baseline schedule
    run_res = await schedule_service.execute_baseline(
        BaselineScheduleRequest(dataset_id=analytics_dataset.dataset_id, setup_time_seconds=120)
    )

    # 2. Add an execution measurement for PASS-AN-01
    await execution_service.transition_execution(
        pass_id="PASS-AN-01",
        request=PassTransitionRequest(
            to_status="ACQUIRING",
            timestamp=base_time,
            actual_start_time=base_time,
            is_simulated=True,
        ),
    )
    await execution_service.transition_execution(
        pass_id="PASS-AN-01",
        request=PassTransitionRequest(
            to_status="TRANSMITTING",
            timestamp=base_time + timedelta(minutes=1),
            actual_data_delivered_gb=12.5,
            is_simulated=True,
        ),
    )
    await execution_service.transition_execution(
        pass_id="PASS-AN-01",
        request=PassTransitionRequest(
            to_status="COMPLETED",
            timestamp=base_time + timedelta(minutes=10),
            actual_end_time=base_time + timedelta(minutes=10),
            actual_data_delivered_gb=18.5,  # Measured delivery is 18.5 GB vs 20.0 GB planned
            is_simulated=True,
        ),
    )

    # 3. Calculate Operational Analytics
    analytics = await analytics_service.get_operational_analytics(run_res.run_id)

    # Assert volume separation
    assert analytics.planned_data_volume_gb > 0.0
    assert analytics.actual_delivered_data_gb == 18.5
    assert analytics.planned_data_volume_gb != analytics.actual_delivered_data_gb
    assert analytics.confirmed_delivery_ratio_pct is not None
    assert analytics.confirmed_delivery_ratio_pct > 0.0

    # Critical priority service rate: 1 critical pass in dataset (PASS-AN-01), scheduled = 1
    assert analytics.critical_total_count == 1
    assert analytics.critical_scheduled_count == 1
    assert analytics.critical_service_rate_pct == 100.0

    # Execution state counts
    assert analytics.completed_passes_count == 1
    assert analytics.locked_passes_count >= 1

    # Time-based utilization vs total occupancy
    assert analytics.transmission_utilization_pct > 0.0
    assert analytics.total_occupancy_pct >= analytics.transmission_utilization_pct
    assert analytics.setup_buffer_seconds_used > 0.0


@pytest.mark.asyncio
async def test_zero_denominators_and_edge_cases(
    db_session: AsyncSession,
    base_time: datetime,
):
    """Verify that zero denominators and missing data evaluate gracefully without zero-division exceptions."""
    ds_service = DatasetService(db_session)
    empty_dataset = await ds_service.create_dataset(
        DatasetCreate(
            dataset_id="ds_empty_analytics_test",
            name="Empty Analytics Scenario",
            ground_stations=[
                GroundStationCreate(
                    station_id="GS-SOLO",
                    name="Solo Station",
                    latitude_deg=10.0,
                    longitude_deg=10.0,
                    elevation_m=10.0,
                    downlink_rate_mbps=100.0,
                )
            ],
            # Pass with priority 3 only (no critical passes)
            satellite_passes=[
                SatellitePassCreate(
                    pass_id="PASS-NON-CRIT-01",
                    satellite_id="SAT-1",
                    ground_station_id="GS-SOLO",
                    start_time=base_time,
                    end_time=base_time + timedelta(minutes=5),
                    max_elevation_deg=30.0,
                    priority=3,
                    data_volume_gb=5.0,
                )
            ],
        )
    )

    engine = RealSchedulerEngine()
    schedule_service = ScheduleService(db_session, engine)
    analytics_service = AnalyticsService(db_session)

    run_res = await schedule_service.execute_baseline(
        BaselineScheduleRequest(dataset_id=empty_dataset.dataset_id, setup_time_seconds=60)
    )

    analytics = await analytics_service.get_operational_analytics(run_res.run_id)

    # Zero critical passes in dataset -> critical_service_rate_pct defaults to 100.0
    assert analytics.critical_total_count == 0
    assert analytics.critical_service_rate_pct == 100.0

    # No execution records recorded yet -> actual delivered is 0.0, not erroring
    assert analytics.actual_delivered_data_gb == 0.0

    # Waiting times exist
    assert analytics.mean_wait_time_seconds is not None
    assert analytics.median_wait_time_seconds is not None


@pytest.mark.asyncio
async def test_outages_affect_ground_station_availability(
    db_session: AsyncSession,
    analytics_dataset,
    base_time: datetime,
):
    """Verify ground-station availability drops after active outages are added."""
    engine = RealSchedulerEngine()
    outage_service = OutageService(db_session, engine)
    schedule_service = ScheduleService(db_session, engine)
    analytics_service = AnalyticsService(db_session)

    run_res = await schedule_service.execute_baseline(
        BaselineScheduleRequest(dataset_id=analytics_dataset.dataset_id, setup_time_seconds=120)
    )

    # 1. Before outage, availability is 100%
    pre_analytics = await analytics_service.get_operational_analytics(run_res.run_id)
    assert pre_analytics.overall_availability_pct == 100.0
    assert pre_analytics.total_outage_hours == 0.0

    # 2. Add active outage for GS-NORTH covering pass window
    await outage_service.create_outage(
        payload=OutageCreate(
            station_id="GS-NORTH",
            start_time=base_time,
            end_time=base_time + timedelta(minutes=15),
            reason="Antenna motor gimbal maintenance",
            dataset_id=analytics_dataset.dataset_id,
        )
    )

    # 3. Post outage, availability should decrease
    post_analytics = await analytics_service.get_operational_analytics(run_res.run_id)
    assert post_analytics.overall_availability_pct < 100.0
    assert post_analytics.total_outage_hours > 0.0
    assert post_analytics.outage_count == 1
    assert post_analytics.affected_passes_count >= 1


@pytest.mark.asyncio
async def test_rule_based_deadline_risk_analysis(
    db_session: AsyncSession,
    analytics_dataset,
    base_time: datetime,
):
    """Verify deterministic deadline risks identify terminal states, outage intersections, and slack buffers."""
    engine = RealSchedulerEngine()
    schedule_service = ScheduleService(db_session, engine)
    analytics_service = AnalyticsService(db_session)
    execution_service = ExecutionService(db_session)

    run_res = await schedule_service.execute_baseline(
        BaselineScheduleRequest(dataset_id=analytics_dataset.dataset_id, setup_time_seconds=120)
    )

    # Transition PASS-AN-01: SCHEDULED -> ACQUIRING -> TRANSMITTING -> COMPLETED
    await execution_service.transition_execution(
        pass_id="PASS-AN-01",
        request=PassTransitionRequest(
            to_status="ACQUIRING",
            timestamp=base_time,
            actual_start_time=base_time,
            is_simulated=True,
        ),
    )
    await execution_service.transition_execution(
        pass_id="PASS-AN-01",
        request=PassTransitionRequest(
            to_status="TRANSMITTING",
            timestamp=base_time + timedelta(minutes=1),
            is_simulated=True,
        ),
    )
    await execution_service.transition_execution(
        pass_id="PASS-AN-01",
        request=PassTransitionRequest(
            to_status="COMPLETED",
            timestamp=base_time + timedelta(minutes=10),
            actual_end_time=base_time + timedelta(minutes=10),
            actual_data_delivered_gb=20.0,
            is_simulated=True,
        ),
    )

    risk_summary = await analytics_service.get_deadline_risk_analysis(run_res.run_id)
    assert risk_summary.total_requests == 3
    assert risk_summary.low_risk_count >= 1

    pass1_risk = next(r for r in risk_summary.items if r.pass_id == "PASS-AN-01")
    assert pass1_risk.risk_level == RiskLevel.LOW
    assert "completed" in pass1_risk.explanation.lower()
    assert pass1_risk.analysis_method == "RULE_BASED_DETERMINISTIC"


@pytest.mark.asyncio
async def test_report_export_json_and_csv(
    db_session: AsyncSession,
    analytics_dataset,
):
    """Verify real report exports generate valid CSV with headers and JSON with metrics."""
    engine = RealSchedulerEngine()
    schedule_service = ScheduleService(db_session, engine)
    analytics_service = AnalyticsService(db_session)

    run_res = await schedule_service.execute_baseline(
        BaselineScheduleRequest(dataset_id=analytics_dataset.dataset_id, setup_time_seconds=120)
    )

    # 1. JSON Export
    json_export = await analytics_service.export_mission_report(run_res.run_id, export_format="json")
    assert isinstance(json_export, dict)
    assert "report_metadata" in json_export
    assert json_export["report_metadata"]["run_id"] == run_res.run_id
    assert "operational_analytics" in json_export
    assert "deadline_risk_analysis" in json_export

    # 2. CSV Export
    csv_export = await analytics_service.export_mission_report(run_res.run_id, export_format="csv")
    assert isinstance(csv_export, str)
    assert "# ORBITOPT MISSION EXECUTION REPORT" in csv_export
    assert "# OPERATIONAL KPIS & METRICS SUMMARY" in csv_export
    assert "# SCHEDULED PASS ALLOCATIONS & EXECUTION TELEMETRY" in csv_export
    assert "# DETERMINISTIC DEADLINE RISK REGISTER (RULE-BASED)" in csv_export
    assert "PASS-AN-01" in csv_export


@pytest.mark.asyncio
async def test_unknown_run_id_raises_not_found(
    db_session: AsyncSession,
):
    """Verify unknown run ID raises ResourceNotFoundError (HTTP 404)."""
    analytics_service = AnalyticsService(db_session)
    with pytest.raises(ResourceNotFoundError):
        await analytics_service.get_operational_analytics("run_non_existent_id")


@pytest.mark.asyncio
async def test_fcfs_vs_cpsat_benchmark_comparison(
    db_session: AsyncSession,
    analytics_dataset,
):
    """Verify benchmark comparison between FCFS and CP-SAT runs on identical dataset."""
    engine = RealSchedulerEngine()
    schedule_service = ScheduleService(db_session, engine)
    analytics_service = AnalyticsService(db_session)

    # 1. Run Baseline FCFS
    fcfs_run = await schedule_service.execute_baseline(
        BaselineScheduleRequest(dataset_id=analytics_dataset.dataset_id, setup_time_seconds=120)
    )

    # 2. Run CP-SAT Optimization on identical dataset
    cpsat_run = await schedule_service.execute_optimize(
        OptimizeScheduleRequest(dataset_id=analytics_dataset.dataset_id, time_limit_seconds=5)
    )

    # 3. Check benchmark comparison inside analytics
    analytics = await analytics_service.get_operational_analytics(cpsat_run.run_id)
    assert analytics.benchmark_comparison is not None
    comp = analytics.benchmark_comparison
    assert comp.baseline_run_id == fcfs_run.run_id
    assert comp.optimized_run_id == cpsat_run.run_id
    assert comp.baseline_volume_gb >= 0.0
    assert comp.optimized_volume_gb >= 0.0
    assert comp.runtime_ratio > 0.0
