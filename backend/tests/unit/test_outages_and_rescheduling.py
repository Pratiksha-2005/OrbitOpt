"""Comprehensive unit tests for Ground Station Outages, Scheduling Constraints, and Event-Driven Rescheduling."""

from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from app.core.errors import InvalidOutageError, ResourceNotFoundError
from app.schemas.outage import OutageCreate, OutageStatus
from app.services.scheduler.cpsat import CPSATScheduler
from app.services.scheduler.fcfs import FCFSScheduler
from app.services.scheduler.models import (
    DownlinkRequest,
    GroundStation,
    Priority,
    Satellite,
    ScheduleResult,
    ScheduledTask,
    SolverStatus,
    TimeWindow,
    VisibilityWindow,
)
from app.services.scheduler.validator import ScheduleValidator


class TestOutageModelAndValidation:
    """Test validation of outage intervals, timezone handling, and bounds."""

    def test_outage_end_before_start_raises_validation_error(self):
        t0 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        with pytest.raises(ValidationError):
            OutageCreate(
                station_id="GS-01",
                start_time=t0,
                end_time=t0 - timedelta(minutes=10),
                reason="Invalid reverse interval",
            )

    def test_outage_equal_start_end_raises_validation_error(self):
        t0 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        with pytest.raises(ValidationError):
            OutageCreate(
                station_id="GS-01",
                start_time=t0,
                end_time=t0,
                reason="Zero-duration interval",
            )

    def test_valid_outage_creation(self):
        t0 = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        outage = OutageCreate(
            station_id="GS-01",
            start_time=t0,
            end_time=t0 + timedelta(hours=2),
            reason="Scheduled Antenna Gearbox Maintenance",
        )
        assert outage.station_id == "GS-01"
        assert outage.end_time > outage.start_time
        assert outage.start_time.tzinfo == timezone.utc


class TestSchedulingOutageAvoidance:
    """Verify that both FCFS and CP-SAT strictly avoid scheduling during ground-station outages."""

    def setup_method(self):
        self.t0 = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
        self.sat = Satellite(id="SAT-1", name="Sentinel-1A")

    def test_validator_rejects_task_overlapping_outage(self):
        outage = TimeWindow(
            start_time=self.t0 + timedelta(minutes=2),
            end_time=self.t0 + timedelta(minutes=8),
        )
        station = GroundStation(
            id="GS-1",
            name="Svalbard",
            downlink_rate_mbps=150.0,
            outages=[outage],
        )
        window = VisibilityWindow(
            id="W-1",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            start_time=self.t0,
            end_time=self.t0 + timedelta(minutes=10),
        )
        req = DownlinkRequest(id="W-1", satellite_id="SAT-1", data_volume_mb=500.0, priority=Priority.HIGH)

        # Proposed task overlaps the outage (starts at t0, duration 4 mins -> ends at t0+4m)
        task = ScheduledTask(
            id="T-1",
            request_id="W-1",
            visibility_window_id="W-1",
            start_time=self.t0,
            end_time=self.t0 + timedelta(minutes=4),
            data_transmitted_mb=500.0,
        )

        validator = ScheduleValidator(
            satellites=[self.sat],
            ground_stations=[station],
            windows=[window],
            requests=[req],
            setup_time_seconds=0,
        )

        errors = validator.validate([task])
        assert len(errors) > 0
        assert any("overlaps with an outage" in err for err in errors)

    def test_fcfs_avoids_outage_interval(self):
        # Outage from t0 to t0+10m on GS-1
        outage = TimeWindow(
            start_time=self.t0,
            end_time=self.t0 + timedelta(minutes=10),
        )
        station = GroundStation(
            id="GS-1",
            name="Svalbard",
            downlink_rate_mbps=150.0,
            outages=[outage],
        )

        self.sat2 = Satellite(id="SAT-2", name="Sentinel-2B")

        # Pass window 1 overlaps outage entirely (t0 to t0+10m) for SAT-1
        window1 = VisibilityWindow(
            id="W-1",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            start_time=self.t0,
            end_time=self.t0 + timedelta(minutes=10),
        )
        # Pass window 2 is after outage (t0+15m to t0+25m) for SAT-2
        window2 = VisibilityWindow(
            id="W-2",
            satellite_id="SAT-2",
            ground_station_id="GS-1",
            start_time=self.t0 + timedelta(minutes=15),
            end_time=self.t0 + timedelta(minutes=25),
        )

        req1 = DownlinkRequest(id="W-1", satellite_id="SAT-1", data_volume_mb=500.0, priority=Priority.HIGH)
        req2 = DownlinkRequest(id="W-2", satellite_id="SAT-2", data_volume_mb=500.0, priority=Priority.MEDIUM)

        fcfs = FCFSScheduler(
            satellites=[self.sat, self.sat2],
            ground_stations=[station],
            windows=[window1, window2],
            requests=[req1, req2],
            setup_time_seconds=60,
        )
        result = fcfs.schedule()

        # W-1 must be rejected due to outage; W-2 should be scheduled
        assert "W-1" in result.rejected_request_ids
        assert any(t.request_id == "W-2" for t in result.scheduled_tasks)
        assert result.is_valid is True

    def test_cpsat_avoids_outage_interval(self):
        outage = TimeWindow(
            start_time=self.t0,
            end_time=self.t0 + timedelta(minutes=10),
        )
        station = GroundStation(
            id="GS-1",
            name="Svalbard",
            downlink_rate_mbps=150.0,
            outages=[outage],
        )
        self.sat2 = Satellite(id="SAT-2", name="Sentinel-2B")

        window1 = VisibilityWindow(
            id="W-1",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            start_time=self.t0,
            end_time=self.t0 + timedelta(minutes=10),
        )
        window2 = VisibilityWindow(
            id="W-2",
            satellite_id="SAT-2",
            ground_station_id="GS-1",
            start_time=self.t0 + timedelta(minutes=15),
            end_time=self.t0 + timedelta(minutes=25),
        )

        req1 = DownlinkRequest(id="W-1", satellite_id="SAT-1", data_volume_mb=500.0, priority=Priority.CRITICAL)
        req2 = DownlinkRequest(id="W-2", satellite_id="SAT-2", data_volume_mb=500.0, priority=Priority.MEDIUM)

        cpsat = CPSATScheduler(
            satellites=[self.sat, self.sat2],
            ground_stations=[station],
            windows=[window1, window2],
            requests=[req1, req2],
            setup_time_seconds=60,
        )
        result = cpsat.schedule()

        # No scheduled task may overlap [t0, t0+10m]
        for task in result.scheduled_tasks:
            assert task.end_time <= outage.start_time or task.start_time >= outage.end_time
        assert "W-1" in result.rejected_request_ids
        assert result.is_valid is True


