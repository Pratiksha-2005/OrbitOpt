"""Database seeder for standard OrbitOpt scenario datasets."""

from datetime import datetime, timezone
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.dataset import DatasetModel, GroundStationModel, SatellitePassModel
from app.schemas.dataset import DatasetCreate
from app.schemas.ground_station import GroundStationCreate
from app.schemas.satellite_pass import SatellitePassCreate
from app.services.dataset_service import DatasetService

logger = logging.getLogger(__name__)


def get_standard_scenarios() -> list[DatasetCreate]:
    """Return the curated OrbitOpt standard scenario datasets."""
    t0 = datetime(2026, 10, 10, 10, 0, 0, tzinfo=timezone.utc)
    t0_end = datetime(2026, 10, 10, 10, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 10, 10, 10, 4, 0, tzinfo=timezone.utc)
    t1_end = datetime(2026, 10, 10, 10, 14, 0, tzinfo=timezone.utc)

    t2 = datetime(2026, 10, 10, 10, 45, 0, tzinfo=timezone.utc)
    t2_end = datetime(2026, 10, 10, 10, 55, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 10, 10, 10, 48, 0, tzinfo=timezone.utc)
    t3_end = datetime(2026, 10, 10, 10, 58, 0, tzinfo=timezone.utc)

    t4 = datetime(2026, 10, 10, 11, 30, 0, tzinfo=timezone.utc)
    t4_end = datetime(2026, 10, 10, 11, 42, 0, tzinfo=timezone.utc)
    t5 = datetime(2026, 10, 10, 12, 15, 0, tzinfo=timezone.utc)
    t5_end = datetime(2026, 10, 10, 12, 25, 0, tzinfo=timezone.utc)
    t6 = datetime(2026, 10, 10, 13, 0, 0, tzinfo=timezone.utc)
    t6_end = datetime(2026, 10, 10, 13, 10, 0, tzinfo=timezone.utc)
    t7 = datetime(2026, 10, 10, 13, 40, 0, tzinfo=timezone.utc)
    t7_end = datetime(2026, 10, 10, 13, 50, 0, tzinfo=timezone.utc)

    stations_4 = [
        GroundStationCreate(station_id="GS-SVALBARD", name="Svalbard Arctic Station", latitude_deg=78.2297, longitude_deg=15.4077, elevation_mask_deg=5.0, max_concurrent_passes=1, supported_bands=["S-band", "X-band"]),
        GroundStationCreate(station_id="GS-PUNTA_ARENAS", name="Punta Arenas Station", latitude_deg=-53.1638, longitude_deg=-70.9171, elevation_mask_deg=5.0, max_concurrent_passes=1, supported_bands=["X-band", "Ka-band"]),
        GroundStationCreate(station_id="GS-HARTEBEESTHOEK", name="Hartebeesthoek Space Station", latitude_deg=-25.8897, longitude_deg=27.7072, elevation_mask_deg=7.0, max_concurrent_passes=1, supported_bands=["S-band", "X-band"]),
        GroundStationCreate(station_id="GS-FAIRBANKS", name="Fairbanks Tracking Facility", latitude_deg=64.8378, longitude_deg=-147.7164, elevation_mask_deg=5.0, max_concurrent_passes=1, supported_bands=["S-band", "X-band", "Ka-band"]),
    ]

    # Scenario 1: Genuine Contention Priority Inversion Benchmark
    scen_contention = DatasetCreate(
        dataset_id="ds_priority_contention_benchmark",
        name="Priority Contention Benchmark (Global 4-Station)",
        description="High-contention downlink scenario where earlier low-priority passes conflict with later critical passes on Svalbard & Fairbanks antennas, proving CP-SAT optimization gain.",
        ground_stations=stations_4,
        satellite_passes=[
            # GS-SVALBARD Contention: Early P3 vs Later P1
            SatellitePassCreate(pass_id="PASS-RADAR-001", satellite_id="SAT-RADARSAT-1", ground_station_id="GS-SVALBARD", start_time=t0, end_time=t0_end, max_elevation_deg=38.0, priority=3, data_volume_gb=25.0, required_bandwidth_mbps=350.0, channel_band="X-band"),
            SatellitePassCreate(pass_id="PASS-EARTHOBS-001", satellite_id="SAT-EARTHOBS-1", ground_station_id="GS-SVALBARD", start_time=t1, end_time=t1_end, max_elevation_deg=72.0, priority=1, data_volume_gb=45.0, required_bandwidth_mbps=600.0, channel_band="X-band"),
            # GS-FAIRBANKS Contention: Early P4 vs Later P2
            SatellitePassCreate(pass_id="PASS-ASTRO-001", satellite_id="SAT-ASTRO-1", ground_station_id="GS-FAIRBANKS", start_time=t2, end_time=t2_end, max_elevation_deg=41.0, priority=4, data_volume_gb=15.0, required_bandwidth_mbps=200.0, channel_band="S-band"),
            SatellitePassCreate(pass_id="PASS-WEATHER-001", satellite_id="SAT-WEATHER-1", ground_station_id="GS-FAIRBANKS", start_time=t3, end_time=t3_end, max_elevation_deg=65.0, priority=2, data_volume_gb=30.0, required_bandwidth_mbps=450.0, channel_band="Ka-band"),
            # Non-conflicting passes
            SatellitePassCreate(pass_id="PASS-EARTHOBS-002", satellite_id="SAT-EARTHOBS-2", ground_station_id="GS-PUNTA_ARENAS", start_time=t4, end_time=t4_end, max_elevation_deg=82.0, priority=1, data_volume_gb=55.0, required_bandwidth_mbps=700.0, channel_band="X-band"),
            SatellitePassCreate(pass_id="PASS-RADAR-002", satellite_id="SAT-RADARSAT-2", ground_station_id="GS-HARTEBEESTHOEK", start_time=t5, end_time=t5_end, max_elevation_deg=54.0, priority=2, data_volume_gb=28.0, required_bandwidth_mbps=400.0, channel_band="X-band"),
            SatellitePassCreate(pass_id="PASS-WEATHER-002", satellite_id="SAT-WEATHER-2", ground_station_id="GS-SVALBARD", start_time=t6, end_time=t6_end, max_elevation_deg=59.0, priority=3, data_volume_gb=22.0, required_bandwidth_mbps=300.0, channel_band="S-band"),
            SatellitePassCreate(pass_id="PASS-ASTRO-002", satellite_id="SAT-ASTRO-2", ground_station_id="GS-HARTEBEESTHOEK", start_time=t7, end_time=t7_end, max_elevation_deg=48.0, priority=5, data_volume_gb=12.0, required_bandwidth_mbps=180.0, channel_band="S-band"),
        ],
    )

    # Scenario 2: Standard Baseline Scenario
    scen_baseline = DatasetCreate(
        dataset_id="ds_leo_constellation_baseline",
        name="LEO Multi-Satellite Constellation (Standard Baseline)",
        description="Standard orbital passes across Global 4-Station network where chronological arrival naturally coincides with global mathematical optimum.",
        ground_stations=stations_4,
        satellite_passes=[
            SatellitePassCreate(pass_id="PASS-EARTHOBS-001", satellite_id="SAT-EARTHOBS-1", ground_station_id="GS-SVALBARD", start_time=t0, end_time=t0_end, max_elevation_deg=72.0, priority=1, data_volume_gb=45.0, required_bandwidth_mbps=600.0, channel_band="X-band"),
            SatellitePassCreate(pass_id="PASS-RADAR-001", satellite_id="SAT-RADARSAT-1", ground_station_id="GS-SVALBARD", start_time=datetime(2026, 10, 10, 10, 6, 0, tzinfo=timezone.utc), end_time=datetime(2026, 10, 10, 10, 16, 0, tzinfo=timezone.utc), max_elevation_deg=38.0, priority=3, data_volume_gb=25.0, required_bandwidth_mbps=350.0, channel_band="X-band"),
            SatellitePassCreate(pass_id="PASS-WEATHER-001", satellite_id="SAT-WEATHER-1", ground_station_id="GS-FAIRBANKS", start_time=t2, end_time=t2_end, max_elevation_deg=65.0, priority=2, data_volume_gb=30.0, required_bandwidth_mbps=450.0, channel_band="Ka-band"),
            SatellitePassCreate(pass_id="PASS-ASTRO-001", satellite_id="SAT-ASTRO-1", ground_station_id="GS-FAIRBANKS", start_time=datetime(2026, 10, 10, 10, 50, 0, tzinfo=timezone.utc), end_time=datetime(2026, 10, 10, 11, 0, 0, tzinfo=timezone.utc), max_elevation_deg=41.0, priority=4, data_volume_gb=15.0, required_bandwidth_mbps=200.0, channel_band="S-band"),
            SatellitePassCreate(pass_id="PASS-EARTHOBS-002", satellite_id="SAT-EARTHOBS-2", ground_station_id="GS-PUNTA_ARENAS", start_time=t4, end_time=t4_end, max_elevation_deg=82.0, priority=1, data_volume_gb=55.0, required_bandwidth_mbps=700.0, channel_band="X-band"),
            SatellitePassCreate(pass_id="PASS-RADAR-002", satellite_id="SAT-RADARSAT-2", ground_station_id="GS-HARTEBEESTHOEK", start_time=t5, end_time=t5_end, max_elevation_deg=54.0, priority=2, data_volume_gb=28.0, required_bandwidth_mbps=400.0, channel_band="X-band"),
            SatellitePassCreate(pass_id="PASS-WEATHER-002", satellite_id="SAT-WEATHER-2", ground_station_id="GS-SVALBARD", start_time=t6, end_time=t6_end, max_elevation_deg=59.0, priority=3, data_volume_gb=22.0, required_bandwidth_mbps=300.0, channel_band="S-band"),
            SatellitePassCreate(pass_id="PASS-ASTRO-002", satellite_id="SAT-ASTRO-2", ground_station_id="GS-HARTEBEESTHOEK", start_time=t7, end_time=t7_end, max_elevation_deg=48.0, priority=5, data_volume_gb=12.0, required_bandwidth_mbps=180.0, channel_band="S-band"),
        ],
    )

    # Scenario 3: Disaster Emergency Response
    stations_2 = [
        GroundStationCreate(station_id="GS-SVALBARD", name="Svalbard Arctic Station", latitude_deg=78.2297, longitude_deg=15.4077, elevation_mask_deg=5.0, max_concurrent_passes=1, supported_bands=["S-band", "X-band", "Ka-band"]),
        GroundStationCreate(station_id="GS-FAIRBANKS", name="Fairbanks Tracking Facility", latitude_deg=64.8378, longitude_deg=-147.7164, elevation_mask_deg=5.0, max_concurrent_passes=1, supported_bands=["S-band", "X-band"]),
    ]
    scen_disaster = DatasetCreate(
        dataset_id="ds_disaster_response_p1_heavy",
        name="Urgent Disaster Response (High Priority Contention)",
        description="High-density emergency scenario where multiple high-priority Earth observation satellites compete for immediate Arctic downlinks.",
        ground_stations=stations_2,
        satellite_passes=[
            SatellitePassCreate(pass_id="PASS-DISASTER-01", satellite_id="SAT-FIREWATCH-1", ground_station_id="GS-SVALBARD", start_time=datetime(2026, 10, 10, 14, 0, 0, tzinfo=timezone.utc), end_time=datetime(2026, 10, 10, 14, 8, 0, tzinfo=timezone.utc), max_elevation_deg=78.0, priority=1, data_volume_gb=40.0, required_bandwidth_mbps=700.0, channel_band="Ka-band"),
            SatellitePassCreate(pass_id="PASS-DISASTER-02", satellite_id="SAT-FLOODSCAN-2", ground_station_id="GS-SVALBARD", start_time=datetime(2026, 10, 10, 14, 5, 0, tzinfo=timezone.utc), end_time=datetime(2026, 10, 10, 14, 14, 0, tzinfo=timezone.utc), max_elevation_deg=62.0, priority=1, data_volume_gb=38.0, required_bandwidth_mbps=650.0, channel_band="X-band"),
            SatellitePassCreate(pass_id="PASS-ROUTINE-03", satellite_id="SAT-METEO-9", ground_station_id="GS-SVALBARD", start_time=datetime(2026, 10, 10, 14, 12, 0, tzinfo=timezone.utc), end_time=datetime(2026, 10, 10, 14, 22, 0, tzinfo=timezone.utc), max_elevation_deg=44.0, priority=4, data_volume_gb=18.0, required_bandwidth_mbps=250.0, channel_band="S-band"),
            SatellitePassCreate(pass_id="PASS-DISASTER-04", satellite_id="SAT-FIREWATCH-1", ground_station_id="GS-FAIRBANKS", start_time=datetime(2026, 10, 10, 15, 30, 0, tzinfo=timezone.utc), end_time=datetime(2026, 10, 10, 15, 40, 0, tzinfo=timezone.utc), max_elevation_deg=71.0, priority=1, data_volume_gb=42.0, required_bandwidth_mbps=600.0, channel_band="Ka-band"),
            SatellitePassCreate(pass_id="PASS-COMM-05", satellite_id="SAT-IOT-RELAY", ground_station_id="GS-FAIRBANKS", start_time=datetime(2026, 10, 10, 15, 35, 0, tzinfo=timezone.utc), end_time=datetime(2026, 10, 10, 15, 45, 0, tzinfo=timezone.utc), max_elevation_deg=35.0, priority=5, data_volume_gb=8.0, required_bandwidth_mbps=150.0, channel_band="S-band"),
        ],
    )

    return [scen_contention, scen_baseline, scen_disaster]


async def seed_standard_datasets(session: AsyncSession) -> None:
    """Seed or update standard scenario datasets into the database."""
    service = DatasetService(session)
    scenarios = get_standard_scenarios()
    
    for sc in scenarios:
        try:
            await service.create_dataset(sc)
            logger.info("Successfully seeded dataset scenario '%s' (ID: %s)", sc.name, sc.dataset_id)
        except Exception as exc:
            logger.warning("Could not seed dataset scenario '%s': %s", sc.name, exc)
