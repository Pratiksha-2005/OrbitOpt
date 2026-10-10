"""Outage Management and Event-Driven Rescheduling Service."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidOutageError, ResourceNotFoundError
from app.db.models.dataset import DatasetModel, GroundStationModel
from app.db.models.outage import OutageModel
from app.db.models.schedule import ScheduleRunModel
from app.schemas.outage import (
    OutageActionResponse,
    OutageCreate,
    OutageRead,
    OutageStatus,
    OutageUpdate,
)
from app.schemas.schedule import OptimizeScheduleRequest, ScheduleRunResponse
from app.services.dataset_service import DatasetService
from app.services.execution_service import ExecutionService
from app.services.schedule_service import ScheduleService
from app.services.scheduler.models import TimeWindow
from app.services.scheduler_interface import BaseSchedulerEngine

logger = logging.getLogger(__name__)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class OutageService:
    """Service layer for managing ground-station outages and triggering safe re-optimization."""

    def __init__(
        self,
        db: AsyncSession,
        scheduler_engine: BaseSchedulerEngine,
    ) -> None:
        self.db = db
        self.scheduler_engine = scheduler_engine
        self.dataset_service = DatasetService(db)
        self.schedule_service = ScheduleService(db, scheduler_engine)
        self.execution_service = ExecutionService(db)


    async def create_outage(self, payload: OutageCreate) -> OutageActionResponse:
        """Create a validated outage and trigger event-driven safe re-optimization."""
        start_utc = _ensure_utc(payload.start_time)
        end_utc = _ensure_utc(payload.end_time)

        if end_utc <= start_utc:
            raise InvalidOutageError(
                f"Outage end_time ({end_utc.isoformat()}) must be strictly after start_time ({start_utc.isoformat()})"
            )

        # 1. Validate that the ground station exists in database or active datasets
        target_dataset_id = payload.dataset_id
        station_exists = await self._verify_station_exists(payload.station_id, target_dataset_id)
        if not station_exists:
            raise ResourceNotFoundError(
                resource="Ground Station",
                resource_id=payload.station_id,
            )

        # If no dataset_id was explicitly provided, find the primary dataset containing this station
        if not target_dataset_id:
            target_dataset_id = await self._find_dataset_for_station(payload.station_id)

        # 2. Check for duplicate active outage on the same station with identical interval
        existing_dup = await self._find_duplicate_outage(payload.station_id, start_utc, end_utc)
        if existing_dup:
            logger.info("Outage already exists (ID: %s). Avoiding duplicate trigger.", existing_dup.id)
            return OutageActionResponse(
                outage=self._to_read_schema(existing_dup),
                affected_pass_ids=[],
                reoptimized_schedule=None,
                message=f"Duplicate active outage detected on station '{payload.station_id}'. No additional re-optimization triggered.",
            )

        # 3. Persist Outage record
        outage_model = OutageModel(
            station_id=payload.station_id,
            dataset_id=target_dataset_id,
            start_time=start_utc,
            end_time=end_utc,
            reason=payload.reason,
            status=OutageStatus.ACTIVE.value,
            notes=payload.notes,
        )
        self.db.add(outage_model)
        await self.db.commit()
        await self.db.refresh(outage_model)

        # 4. Identify affected passes in target dataset
        affected_pass_ids: List[str] = []
        if target_dataset_id:
            try:
                dataset = await self.dataset_service.get_dataset(target_dataset_id)
                for p in dataset.satellite_passes:
                    if p.ground_station_id == payload.station_id:
                        p_start = _ensure_utc(p.start_time)
                        p_end = _ensure_utc(p.end_time)
                        if p_start < end_utc and p_end > start_utc:
                            affected_pass_ids.append(p.pass_id)
            except Exception as exc:
                logger.warning("Could not evaluate affected passes: %s", exc)

        # 5. Safe Automatic Re-optimization
        reoptimized_run: Optional[ScheduleRunResponse] = None
        if payload.auto_reoptimize and target_dataset_id:
            reoptimized_run = await self._run_safe_reoptimization(
                dataset_id=target_dataset_id,
                outage_id=outage_model.id,
            )
            if reoptimized_run:
                outage_model.auto_reoptimized = True
                outage_model.reoptimization_run_id = reoptimized_run.run_id
                await self.db.commit()

        msg = (
            f"Ground station '{payload.station_id}' outage registered. "
            f"{len(affected_pass_ids)} pass(es) affected. "
        )
        if reoptimized_run:
            msg += f"Safe re-optimization completed (Run ID: {reoptimized_run.run_id}, Valid: {reoptimized_run.is_valid})."
        else:
            msg += "No automatic re-optimization run."

        return OutageActionResponse(
            outage=self._to_read_schema(outage_model),
            affected_pass_ids=affected_pass_ids,
            reoptimized_schedule=reoptimized_run,
            message=msg,
        )

    async def list_outages(
        self,
        station_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[OutageRead]:
        """List outages with optional filtering."""
        stmt = select(OutageModel).order_by(OutageModel.start_time.desc())
        if station_id:
            stmt = stmt.where(OutageModel.station_id == station_id)
        if dataset_id:
            stmt = stmt.where(OutageModel.dataset_id == dataset_id)
        if status:
            stmt = stmt.where(OutageModel.status == status)

        result = await self.db.execute(stmt)
        outages = result.scalars().all()
        return [self._to_read_schema(o) for o in outages]

    async def get_outage(self, outage_id: str) -> OutageRead:
        """Fetch outage record by ID."""
        stmt = select(OutageModel).where(OutageModel.id == outage_id)
        result = await self.db.execute(stmt)
        outage = result.scalar_one_or_none()
        if not outage:
            raise ResourceNotFoundError(resource="Outage", resource_id=outage_id)
        return self._to_read_schema(outage)

    async def resolve_outage(
        self,
        outage_id: str,
        auto_reoptimize: bool = True,
    ) -> OutageActionResponse:
        """Resolve/close an outage and re-optimize to recover station capacity."""
        stmt = select(OutageModel).where(OutageModel.id == outage_id)
        result = await self.db.execute(stmt)
        outage = result.scalar_one_or_none()
        if not outage:
            raise ResourceNotFoundError(resource="Outage", resource_id=outage_id)

        outage.status = OutageStatus.RESOLVED.value
        await self.db.commit()
        await self.db.refresh(outage)

        reoptimized_run: Optional[ScheduleRunResponse] = None
        if auto_reoptimize and outage.dataset_id:
            reoptimized_run = await self._run_safe_reoptimization(
                dataset_id=outage.dataset_id,
                outage_id=outage.id,
            )
            if reoptimized_run:
                outage.reoptimization_run_id = reoptimized_run.run_id
                await self.db.commit()

        msg = (
            f"Outage '{outage_id}' on station '{outage.station_id}' marked as RESOLVED. "
            f"Station capacity restored."
        )
        if reoptimized_run:
            msg += f" Re-optimization scheduled recovered capacity (Run ID: {reoptimized_run.run_id})."

        return OutageActionResponse(
            outage=self._to_read_schema(outage),
            affected_pass_ids=[],
            reoptimized_schedule=reoptimized_run,
            message=msg,
        )

    async def delete_outage(self, outage_id: str) -> None:
        """Delete an outage record."""
        stmt = select(OutageModel).where(OutageModel.id == outage_id)
        result = await self.db.execute(stmt)
        outage = result.scalar_one_or_none()
        if not outage:
            raise ResourceNotFoundError(resource="Outage", resource_id=outage_id)
        await self.db.delete(outage)
        await self.db.commit()

    async def _run_safe_reoptimization(
        self,
        dataset_id: str,
        outage_id: str,
    ) -> Optional[ScheduleRunResponse]:
        """Execute safe re-optimization with active outages and safe fallback."""
        try:
            dataset = await self.dataset_service.get_dataset(dataset_id)
            
            # Fetch all currently active outages for this dataset or associated stations
            station_ids = [gs.station_id for gs in dataset.ground_stations]
            active_outages_stmt = select(OutageModel).where(
                OutageModel.station_id.in_(station_ids),
                OutageModel.status == OutageStatus.ACTIVE.value,
            )
            outages_res = await self.db.execute(active_outages_stmt)
            active_outages = outages_res.scalars().all()

            outages_by_station: Dict[str, List[TimeWindow]] = {}
            for o in active_outages:
                outages_by_station.setdefault(o.station_id, []).append(
                    TimeWindow(
                        start_time=_ensure_utc(o.start_time),
                        end_time=_ensure_utc(o.end_time),
                    )
                )

            # Retrieve most recent valid run for fallback
            latest_run_stmt = (
                select(ScheduleRunModel)
                .where(ScheduleRunModel.dataset_id == dataset_id)
                .order_by(ScheduleRunModel.created_at.desc())
            )
            latest_res = await self.db.execute(latest_run_stmt)
            previous_model = latest_res.scalars().first()
            previous_schedule = None
            if previous_model:
                try:
                    previous_schedule = await self.schedule_service.get_schedule_run(previous_model.id)
                except Exception:
                    pass

            # Query real execution state machine for locked passes (ACQUIRING, TRANSMITTING, COMPLETED).
            # Passes in SCHEDULED, MISSED, CANCELLED or unknown states are NOT locked.
            # Passes are NOT locked merely because their start time is in the past if execution state is unknown.
            locked_pass_ids = await self.execution_service.get_locked_pass_ids(dataset_id=dataset_id)
            if previous_schedule:
                for sp in previous_schedule.scheduled_passes:
                    if getattr(sp, "is_locked", False) or getattr(sp, "execution_status", "") in ("ACQUIRING", "TRANSMITTING", "COMPLETED"):
                        if sp.pass_id not in locked_pass_ids:
                            locked_pass_ids.append(sp.pass_id)

            req = OptimizeScheduleRequest(
                dataset_id=dataset_id,
                time_limit_seconds=15.0,
                setup_time_seconds=120,
            )

            result = await self.scheduler_engine.safe_reoptimize(
                dataset=dataset,
                request=req,
                previous_schedule=previous_schedule,
                locked_pass_ids=locked_pass_ids,
                outages_by_station=outages_by_station,
            )

            # Persist run and sync execution lifecycle records
            await self.schedule_service._persist_run(
                result,
                parameters={
                    "event": "outage_reoptimization",
                    "outage_id": outage_id,
                    "active_outages_count": len(active_outages),
                },
            )
            await self.execution_service.sync_executions_from_run(result)
            return result


        except Exception as exc:
            logger.error("Automatic safe re-optimization failed: %s", exc, exc_info=True)
            return None

    async def _verify_station_exists(self, station_id: str, dataset_id: Optional[str] = None) -> bool:
        stmt = select(GroundStationModel).where(GroundStationModel.station_id == station_id)
        if dataset_id:
            stmt = stmt.where(GroundStationModel.dataset_id == dataset_id)
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    async def _find_dataset_for_station(self, station_id: str) -> Optional[str]:
        stmt = select(GroundStationModel.dataset_id).where(GroundStationModel.station_id == station_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _find_duplicate_outage(
        self,
        station_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[OutageModel]:
        stmt = select(OutageModel).where(
            OutageModel.station_id == station_id,
            OutageModel.start_time == start_time,
            OutageModel.end_time == end_time,
            OutageModel.status == OutageStatus.ACTIVE.value,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    def _to_read_schema(self, model: OutageModel) -> OutageRead:
        dur_sec = (model.end_time - model.start_time).total_seconds()
        return OutageRead(
            id=model.id,
            station_id=model.station_id,
            dataset_id=model.dataset_id,
            start_time=_ensure_utc(model.start_time),
            end_time=_ensure_utc(model.end_time),
            duration_seconds=round(dur_sec, 2),
            reason=model.reason,
            status=OutageStatus(model.status),
            auto_reoptimized=model.auto_reoptimized,
            reoptimization_run_id=model.reoptimization_run_id,
            notes=model.notes,
            created_at=_ensure_utc(model.created_at),
            updated_at=_ensure_utc(model.updated_at),
        )
