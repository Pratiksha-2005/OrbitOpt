"""Unit tests for dynamic dataset switching and solver engine metric verification."""

import pytest
from datetime import datetime, timezone
from app.db.seeder import get_standard_scenarios
from app.schemas.dataset import DatasetRead
from app.schemas.schedule import BaselineScheduleRequest, OptimizeScheduleRequest
from app.services.scheduler.real_engine import RealSchedulerEngine


@pytest.mark.asyncio
async def test_dataset_switching_scenarios():
    """Verify that every standard scenario generates authentic, non-zero dataset-driven metrics."""
    scenarios = get_standard_scenarios()
    assert len(scenarios) == 3

    engine = RealSchedulerEngine()
    
    for sc in scenarios:
        ds = DatasetRead(
            dataset_id=sc.dataset_id,
            name=sc.name,
            description=sc.description,
            ground_stations=sc.ground_stations,
            satellite_passes=sc.satellite_passes,
            ground_station_count=len(sc.ground_stations),
            satellite_pass_count=len(sc.satellite_passes),
            created_at=datetime.now(timezone.utc),
        )

        b_res = await engine.schedule_baseline(ds, BaselineScheduleRequest(dataset_id=ds.dataset_id))
        o_res = await engine.schedule_optimize(ds, OptimizeScheduleRequest(dataset_id=ds.dataset_id))

        assert b_res.dataset_id == ds.dataset_id
        assert o_res.dataset_id == ds.dataset_id
        assert b_res.metrics.total_passes == len(ds.satellite_passes)
        assert o_res.metrics.total_passes == len(ds.satellite_passes)
        assert o_res.metrics.total_data_downlinked_gb >= b_res.metrics.total_data_downlinked_gb
        assert o_res.metrics.objective_value >= b_res.metrics.objective_value
        assert o_res.is_valid is True
        assert b_res.is_valid is True


@pytest.mark.asyncio
async def test_empty_dataset_handling():
    """Verify solver handles empty or single-pass dataset safely without divide-by-zero."""
    engine = RealSchedulerEngine()
    empty_ds = DatasetRead(
        dataset_id="ds_empty_test",
        name="Empty Scenario",
        description="Empty test dataset",
        ground_stations=[],
        satellite_passes=[],
        ground_station_count=0,
        satellite_pass_count=0,
        created_at=datetime.now(timezone.utc),
    )

    b_res = await engine.schedule_baseline(empty_ds, BaselineScheduleRequest(dataset_id=empty_ds.dataset_id))
    o_res = await engine.schedule_optimize(empty_ds, OptimizeScheduleRequest(dataset_id=empty_ds.dataset_id))

    assert b_res.metrics.total_passes == 0
    assert o_res.metrics.total_passes == 0
    assert b_res.metrics.scheduled_percentage == 0.0
    assert o_res.metrics.scheduled_percentage == 0.0
