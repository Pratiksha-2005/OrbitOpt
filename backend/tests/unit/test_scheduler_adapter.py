"""Integration tests for Scheduler Adapter boundary using deterministic fake engines."""

from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import SchedulingEngineError
from app.schemas.dataset import DatasetRead
from app.schemas.ground_station import GroundStationRead
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
from app.services.dataset_service import DatasetService
from app.services.schedule_service import ScheduleService
from app.services.scheduler_interface import BaseSchedulerEngine


@pytest.fixture
def sample_dataset_read() -> DatasetRead:
    return DatasetRead(
        dataset_id="ds_adapter_test",
        name="Adapter Test Scenario",
        ground_station_count=1,
        satellite_pass_count=2,
        created_at=datetime.now(timezone.utc),
        ground_stations=[
            GroundStationRead(
                station_id="GS-01",
                name="Station 1",
                latitude_deg=10.0,
                longitude_deg=20.0,
                elevation_mask_deg=5.0,
                max_concurrent_passes=1,
                supported_bands=["X-band"],
            )
        ],
        satellite_passes=[
            SatellitePassRead(
                pass_id="PASS-01",
                satellite_id="SAT-1",
                ground_station_id="GS-01",
                start_time=datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 10, 10, 8, 10, tzinfo=timezone.utc),
                max_elevation_deg=50.0,
                priority=1,
                data_volume_gb=40.0,
                pending_data_gb=40.0,
                effective_data_rate_mbps=100.0,
            ),
            SatellitePassRead(
                pass_id="PASS-02",
                satellite_id="SAT-2",
                ground_station_id="GS-01",
                start_time=datetime(2026, 10, 10, 8, 5, tzinfo=timezone.utc),
                end_time=datetime(2026, 10, 10, 8, 15, tzinfo=timezone.utc),
                max_elevation_deg=45.0,
                priority=2,
                data_volume_gb=30.0,
                pending_data_gb=30.0,
                effective_data_rate_mbps=100.0,
            ),
        ],
    )


class FakeTimeoutEngine(BaseSchedulerEngine):
    """Deterministic fake engine simulating a solver timeout."""

    async def schedule_baseline(self, dataset: DatasetRead, request: BaselineScheduleRequest) -> ScheduleRunResponse:
        return self._make_response(dataset.dataset_id, AlgorithmType.BASELINE_FCFS)

    async def schedule_optimize(self, dataset: DatasetRead, request: OptimizeScheduleRequest) -> ScheduleRunResponse:
        return self._make_response(dataset.dataset_id, AlgorithmType.CP_SAT_OPTIMIZER)

    def _make_response(self, dataset_id: str, algo: AlgorithmType) -> ScheduleRunResponse:
        return ScheduleRunResponse(
            run_id="run_fake_timeout",
            dataset_id=dataset_id,
            algorithm=algo,
            status=ScheduleStatus.TIMEOUT,
            is_mock=True,
            solver_status_detail="TIMEOUT",
            created_at=datetime.now(timezone.utc),
            execution_time_ms=30000.0,
            scheduled_passes=[],
            unassigned_passes=[],
            metrics=ScheduleMetrics(
                total_passes=2,
                scheduled_passes_count=0,
                unassigned_passes_count=2,
                scheduled_percentage=0.0,
                total_data_downlinked_gb=0.0,
                total_contact_time_seconds=0.0,
                objective_value=0.0,
                priority_satisfaction_rate=0.0,
            ),
        )


class FakeInfeasibleEngine(BaseSchedulerEngine):
    """Deterministic fake engine simulating an infeasible optimization model."""

    async def schedule_baseline(self, dataset: DatasetRead, request: BaselineScheduleRequest) -> ScheduleRunResponse:
        return self._make_response(dataset.dataset_id, AlgorithmType.BASELINE_FCFS)

    async def schedule_optimize(self, dataset: DatasetRead, request: OptimizeScheduleRequest) -> ScheduleRunResponse:
        return self._make_response(dataset.dataset_id, AlgorithmType.CP_SAT_OPTIMIZER)

    def _make_response(self, dataset_id: str, algo: AlgorithmType) -> ScheduleRunResponse:
        return ScheduleRunResponse(
            run_id="run_fake_infeasible",
            dataset_id=dataset_id,
            algorithm=algo,
            status=ScheduleStatus.INFEASIBLE,
            is_mock=True,
            solver_status_detail="INFEASIBLE",
            created_at=datetime.now(timezone.utc),
            execution_time_ms=12.5,
            scheduled_passes=[],
            unassigned_passes=[
                UnassignedPass(
                    pass_id="PASS-01",
                    satellite_id="SAT-1",
                    ground_station_id="GS-01",
                    start_time=datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc),
                    end_time=datetime(2026, 10, 10, 8, 10, tzinfo=timezone.utc),
                    priority=1,
                    reason="Model constraints unsatisfiable",
                )
            ],
            metrics=ScheduleMetrics(
                total_passes=2,
                scheduled_passes_count=0,
                unassigned_passes_count=1,
                scheduled_percentage=0.0,
                total_data_downlinked_gb=0.0,
                total_contact_time_seconds=0.0,
                objective_value=0.0,
                priority_satisfaction_rate=0.0,
            ),
        )


