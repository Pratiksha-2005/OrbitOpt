"""Dynamic Priority Scoring Engine for OrbitOpt.

Computes multi-factor priority scores combining:
- Emergency Severity (E = 0.40)
- Deadline Urgency (U = 0.30)
- Data Freshness (F = 0.10)
- Waiting-Time Anti-Starvation (W = 0.20)
All scores are bounded in [0.0, 100.0].
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, model_validator


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class DynamicPriorityWeights(BaseModel):
    """Configurable weights for dynamic multi-factor scoring. Sum must equal 1.0."""

    emergency_weight: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description="Weight E for emergency and mission criticality tier",
    )
    urgency_weight: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Weight U for deadline urgency and time-to-loss",
    )
    freshness_weight: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Weight F for data generation freshness",
    )
    waiting_weight: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Weight W for waiting-time anti-starvation aging",
    )

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "DynamicPriorityWeights":
        total = (
            self.emergency_weight
            + self.urgency_weight
            + self.freshness_weight
            + self.waiting_weight
        )
        if abs(total - 1.0) > 1e-5:
            raise ValueError(
                f"Dynamic priority weights must sum to 1.0 (E+U+F+W = {total:.4f})"
            )
        return self


class PriorityScoreBreakdown(BaseModel):
    """Transparent factor breakdown and explanation for operators."""

    emergency_score: float = Field(..., ge=0.0, le=100.0, description="Emergency severity [0-100]")
    urgency_score: float = Field(..., ge=0.0, le=100.0, description="Deadline urgency [0-100]")
    freshness_score: float = Field(..., ge=0.0, le=100.0, description="Data freshness [0-100]")
    waiting_score: float = Field(..., ge=0.0, le=100.0, description="Waiting-time aging [0-100]")
    combined_score: float = Field(..., ge=0.0, le=100.0, description="Final weighted score [0-100]")
    explanation: str = Field(..., description="Human-readable rationale for operator audit")


class DynamicPriorityScorer:
    """Authoritative scoring policy evaluating multi-factor priority."""

    DEFAULT_WEIGHTS = DynamicPriorityWeights(
        emergency_weight=0.40,
        urgency_weight=0.30,
        freshness_weight=0.10,
        waiting_weight=0.20,
    )

    # Base emergency points per priority level
    PRIORITY_EMERGENCY_MAP = {
        1: 100.0,  # Critical / Disaster / Threat
        2: 75.0,   # High / Operational Science
        3: 50.0,   # Medium / Standard Downlink
        4: 25.0,   # Low / Routine Telemetry
        5: 10.0,   # Lowest / Background Dump
    }

    def __init__(self, weights: Optional[DynamicPriorityWeights] = None) -> None:
        self.weights = weights or self.DEFAULT_WEIGHTS

    def calculate_emergency_score(self, priority: int, is_emergency: bool = False) -> float:
        """Derive emergency severity score S_E in [0, 100]."""
        if is_emergency or priority == 1:
            return 100.0
        return float(self.PRIORITY_EMERGENCY_MAP.get(priority, 50.0))

    def calculate_urgency_score(
        self,
        start_time: Optional[datetime],
        deadline: Optional[datetime],
        evaluation_time: datetime,
    ) -> float:
        """
        Derive deadline urgency score S_U in [0, 100].
        
        Urgency increases as time remaining to pass start or deadline approaches 0.
        Explicitly handles past/stale/future timestamps without false urgency.
        """
        eval_utc = _ensure_utc(evaluation_time)
        target_time = _ensure_utc(deadline or start_time)

        if not target_time or not eval_utc:
            return 50.0  # Neutral fallback when no timestamp exists

        delta_sec = (target_time - eval_utc).total_seconds()

        # Stale or missed pass (in the past relative to evaluation)
        if delta_sec < -300:  # More than 5 mins in the past
            return 0.0

        # Currently active or imminent within 15 minutes
        if delta_sec <= 900:
            return 100.0

        # Within 1 hour (900s to 3600s) -> 80.0 to 100.0
        if delta_sec <= 3600:
            fraction = (3600 - delta_sec) / (3600 - 900)
            return round(80.0 + fraction * 20.0, 2)

        # Within 6 hours (3600s to 21600s) -> 40.0 to 80.0
        if delta_sec <= 21600:
            fraction = (21600 - delta_sec) / (21600 - 3600)
            return round(40.0 + fraction * 40.0, 2)

        # Within 24 hours (21600s to 86400s) -> 10.0 to 40.0
        if delta_sec <= 86400:
            fraction = (86400 - delta_sec) / (86400 - 21600)
            return round(10.0 + fraction * 30.0, 2)

        # Beyond 24 hours -> Low baseline urgency decaying to 0
        decay = max(0.0, 10.0 - ((delta_sec - 86400) / 86400) * 5.0)
        return round(decay, 2)

    def calculate_freshness_score(
        self,
        data_generated_at: Optional[datetime],
        evaluation_time: datetime,
    ) -> float:
        """
        Derive data freshness score S_F in [0, 100].
        
        Newer generated satellite data has highest freshness (100).
        Stale/old data decays over a 48-hour operational horizon.
        """
        eval_utc = _ensure_utc(evaluation_time)
        gen_utc = _ensure_utc(data_generated_at)

        if not gen_utc or not eval_utc:
            return 70.0  # Reasonable default for typical telemetry batches

        age_sec = (eval_utc - gen_utc).total_seconds()

        # Generated in the future (clock skew or prospective task) -> cap at 100
        if age_sec <= 0:
            return 100.0

        # Fresh data within 1 hour -> 90 to 100
        if age_sec <= 3600:
            fraction = (3600 - age_sec) / 3600
            return round(90.0 + fraction * 10.0, 2)

        # 1 to 12 hours -> 50 to 90
        if age_sec <= 43200:
            fraction = (43200 - age_sec) / (43200 - 3600)
            return round(50.0 + fraction * 40.0, 2)

        # 12 to 48 hours -> 10 to 50
        if age_sec <= 172800:
            fraction = (172800 - age_sec) / (172800 - 43200)
            return round(10.0 + fraction * 40.0, 2)

        # Beyond 48 hours -> Stale historical data
        return 5.0

    def calculate_waiting_score(
        self,
        created_at: Optional[datetime],
        evaluation_time: datetime,
    ) -> float:
        """
        Derive anti-starvation waiting-time score S_W in [0, 100].
        
        Prevents low-priority passes from starving indefinitely.
        Score rises smoothly as wait time increases from 0 to 24 hours.
        """
        eval_utc = _ensure_utc(evaluation_time)
        created_utc = _ensure_utc(created_at)

        if not created_utc or not eval_utc:
            return 20.0  # Baseline neutral waiting points

        wait_sec = (eval_utc - created_utc).total_seconds()

        if wait_sec <= 0:
            return 0.0  # Just submitted

        # Rises to 100 after 24 hours of waiting
        hours_waiting = wait_sec / 3600.0
        score = min(100.0, (hours_waiting / 24.0) * 100.0)
        return round(score, 2)

    def evaluate_pass(
        self,
        priority: int,
        start_time: Optional[datetime] = None,
        deadline: Optional[datetime] = None,
        data_generated_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        is_emergency: bool = False,
        evaluation_time: Optional[datetime] = None,
    ) -> PriorityScoreBreakdown:
        """Compute complete multi-factor priority breakdown for a pass opportunity."""
        eval_time = _ensure_utc(evaluation_time) or datetime.now(timezone.utc)

        s_e = self.calculate_emergency_score(priority=priority, is_emergency=is_emergency)
        s_u = self.calculate_urgency_score(start_time=start_time, deadline=deadline, evaluation_time=eval_time)
        s_f = self.calculate_freshness_score(data_generated_at=data_generated_at, evaluation_time=eval_time)
        s_w = self.calculate_waiting_score(created_at=created_at, evaluation_time=eval_time)

        combined = (
            self.weights.emergency_weight * s_e
            + self.weights.urgency_weight * s_u
            + self.weights.freshness_weight * s_f
            + self.weights.waiting_weight * s_w
        )
        combined_clamped = max(0.0, min(100.0, round(combined, 2)))

        explanation = (
            f"Score {combined_clamped:.1f} = "
            f"Emergency({s_e:.0f}×{self.weights.emergency_weight:.2f}) + "
            f"Urgency({s_u:.0f}×{self.weights.urgency_weight:.2f}) + "
            f"Freshness({s_f:.0f}×{self.weights.freshness_weight:.2f}) + "
            f"WaitAging({s_w:.0f}×{self.weights.waiting_weight:.2f})"
        )

        return PriorityScoreBreakdown(
            emergency_score=s_e,
            urgency_score=s_u,
            freshness_score=s_f,
            waiting_score=s_w,
            combined_score=combined_clamped,
            explanation=explanation,
        )

    def score_request(
        self,
        priority: int,
        deadline_time: Optional[datetime] = None,
        data_generated_time: Optional[datetime] = None,
        queued_time: Optional[datetime] = None,
        evaluation_time: Optional[datetime] = None,
        is_emergency: bool = False,
    ) -> PriorityScoreBreakdown:
        """Alias for evaluate_pass matching parameter naming."""
        return self.evaluate_pass(
            priority=priority,
            deadline=deadline_time,
            data_generated_at=data_generated_time,
            created_at=queued_time,
            evaluation_time=evaluation_time,
            is_emergency=is_emergency,
        )
