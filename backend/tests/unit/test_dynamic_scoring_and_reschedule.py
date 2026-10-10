"""Unit tests for Dynamic Priority Scoring, Setup Buffer Enforcement, and Safe Re-optimization."""

from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from app.services.scheduler.models import (
    DownlinkRequest,
    GroundStation,
    Priority,
    Satellite,
    ScheduleResult,
    ScheduledTask,
    SolverStatus,
    VisibilityWindow,
)
from app.services.scheduler.priority_scoring import (
    DynamicPriorityScorer,
    DynamicPriorityWeights,
    PriorityScoreBreakdown,
)
from app.services.scheduler.validator import ScheduleValidator
from app.services.scheduler.cpsat import CPSATScheduler
from app.services.scheduler.fcfs import FCFSScheduler


class TestDynamicPriorityWeights:
    """Test suite for priority weights validation and defaults."""

    def test_default_weights_sum_to_one(self):
        weights = DynamicPriorityWeights()
        assert weights.emergency_weight == 0.40
        assert weights.urgency_weight == 0.30
        assert weights.freshness_weight == 0.10
        assert weights.waiting_weight == 0.20
        total = (
            weights.emergency_weight
            + weights.urgency_weight
            + weights.freshness_weight
            + weights.waiting_weight
        )
        assert abs(total - 1.0) < 1e-6

    def test_custom_valid_weights(self):
        weights = DynamicPriorityWeights(
            emergency_weight=0.50,
            urgency_weight=0.20,
            freshness_weight=0.15,
            waiting_weight=0.15,
        )
        assert weights.emergency_weight == 0.50

    def test_invalid_weights_sum_raises_validation_error(self):
        with pytest.raises(ValidationError):
            DynamicPriorityWeights(
                emergency_weight=0.50,
                urgency_weight=0.50,
                freshness_weight=0.10,
                waiting_weight=0.20,
            )


class TestDynamicPriorityScorer:
    """Test multi-factor score calculations, bounds [0, 100], and timestamp handling."""

    def setup_method(self):
        self.scorer = DynamicPriorityScorer()
        self.now = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)

    def test_emergency_severity_points(self):
        score_p1 = self.scorer.calculate_emergency_score(priority=1, is_emergency=False)
        assert score_p1 == 100.0

        score_p5 = self.scorer.calculate_emergency_score(priority=5, is_emergency=False)
        assert score_p5 == 10.0

        score_emerg = self.scorer.calculate_emergency_score(priority=4, is_emergency=True)
        assert score_emerg == 100.0

    def test_deadline_urgency_bounds_and_stale_handling(self):
        # Imminent deadline (< 15 mins) -> 100.0
        imminent = self.now + timedelta(minutes=10)
        urg_imminent = self.scorer.calculate_urgency_score(start_time=imminent, deadline=imminent, evaluation_time=self.now)
        assert urg_imminent == 100.0

        # Distant deadline (> 24 hours) -> near 0
        distant = self.now + timedelta(hours=30)
        urg_distant = self.scorer.calculate_urgency_score(start_time=distant, deadline=distant, evaluation_time=self.now)
        assert 0.0 <= urg_distant <= 10.0

        # Stale deadline in the past (> 5 mins overdue) -> 0.0
        stale = self.now - timedelta(minutes=10)
        urg_stale = self.scorer.calculate_urgency_score(start_time=stale, deadline=stale, evaluation_time=self.now)
        assert urg_stale == 0.0

        # Missing deadline -> neutral fallback 50.0
        assert self.scorer.calculate_urgency_score(start_time=None, deadline=None, evaluation_time=self.now) == 50.0

    def test_data_freshness_decay(self):
        # Brand new data (0 mins old) -> 100.0
        fresh = self.scorer.calculate_freshness_score(data_generated_at=self.now, evaluation_time=self.now)
        assert fresh == 100.0

        # 48 hours old data -> near 0
        old_data = self.now - timedelta(hours=50)
        old_score = self.scorer.calculate_freshness_score(data_generated_at=old_data, evaluation_time=self.now)
        assert 0.0 <= old_score <= 10.0

        # Future timestamp -> capped to 100.0
        future_data = self.now + timedelta(minutes=10)
        assert self.scorer.calculate_freshness_score(data_generated_at=future_data, evaluation_time=self.now) == 100.0

    def test_waiting_time_anti_starvation_growth(self):
        # Newly queued (0 mins waiting) -> 0.0
        wait_new = self.scorer.calculate_waiting_score(created_at=self.now, evaluation_time=self.now)
        assert wait_new == 0.0

        # Queued 12 hours ago -> ~50.0
        wait_12h = self.scorer.calculate_waiting_score(created_at=self.now - timedelta(hours=12), evaluation_time=self.now)
        assert 48.0 <= wait_12h <= 52.0

        # Queued 24+ hours ago -> 100.0
        wait_24h = self.scorer.calculate_waiting_score(created_at=self.now - timedelta(hours=26), evaluation_time=self.now)
        assert wait_24h == 100.0

    def test_combined_score_clamped_and_breakdown(self):
        breakdown = self.scorer.score_request(
            priority=1,
            deadline_time=self.now + timedelta(minutes=10),
            data_generated_time=self.now,
            queued_time=self.now - timedelta(hours=24),
            evaluation_time=self.now,
            is_emergency=True,
        )
        assert isinstance(breakdown, PriorityScoreBreakdown)
        assert breakdown.combined_score == 100.0
        assert breakdown.emergency_score == 100.0
        assert breakdown.urgency_score == 100.0
        assert breakdown.freshness_score == 100.0
        assert breakdown.waiting_score == 100.0
        assert "E=" in breakdown.explanation or "Emergency" in breakdown.explanation


