"""Pytest fixtures for OrbitOpt backend tests."""

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import get_db
from app.db.base import Base
from app.main import app

# In-memory test SQLite engine
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create fresh in-memory database tables for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI AsyncClient fixture overriding database session dependency."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_dataset_payload() -> dict:
    """Standard valid dataset creation payload."""
    return {
        "name": "Test Scenario Alpha",
        "description": "Integration test scenario with 2 ground stations and 3 satellite passes",
        "ground_stations": [
            {
                "station_id": "GS-SVALBARD",
                "name": "Svalbard Ground Station",
                "latitude_deg": 78.2297,
                "longitude_deg": 15.4077,
                "elevation_mask_deg": 5.0,
                "max_concurrent_passes": 1,
                "supported_bands": ["S-band", "X-band"],
            },
            {
                "station_id": "GS-PUNTA_ARENAS",
                "name": "Punta Arenas Station",
                "latitude_deg": -53.1638,
                "longitude_deg": -70.9171,
                "elevation_mask_deg": 5.0,
                "max_concurrent_passes": 1,
                "supported_bands": ["X-band", "Ka-band"],
            },
        ],
        "satellite_passes": [
            {
                "pass_id": "PASS-SAT1-001",
                "satellite_id": "SAT-1",
                "ground_station_id": "GS-SVALBARD",
                "start_time": "2026-10-10T10:00:00Z",
                "end_time": "2026-10-10T10:10:00Z",
                "max_elevation_deg": 45.0,
                "priority": 1,
                "data_volume_gb": 50.0,
                "channel_band": "X-band",
            },
            {
                "pass_id": "PASS-SAT2-001",
                "satellite_id": "SAT-2",
                "ground_station_id": "GS-SVALBARD",
                "start_time": "2026-10-10T10:05:00Z",
                "end_time": "2026-10-10T10:15:00Z",
                "max_elevation_deg": 30.0,
                "priority": 2,
                "data_volume_gb": 35.0,
                "channel_band": "X-band",
            },
            {
                "pass_id": "PASS-SAT1-002",
                "satellite_id": "SAT-1",
                "ground_station_id": "GS-PUNTA_ARENAS",
                "start_time": "2026-10-10T11:00:00Z",
                "end_time": "2026-10-10T11:12:00Z",
                "max_elevation_deg": 65.0,
                "priority": 1,
                "data_volume_gb": 60.0,
                "channel_band": "Ka-band",
            },
        ],
    }
