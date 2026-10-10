"""Service for Pass Execution Tracking, State Machine enforcement, and Telemetry."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateTransitionError, ResourceNotFoundError
from app.db.models.execution import PassExecutionModel
from app.schemas.execution import (
    LEGAL_STATE_TRANSITIONS,
    LOCKED_EXECUTION_STATES,
    PassExecutionRead,
    PassExecutionStatus,
    PassExecutionSummary,
    PassExecutionTransitionEvent,
    PassTransitionRequest,
    is_legal_transition,
    is_status_locked,
)
from app.schemas.schedule import ScheduledPass, ScheduleRunResponse

logger = logging.getLogger(__name__)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class ExecutionService:
    """Manages pass lifecycle states, transition legality, measurements, and preemption locks."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_executions(
        self,
        dataset_id: Optional[str] = None,
        schedule_run_id: Optional[str] = None,
        status: Optional[str] = None,
        is_locked: Optional[bool] = None,
    ) -> List[PassExecutionRead]:
        """List pass execution records with optional filtering."""
        stmt = select(PassExecutionModel)
        if dataset_id:
            stmt = stmt.where(PassExecutionModel.dataset_id == dataset_id)
        if schedule_run_id:
            stmt = stmt.where(PassExecutionModel.schedule_run_id == schedule_run_id)
        if status:
            stmt = stmt.where(PassExecutionModel.status == status.upper())
        if is_locked is not None:
            stmt = stmt.where(PassExecutionModel.is_locked == is_locked)

        stmt = stmt.order_by(PassExecutionModel.planned_start_time.asc())
        result = await self.db.execute(stmt)
        models = result.scalars().all()
        return [self._to_read_schema(m) for m in models]

    async def get_execution(self, pass_id: str) -> PassExecutionRead:
        """Fetch execution record for a specific pass ID."""
        stmt = select(PassExecutionModel).where(PassExecutionModel.pass_id == pass_id)
        result = await self.db.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise ResourceNotFoundError(resource="Pass execution", resource_id=pass_id)
        return self._to_read_schema(model)

    async def get_locked_pass_ids(self, dataset_id: Optional[str] = None) -> List[str]:
        """Retrieve pass IDs that are strictly locked against ordinary re-optimization or preemption.
        
        Locked states: ACQUIRING, TRANSMITTING, COMPLETED.
        SCHEDULED future passes are NOT locked.
        MISSED and CANCELLED passes are NOT locked.
        Unknown execution states are explicitly handled and NEVER locked merely because planned start is in the past.
        """
        stmt = select(PassExecutionModel.pass_id).where(
            PassExecutionModel.status.in_(["ACQUIRING", "TRANSMITTING", "COMPLETED"])
        )
        if dataset_id:
            stmt = stmt.where(PassExecutionModel.dataset_id == dataset_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def transition_execution(
        self,
        pass_id: str,
        request: PassTransitionRequest,
    ) -> PassExecutionRead:
        """Execute and validate a state transition for a satellite pass."""
        stmt = select(PassExecutionModel).where(PassExecutionModel.pass_id == pass_id)
        result = await self.db.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise ResourceNotFoundError(resource="Pass execution", resource_id=pass_id)

        current_status = PassExecutionStatus(model.status)
        target_status = request.to_status

        # 1. Reject duplicate updates to identical state
        if current_status == target_status:
            raise InvalidStateTransitionError(
                message=f"Duplicate execution update: Pass '{pass_id}' is already in state '{current_status.value}'."
            )

        # 2. Reject illegal state transitions
        if not is_legal_transition(current_status, target_status):
            allowed = [s.value for s in LEGAL_STATE_TRANSITIONS.get(current_status, set())]
            allowed_desc = ", ".join(allowed) if allowed else "none (terminal state)"
            raise InvalidStateTransitionError(
                message=(
                    f"Illegal state transition: Cannot transition pass '{pass_id}' "
                    f"from '{current_status.value}' to '{target_status.value}'. "
                    f"Allowed transitions from '{current_status.value}' are: [{allowed_desc}]."
                )
            )

        now_utc = _ensure_utc(request.timestamp) or datetime.now(timezone.utc)

        # 3. Handle actual timestamps and timestamp ordering
        actual_start = _ensure_utc(request.actual_start_time)
        actual_end = _ensure_utc(request.actual_end_time)

        if actual_start is not None:
            model.actual_start_time = actual_start
        elif target_status in (PassExecutionStatus.ACQUIRING, PassExecutionStatus.TRANSMITTING) and model.actual_start_time is None:
            model.actual_start_time = now_utc

        if actual_end is not None:
            model.actual_end_time = actual_end
        elif target_status in (PassExecutionStatus.COMPLETED, PassExecutionStatus.MISSED, PassExecutionStatus.CANCELLED):
            if model.actual_end_time is None:
                model.actual_end_time = now_utc

        start_utc = _ensure_utc(model.actual_start_time)
        end_utc = _ensure_utc(model.actual_end_time)
        model.actual_start_time = start_utc
        model.actual_end_time = end_utc

        # Validate timestamp ordering
        if start_utc and end_utc:
            if end_utc < start_utc:
                raise InvalidStateTransitionError(
                    message=(
                        f"Invalid timestamps: actual_end_time ({end_utc.isoformat()}) "
                        f"cannot be earlier than actual_start_time ({start_utc.isoformat()})."
                    )
                )

        # 4. Handle measurements (distinguishing planned vs actual delivered volume, and estimated vs measured rate)
        if request.actual_data_delivered_gb is not None:
            model.actual_data_delivered_gb = request.actual_data_delivered_gb
        elif target_status == PassExecutionStatus.COMPLETED and model.actual_data_delivered_gb is None:
            # In simulation mode or default completion without explicit telemetry, use planned volume
            model.actual_data_delivered_gb = model.planned_data_volume_gb

        if request.measured_transfer_rate_mbps is not None:
            model.measured_transfer_rate_mbps = request.measured_transfer_rate_mbps
        elif model.actual_data_delivered_gb is not None and start_utc and end_utc:
            duration_sec = (end_utc - start_utc).total_seconds()
            if duration_sec > 0:
                model.measured_transfer_rate_mbps = round((model.actual_data_delivered_gb * 8000.0) / duration_sec, 2)


        model.telemetry_source = request.telemetry_source
        if request.notes:
            model.notes = request.notes

        # 5. Apply new state and lock status
        model.status = target_status.value
        model.is_locked = is_status_locked(target_status)

        # 6. Record transition event in chronological audit history
        transition_event = {
            "from_status": current_status.value,
            "to_status": target_status.value,
            "timestamp": now_utc.isoformat(),
            "actual_start_time": model.actual_start_time.isoformat() if model.actual_start_time else None,
            "actual_end_time": model.actual_end_time.isoformat() if model.actual_end_time else None,
            "actual_data_delivered_gb": model.actual_data_delivered_gb,
            "measured_transfer_rate_mbps": model.measured_transfer_rate_mbps,
            "telemetry_source": model.telemetry_source,
            "notes": request.notes,
        }
        history = list(model.transition_history or [])
        history.append(transition_event)
        model.transition_history = history

        await self.db.commit()
        await self.db.refresh(model)
        logger.info(
            "Pass '%s' transitioned: %s -> %s (locked=%s, delivered=%.2fGB)",
            pass_id,
            current_status.value,
            target_status.value,
            model.is_locked,
            model.actual_data_delivered_gb or 0.0,
        )
        return self._to_read_schema(model)

    async def sync_executions_from_run(self, run_response: ScheduleRunResponse) -> None:
        """Create or update execution records from a schedule run.
        
        - Passes in active/locked/terminal states (ACQUIRING, TRANSMITTING, COMPLETED, MISSED, CANCELLED)
          are PRESERVED and never overwritten.
        - Un-tracked passes are initialized in SCHEDULED status.
        - Existing SCHEDULED passes have their planned timings updated.
        """
        for sp in run_response.scheduled_passes:
            stmt = select(PassExecutionModel).where(PassExecutionModel.pass_id == sp.pass_id)
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                now_utc = datetime.now(timezone.utc)
                initial_event = {
                    "from_status": None,
                    "to_status": PassExecutionStatus.SCHEDULED.value,
                    "timestamp": now_utc.isoformat(),
                    "telemetry_source": "scheduler_allocation",
                    "notes": f"Initial scheduled allocation in run {run_response.run_id}",
                }
                new_model = PassExecutionModel(
                    pass_id=sp.pass_id,
                    dataset_id=run_response.dataset_id,
                    schedule_run_id=run_response.run_id,
                    satellite_id=sp.satellite_id,
                    ground_station_id=sp.ground_station_id,
                    status=PassExecutionStatus.SCHEDULED.value,
                    is_locked=False,
                    planned_start_time=_ensure_utc(sp.start_time),
                    planned_end_time=_ensure_utc(sp.end_time),
                    planned_data_volume_gb=sp.data_volume_gb,
                    estimated_transfer_rate_mbps=getattr(sp, "effective_data_rate_mbps", None) or 150.0,
                    telemetry_source="simulated",
                    transition_history=[initial_event],
                )
                self.db.add(new_model)
            else:
                # If currently SCHEDULED, update planned parameters
                if existing.status == PassExecutionStatus.SCHEDULED.value:
                    existing.schedule_run_id = run_response.run_id
                    existing.planned_start_time = _ensure_utc(sp.start_time)
                    existing.planned_end_time = _ensure_utc(sp.end_time)
                    existing.planned_data_volume_gb = sp.data_volume_gb

        await self.db.commit()

    async def get_execution_summary(self, dataset_id: Optional[str] = None) -> PassExecutionSummary:
        """Calculate state machine aggregate metrics across passes."""
        executions = await self.list_executions(dataset_id=dataset_id)
        total = len(executions)

        status_counts = {
            PassExecutionStatus.SCHEDULED: 0,
            PassExecutionStatus.ACQUIRING: 0,
            PassExecutionStatus.TRANSMITTING: 0,
            PassExecutionStatus.COMPLETED: 0,
            PassExecutionStatus.MISSED: 0,
            PassExecutionStatus.CANCELLED: 0,
        }

        locked_count = 0
        total_planned_vol = 0.0
        total_actual_delivered = 0.0

        for ex in executions:
            if ex.status in status_counts:
                status_counts[ex.status] += 1
            if ex.is_locked:
                locked_count += 1
            total_planned_vol += ex.planned_data_volume_gb
            if ex.actual_data_delivered_gb is not None:
                total_actual_delivered += ex.actual_data_delivered_gb

        return PassExecutionSummary(
            total_passes=total,
            scheduled_count=status_counts[PassExecutionStatus.SCHEDULED],
            acquiring_count=status_counts[PassExecutionStatus.ACQUIRING],
            transmitting_count=status_counts[PassExecutionStatus.TRANSMITTING],
            completed_count=status_counts[PassExecutionStatus.COMPLETED],
            missed_count=status_counts[PassExecutionStatus.MISSED],
            cancelled_count=status_counts[PassExecutionStatus.CANCELLED],
            locked_passes_count=locked_count,
            total_planned_volume_gb=round(total_planned_vol, 2),
            total_actual_delivered_gb=round(total_actual_delivered, 2),
        )

    def _to_read_schema(self, model: PassExecutionModel) -> PassExecutionRead:
        events = []
        for h in model.transition_history or []:
            try:
                events.append(
                    PassExecutionTransitionEvent(
                        from_status=h.get("from_status"),
                        to_status=h.get("to_status", "SCHEDULED"),
                        timestamp=_ensure_utc(datetime.fromisoformat(h["timestamp"])),
                        actual_start_time=_ensure_utc(datetime.fromisoformat(h["actual_start_time"])) if h.get("actual_start_time") else None,
                        actual_end_time=_ensure_utc(datetime.fromisoformat(h["actual_end_time"])) if h.get("actual_end_time") else None,
                        actual_data_delivered_gb=h.get("actual_data_delivered_gb"),
                        measured_transfer_rate_mbps=h.get("measured_transfer_rate_mbps"),
                        telemetry_source=h.get("telemetry_source", "simulated"),
                        notes=h.get("notes"),
                    )
                )
            except Exception:
                pass

        return PassExecutionRead(
            id=model.id,
            pass_id=model.pass_id,
            dataset_id=model.dataset_id,
            schedule_run_id=model.schedule_run_id,
            satellite_id=model.satellite_id,
            ground_station_id=model.ground_station_id,
            status=PassExecutionStatus(model.status),
            is_locked=model.is_locked,
            planned_start_time=_ensure_utc(model.planned_start_time),
            planned_end_time=_ensure_utc(model.planned_end_time),
            planned_data_volume_gb=model.planned_data_volume_gb,
            estimated_transfer_rate_mbps=model.estimated_transfer_rate_mbps,
            actual_start_time=_ensure_utc(model.actual_start_time),
            actual_end_time=_ensure_utc(model.actual_end_time),
            actual_data_delivered_gb=model.actual_data_delivered_gb,
            measured_transfer_rate_mbps=model.measured_transfer_rate_mbps,
            telemetry_source=model.telemetry_source,
            notes=model.notes,
            transition_history=events,
            created_at=_ensure_utc(model.created_at),
            updated_at=_ensure_utc(model.updated_at),
        )
