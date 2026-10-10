"""FastAPI dependency providers for Database and Services."""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.dataset_service import DatasetService
from app.services.schedule_service import ScheduleService
from app.services.scheduler.real_engine import RealSchedulerEngine
from app.services.scheduler_interface import BaseSchedulerEngine

# Production instance: Developer 1's real FCFS & CP-SAT Scheduler Engine
_scheduler_engine = RealSchedulerEngine()


def get_scheduler_engine() -> BaseSchedulerEngine:
    """Provide the scheduler engine instance."""
    return _scheduler_engine


def get_dataset_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DatasetService:
    """Provide DatasetService with active database session."""
    return DatasetService(db)


def get_schedule_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    scheduler_engine: Annotated[BaseSchedulerEngine, Depends(get_scheduler_engine)],
) -> ScheduleService:
    """Provide ScheduleService with active database session and scheduler engine."""
    return ScheduleService(db=db, scheduler_engine=scheduler_engine)
