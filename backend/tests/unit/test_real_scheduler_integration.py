"""Integration tests verifying Developer 1's real FCFS and CP-SAT Scheduler Engine."""

from datetime import datetime, timezone
import pytest

from app.schemas.dataset import DatasetRead
from app.schemas.ground_station import GroundStationRead
from app.schemas.satellite_pass import SatellitePassRead
from app.schemas.schedule import (
    AlgorithmType,
    BaselineScheduleRequest,
    OptimizeScheduleRequest,
    ScheduleStatus,
)
from app.services.scheduler.real_engine import RealSchedulerEngine
from app.services.scheduler.validator import ScheduleValidator
from app.services.scheduler.models import (
    GroundStation,
    Satellite,
    VisibilityWindow,
    DownlinkRequest,
    ScheduledTask,
    Priority,
)


@pytest.fixture
def deterministic_conflict_dataset() -> DatasetRead:
    """Deterministic dataset where 2 passes conflict over 1 ground station:
    Pass 1: High Priority (1), SAT-1, GS-01, 08:00 - 08:10 (600s), 100 Mbps, 5.0 GB -> 400s contact needed
    Pass 2: Low Priority (5), SAT-2, GS-01, 08:00 - 08:10 (600s), 100 Mbps, 5.0 GB -> 400s contact needed (conflicts on GS-01)
    Pass 3: Independent SAT-3, GS-02, 08:00 - 08:10 (600s), 100 Mbps, 3.0 GB -> 240s contact needed
    """
    t0 = datetime(2026, 10, 10, 8, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 10, 8, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 10, 8, 5, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 10, 10, 8, 15, 0, tzinfo=timezone.utc)

    return DatasetRead(
        dataset_id="ds_real_test",
        name="Real Scheduler Deterministic Test",
        ground_station_count=2,
        satellite_pass_count=3,
        created_at=datetime.now(timezone.utc),
        ground_stations=[
            GroundStationRead(
                station_id="GS-01",
                name="Station Alpha",
                latitude_deg=10.0,
                longitude_deg=20.0,
                elevation_mask_deg=5.0,
                max_concurrent_passes=1,
                supported_bands=["X-band"],
            ),
            GroundStationRead(
                station_id="GS-02",
                name="Station Beta",
                latitude_deg=30.0,
                longitude_deg=40.0,
                elevation_mask_deg=5.0,
                max_concurrent_passes=1,
                supported_bands=["X-band"],
            ),
        ],
        satellite_passes=[
            SatellitePassRead(
                pass_id="PASS-CONF-1",
                satellite_id="SAT-1",
                ground_station_id="GS-01",
                start_time=t0,
                end_time=t1,
                max_elevation_deg=65.0,
                priority=1,
                data_volume_gb=5.0,
                pending_data_gb=5.0,
                effective_data_rate_mbps=100.0,
            ),
            SatellitePassRead(
                pass_id="PASS-CONF-2",
                satellite_id="SAT-2",
                ground_station_id="GS-01",
                start_time=t0,
                end_time=t1,
                max_elevation_deg=45.0,
                priority=5,
                data_volume_gb=5.0,
                pending_data_gb=5.0,
                effective_data_rate_mbps=100.0,
            ),
            SatellitePassRead(
                pass_id="PASS-INDEP-3",
                satellite_id="SAT-3",
                ground_station_id="GS-02",
                start_time=t0,
                end_time=t1,
                max_elevation_deg=70.0,
                priority=2,
                data_volume_gb=3.0,
                pending_data_gb=3.0,
                effective_data_rate_mbps=100.0,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_real_fcfs_engine_execution(deterministic_conflict_dataset: DatasetRead) -> None:
    """Verify RealSchedulerEngine executes Developer 1's real FCFS algorithm."""
    engine = RealSchedulerEngine()
    req = BaselineScheduleRequest(dataset_id="ds_real_test", setup_time_seconds=60)

    res = await engine.schedule_baseline(deterministic_conflict_dataset, req)

    # 1. Output flags & algorithm
    assert res.algorithm == AlgorithmType.BASELINE_FCFS
    assert res.status == ScheduleStatus.COMPLETED
    assert res.is_mock is False  # MUST be False for real engine
    assert res.is_valid is True  # Developer 1 validator ran and verified no conflicts
    assert len(res.validation_violations) == 0
    assert res.solver_status_detail in ("FEASIBLE", "OPTIMAL")
    assert res.execution_time_ms >= 0.0

    # 2. Scheduling logic: PASS-CONF-1 starts at 08:00 and takes 400s (ends 08:06:40),
    # so PASS-CONF-2 starting at 08:05 cannot fit on GS-01 and is rejected.
    # PASS-INDEP-3 on GS-02 is scheduled without conflict.
    sched_ids = {p.pass_id for p in res.scheduled_passes}
    unassigned_ids = {p.pass_id for p in res.unassigned_passes}

    assert "PASS-CONF-1" in sched_ids
    assert "PASS-INDEP-3" in sched_ids
    assert "PASS-CONF-2" in unassigned_ids
    assert len(res.scheduled_passes) == 2
    assert len(res.unassigned_passes) == 1

    # 3. Metrics verification
    assert res.metrics.total_passes == 3
    assert res.metrics.scheduled_passes_count == 2
    assert res.metrics.unassigned_passes_count == 1
    assert res.metrics.total_data_downlinked_gb == 8.0  # 5.0 + 3.0
    # Objective = 10.0 * 5.0 + 5.0 * 3.0 = 50.0 + 15.0 = 65.0
    assert res.metrics.objective_value == 65.0


@pytest.mark.asyncio
async def test_real_cpsat_engine_execution(deterministic_conflict_dataset: DatasetRead) -> None:
    """Verify RealSchedulerEngine executes Developer 1's real OR-Tools CP-SAT optimizer."""
    engine = RealSchedulerEngine()
    req = OptimizeScheduleRequest(
        dataset_id="ds_real_test",
        time_limit_seconds=10.0,
        priority_weights={"1": 10.0, "2": 5.0, "5": 0.5},
    )

    res = await engine.schedule_optimize(deterministic_conflict_dataset, req)

    # 1. Output flags & algorithm
    assert res.algorithm == AlgorithmType.CP_SAT_OPTIMIZER
    assert res.status == ScheduleStatus.COMPLETED
    assert res.is_mock is False
    assert res.is_valid is True
    assert len(res.validation_violations) == 0
    assert res.solver_status_detail in ("OPTIMAL", "FEASIBLE")

    # 2. CP-SAT must choose the higher priority pass (PASS-CONF-1 with prio 1 over PASS-CONF-2 with prio 5)
    sched_ids = {p.pass_id for p in res.scheduled_passes}
    unassigned_ids = {p.pass_id for p in res.unassigned_passes}

    assert "PASS-CONF-1" in sched_ids
    assert "PASS-INDEP-3" in sched_ids
    assert "PASS-CONF-2" in unassigned_ids
    assert len(res.scheduled_passes) == 2
    assert len(res.unassigned_passes) == 1
    assert res.metrics.objective_value == 65.0


def test_independent_validator_detects_overlaps() -> None:
    """Verify Developer 1's ScheduleValidator catches overlapping ground station allocations."""
    sat = Satellite(id="SAT-1", name="Sat 1")
    gs = GroundStation(id="GS-01", name="Station 1", downlink_rate_mbps=100.0)
    w1 = VisibilityWindow(
        id="W-1",
        satellite_id="SAT-1",
        ground_station_id="GS-01",
        start_time=datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 10, 8, 30, tzinfo=timezone.utc),
    )
    req1 = DownlinkRequest(id="R-1", satellite_id="SAT-1", data_volume_mb=1000.0, priority=Priority.HIGH)
    req2 = DownlinkRequest(id="R-2", satellite_id="SAT-1", data_volume_mb=1000.0, priority=Priority.HIGH)

    # Overlapping tasks on the same GS-01
    t1 = ScheduledTask(
        id="T-1",
        request_id="R-1",
        visibility_window_id="W-1",
        start_time=datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 10, 8, 10, tzinfo=timezone.utc),
        data_transmitted_mb=1000.0,
    )
    t2 = ScheduledTask(
        id="T-2",
        request_id="R-2",
        visibility_window_id="W-1",
        start_time=datetime(2026, 10, 10, 8, 5, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 10, 8, 15, tzinfo=timezone.utc),
        data_transmitted_mb=1000.0,
    )

    validator = ScheduleValidator([sat], [gs], [w1], [req1, req2])
    errors = validator.validate([t1, t2])

    assert len(errors) > 0
    assert any("overlap" in e.lower() for e in errors)


@pytest.mark.asyncio
async def test_fcfs_and_cpsat_independent_execution_under_priority_contention() -> None:
    """Regression test: verify FCFS and CP-SAT run completely independently on a contention dataset.
    
    Setup:
      Pass A: 08:00 - 08:10, GS-01, Priority 5 (Low), Data Volume: 10 GB (400s contact)
      Pass B: 08:04 - 08:14, GS-01, Priority 1 (Critical), Data Volume: 30 GB (400s contact)
      Both compete for the single channel on GS-01.
      
    Expected Behavior:
      - FCFS schedules Pass A (arrives first at 08:00), rejecting Pass B -> Throughput = 10 GB, Obj = 5.0.
      - CP-SAT schedules Pass B (Priority 1 + higher volume), rejecting Pass A -> Throughput = 30 GB, Obj = 300.0.
      - Both solutions are verified feasible and free of constraint violations by ScheduleValidator.
    """
    t_a_start = datetime(2026, 10, 10, 8, 0, 0, tzinfo=timezone.utc)
    t_a_end = datetime(2026, 10, 10, 8, 10, 0, tzinfo=timezone.utc)
    t_b_start = datetime(2026, 10, 10, 8, 4, 0, tzinfo=timezone.utc)
    t_b_end = datetime(2026, 10, 10, 8, 14, 0, tzinfo=timezone.utc)

    dataset = DatasetRead(
        dataset_id="ds_contention_benchmark",
        name="Contention Priority Inversion Benchmark",
        ground_station_count=1,
        satellite_pass_count=2,
        created_at=datetime.now(timezone.utc),
        ground_stations=[
            GroundStationRead(
                station_id="GS-01",
                name="Svalbard Polar Station",
                latitude_deg=78.22,
                longitude_deg=15.65,
                elevation_mask_deg=5.0,
                max_concurrent_passes=1,
                supported_bands=["X-band"],
            ),
        ],
        satellite_passes=[
            SatellitePassRead(
                pass_id="PASS-EARLY-LOWPRIO",
                satellite_id="SAT-LOW",
                ground_station_id="GS-01",
                start_time=t_a_start,
                end_time=t_a_end,
                max_elevation_deg=55.0,
                priority=5,
                data_volume_gb=10.0,
                pending_data_gb=10.0,
                effective_data_rate_mbps=200.0,
            ),
            SatellitePassRead(
                pass_id="PASS-LATER-HIGHPRIO",
                satellite_id="SAT-HIGH",
                ground_station_id="GS-01",
                start_time=t_b_start,
                end_time=t_b_end,
                max_elevation_deg=75.0,
                priority=1,
                data_volume_gb=30.0,
                pending_data_gb=30.0,
                effective_data_rate_mbps=200.0,
            ),
        ],
    )

    engine = RealSchedulerEngine()

    # 1. Run FCFS
    fcfs_req = BaselineScheduleRequest(dataset_id="ds_contention_benchmark", setup_time_seconds=60)
    fcfs_res = await engine.schedule_baseline(dataset, fcfs_req)

    # 2. Run CP-SAT
    cpsat_req = OptimizeScheduleRequest(
        dataset_id="ds_contention_benchmark",
        time_limit_seconds=5.0,
        priority_weights={"1": 10.0, "2": 5.0, "3": 2.0, "4": 1.0, "5": 0.5},
    )
    cpsat_res = await engine.schedule_optimize(dataset, cpsat_req)

    # 3. Verify validity & real solver execution
    assert fcfs_res.is_mock is False
    assert cpsat_res.is_mock is False
    assert fcfs_res.is_valid is True
    assert cpsat_res.is_valid is True
    assert len(fcfs_res.validation_violations) == 0
    assert len(cpsat_res.validation_violations) == 0

    # 4. Verify FCFS chose early low-priority pass
    fcfs_sched_ids = {p.pass_id for p in fcfs_res.scheduled_passes}
    assert "PASS-EARLY-LOWPRIO" in fcfs_sched_ids
    assert "PASS-LATER-HIGHPRIO" not in fcfs_sched_ids
    assert fcfs_res.metrics.total_data_downlinked_gb == 10.0
    assert fcfs_res.metrics.objective_value == 5.0  # 0.5 * 10.0

    # 5. Verify CP-SAT chose higher-priority larger volume pass
    cpsat_sched_ids = {p.pass_id for p in cpsat_res.scheduled_passes}
    assert "PASS-LATER-HIGHPRIO" in cpsat_sched_ids
    assert "PASS-EARLY-LOWPRIO" not in cpsat_sched_ids
    # 600s duration at 200 Mbps transfers min(30.0, 15.0) = 15.0 GB
    assert cpsat_res.metrics.total_data_downlinked_gb == 15.0
    assert cpsat_res.metrics.objective_value == 150.0  # 10.0 * 15.0

    # 6. Verify CP-SAT strictly outperforms FCFS under contention
    assert cpsat_res.metrics.objective_value > fcfs_res.metrics.objective_value
    assert cpsat_res.metrics.total_data_downlinked_gb > fcfs_res.metrics.total_data_downlinked_gb


@pytest.mark.asyncio
async def test_global_4station_priority_contention_benchmark() -> None:
    """Verify seeded 4-station Priority Contention Benchmark yields authentic CP-SAT throughput and objective gain."""
    from app.db.seeder import get_standard_scenarios
    from app.services.dataset_service import DatasetService

    scenarios = get_standard_scenarios()
    contention_scen_create = next(s for s in scenarios if s.dataset_id == "ds_priority_contention_benchmark")
    
    # Construct DatasetRead model
    dataset = DatasetRead(
        dataset_id=contention_scen_create.dataset_id,
        name=contention_scen_create.name,
        description=contention_scen_create.description,
        ground_station_count=len(contention_scen_create.ground_stations),
        satellite_pass_count=len(contention_scen_create.satellite_passes),
        created_at=datetime.now(timezone.utc),
        ground_stations=[
            GroundStationRead(
                station_id=gs.station_id,
                name=gs.name,
                latitude_deg=gs.latitude_deg,
                longitude_deg=gs.longitude_deg,
                elevation_mask_deg=gs.elevation_mask_deg,
                max_concurrent_passes=gs.max_concurrent_passes,
                supported_bands=gs.supported_bands,
            )
            for gs in contention_scen_create.ground_stations
        ],
        satellite_passes=[
            SatellitePassRead(
                pass_id=p.pass_id,
                satellite_id=p.satellite_id,
                ground_station_id=p.ground_station_id,
                start_time=p.start_time,
                end_time=p.end_time,
                max_elevation_deg=p.max_elevation_deg,
                priority=p.priority,
                data_volume_gb=p.data_volume_gb,
                pending_data_gb=p.data_volume_gb,
                effective_data_rate_mbps=p.required_bandwidth_mbps,
                required_bandwidth_mbps=p.required_bandwidth_mbps,
                channel_band=p.channel_band,
            )
            for p in contention_scen_create.satellite_passes
        ],
    )

    engine = RealSchedulerEngine()
    fcfs_res = await engine.schedule_baseline(dataset, BaselineScheduleRequest(dataset_id="ds_priority_contention_benchmark", setup_time_seconds=60))
    cpsat_res = await engine.schedule_optimize(dataset, OptimizeScheduleRequest(dataset_id="ds_priority_contention_benchmark", time_limit_seconds=10.0))

    # Real engine & validity checks
    assert fcfs_res.is_mock is False
    assert cpsat_res.is_mock is False
    assert fcfs_res.is_valid is True
    assert cpsat_res.is_valid is True
    assert len(fcfs_res.validation_violations) == 0
    assert len(cpsat_res.validation_violations) == 0

    # CP-SAT scheduled Critical P1 and High P2 passes that FCFS rejected
    fcfs_sched = {p.pass_id for p in fcfs_res.scheduled_passes}
    cpsat_sched = {p.pass_id for p in cpsat_res.scheduled_passes}

    assert "PASS-EARTHOBS-001" in cpsat_sched
    assert "PASS-WEATHER-001" in cpsat_sched
    assert "PASS-EARTHOBS-001" not in fcfs_sched
    assert "PASS-WEATHER-001" not in fcfs_sched

    # Exact metrics verification
    assert cpsat_res.metrics.total_data_downlinked_gb == 155.0
    assert fcfs_res.metrics.total_data_downlinked_gb == 140.0
    assert cpsat_res.metrics.objective_value == 1042.5
    assert fcfs_res.metrics.objective_value == 727.5

    # Positive Optimization Gains
    assert cpsat_res.metrics.total_data_downlinked_gb > fcfs_res.metrics.total_data_downlinked_gb
    assert cpsat_res.metrics.objective_value > fcfs_res.metrics.objective_value
    assert cpsat_res.metrics.priority_satisfaction_rate > fcfs_res.metrics.priority_satisfaction_rate


