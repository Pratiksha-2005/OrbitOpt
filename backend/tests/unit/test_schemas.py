"""Unit tests for Pydantic Schema validations, constraints, and field synchronizations."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.ground_station import GroundStationCreate
from app.schemas.satellite_pass import SatellitePassCreate
from app.schemas.schedule import ScheduledPass


def test_ground_station_coordinate_bounds() -> None:
    """Test latitude and longitude valid bounds and validation failures."""
    gs = GroundStationCreate(
        station_id="GS-01",
        name="Station 1",
        latitude_deg=45.0,
        longitude_deg=90.0,
        elevation_mask_deg=10.0,
        max_concurrent_passes=2,
        supported_bands=["X-band"],
    )
    assert gs.latitude_deg == 45.0

    with pytest.raises(ValidationError):
        GroundStationCreate(
            station_id="GS-BAD-LAT",
            name="Station Bad Lat",
            latitude_deg=95.0,
            longitude_deg=0.0,
        )

    with pytest.raises(ValidationError):
        GroundStationCreate(
            station_id="GS-BAD-LON",
            name="Station Bad Lon",
            latitude_deg=0.0,
            longitude_deg=-185.0,
        )


def test_satellite_pass_time_window_validation() -> None:
    """Test satellite pass start/end time chronological validation."""
    now = datetime.now(timezone.utc)
    earlier = datetime.fromtimestamp(now.timestamp() - 600, tz=timezone.utc)

    with pytest.raises(ValidationError) as exc:
        SatellitePassCreate(
            pass_id="PASS-01",
            satellite_id="SAT-1",
            ground_station_id="GS-01",
            start_time=now,
            end_time=earlier,
            max_elevation_deg=50.0,
            priority=1,
            data_volume_gb=10.0,
        )
    assert "end_time" in str(exc.value)


def test_satellite_pass_priority_range() -> None:
    """Test priority limits between 1 and 5."""
    now = datetime.now(timezone.utc)
    later = datetime.fromtimestamp(now.timestamp() + 600, tz=timezone.utc)

    with pytest.raises(ValidationError):
        SatellitePassCreate(
            pass_id="PASS-01",
            satellite_id="SAT-1",
            ground_station_id="GS-01",
            start_time=now,
            end_time=later,
            max_elevation_deg=50.0,
            priority=0,
            data_volume_gb=10.0,
        )

    with pytest.raises(ValidationError):
        SatellitePassCreate(
            pass_id="PASS-01",
            satellite_id="SAT-1",
            ground_station_id="GS-01",
            start_time=now,
            end_time=later,
            max_elevation_deg=50.0,
            priority=6,
            data_volume_gb=10.0,
        )


def test_satellite_pass_field_synchronization_and_compatibility() -> None:
    """Verify synchronization between legacy and explicit field names."""
    now = datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc)
    later = datetime(2026, 10, 10, 8, 12, tzinfo=timezone.utc)

    # 1. Legacy payload with data_volume_gb sets pending_data_gb
    p1 = SatellitePassCreate(
        pass_id="PASS-LEGACY",
        satellite_id="SAT-1",
        ground_station_id="GS-01",
        start_time=now,
        end_time=later,
        max_elevation_deg=45.0,
        data_volume_gb=50.0,
        required_bandwidth_mbps=150.0,
    )
    assert p1.data_volume_gb == 50.0
    assert p1.pending_data_gb == 50.0
    assert p1.effective_data_rate_mbps == 150.0

    # 2. Modern payload with pending_data_gb sets data_volume_gb
    p2 = SatellitePassCreate(
        pass_id="PASS-MODERN",
        satellite_id="SAT-1",
        ground_station_id="GS-01",
        start_time=now,
        end_time=later,
        max_elevation_deg=45.0,
        pending_data_gb=35.0,
        effective_data_rate_mbps=200.0,
    )
    assert p2.data_volume_gb == 35.0
    assert p2.pending_data_gb == 35.0
    assert p2.required_bandwidth_mbps == 200.0

    # 3. Conflicting data volume values must raise ValidationError
    with pytest.raises(ValidationError) as exc:
        SatellitePassCreate(
            pass_id="PASS-CONFLICT-VOL",
            satellite_id="SAT-1",
            ground_station_id="GS-01",
            start_time=now,
            end_time=later,
            max_elevation_deg=45.0,
            data_volume_gb=50.0,
            pending_data_gb=20.0,  # Conflict!
        )
    assert "Conflicting values provided" in str(exc.value)

    # 4. Conflicting bandwidth values must raise ValidationError
    with pytest.raises(ValidationError) as exc2:
        SatellitePassCreate(
            pass_id="PASS-CONFLICT-RATE",
            satellite_id="SAT-1",
            ground_station_id="GS-01",
            start_time=now,
            end_time=later,
            max_elevation_deg=45.0,
            data_volume_gb=50.0,
            effective_data_rate_mbps=150.0,
            required_bandwidth_mbps=300.0,  # Conflict!
        )
    assert "Conflicting values provided" in str(exc2.value)


def test_scheduled_pass_transferable_data_sync() -> None:
    """Verify ScheduledPass syncs transferable_data_gb from data_volume_gb."""
    now = datetime(2026, 10, 10, 8, 0, tzinfo=timezone.utc)
    later = datetime(2026, 10, 10, 8, 12, tzinfo=timezone.utc)

    sp = ScheduledPass(
        pass_id="PASS-01",
        satellite_id="SAT-1",
        ground_station_id="GS-01",
        start_time=now,
        end_time=later,
        duration_seconds=720.0,
        data_volume_gb=13.5,
        priority=1,
    )
    assert sp.transferable_data_gb == 13.5