class FakeInvalidOutputEngine(BaseSchedulerEngine):
    """Deterministic fake engine returning schedule that failed independent validator."""

    async def schedule_baseline(self, dataset: DatasetRead, request: BaselineScheduleRequest) -> ScheduleRunResponse:
        return self._make_response(dataset.dataset_id, AlgorithmType.BASELINE_FCFS)

    async def schedule_optimize(self, dataset: DatasetRead, request: OptimizeScheduleRequest) -> ScheduleRunResponse:
        return self._make_response(dataset.dataset_id, AlgorithmType.CP_SAT_OPTIMIZER)

    def _make_response(self, dataset_id: str, algo: AlgorithmType) -> ScheduleRunResponse:
        return ScheduleRunResponse(
            run_id="run_fake_invalid",
            dataset_id=dataset_id,
            algorithm=algo,
            status=ScheduleStatus.COMPLETED,
            is_mock=True,
            is_valid=False,
            validation_violations=["Antenna overlap violation on GS-01: PASS-01 and PASS-02 overlap"],
            created_at=datetime.now(timezone.utc),
            execution_time_ms=25.0,
            scheduled_passes=[],
            unassigned_passes=[],
            metrics=ScheduleMetrics(
                total_passes=2,
                scheduled_passes_count=0,
                unassigned_passes_count=0,
                scheduled_percentage=0.0,
                total_data_downlinked_gb=0.0,
                total_contact_time_seconds=0.0,
                objective_value=0.0,
                priority_satisfaction_rate=0.0,
            ),
        )


@pytest.mark.asyncio
async def test_adapter_handles_solver_timeout(
    db_session: AsyncSession,
    sample_dataset_payload: dict,
) -> None:
    """Verify ScheduleService persists and returns TIMEOUT status accurately."""
    ds_svc = DatasetService(db_session)
    dataset = await ds_svc.create_dataset(
        type("DatasetCreateFromPayload", (), {"model_validate": lambda x: x})()
    ) if False else None  # We'll create via DatasetCreate schema

    from app.schemas.dataset import DatasetCreate
    created = await ds_svc.create_dataset(DatasetCreate.model_validate(sample_dataset_payload))

    service = ScheduleService(db=db_session, scheduler_engine=FakeTimeoutEngine())
    res = await service.execute_optimize(
        OptimizeScheduleRequest(dataset_id=created.dataset_id, time_limit_seconds=30.0)
    )

    assert res.status == ScheduleStatus.TIMEOUT
    assert res.solver_status_detail == "TIMEOUT"
    assert res.is_mock is True

    # Check retrieval from DB
    persisted = await service.get_schedule_run(res.run_id)
    assert persisted.status == ScheduleStatus.TIMEOUT
    assert persisted.solver_status_detail == "TIMEOUT"


@pytest.mark.asyncio
async def test_adapter_handles_solver_infeasible(
    db_session: AsyncSession,
    sample_dataset_payload: dict,
) -> None:
    """Verify ScheduleService persists and returns INFEASIBLE status accurately."""
    from app.schemas.dataset import DatasetCreate
    ds_svc = DatasetService(db_session)
    created = await ds_svc.create_dataset(DatasetCreate.model_validate(sample_dataset_payload))

    service = ScheduleService(db=db_session, scheduler_engine=FakeInfeasibleEngine())
    res = await service.execute_optimize(
        OptimizeScheduleRequest(dataset_id=created.dataset_id, time_limit_seconds=10.0)
    )

    assert res.status == ScheduleStatus.INFEASIBLE
    assert res.solver_status_detail == "INFEASIBLE"
    assert len(res.unassigned_passes) == 1
    assert "unsatisfiable" in res.unassigned_passes[0].reason


@pytest.mark.asyncio
async def test_adapter_handles_validation_violations(
    db_session: AsyncSession,
    sample_dataset_payload: dict,
) -> None:
    """Verify ScheduleService preserves validation violations from independent validator."""
    from app.schemas.dataset import DatasetCreate
    ds_svc = DatasetService(db_session)
    created = await ds_svc.create_dataset(DatasetCreate.model_validate(sample_dataset_payload))

    service = ScheduleService(db=db_session, scheduler_engine=FakeInvalidOutputEngine())
    res = await service.execute_baseline(
        BaselineScheduleRequest(dataset_id=created.dataset_id, setup_time_seconds=120)
    )

    assert res.is_valid is False
    assert len(res.validation_violations) == 1
    assert "Antenna overlap" in res.validation_violations[0]

    persisted = await service.get_schedule_run(res.run_id)
    assert persisted.is_valid is False
    assert len(persisted.validation_violations) == 1
