"""Unit tests for Sprint 3 Pass Execution Lifecycle, State Machine, Locking, and Telemetry."""

import pytest
from datetime import datetime, timezone, timedelta

from app.core.errors import InvalidStateTransitionError, ResourceNotFoundError
from app.db.models.execution import PassExecutionModel
from app.schemas.dataset import DatasetCreate, DatasetRead
from app.schemas.execution import (

    PassExecutionStatus,
    PassTransitionRequest,
    is_legal_transition,
    is_status_locked,
)
from app.schemas.schedule import (
    OptimizeScheduleRequest,
    ScheduledPass,
    ScheduleRunResponse,
    ScheduleStatus,
)
from app.services.dataset_service import DatasetService
from app.services.execution_service import ExecutionService
from app.services.scheduler.models import TimeWindow
from app.services.scheduler.real_engine import RealSchedulerEngine


@pytest.mark.asyncio
class TestPassExecutionLifecycle:
    """Tests for Pass Execution State Machine, Telemetry, and Transition validation."""

    async def test_legal_state_machine_transitions(self, db_session):
        """Verify normal operational lifecycle: SCHEDULED -> ACQUIRING -> TRANSMITTING -> COMPLETED."""
        service = ExecutionService(db_session)
        now = datetime.now(timezone.utc)

        # Seed an initial scheduled pass execution record
        pass_model = PassExecutionModel(
            pass_id="PASS-TEST-001",
            dataset_id="ds_test",
            schedule_run_id="run_test",
            satellite_id="SAT-1",
            ground_station_id="GS-SVALBARD",
            status=PassExecutionStatus.SCHEDULED.value,
            is_locked=False,
            planned_start_time=now,
            planned_end_time=now + timedelta(minutes=10),
            planned_data_volume_gb=50.0,
            estimated_transfer_rate_mbps=400.0,
            telemetry_source="simulated",
            transition_history=[],
        )
        db_session.add(pass_model)
        await db_session.commit()

        # Step 1: SCHEDULED -> ACQUIRING
        req1 = PassTransitionRequest(
            to_status=PassExecutionStatus.ACQUIRING,
            timestamp=now,
            actual_start_time=now,
            telemetry_source="operator_manual",
            notes="Acquisition commenced on Azimuth 120",
        )
        p1 = await service.transition_execution("PASS-TEST-001", req1)
        assert p1.status == PassExecutionStatus.ACQUIRING
        assert p1.is_locked is True
        assert p1.actual_start_time is not None
        assert len(p1.transition_history) == 1

        # Step 2: ACQUIRING -> TRANSMITTING
        req2 = PassTransitionRequest(
            to_status=PassExecutionStatus.TRANSMITTING,
            timestamp=now + timedelta(minutes=1),
            telemetry_source="operator_manual",
            notes="Carrier locked; downlink transfer active",
        )
        p2 = await service.transition_execution("PASS-TEST-001", req2)
        assert p2.status == PassExecutionStatus.TRANSMITTING
        assert p2.is_locked is True
        assert len(p2.transition_history) == 2

        # Step 3: TRANSMITTING -> COMPLETED (with telemetry measurements)
        end_time = now + timedelta(minutes=9)
        req3 = PassTransitionRequest(
            to_status=PassExecutionStatus.COMPLETED,
            timestamp=end_time,
            actual_end_time=end_time,
            actual_data_delivered_gb=48.2,
            measured_transfer_rate_mbps=395.0,
            telemetry_source="operator_manual",
            notes="Pass downlink completed nominal",
        )
        p3 = await service.transition_execution("PASS-TEST-001", req3)
        assert p3.status == PassExecutionStatus.COMPLETED
        assert p3.is_locked is True
        assert p3.actual_data_delivered_gb == 48.2
        assert p3.planned_data_volume_gb == 50.0  # Planned distinct from actual
        assert p3.measured_transfer_rate_mbps == 395.0
        assert p3.estimated_transfer_rate_mbps == 400.0
        assert len(p3.transition_history) == 3

    async def test_illegal_state_transitions_rejected(self, db_session):
        """Verify invalid jumps and terminal state transitions are strictly rejected."""
        service = ExecutionService(db_session)
        now = datetime.now(timezone.utc)

        pass_model = PassExecutionModel(
            pass_id="PASS-TEST-ILLEGAL",
            dataset_id="ds_test",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            status=PassExecutionStatus.SCHEDULED.value,
            is_locked=False,
            planned_start_time=now,
            planned_end_time=now + timedelta(minutes=10),
            planned_data_volume_gb=30.0,
            estimated_transfer_rate_mbps=150.0,
        )
        db_session.add(pass_model)
        await db_session.commit()

        # Cannot jump SCHEDULED -> COMPLETED without acquiring/transmitting
        with pytest.raises(InvalidStateTransitionError) as exc_info:
            await service.transition_execution(
                "PASS-TEST-ILLEGAL",
                PassTransitionRequest(to_status=PassExecutionStatus.COMPLETED),
            )
        assert "Illegal state transition" in exc_info.value.message

        # Legal transition to CANCELLED
        await service.transition_execution(
            "PASS-TEST-ILLEGAL",
            PassTransitionRequest(to_status=PassExecutionStatus.CANCELLED, notes="Cancelled by operator"),
        )

        # Cannot transition out of CANCELLED (terminal state)
        with pytest.raises(InvalidStateTransitionError):
            await service.transition_execution(
                "PASS-TEST-ILLEGAL",
                PassTransitionRequest(to_status=PassExecutionStatus.ACQUIRING),
            )

    async def test_duplicate_transition_rejected(self, db_session):
        """Verify duplicate updates to the current state are rejected."""
        service = ExecutionService(db_session)
        now = datetime.now(timezone.utc)

        pass_model = PassExecutionModel(
            pass_id="PASS-TEST-DUP",
            dataset_id="ds_test",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            status=PassExecutionStatus.SCHEDULED.value,
            is_locked=False,
            planned_start_time=now,
            planned_end_time=now + timedelta(minutes=10),
            planned_data_volume_gb=30.0,
            estimated_transfer_rate_mbps=150.0,
        )
        db_session.add(pass_model)
        await db_session.commit()

        # Duplicate transition to SCHEDULED
        with pytest.raises(InvalidStateTransitionError) as exc:
            await service.transition_execution(
                "PASS-TEST-DUP",
                PassTransitionRequest(to_status=PassExecutionStatus.SCHEDULED),
            )
        assert "Duplicate execution update" in exc.value.message

    async def test_invalid_timestamp_ordering_rejected(self, db_session):
        """Verify actual_end_time cannot be earlier than actual_start_time."""
        service = ExecutionService(db_session)
        now = datetime.now(timezone.utc)

        pass_model = PassExecutionModel(
            pass_id="PASS-TEST-TIME",
            dataset_id="ds_test",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            status=PassExecutionStatus.TRANSMITTING.value,
            is_locked=True,
            planned_start_time=now,
            planned_end_time=now + timedelta(minutes=10),
            planned_data_volume_gb=30.0,
            estimated_transfer_rate_mbps=150.0,
            actual_start_time=now + timedelta(minutes=5),
        )
        db_session.add(pass_model)
        await db_session.commit()

        # End time before start time
        with pytest.raises(InvalidStateTransitionError) as exc:
            await service.transition_execution(
                "PASS-TEST-TIME",
                PassTransitionRequest(
                    to_status=PassExecutionStatus.COMPLETED,
                    actual_end_time=now + timedelta(minutes=2),  # Before start time (now + 5min)
                ),
            )
        assert "actual_end_time" in exc.value.message and "cannot be earlier" in exc.value.message

    async def test_missed_and_cancelled_not_locked_and_not_successful(self, db_session):
        """MISSED and CANCELLED passes must not be locked and must not count as successful transmissions."""
        service = ExecutionService(db_session)
        now = datetime.now(timezone.utc)

        pass_model = PassExecutionModel(
            pass_id="PASS-TEST-MISSED",
            dataset_id="ds_test",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            status=PassExecutionStatus.SCHEDULED.value,
            is_locked=False,
            planned_start_time=now,
            planned_end_time=now + timedelta(minutes=10),
            planned_data_volume_gb=25.0,
            estimated_transfer_rate_mbps=150.0,
        )
        db_session.add(pass_model)
        await db_session.commit()

        res = await service.transition_execution(
            "PASS-TEST-MISSED",
            PassTransitionRequest(to_status=PassExecutionStatus.MISSED, notes="LOS before acquisition"),
        )
        assert res.status == PassExecutionStatus.MISSED
        assert res.is_locked is False

        locked_ids = await service.get_locked_pass_ids(dataset_id="ds_test")
        assert "PASS-TEST-MISSED" not in locked_ids

    async def test_unknown_execution_state_handled_safely(self, db_session):
        """Passes with unknown state are NOT locked merely because planned start is in the past."""
        service = ExecutionService(db_session)
        # Pass not in execution DB
        locked_ids = await service.get_locked_pass_ids(dataset_id="ds_unknown")
        assert len(locked_ids) == 0

    async def test_locked_active_pass_preserved_in_safe_reoptimize(self, db_session, sample_dataset_payload):
        """Active/transmitting pass must remain locked during re-optimization while scheduled future passes can be reconsidered."""
        ds_service = DatasetService(db_session)
        dataset = await ds_service.create_dataset(DatasetCreate(**sample_dataset_payload))
        dataset_read = await ds_service.get_dataset(dataset.dataset_id)

        engine = RealSchedulerEngine()
        exec_service = ExecutionService(db_session)

        # Run initial optimization
        req = OptimizeScheduleRequest(dataset_id=dataset.dataset_id, time_limit_seconds=10.0)
        initial_run = await engine.schedule_optimize(dataset_read, req)
        assert initial_run.is_valid is True
        assert len(initial_run.scheduled_passes) > 0

        # Mark first pass as ACQUIRING
        active_pass_id = initial_run.scheduled_passes[0].pass_id
        await exec_service.sync_executions_from_run(initial_run)
        await exec_service.transition_execution(
            active_pass_id,
            PassTransitionRequest(
                to_status=PassExecutionStatus.ACQUIRING,
                notes="Pass is actively tracking antenna",
            ),
        )

        locked_ids = await exec_service.get_locked_pass_ids(dataset.dataset_id)
        assert active_pass_id in locked_ids

        # Trigger safe re-optimization with locked_pass_ids
        reopt_run = await engine.safe_reoptimize(
            dataset=dataset_read,
            request=req,
            previous_schedule=initial_run,
            locked_pass_ids=locked_ids,
        )

        assert reopt_run.is_valid is True
        reopt_pass_ids = {sp.pass_id for sp in reopt_run.scheduled_passes}
        # The locked active pass MUST remain scheduled
        assert active_pass_id in reopt_pass_ids

    async def test_failed_reoptimization_preserves_previous_valid_schedule(self, sample_dataset_payload, db_session):
        """When re-optimization fails due to infeasibility, the previous valid schedule is preserved."""
        ds_service = DatasetService(db_session)
        dataset = await ds_service.create_dataset(DatasetCreate(**sample_dataset_payload))
        dataset_read = await ds_service.get_dataset(dataset.dataset_id)


        engine = RealSchedulerEngine()
        req = OptimizeScheduleRequest(dataset_id=dataset.dataset_id, time_limit_seconds=5.0)
        initial_run = await engine.schedule_optimize(dataset_read, req)
        assert initial_run.is_valid is True

        locked_pass = initial_run.scheduled_passes[0]
        # Simulate a conflicting outage on the ground station that directly collides with the locked pass
        outage_window = TimeWindow(
            start_time=locked_pass.start_time,
            end_time=locked_pass.end_time,
        )
        outages = {locked_pass.ground_station_id: [outage_window]}

        # safe_reoptimize with locked pass and colliding outage
        fallback_run = await engine.safe_reoptimize(
            dataset=dataset_read,
            request=req,
            previous_schedule=initial_run,
            locked_pass_ids=[locked_pass.pass_id],
            outages_by_station=outages,
        )

        # Fallback preserves previous valid schedule
        assert fallback_run.is_valid is True
        assert fallback_run.run_id == initial_run.run_id
        assert len(fallback_run.scheduled_passes) == len(initial_run.scheduled_passes)
        assert any("preserved" in v.lower() for v in fallback_run.validation_violations)
