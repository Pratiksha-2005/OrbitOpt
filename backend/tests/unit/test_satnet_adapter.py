"""Unit tests verifying the SatNet Dataset Inspector, Adapter, Validator, and Solvers."""

import os
from datetime import datetime, timezone
import pytest

from app.services.satnet.inspector import SatNetInspector
from app.services.satnet.adapter import SatNetAdapter, get_week_epoch_start
from app.services.satnet.models import (
    SatNetScenario,
    SatNetRequest,
    SatNetCandidateWindow,
    SatNetMaintenanceInterval,
    SatNetScheduledTask,
    SatNetSolverStatus,
)
from app.services.satnet.solver import (
    SatNetValidator,
    SatNetFCFSEngine,
    SatNetCPSATEngine,
)


@pytest.fixture
def data_dir() -> str:
    """Return path to datasets/satnet-master/data."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base_dir, "datasets", "satnet-master", "data")


class TestSatNetInspector:
    @pytest.mark.dataset_dependent
    def test_inspector_validation_and_stats(self, data_dir: str):
        inspector = SatNetInspector(data_dir=data_dir)
        report = inspector.inspect_week("W10_2018")

        assert report["week_key"] == "W10_2018"
        assert report["week_number"] == 10
        assert report["year"] == 2018
        assert report["total_requests"] == 257
        assert report["valid_requests"] == 257
        assert report["malformed_count"] == 0
        assert report["unique_subjects_count"] == 30
        assert report["total_view_periods"] == 2513
        assert report["unique_resources_count"] == 39
        assert report["single_antennas_count"] == 12
        assert "DSS-14" in report["single_antennas"]
        assert "DSS-24_DSS-25" in report["array_antennas"]
        assert report["maintenance_intervals_count"] == 37

    def test_missing_data_dir_raises_error(self):
        inspector = SatNetInspector(data_dir="E:/non_existent_path_xyz")
        with pytest.raises(FileNotFoundError):
            inspector.load_problems()

    @pytest.mark.dataset_dependent
    def test_unknown_week_raises_error(self, data_dir: str):
        inspector = SatNetInspector(data_dir=data_dir)
        with pytest.raises(KeyError):
            inspector.inspect_week("W99_2099")


class TestSatNetAdapter:
    def test_week_epoch_calculation(self):
        # 2018 ISO Week 10 starts Monday, March 5, 2018 00:00:00 UTC
        epoch_w10 = get_week_epoch_start(10, 2018)
        assert epoch_w10 == datetime(2018, 3, 5, 0, 0, 0, tzinfo=timezone.utc)

        # 2018 ISO Week 1 starts Monday, Jan 1, 2018 00:00:00 UTC
        epoch_w1 = get_week_epoch_start(1, 2018)
        assert epoch_w1 == datetime(2018, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    @pytest.mark.dataset_dependent
    def test_load_scenario_w10(self, data_dir: str):
        adapter = SatNetAdapter(data_dir=data_dir)
        scenario = adapter.load_scenario("W10_2018")

        assert scenario.week_key == "W10_2018"
        assert scenario.week_number == 10
        assert scenario.year == 2018
        assert len(scenario.requests) == 257
        assert len(scenario.maintenance_intervals) == 37
        assert len(scenario.single_antennas) == 12
        assert "DSS-14" in scenario.single_antennas

        # Check a specific request preservation
        r0 = scenario.requests[0]
        assert r0.track_id is not None
        assert r0.subject > 0
        assert r0.duration_hours > 0
        assert r0.duration_min_hours <= r0.duration_hours
        assert len(r0.candidate_windows) > 0

        # Check candidate window constituent antenna expansion
        array_cw = next(
            (cw for r in scenario.requests for cw in r.candidate_windows if "_" in cw.resource_id),
            None,
        )
        assert array_cw is not None
        assert len(array_cw.constituent_antennas) >= 2


class TestSatNetValidatorAndSolvers:
    @pytest.fixture
    def small_test_scenario(self) -> SatNetScenario:
        """Synthetic deterministic scenario with 2 requests, 1 array, and 1 maintenance interval."""
        epoch = datetime(2018, 3, 5, 0, 0, 0, tzinfo=timezone.utc)
        scenario = SatNetScenario(
            name="Test Mini Scenario",
            week_key="W10_2018",
            week_number=10,
            year=2018,
            week_start_epoch=epoch,
            single_antennas={"DSS-24", "DSS-25"},
            array_antennas={"DSS-24_DSS-25": ["DSS-24", "DSS-25"]},
            all_resources={"DSS-24", "DSS-25", "DSS-24_DSS-25"},
        )

        # Maintenance on DSS-24 from sec 1000 to 2000
        scenario.maintenance_intervals.append(
            SatNetMaintenanceInterval(
                interval_id="maint_01",
                antenna="DSS-24",
                start_time=epoch,
                end_time=epoch,
                start_sec=1000,
                end_sec=2000,
                week=10,
                year=2018,
            )
        )

        # Request 1: Needs 1.0 hr (3600s), setup=1800s, teardown=900s
        # Window on DSS-24 from 0 to 10000 -> Cannot overlap [1000, 2000]
        scenario.requests.append(
            SatNetRequest(
                track_id="REQ-01",
                subject=101,
                user="101_0",
                week=10,
                year=2018,
                duration_hours=1.0,
                duration_min_hours=1.0,
                setup_time_minutes=30,  # 1800s
                teardown_time_minutes=15,  # 900s
                time_window_start_sec=0,
                time_window_end_sec=10000,
                time_window_start=epoch,
                time_window_end=epoch,
                candidate_resources=["DSS-24"],
                candidate_windows=[
                    SatNetCandidateWindow(
                        window_id="win_req1_dss24",
                        track_id="REQ-01",
                        resource_id="DSS-24",
                        constituent_antennas=["DSS-24"],
                        start_time=epoch,
                        end_time=epoch,
                        vp_start_sec=0,
                        vp_end_sec=10000,
                        duration_hours=2.77,
                    )
                ],
            )
        )

        # Request 2: Array request on DSS-24_DSS-25
        scenario.requests.append(
            SatNetRequest(
                track_id="REQ-02",
                subject=102,
                user="102_0",
                week=10,
                year=2018,
                duration_hours=2.0,
                duration_min_hours=1.5,
                setup_time_minutes=30,
                teardown_time_minutes=15,
                time_window_start_sec=0,
                time_window_end_sec=20000,
                time_window_start=epoch,
                time_window_end=epoch,
                candidate_resources=["DSS-24_DSS-25"],
                candidate_windows=[
                    SatNetCandidateWindow(
                        window_id="win_req2_array",
                        track_id="REQ-02",
                        resource_id="DSS-24_DSS-25",
                        constituent_antennas=["DSS-24", "DSS-25"],
                        start_time=epoch,
                        end_time=epoch,
                        vp_start_sec=0,
                        vp_end_sec=20000,
                        duration_hours=5.55,
                    )
                ],
            )
        )

        return scenario

    def test_fcfs_execution_on_synthetic_scenario(self, small_test_scenario: SatNetScenario):
        fcfs = SatNetFCFSEngine(small_test_scenario)
        result = fcfs.solve()

        assert result.is_valid is True
        assert len(result.validation_violations) == 0
        assert len(result.scheduled_tasks) == 2
        assert result.metrics.scheduled_requests_count == 2
        assert result.metrics.request_satisfaction_rate == 100.0

    def test_cpsat_execution_on_synthetic_scenario(self, small_test_scenario: SatNetScenario):
        cpsat = SatNetCPSATEngine(small_test_scenario, time_limit_seconds=5.0)
        result = cpsat.solve()

        assert result.is_valid is True
        assert result.solver_status == SatNetSolverStatus.OPTIMAL
        assert len(result.validation_violations) == 0
        assert len(result.scheduled_tasks) == 2
        assert result.metrics.scheduled_requests_count == 2

    def test_validator_catches_maintenance_overlap(self, small_test_scenario: SatNetScenario):
        epoch = small_test_scenario.week_start_epoch
        # Construct invalid task overlapping maintenance at sec 1500
        invalid_task = SatNetScheduledTask(
            task_id="bad_task",
            track_id="REQ-01",
            subject=101,
            resource_id="DSS-24",
            constituent_antennas=["DSS-24"],
            start_time=epoch,
            end_time=epoch,
            start_sec=1200,
            end_sec=2400,
            scheduled_duration_hours=1.0,
            setup_start_time=epoch,
            teardown_end_time=epoch,
            setup_start_sec=0,
            teardown_end_sec=3300,
        )

        validator = SatNetValidator(small_test_scenario)
        violations = validator.validate([invalid_task])
        assert len(violations) > 0
        assert any("Overlap on physical antenna 'DSS-24'" in v for v in violations)

    def test_validator_catches_multiple_allocations_for_same_request(self, small_test_scenario: SatNetScenario):
        epoch = small_test_scenario.week_start_epoch
        task1 = SatNetScheduledTask(
            task_id="t1",
            track_id="REQ-01",
            subject=101,
            resource_id="DSS-24",
            constituent_antennas=["DSS-24"],
            start_time=epoch,
            end_time=epoch,
            start_sec=3000,
            end_sec=6600,
            scheduled_duration_hours=1.0,
            setup_start_time=epoch,
            teardown_end_time=epoch,
            setup_start_sec=1200,
            teardown_end_sec=7500,
        )
        task2 = SatNetScheduledTask(
            task_id="t2",
            track_id="REQ-01",
            subject=101,
            resource_id="DSS-24",
            constituent_antennas=["DSS-24"],
            start_time=epoch,
            end_time=epoch,
            start_sec=8000,
            end_sec=11600,
            scheduled_duration_hours=1.0,
            setup_start_time=epoch,
            teardown_end_time=epoch,
            setup_start_sec=6200,
            teardown_end_sec=12500,
        )

        validator = SatNetValidator(small_test_scenario)
        violations = validator.validate([task1, task2])
        assert len(violations) > 0
        assert any("scheduled multiple times" in v for v in violations)

    @pytest.mark.dataset_dependent
    def test_reproducible_fcfs_on_real_w10(self, data_dir: str):
        adapter = SatNetAdapter(data_dir=data_dir)
        scenario = adapter.load_scenario("W10_2018")

        fcfs = SatNetFCFSEngine(scenario)
        result1 = fcfs.solve()
        result2 = fcfs.solve()

        assert result1.is_valid is True
        assert result2.is_valid is True
        assert result1.metrics.scheduled_requests_count == result2.metrics.scheduled_requests_count
        assert result1.metrics.total_scheduled_hours == result2.metrics.total_scheduled_hours
        assert len(result1.scheduled_tasks) > 0
