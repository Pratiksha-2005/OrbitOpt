"""API v1 Router aggregation."""

from fastapi import APIRouter
from app.api.v1.endpoints import datasets, health, schedules

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(datasets.router)
api_router.include_router(schedules.router)