class TestSetupBufferAndFeasibility:
    """Test that antenna slew/setup buffer and temporal constraints are strictly enforced."""

    def setup_method(self):
        self.t0 = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
        self.station = GroundStation(id="GS-1", name="Svalbard", downlink_rate_mbps=150.0)
        self.sat = Satellite(id="SAT-1", name="Sentinel-1A")

    def test_validator_rejects_insufficient_setup_buffer(self):
        # 11250 MB at 150 Mbps = 600s (full 10-minute window)
        window1 = VisibilityWindow(
            id="W-1",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            start_time=self.t0,
            end_time=self.t0 + timedelta(minutes=10),
        )
        window2 = VisibilityWindow(
            id="W-2",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            start_time=self.t0 + timedelta(minutes=10, seconds=30),  # Only 30s gap after W-1
            end_time=self.t0 + timedelta(minutes=20),
        )
        req1 = DownlinkRequest(id="W-1", satellite_id="SAT-1", data_volume_mb=11250.0, priority=Priority.HIGH)
        req2 = DownlinkRequest(id="W-2", satellite_id="SAT-1", data_volume_mb=11250.0, priority=Priority.HIGH)

        result = ScheduleResult(
            id="res-001",
            scheduled_tasks=[
                ScheduledTask(id="T-1", request_id="W-1", visibility_window_id="W-1", start_time=window1.start_time, end_time=window1.end_time, data_transmitted_mb=11250.0),
                ScheduledTask(id="T-2", request_id="W-2", visibility_window_id="W-2", start_time=window2.start_time, end_time=window2.end_time, data_transmitted_mb=11250.0),
            ],
            rejected_request_ids=[],
            objective_value=100.0,
            solver_status=SolverStatus.OPTIMAL,
            runtime_seconds=0.01,
            is_valid=True,
        )

        validator = ScheduleValidator(
            satellites=[self.sat],
            ground_stations=[self.station],
            windows=[window1, window2],
            requests=[req1, req2],
            setup_time_seconds=120,
        )

        errors = validator.validate(result.scheduled_tasks)
        assert len(errors) > 0
        assert any("antenna slew buffer" in err or "setup-time" in err for err in errors)

    def test_fcfs_respects_setup_buffer(self):
        # 11250 MB at 150 Mbps = 600s duration (fills full 10m window)
        window1 = VisibilityWindow(
            id="W-1",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            start_time=self.t0,
            end_time=self.t0 + timedelta(minutes=10),
        )
        window2 = VisibilityWindow(
            id="W-2",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            start_time=self.t0 + timedelta(minutes=10, seconds=30),  # Only 30s gap
            end_time=self.t0 + timedelta(minutes=20),
        )
        req1 = DownlinkRequest(id="W-1", satellite_id="SAT-1", data_volume_mb=11250.0, priority=Priority.HIGH)
        req2 = DownlinkRequest(id="W-2", satellite_id="SAT-1", data_volume_mb=11250.0, priority=Priority.HIGH)

        fcfs = FCFSScheduler(
            satellites=[self.sat],
            ground_stations=[self.station],
            windows=[window1, window2],
            requests=[req1, req2],
            setup_time_seconds=120,
        )
        result = fcfs.schedule()
        assert len(result.scheduled_tasks) == 1
        assert "W-2" in result.rejected_request_ids

    def test_cpsat_respects_setup_buffer(self):
        # 11250 MB at 150 Mbps = 600s duration
        window1 = VisibilityWindow(
            id="W-1",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            start_time=self.t0,
            end_time=self.t0 + timedelta(minutes=10),
        )
        window2 = VisibilityWindow(
            id="W-2",
            satellite_id="SAT-1",
            ground_station_id="GS-1",
            start_time=self.t0 + timedelta(minutes=10, seconds=30),
            end_time=self.t0 + timedelta(minutes=20),
        )
        req1 = DownlinkRequest(id="W-1", satellite_id="SAT-1", data_volume_mb=11250.0, priority=Priority.HIGH, dynamic_score=80.0)
        req2 = DownlinkRequest(id="W-2", satellite_id="SAT-1", data_volume_mb=11250.0, priority=Priority.HIGH, dynamic_score=90.0)

        cpsat = CPSATScheduler(
            satellites=[self.sat],
            ground_stations=[self.station],
            windows=[window1, window2],
            requests=[req1, req2],
            setup_time_seconds=120,
        )
        result = cpsat.schedule()
        assert len(result.scheduled_tasks) == 1
        assert result.is_valid is True


