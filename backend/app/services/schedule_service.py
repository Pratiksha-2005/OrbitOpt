"""Service for executing scheduling algorithms and persisting run outcomes."""

import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ResourceNotFoundError, SchedulingEngineError
from app.db.models.schedule import (
    ScheduledAllocationModel,
    ScheduleRunModel,
)
from app.schemas.metrics import ScheduleMetrics
from app.schemas.schedule import (
    AlgorithmType,
    BaselineScheduleRequest,
    OptimizeScheduleRequest,
    ScheduledPass,
    ScheduleRunResponse,
    ScheduleStatus,
    UnassignedPass,
)
from app.services.dataset_service import DatasetService
from app.services.scheduler_interface import BaseSchedulerEngine

logger = logging.getLogger(__name__)


class ScheduleService:
    """Service layer for running schedules and persisting results."""

    def __init__(
        self,
        db: AsyncSession,
        scheduler_engine: BaseSchedulerEngine,
    ) -> None:
        self.db = db
        self.scheduler_engine = scheduler_engine
        self.dataset_service = DatasetService(db)

    async def execute_baseline(
        self,
        request: BaselineScheduleRequest,
    ) -> ScheduleRunResponse:
        """Run baseline FCFS algorithm and persist results."""
        dataset = await self.dataset_service.get_dataset(request.dataset_id)
        
        try:
            result = await self.scheduler_engine.schedule_baseline(dataset, request)
        except Exception as exc:
            logger.error("Baseline scheduling engine failed: %s", exc, exc_info=True)
            raise SchedulingEngineError(
                message=f"Baseline scheduling engine failed for dataset '{request.dataset_id}': {str(exc)}"
            ) from exc

        await self._persist_run(result, parameters=request.model_dump(mode="json"))
        return result

    async def execute_optimize(
        self,
        request: OptimizeScheduleRequest,
    ) -> ScheduleRunResponse:
        """Run CP-SAT optimization and persist results."""
        dataset = await self.dataset_service.get_dataset(request.dataset_id)

        try:
            result = await self.scheduler_engine.schedule_optimize(dataset, request)
        except Exception as exc:
            logger.error("Optimization scheduling engine failed: %s", exc, exc_info=True)
            raise SchedulingEngineError(
                message=f"CP-SAT optimization solver failed for dataset '{request.dataset_id}': {str(exc)}"
            ) from exc

        await self._persist_run(result, parameters=request.model_dump(mode="json"))
        return result

    async def execute_reoptimize(
        self,
        request: OptimizeScheduleRequest,
        previous_run_id: Optional[str] = None,
    ) -> ScheduleRunResponse:
        """Run safe re-optimization preserving previous schedule if candidate is invalid or fails."""
        dataset = await self.dataset_service.get_dataset(request.dataset_id)
        previous_schedule = None
        if previous_run_id:
            try:
                previous_schedule = await self.get_schedule_run(previous_run_id)
            except ResourceNotFoundError:
                logger.warning("Previous run ID '%s' not found for re-optimization fallback.", previous_run_id)

        try:
            if hasattr(self.scheduler_engine, "safe_reoptimize"):
                result = await self.scheduler_engine.safe_reoptimize(
                    dataset=dataset,
                    request=request,
                    previous_schedule=previous_schedule,
                )
            else:
                result = await self.scheduler_engine.schedule_optimize(dataset, request)
        except Exception as exc:
            logger.error("Re-optimization scheduling engine failed: %s", exc, exc_info=True)
            if previous_schedule and previous_schedule.is_valid:
                logger.info("Preserving previous valid schedule '%s' after error.", previous_schedule.run_id)
                return previous_schedule
            raise SchedulingEngineError(
                message=f"Re-optimization failed for dataset '{request.dataset_id}': {str(exc)}"
            ) from exc

        await self._persist_run(result, parameters=request.model_dump(mode="json"))
        return result

    async def get_schedule_run(self, run_id: str) -> ScheduleRunResponse:
        """Retrieve a previous schedule run from database."""
        stmt = (
            select(ScheduleRunModel)
            .where(ScheduleRunModel.id == run_id)
            .options(selectinload(ScheduleRunModel.scheduled_passes))
        )
        result = await self.db.execute(stmt)
        run_model = result.scalar_one_or_none()

        if not run_model:
            raise ResourceNotFoundError(resource="Schedule Run", resource_id=run_id)

        return self._to_response_schema(run_model)

    async def get_schedule_metrics(self, run_id: str) -> ScheduleMetrics:
        """Retrieve only the metrics and KPI summary of a run."""
        run = await self.get_schedule_run(run_id)
        return run.metrics

    async def _persist_run(
        self,
        response: ScheduleRunResponse,
        parameters: dict,
    ) -> None:
        """Store the run record and allocated passes in the database."""
        run_model = ScheduleRunModel(
            id=response.run_id,
            dataset_id=response.dataset_id,
            algorithm=response.algorithm.value,
            status=response.status.value,
            is_mock=response.is_mock,
            is_valid=response.is_valid,
            validation_violations=response.validation_violations,
            solver_status_detail=response.solver_status_detail,
            execution_time_ms=response.execution_time_ms,
            parameters=parameters,
            metrics=response.metrics.model_dump(mode="json"),
            unassigned_passes=[p.model_dump(mode="json") for p in response.unassigned_passes],
        )

        for sp in response.scheduled_passes:
            run_model.scheduled_passes.append(
                ScheduledAllocationModel(
                    pass_id=sp.pass_id,
                    satellite_id=sp.satellite_id,
                    ground_station_id=sp.ground_station_id,
                    start_time=sp.start_time,
                    end_time=sp.end_time,
                    duration_seconds=sp.duration_seconds,
                    data_volume_gb=sp.data_volume_gb,
                    priority=sp.priority,
                )
            )

        self.db.add(run_model)
        await self.db.commit()

    def _to_response_schema(self, model: ScheduleRunModel) -> ScheduleRunResponse:
        return ScheduleRunResponse(
            run_id=model.id,
            dataset_id=model.dataset_id,
            algorithm=AlgorithmType(model.algorithm),
            status=ScheduleStatus(model.status),
            is_mock=model.is_mock,
            is_valid=model.is_valid,
            validation_violations=model.validation_violations or [],
            solver_status_detail=model.solver_status_detail,
            created_at=model.created_at,
            execution_time_ms=model.execution_time_ms,
            scheduled_passes=[
                ScheduledPass(
                    pass_id=sp.pass_id,
                    satellite_id=sp.satellite_id,
                    ground_station_id=sp.ground_station_id,
                    start_time=sp.start_time,
                    end_time=sp.end_time,
                    duration_seconds=sp.duration_seconds,
                    data_volume_gb=sp.data_volume_gb,
                    transferable_data_gb=sp.data_volume_gb,
                    priority=sp.priority,
                )
                for sp in model.scheduled_passes
            ],
            unassigned_passes=[
                UnassignedPass(**up) for up in (model.unassigned_passes or [])
            ],
            metrics=ScheduleMetrics(**model.metrics),
        )
