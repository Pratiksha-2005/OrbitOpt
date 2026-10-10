"""Operational Analytics, Reporting, and Deadline Risk endpoints."""

from typing import Annotated, Literal, Optional
from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_analytics_service
from app.schemas.analytics import (
    BenchmarkComparisonMetric,
    DeadlineRiskSummary,
    OperationalAnalyticsResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Operational Analytics & Reports"])


@router.get(
    "/runs/{run_id}",
    response_model=OperationalAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Comprehensive Operational Analytics",
    description="Calculates real operational metrics: planned vs actual volume, critical service rate, waiting times, station availability post-outage, and time-based resource utilization.",
)
async def get_run_operational_analytics(
    run_id: str,
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> OperationalAnalyticsResponse:
    """Retrieve operational KPIs and audit analytics for a schedule run."""
    return await service.get_operational_analytics(run_id)


@router.get(
    "/runs/{run_id}/deadline-risks",
    response_model=DeadlineRiskSummary,
    status_code=status.HTTP_200_OK,
    summary="Perform Rule-Based Deterministic Deadline Risk Analysis",
    description="Identifies passes at risk of missing deadlines using remaining time, transfer duration, antenna slew margins, and active station outages.",
)
async def get_run_deadline_risk_analysis(
    run_id: str,
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> DeadlineRiskSummary:
    """Execute rule-based deadline risk evaluation for a schedule run."""
    return await service.get_deadline_risk_analysis(run_id)


@router.get(
    "/runs/{run_id}/export",
    summary="Export Mission Schedule Run and Operational Report",
    description="Exports complete schedule results, execution measurements, and operational metrics in CSV or JSON format.",
)
async def export_mission_report(
    run_id: str,
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    export_format: Literal["json", "csv"] = Query(
        default="json",
        alias="format",
        description="Desired export file format ('json' or 'csv')",
    ),
):
    """Export mission performance and schedule run in CSV or JSON."""
    result = await service.export_mission_report(run_id, export_format=export_format)
    if export_format == "csv":
        return Response(
            content=result,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="mission_report_{run_id}.csv"',
                "Cache-Control": "no-cache",
            },
        )
    return result