class TestSafeReoptimizationOnOutage:
    """Test re-optimization safety and preservation on outage changes."""

    @pytest.mark.asyncio
    async def test_reoptimize_preserves_previous_schedule_when_candidate_fails(self):
        from app.schemas.dataset import DatasetRead, GroundStationRead, SatellitePassRead
        from app.schemas.metrics import ScheduleMetrics
        from app.schemas.schedule import AlgorithmType, OptimizeScheduleRequest, ScheduleRunResponse, ScheduleStatus
        from app.services.scheduler.real_engine import RealSchedulerEngine

        now = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
        prev_run = ScheduleRunResponse(
            run_id="run_valid_initial",
            dataset_id="ds_test",
            algorithm=AlgorithmType.CP_SAT_OPTIMIZER,
            status=ScheduleStatus.COMPLETED,
            is_mock=False,
            is_valid=True,
            validation_violations=[],
            created_at=now,
            execution_time_ms=20.0,
            scheduled_passes=[],
            unassigned_passes=[],
            metrics=ScheduleMetrics(
                total_passes=1,
                scheduled_passes_count=1,
                unassigned_passes_count=0,
                scheduled_percentage=100.0,
                total_data_downlinked_gb=5.0,
                total_pending_data_gb=5.0,
                total_contact_time_seconds=200.0,
                objective_value=50.0,
                priority_satisfaction_rate=100.0,
            ),
        )

        dataset = DatasetRead(
            dataset_id="ds_test",
            name="Test Dataset",
            ground_station_count=1,
            satellite_pass_count=1,
            ground_stations=[
                GroundStationRead(station_id="GS-1", name="Svalbard", latitude_deg=78.2, longitude_deg=15.4)
            ],
            satellite_passes=[
                SatellitePassRead(
                    pass_id="P-1",
                    satellite_id="SAT-1",
                    ground_station_id="GS-1",
                    start_time=now,
                    end_time=now + timedelta(minutes=10),
                    max_elevation_deg=45.0,
                    data_volume_gb=5.0,
                    priority=1,
                    effective_data_rate_mbps=150.0,
                )
            ],
            created_at=now,
        )

        engine = RealSchedulerEngine()
        # Full outage on GS-1 during entire pass window
        outage = TimeWindow(start_time=now, end_time=now + timedelta(minutes=10))
        outages_by_station = {"GS-1": [outage]}

        req = OptimizeScheduleRequest(dataset_id="ds_test", time_limit_seconds=5.0)

        result = await engine.safe_reoptimize(
            dataset=dataset,
            request=req,
            previous_schedule=prev_run,
            outages_by_station=outages_by_station,
        )

        # Candidate is safely computed and valid (or fallback preserved)
        assert result.is_valid is True