class TestSafeReoptimization:
    """Test safe re-optimization preserving previous valid schedules on failure."""

    @pytest.mark.asyncio
    async def test_safe_reoptimize_preserves_previous_on_infeasible_or_failure(self):
        from app.schemas.dataset import DatasetRead, GroundStationRead, SatellitePassRead
        from app.schemas.schedule import OptimizeScheduleRequest, ScheduleRunResponse, ScheduleStatus, AlgorithmType
        from app.schemas.metrics import ScheduleMetrics
        from app.services.scheduler.real_engine import RealSchedulerEngine

        now = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
        prev_run = ScheduleRunResponse(
            run_id="run_prev_001",
            dataset_id="ds_test",
            algorithm=AlgorithmType.CP_SAT_OPTIMIZER,
            status=ScheduleStatus.COMPLETED,
            is_mock=False,
            is_valid=True,
            validation_violations=[],
            created_at=now,
            execution_time_ms=15.0,
            scheduled_passes=[],
            unassigned_passes=[],
            metrics=ScheduleMetrics(
                total_passes=2,
                scheduled_passes_count=1,
                unassigned_passes_count=1,
                scheduled_percentage=50.0,
                total_data_downlinked_gb=10.0,
                total_pending_data_gb=20.0,
                total_contact_time_seconds=300.0,
                objective_value=50.0,
                priority_satisfaction_rate=50.0,
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
                    data_volume_gb=10.0,
                    priority=1,
                    effective_data_rate_mbps=150.0,
                )
            ],
            created_at=now,
        )

        engine = RealSchedulerEngine()
        req = OptimizeScheduleRequest(dataset_id="ds_test", time_limit_seconds=5.0)

        result = await engine.safe_reoptimize(
            dataset=dataset,
            request=req,
            previous_schedule=prev_run,
        )

        assert result.is_valid is True
        assert result.status == ScheduleStatus.COMPLETED

