from datetime import datetime, timezone
import inspect
import logging
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ResourceNotFoundError, SchedulingEngineError
from app.db.models.execution import PassExecutionModel
from app.db.models.outage import OutageModel
from app.db.models.schedule import (
    ScheduledAllocationModel,
    ScheduleRunModel,
)
from app.schemas.dataset import DatasetRead
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
from app.services.execution_service import ExecutionService
from app.services.scheduler.models import TimeWindow
from app.services.scheduler_interface import BaseSchedulerEngine

logger = logging.getLogger(__name__)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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
        self.execution_service = ExecutionService(db)

    async def _get_active_outages(self, dataset: DatasetRead) -> Dict[str, List[TimeWindow]]:
        """Retrieve active outages for stations participating in the dataset."""
        station_ids = [gs.station_id for gs in dataset.ground_stations]
        stmt = select(OutageModel).where(
            OutageModel.station_id.in_(station_ids),
            OutageModel.status.in_(["active", "ACTIVE"]),
        )
        outage_rows = (await self.db.execute(stmt)).scalars().all()
        outages_by_station: Dict[str, List[TimeWindow]] = {}
        for o in outage_rows:
            outages_by_station.setdefault(o.station_id, []).append(
                TimeWindow(
                    start_time=_ensure_utc(o.start_time),
                    end_time=_ensure_utc(o.end_time),
                )
            )
        return outages_by_station

    async def _invoke_engine_method(
        self,
        method,
        dataset: DatasetRead,
        request,
        outages_by_station=None,
        locked_tasks=None,
    ) -> ScheduleRunResponse:
        sig = inspect.signature(method)
        params = sig.parameters
        has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
        kwargs = {}
        if has_var_kw or "outages_by_station" in params:
            kwargs["outages_by_station"] = outages_by_station
        if has_var_kw or "locked_tasks" in params:
            kwargs["locked_tasks"] = locked_tasks
        return await method(dataset=dataset, request=request, **kwargs)

    async def execute_baseline(
        self,
        request: BaselineScheduleRequest,
    ) -> ScheduleRunResponse:
        """Run baseline FCFS algorithm with active outages and locked tasks, and persist results."""
        dataset = await self.dataset_service.get_dataset(request.dataset_id)
        outages_by_station = await self._get_active_outages(dataset)
        locked_pass_ids = await self.execution_service.get_locked_pass_ids(dataset_id=request.dataset_id)
        locked_tasks = None
        if locked_pass_ids and hasattr(self.scheduler_engine, "_extract_locked_tasks"):
            locked_tasks = self.scheduler_engine._extract_locked_tasks(dataset, locked_pass_ids, None)

        try:
            result = await self._invoke_engine_method(
                self.scheduler_engine.schedule_baseline,
                dataset=dataset,
                request=request,
                outages_by_station=outages_by_station,
                locked_tasks=locked_tasks,
            )
        except Exception as exc:
            logger.error("Baseline scheduling engine failed: %s", exc, exc_info=True)
            raise SchedulingEngineError(
                message=f"Baseline scheduling engine failed for dataset '{request.dataset_id}': {str(exc)}"
            ) from exc

        await self._persist_run(result, parameters=request.model_dump(mode="json"))
        await self.execution_service.sync_executions_from_run(result)
        return await self.get_schedule_run(result.run_id)

    async def execute_optimize(
        self,
        request: OptimizeScheduleRequest,
    ) -> ScheduleRunResponse:
        """Run CP-SAT optimization with active outages and locked tasks, and persist results."""
        dataset = await self.dataset_service.get_dataset(request.dataset_id)
        outages_by_station = await self._get_active_outages(dataset)
        locked_pass_ids = await self.execution_service.get_locked_pass_ids(dataset_id=request.dataset_id)
        locked_tasks = None
        if locked_pass_ids and hasattr(self.scheduler_engine, "_extract_locked_tasks"):
            locked_tasks = self.scheduler_engine._extract_locked_tasks(dataset, locked_pass_ids, None)

        try:
            result = await self._invoke_engine_method(
                self.scheduler_engine.schedule_optimize,
                dataset=dataset,
                request=request,
                outages_by_station=outages_by_station,
                locked_tasks=locked_tasks,
            )
        except Exception as exc:
            logger.error("Optimization scheduling engine failed: %s", exc, exc_info=True)
            raise SchedulingEngineError(
                message=f"CP-SAT optimization solver failed for dataset '{request.dataset_id}': {str(exc)}"
            ) from exc

        await self._persist_run(result, parameters=request.model_dump(mode="json"))
        await self.execution_service.sync_executions_from_run(result)
        return await self.get_schedule_run(result.run_id)

    async def execute_reoptimize(
        self,
        request: OptimizeScheduleRequest,
        previous_run_id: Optional[str] = None,
    ) -> ScheduleRunResponse:
        """Run safe re-optimization preserving previous schedule if candidate is invalid or fails."""
        dataset = await self.dataset_service.get_dataset(request.dataset_id)
        outages_by_station = await self._get_active_outages(dataset)
        previous_schedule = None
        if previous_run_id:
            try:
                previous_schedule = await self.get_schedule_run(previous_run_id)
            except ResourceNotFoundError:
                logger.warning("Previous run ID '%s' not found for re-optimization fallback.", previous_run_id)

        locked_pass_ids = await self.execution_service.get_locked_pass_ids(dataset_id=request.dataset_id)

        try:
            if hasattr(self.scheduler_engine, "safe_reoptimize"):
                sig = inspect.signature(self.scheduler_engine.safe_reoptimize)
                kwargs = {
                    "dataset": dataset,
                    "request": request,
                    "previous_schedule": previous_schedule,
                    "locked_pass_ids": locked_pass_ids,
                }
                if "outages_by_station" in sig.parameters:
                    kwargs["outages_by_station"] = outages_by_station
                result = await self.scheduler_engine.safe_reoptimize(**kwargs)
            else:
                locked_tasks = None
                if locked_pass_ids and hasattr(self.scheduler_engine, "_extract_locked_tasks"):
                    locked_tasks = self.scheduler_engine._extract_locked_tasks(dataset, locked_pass_ids, previous_schedule)
                result = await self._invoke_engine_method(
                    self.scheduler_engine.schedule_optimize,
                    dataset=dataset,
                    request=request,
                    outages_by_station=outages_by_station,
                    locked_tasks=locked_tasks,
                )
        except Exception as exc:
            logger.error("Re-optimization scheduling engine failed: %s", exc, exc_info=True)
            if previous_schedule and previous_schedule.is_valid:
                logger.info("Preserving previous valid schedule '%s' after error.", previous_schedule.run_id)
                return previous_schedule
            raise SchedulingEngineError(
                message=f"Re-optimization failed for dataset '{request.dataset_id}': {str(exc)}"
            ) from exc

        await self._persist_run(result, parameters=request.model_dump(mode="json"))
        await self.execution_service.sync_executions_from_run(result)
        return await self.get_schedule_run(result.run_id)


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

        return await self._to_response_schema_async(run_model)


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

    async def _to_response_schema_async(self, model: ScheduleRunModel) -> ScheduleRunResponse:
        stmt = select(PassExecutionModel).where(PassExecutionModel.dataset_id == model.dataset_id)
        exec_res = await self.db.execute(stmt)
        exec_map = {em.pass_id: em for em in exec_res.scalars().all()}

        scheduled_passes = []
        for sp in model.scheduled_passes:
            em = exec_map.get(sp.pass_id)
            scheduled_passes.append(
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
                    execution_status=em.status if em else "SCHEDULED",
                    is_locked=em.is_locked if em else False,
                    actual_start_time=em.actual_start_time if em else None,
                    actual_end_time=em.actual_end_time if em else None,
                    actual_data_delivered_gb=em.actual_data_delivered_gb if em else None,
                    measured_transfer_rate_mbps=em.measured_transfer_rate_mbps if em else None,
                    estimated_transfer_rate_mbps=em.estimated_transfer_rate_mbps if em else None,
                )
            )

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
            scheduled_passes=scheduled_passes,
            unassigned_passes=[
                UnassignedPass(**up) for up in (model.unassigned_passes or [])
            ],
            metrics=ScheduleMetrics(**model.metrics),
        )

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
