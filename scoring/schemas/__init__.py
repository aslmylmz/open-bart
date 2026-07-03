"""
BART Event & Metrics Schemas — Self-Contained Pydantic Models

Defines the data models for BART game events and scoring output.
This is a standalone package — no external schema dependencies required.

Models:
    GameEvent       — A single timestamped event (pump, collect, explode)
    EventPayload    — Flexible payload attached to each event
    GameSession     — Complete session with ordered event log
    ColorMetrics    — Per-color scoring breakdown
    BARTMetrics     — Full scoring output from score_bart()
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ── Game Type Registry ───────────────────────────────────────────────────────


class GameType(str, Enum):
    """Supported cognitive assessment game types."""

    BART_RISK = "BART_RISK"


# ── Event Models ─────────────────────────────────────────────────────────────


class EventPayload(BaseModel):
    """
    Flexible payload attached to each event.

    Each game type defines its own payload shape.
    Using model_config extra="allow" for extensibility.
    """

    model_config = {"extra": "allow"}

    balloon_id: Optional[int] = Field(default=None, description="BART: which balloon")
    color: Optional[str] = Field(
        default=None,
        description="BART: balloon color (purple/teal/orange) for multi-risk profiles",
    )
    balloon_color: Optional[str] = Field(
        default=None,
        description="BART: alternative field name for balloon color",
    )
    stimulus: Optional[str] = Field(default=None, description="Stimulus value")
    response: Optional[str] = Field(default=None, description="Player response")
    position: Optional[int] = Field(default=None, description="Grid/sequence position")


class GameEvent(BaseModel):
    """
    A single timestamped event from a game session.

    This is the atomic unit of data collected from the frontend.
    Timestamps use ``performance.now()`` (ms since page load) for
    sub-millisecond precision.
    """

    timestamp: float = Field(
        ...,
        description="Monotonic timestamp in ms (via performance.now())",
    )
    type: str = Field(
        ...,
        description="Event type identifier (e.g. 'pump', 'explode', 'collect')",
    )
    payload: EventPayload = Field(
        default_factory=EventPayload,
        description="Event-specific data",
    )

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Timestamp must be non-negative")
        return v


# ── Session Submission ───────────────────────────────────────────────────────


class GameSession(BaseModel):
    """
    Complete game session payload received from the frontend.

    Contains the full ordered event log for server-side scoring.
    """

    session_id: str = Field(
        ...,
        description="Unique session identifier (UUID string)",
    )
    game_type: GameType = Field(
        ...,
        description="Which cognitive assessment game was played",
    )
    candidate_id: str = Field(
        default="anonymous",
        description="Identifier for the candidate being assessed",
    )
    condition: Optional[str] = Field(
        default=None,
        description=(
            "assigned condition for between-subject designs; one of the study "
            "config's declared `conditions` (issue 37), None when the study "
            "has none"
        ),
    )
    duplicate_acknowledged: bool = Field(
        default=False,
        description=(
            "True when the ID screen warned that this candidate_id already had "
            "recorded sessions and the researcher chose to continue (issue 38) "
            "— keeps accidental ID reuse visible in the data"
        ),
    )
    events: list[GameEvent] = Field(
        ...,
        min_length=1,
        description="Chronologically ordered list of raw game events",
    )

    @field_validator("events")
    @classmethod
    def events_must_be_chronological(cls, v: list[GameEvent]) -> list[GameEvent]:
        """
        Validate that events are in chronological order.

        Out-of-order timestamps indicate either client tampering
        or a corrupted event stream — reject with 422.
        """
        for i in range(1, len(v)):
            if v[i].timestamp < v[i - 1].timestamp:
                raise ValueError(
                    f"Events out of chronological order at index {i}: "
                    f"timestamp {v[i].timestamp} < previous {v[i - 1].timestamp}"
                )
        return v


# ── Scoring Response ─────────────────────────────────────────────────────────


class ColorMetrics(BaseModel):
    """Per-color metrics for multi-risk BART profiles."""

    color: str = Field(..., description="Balloon color (purple/teal/orange)")
    average_pumps: float = Field(
        ...,
        description="Mean pumps for this color across ALL balloons (both exploded and collected)",
    )
    behavioral_avg_pumps: float = Field(
        default=0.0,
        description=(
            "Mean pumps using collected-only balloons (behavioral intention). "
            "Falls back to all balloons when fewer than 2 collected."
        ),
    )
    explosion_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Explosion rate specific to this color",
    )
    total_balloons: int = Field(..., description="Number of balloons of this color")
    collected_count: int = Field(
        default=0,
        description="Number of non-exploded (collected) balloons of this color",
    )
    risk_profile: str = Field(
        ...,
        description="Risk classification (low/medium/high)",
    )
    used_fallback: bool = Field(
        default=False,
        description="True if behavioral_avg_pumps fell back to all balloons due to insufficient collected count",
    )
    ev_efficiency: Optional[float] = Field(
        default=None,
        description="EV(behavioral_avg) / EV(optimal) for this color. None if insufficient collected data.",
    )
    ev_optimal_stop: Optional[int] = Field(
        default=None,
        description="Dynamically computed EV-optimal pump count for this color.",
    )
    excess_explosion_rate: Optional[float] = Field(
        default=None,
        description="Observed explosion rate minus expected rate at EV-optimal. Positive = over-pumping.",
    )


class TrialRecord(BaseModel):
    """One trial (balloon) of a session in long format (issue 39).

    The row shape of the study-wide trials CSV — identity columns are added by
    the writer; this model carries the design + behavior columns the scoring
    engine computes from the event log. Field names follow the canonical BART
    nomenclature (CONTEXT.md) so the file reads without a codebook.
    """

    trial: int = Field(description="1-based trial index within the session")
    balloon_color: str
    hazard_family: Optional[str] = Field(
        default=None,
        description=(
            "the hazard family this balloon's color ran under (from the study "
            "config); None when the color is not in the config"
        ),
    )
    pumps: int
    outcome: Literal["collected", "exploded"]
    trial_earnings: float = Field(
        description="pumps × reward_per_pump when collected; 0 when popped"
    )
    mean_latency_between_pumps: Optional[float] = Field(
        default=None,
        description=(
            "mean gap between this trial's successive pumps (ms); None when "
            "the trial has fewer than two pumps"
        ),
    )


class BARTMetrics(BaseModel):
    """Computed metrics from a BART game session."""

    # Overall metrics
    average_pumps_adjusted: float = Field(
        ...,
        description="Mean pumps per non-exploded balloon (adjusted BART score)",
    )
    explosion_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fraction of balloons that exploded (0.0 – 1.0)",
    )
    mean_latency_between_pumps: float = Field(
        ...,
        description="Average inter-pump interval in ms (computed via NumPy)",
    )
    total_balloons: int = Field(
        ...,
        description="Total number of balloons in the session",
    )
    total_pumps: int = Field(
        ...,
        description="Total pump events across all balloons",
    )
    total_explosions: int = Field(
        ...,
        description="Number of balloons that exploded",
    )
    total_collections: int = Field(
        ...,
        description="Number of balloons successfully collected",
    )

    # Color-based metrics (Multi-risk profiles)
    color_metrics: list[ColorMetrics] = Field(
        default_factory=list,
        description="Per-color performance metrics for purple/teal/orange balloons",
    )

    # Learning & Adaptation metrics
    learning_rate: float = Field(
        default=0.0,
        description="Rate of behavioral adaptation across trials (-1 to 1, higher = faster learning)",
    )
    risk_adjustment_score: float = Field(
        default=0.0,
        description="Ability to adjust behavior based on color cues (0-100)",
    )
    color_discrimination_index: Optional[float] = Field(
        default=None,
        description="DEPRECATED: Use ev_efficiency_uniformity instead. Kept for backward compatibility.",
    )
    rng_normalized_pumps: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Mean pumps as ratio of EV-optimal stop per color, averaged across colors. "
            "1.0 = pumping at exactly EV-optimal. >1.0 = over-pumping. <1.0 = conservative. "
            "Uses collected (non-exploded) balloons only."
        ),
    )
    orange_avg_pumps: Optional[float] = Field(
        default=None,
        description=(
            "Mean pump count on collected orange (high-risk) balloons. "
            "None when orange has insufficient collected balloons."
        ),
    )
    patience_index: float = Field(
        default=0.0,
        ge=0.0,
        description="Low-risk balloon average pumps (purple balloons)",
    )
    response_consistency: float = Field(
        default=0.0,
        ge=0.0,
        description="Coefficient of variation in pump latencies (lower = more consistent)",
    )
    adaptive_strategy_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description=(
            "Composite score (0-100). Fixed weights: calibration 35%, learning 25%, "
            "uniformity 25%, money efficiency 15%."
        ),
    )
    risk_sensitivity: float = Field(
        default=0.0,
        description="Correlation between risk level and pumping behavior (-1 to 1)",
    )
    behavioral_profile: dict[str, Any] = Field(
        default_factory=dict,
        description="Narrative behavioral insights (risk style, adaptability, etc.)",
    )

    # ── Behavioral indices ───────────────────────────────────────────────────

    impulsivity_index: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Latency-based impulsivity index [0-1]. "
            "Derived from mean inter-pump latency: 1 - clamp(latency / 800ms, 0, 1). "
            "Higher = faster/more reflexive pumping. "
            "Based on Lejuez et al. (2002): pump latency is the primary BART "
            "correlate of trait impulsivity."
        ),
    )
    avg_pumps_all_balloons: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Mean pumps across ALL balloons regardless of outcome. "
            "Unlike average_pumps_adjusted (collected only), this includes exploded balloons "
            "and is not subject to censoring bias from RNG explosion-point selection."
        ),
    )
    patience_index_normalized: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Purple (low-risk) EV-efficiency: EV(participant_purple) / EV(optimal_purple). "
            "Peaks at EV-optimal play (11 pumps) and decreases with both under- and "
            "over-pumping. Distinguishes patience from reckless over-pumping."
        ),
    )
    half_split_learning_rate: float = Field(
        default=0.0,
        description=(
            "Learning rate from first-half vs second-half trial comparison per color. "
            "More robust than regression-based learning_rate at N=10 per color because "
            "no single outlier trial can dominate. "
            "Positive = improved performance in second half. Range: -1 to 1."
        ),
    )
    within_balloon_consistency: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Mean CV of intra-pump latencies WITHIN individual balloons. "
            "Measures timing consistency during a single inflation sequence. "
            "Unlike response_consistency, immune to between-balloon strategy shifts."
        ),
    )
    between_balloon_consistency: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "CV of pump counts across all balloons. "
            "Measures how variable the participant's pumping strategy is balloon-to-balloon. "
            "High = erratic strategy; low = consistent strategy."
        ),
    )

    # ── EV-based metrics (sequential model) ──────────────────────────────────

    ev_ratio_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description=(
            "EV-Ratio Risk Calibration: EV(participant) / EV(optimal) × 100 per color, "
            "weighted average. Derived from sequential model. 100 = perfectly optimal."
        ),
    )
    explosion_penalty: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "Excess explosion rate vs expected-at-optimal, averaged across colors. "
            "0 = no excess explosions; 1 = maximum excess. Penalizes over-pumping."
        ),
    )
    risk_calibration_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description=(
            "EV-Ratio Risk Calibration: EV(participant) / EV(optimal) × 100, "
            "EV-weighted across colors. 100 = perfectly EV-optimal pumping. "
            "Explosion penalty is reported separately to avoid double-penalizing."
        ),
    )
    ev_efficiency_uniformity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "1 - CV(per_color_ev_efficiencies). Measures how uniform efficiency is "
            "across risk levels. High = consistent efficiency (but not necessarily high). "
            "None if fewer than 2 colors have sufficient collected data."
        ),
    )
    money_collected: float = Field(
        default=0.0,
        ge=0.0,
        description="Total money earned from collected balloons (pumps × $0.25).",
    )
    money_efficiency: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description=(
            "Money collected / median earnings at EV-optimal play (from Monte Carlo simulation). "
            "1.0 = earned what a median optimal session earns. >1.0 = lucky or better than optimal. "
            "Uses simulated median instead of EV because ~50% of optimal sessions earn below EV."
        ),
    )
    flat_strategy_detected: bool = Field(
        default=False,
        description=(
            "True if participant appears to use undifferentiated pumping strategy "
            "(same target across all colors)."
        ),
    )

    # ── Advanced learning metrics ────────────────────────────────────────────

    color_discrimination_trajectory: Optional[float] = Field(
        default=None,
        description=(
            "Change in purple-vs-orange discrimination from first to last session "
            "third, normalized by EV-optimal spread (≈9 pumps). "
            "+1 = gained one optimal-spread of differentiation. "
            "0 = stable. Negative = converged (reduced over-spread). "
            "None if insufficient color data."
        ),
    )
    post_explosion_sensitivity: Optional[float] = Field(
        default=None,
        description=(
            "Mean pump change on the next same-color balloon after an explosion, "
            "normalized by EV-optimal stop for the color. "
            "Positive = participant reduced pumps after pops (adaptive). "
            "Range approx [-2, 2]. None if no same-color follow-ups after explosions."
        ),
    )
    tercile_learning_rate: float = Field(
        default=0.0,
        description=(
            "Learning rate from first-third vs last-third trials per color. "
            "Drops the noisy middle third to capture late learners more sharply. "
            "Same directional logic as half-split. Range [-1, 1]."
        ),
    )
    ev_optimal_stops: dict[str, float] = Field(
        default_factory=dict,
        description="Dynamically computed EV-optimal stopping points per color, plus per-color EV-efficiency values.",
    )

    session_valid: bool = Field(
        default=True,
        description="True if the session passes all validity checks (complete, chronological, non-anomalous).",
    )
    session_warnings: list[str] = Field(
        default_factory=list,
        description="Validation warnings for this session (empty if fully valid).",
    )

    # Data-quality flags (issue 40). Flags annotate — the instrument never
    # excludes, reorders, or withholds a session because of them; exclusion is
    # the analyst's preregistered decision.
    qc_fast_response_trials: int = Field(
        default=0,
        description=(
            "Number of trials containing at least one inter-pump gap faster "
            "than the study's fast-response threshold."
        ),
    )
    qc_zero_pump_streak: int = Field(
        default=0,
        description="Longest run of consecutive trials with zero pumps.",
    )
    qc_flagged: bool = Field(
        default=False,
        description="True when any QC rule tripped (annotate-only; nothing is excluded).",
    )
    qc_fast_response_ms: float = Field(
        default=100.0,
        description=(
            "The fast-response threshold (ms) this session was judged against "
            "— recorded so a flag's criteria can be stated post hoc."
        ),
    )
    qc_zero_pump_streak_threshold: int = Field(
        default=5,
        description=(
            "The zero-pump streak length this session was judged against "
            "— recorded so a flag's criteria can be stated post hoc."
        ),
    )

    # Real-world payout conversion (issue 41): computed once, here in the
    # engine, so the debrief and the CSV can never disagree. None when the
    # study declares no payout block.
    payout_amount: Optional[float] = Field(
        default=None,
        description=(
            "Amount actually owed: money_collected × payout.rate, rounded "
            "half-up to 2 decimals. None when the study has no payout block."
        ),
    )
    payout_currency: Optional[str] = Field(
        default=None,
        description="The payout block's freeform currency label ('₺', '$', 'credits').",
    )


# ── Normalization (optional) ─────────────────────────────────────────────────


class NormalizedScore(BaseModel):
    """A raw metric normalized against population norms."""

    metric_name: str
    raw_value: float
    z_score: float = Field(description="Standard deviations from population mean")
    percentile: float = Field(
        ge=0.0,
        le=100.0,
        description="Percentile rank (0–100)",
    )
    population_mean: float
    population_std: float


class AssessmentResponse(BaseModel):
    """Full response after scoring and norming an assessment."""

    session_id: str
    game_type: GameType
    candidate_id: str
    raw_metrics: BARTMetrics
    normalized_scores: list[NormalizedScore]
    profile_traits: dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated trait labels derived from normalized scores",
    )
