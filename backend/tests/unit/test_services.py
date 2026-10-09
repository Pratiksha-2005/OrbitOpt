"""Unit tests for MockSchedulerEngine, mathematical unit conversions, and service logic."""

from datetime import datetime, timezone
import pytest

from app.schemas.dataset import DatasetRead
from app.schemas.ground_station import GroundStationRead
from app.schemas.satellite_pass import SatellitePassRead
from app.schemas.schedule import (
    BaselineScheduleRequest,
    OptimizeScheduleRequest,
)
from app.services.mock_scheduler import MockSchedulerEngine


@pytest.mark.asyncio
async def test_mock_scheduler_transferable_data_unit_conversion() -> None:
    """Verify conversion formula: transferable = min(pending_data, data_rate * duration / 8000)."""
    engine = MockSchedulerEngine()
    
    t0 = datetime(2026, 10, 10, 8, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 10, 8, 12, 0, tzinfo=timezone.utc)  # 720 seconds
    
    # 150 Mbps * 720 s = 108,000 Mbits / 8000 = 13.5 GB capacity
    # Case A: pending is 50 GB > 13.5 GB -> transferable must be 13.5 GB (channel bottleneck)
    # Case B: pending is 5.0 GB < 13.5 GB -> transferable must be 5.0 GB (data bottleneck)
    dataset = DatasetRead(
        dataset_id="ds_unit_test",
        name="Unit Conversion Test",
        ground_station_count=1,
        satellite_pass_count=1,
        created_at=datetime.now(timezone.utc),
        ground_stations=[
            GroundStationRead(
                station_id="GS-01",
                name="Station 1",
                latitude_deg=0.0,
                longitude_deg=0.0,
                elevation_mask_deg=5.0,
                max_concurrent_passes=1,
                supported_bands=["X-band"],
            )
        ],
        satellite_passes=[
            SatellitePassRead(
                pass_id="PASS-BOTTLENECK",
                satellite_id="SAT-1",
                ground_station_id="GS-01",
                start_time=t0,
                end_time=t1,
                max_elevation_deg=45.0,
                priority=1,
                data_volume_gb=50.0,
                pending_data_gb=50.0,
                effective_data_rate_mbps=150.0,
            )
        ],
    )

    result = await engine.schedule_baseline(
        dataset,
        BaselineScheduleRequest(dataset_id="ds_unit_test", setup_time_seconds=60),
    )
    assert len(result.scheduled_passes) == 1
    scheduled_pass = result.scheduled_passes[0]
    # Expected: 150 * 720 / 8000 = 13.5 GB
    assert scheduled_pass.data_volume_gb == 13.5
    assert scheduled_pass.transferable_data_gb == 13.5
    assert result.metrics.total_data_downlinked_gb == 13.5
    assert result.metrics.total_pending_data_gb == 50.0
    # Objective = 10.0 (weight for priority 1) * 13.5 = 135.0
    assert result.metrics.objective_value == 135.0


@pytest.mark.asyncio
async def test_mock_scheduler_conflict_detection() -> None:
    """Verify mock scheduler detects overlapping passes on same ground station."""
    engine = MockSchedulerEngine()
    
    t0 = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 10, 12, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 10, 12, 5, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 10, 10, 12, 15, 0, tzinfo=timezone.utc)

    dataset = DatasetRead(
        dataset_id="ds_test",
        name="Conflict Test",
        ground_station_count=1,
        satellite_pass_count=2,
        created_at=datetime.now(timezone.utc),
        ground_stations=[
            GroundStationRead(
                station_id="GS-01",
                name="Station 1",
                latitude_deg=0.0,
                longitude_deg=0.0,
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
                start_time=t0,
                end_time=t1,
                max_elevation_deg=40.0,
                priority=1,
                data_volume_gb=20.0,
            ),
            SatellitePassRead(
                pass_id="PASS-02",
                satellite_id="SAT-2",
                ground_station_id="GS-01",
                start_time=t2,
                end_time=t3,
                max_elevation_deg=50.0,
                priority=2,
                data_volume_gb=30.0,
            ),
        ],
    )

    result = await engine.schedule_baseline(
        dataset,
        BaselineScheduleRequest(dataset_id="ds_test", setup_time_seconds=60),
    )
    assert result.status.value == "completed"
    assert result.is_mock is True
    assert len(result.scheduled_passes) == 1
    assert result.scheduled_passes[0].pass_id == "PASS-01"
    assert len(result.unassigned_passes) == 1
    assert result.unassigned_passes[0].pass_id == "PASS-02"
    assert result.metrics.conflicts_detected >= 1
    assert result.metrics.objective_value > 0


@pytest.mark.asyncio
async def test_mock_scheduler_objective_prioritization() -> None:
    """Verify mock scheduler prioritizes higher weighted transferable data volume in optimize mode."""
    engine = MockSchedulerEngine()
    
    t0 = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 10, 12, 10, 0, tzinfo=timezone.utc)

    # Two passes overlapping on the same station: PASS-HIGH (priority 1, 50 GB) vs PASS-LOW (priority 5, 10 GB)
    dataset = DatasetRead(
        dataset_id="ds_opt_test",
        name="Objective Test",
        ground_station_count=1,
        satellite_pass_count=2,
        created_at=datetime.now(timezone.utc),
        ground_stations=[
            GroundStationRead(
                station_id="GS-01",
                name="Station 1",
                latitude_deg=0.0,
                longitude_deg=0.0,
                elevation_mask_deg=5.0,
                max_concurrent_passes=1,
                supported_bands=["X-band"],
            )
        ],
        satellite_passes=[
            SatellitePassRead(
                pass_id="PASS-LOW",
                satellite_id="SAT-LOW",
                ground_station_id="GS-01",
                start_time=t0,
                end_time=t1,
                max_elevation_deg=30.0,
                priority=5,
                data_volume_gb=10.0,
            ),
            SatellitePassRead(
                pass_id="PASS-HIGH",
                satellite_id="SAT-HIGH",
                ground_station_id="GS-01",
                start_time=t0,
                end_time=t1,
                max_elevation_deg=60.0,
                priority=1,
                data_volume_gb=50.0,
            ),
        ],
    )

    result = await engine.schedule_optimize(
        dataset,
        OptimizeScheduleRequest(
            dataset_id="ds_opt_test",
            setup_time_seconds=60,
            priority_weights={"1": 10.0, "5": 0.5},
        ),
    )

    assert result.status.value == "completed"
    assert result.is_mock is True
    assert len(result.scheduled_passes) == 1
    assert result.scheduled_passes[0].pass_id == "PASS-HIGH"
    assert result.metrics.objective_value == 500.0


@pytest.mark.asyncio
async def test_dataset_service_list_and_not_found(db_session) -> None:
    """Verify DatasetService handles list operations and missing dataset queries."""
    from app.services.dataset_service import DatasetService
    from app.core.errors import ResourceNotFoundError

    svc = DatasetService(db_session)
    # 1. Non-existent dataset throws ResourceNotFoundError
    with pytest.raises(ResourceNotFoundError) as exc_info:
        await svc.get_dataset("ds_non_existent_12345")
    assert "ds_non_existent_12345" in str(exc_info.value)
    assert exc_info.value.status_code == 404

    # 2. List returns empty list initially
    datasets = await svc.list_datasets()
    assert isinstance(datasets, list)

