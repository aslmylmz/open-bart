from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np

from scoring.config import DEFAULT_TASK_CONFIG, BalloonCurve, TaskConfig
from scoring.schemas.game_events import BARTMetrics, ColorMetrics, GameEvent, TrialRecord

logger = logging.getLogger(__name__)

# The engine's public interface: everything else in this module is an
# implementation detail (private helpers, module-level fallbacks/constants).
__all__ = ["score_bart", "trial_table", "validate_bart_session"]


# ── Color Profile Constants ──────────────────────────────────────────────────

# Risk labels are a semantic property of the study, not derivable from the cap.
_RISK_BY_COLOR = {"purple": "low", "teal": "medium", "orange": "high"}

# Derived from the default study so the 128/32/8 caps live in exactly one place
# (scoring.config.DEFAULT_TASK_CONFIG) instead of being a second hardcoded copy.
COLOR_PROFILES = {
    c.name: {"risk": _RISK_BY_COLOR.get(c.name, "medium"), "max_pumps": c.max_pumps}
    for c in DEFAULT_TASK_CONFIG.colors
}

# Per-color precomputed EV curves for the default study; used as the fallback
# when a helper is called without an explicit config (e.g. direct unit calls).
_DEFAULT_CURVES: dict[str, BalloonCurve] = DEFAULT_TASK_CONFIG.curves

# Minimum collected (non-exploded) balloons per color before fallback
MIN_COLLECTED_FALLBACK = 2


# ── Risk ranking ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _RiskRanking:
    """A study's colors ordered by risk, so the name-keyed persona metrics resolve
    behavior by *risk role* rather than by literal color name (issue 56).

    ``low_color`` is the lowest-risk color (highest EV-optimal stop) — the role
    the default study's ``purple`` plays; ``high_color`` is the highest-risk color
    (lowest EV-optimal stop) — the ``orange`` role; every color between is
    excluded from the two-color contrasts (the ``teal`` role). ``risk_label`` maps
    each color to ``low``/``medium``/``high``. A single-color study has no risk
    contrast: ``low_color`` names that color, ``high_color`` is ``None`` (so the
    discrimination metrics stay degenerate), and the label is ``medium``.
    """

    low_color: str | None
    high_color: str | None
    risk_label: dict[str, str]


def _risk_ranking(curves: dict[str, BalloonCurve]) -> _RiskRanking:
    """Rank a study's colors by risk — lowest risk = highest EV-optimal stop.

    The EV-optimal stop (``curve.optimum``) is the behaviorally-meaningful risk
    measure: a color you can safely pump further is lower-risk. Config/insertion
    order breaks ties, keeping the ranking deterministic. For the default 128/32/8
    study this yields purple (low) / teal (medium) / orange (high), so every
    name-keyed metric stays byte-identical to the old literal-name resolution.
    """
    names = list(curves)
    if not names:
        return _RiskRanking(low_color=None, high_color=None, risk_label={})
    if len(names) == 1:
        only = names[0]
        return _RiskRanking(low_color=only, high_color=None, risk_label={only: "medium"})

    # Descending EV-optimal; Python's stable sort preserves config order on ties.
    ordered = sorted(names, key=lambda n: curves[n].optimum, reverse=True)
    low_color, high_color = ordered[0], ordered[-1]
    risk_label = {n: "medium" for n in names}
    risk_label[low_color] = "low"
    risk_label[high_color] = "high"
    return _RiskRanking(low_color=low_color, high_color=high_color, risk_label=risk_label)


# The ranking for the default study; the fallback when a helper is called without
# an explicit ranking (direct unit calls), mirroring ``_DEFAULT_CURVES``.
_DEFAULT_RANKING = _risk_ranking(_DEFAULT_CURVES)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _segment_balloons(events: list[GameEvent]) -> list[list[GameEvent]]:
    """
    Segment flat event list into lists of events per balloon.
    """
    balloons: list[list[GameEvent]] = []
    current: list[GameEvent] = []

    for event in events:
        current.append(event)
        if event.type in ("collect", "explode"):
            balloons.append(current)
            current = []

    if current:
        balloons.append(current)

    return balloons


def _extract_balloon_color(balloon_events: list[GameEvent]) -> str:
    """
    Extract balloon color from event payload; defaults to 'teal'.
    """
    for event in balloon_events:
        if hasattr(event.payload, "color") and event.payload.color:
            return event.payload.color.lower()
        if hasattr(event.payload, "balloon_color") and event.payload.balloon_color:
            return event.payload.balloon_color.lower()

    return "teal"


def _compute_qc_flags(
    balloons: list[list[GameEvent]],
    fast_response_ms: float,
    zero_pump_streak: int,
) -> tuple[int, int, bool]:
    """Data-quality flags from the raw balloons (issue 40).

    Returns (trials containing a sub-threshold inter-pump gap, longest run of
    consecutive zero-pump trials, any rule tripped). Computed on the raw data —
    auto-repeat balloons included — because the flags describe data quality;
    they annotate, never exclude.
    """
    fast_trials = 0
    longest_streak = 0
    streak = 0
    for balloon_events in balloons:
        pump_times = [e.timestamp for e in balloon_events if e.type == "pump"]
        if len(pump_times) >= 2 and float(np.min(np.diff(pump_times))) < fast_response_ms:
            fast_trials += 1
        streak = streak + 1 if not pump_times else 0
        longest_streak = max(longest_streak, streak)
    flagged = fast_trials > 0 or longest_streak >= zero_pump_streak
    return fast_trials, longest_streak, flagged


def trial_table(
    events: list[GameEvent],
    config: TaskConfig = DEFAULT_TASK_CONFIG,
) -> list[TrialRecord]:
    """The session as long-format trial rows: one record per balloon (issue 39).

    This is the row shape of the study-wide trials CSV, computed here — not
    re-derived in the sidecar — so CLI users of ``scoring`` get the same trial
    table. A trailing balloon without a terminal event (an aborted session)
    has no outcome and is omitted.
    """
    families = {c.name: c.hazard.family for c in config.colors}
    records: list[TrialRecord] = []
    for index, balloon_events in enumerate(_segment_balloons(events), start=1):
        terminal = next(
            (e.type for e in reversed(balloon_events) if e.type in ("collect", "explode")),
            None,
        )
        if terminal is None:
            continue
        color = _extract_balloon_color(balloon_events)
        pumps = sum(1 for e in balloon_events if e.type == "pump")
        collected = terminal == "collect"
        pump_times = [e.timestamp for e in balloon_events if e.type == "pump"]
        gaps = np.diff(pump_times)
        records.append(
            TrialRecord(
                trial=index,
                balloon_color=color,
                hazard_family=families.get(color),
                pumps=pumps,
                outcome="collected" if collected else "exploded",
                trial_earnings=pumps * config.reward_per_pump if collected else 0.0,
                mean_latency_between_pumps=float(np.mean(gaps)) if gaps.size else None,
            )
        )
    return records


def _prefer_collected(
    collected: list[int],
    all_data: list[int],
    min_count: int = MIN_COLLECTED_FALLBACK,
) -> tuple[list[int], bool]:
    """
    Prefer non-exploded balloon data to avoid truncation bias, otherwise fall back.
    """
    if len(collected) >= min_count:
        return collected, False
    return all_data, True


def validate_bart_session(events: list[GameEvent]) -> dict[str, Any]:
    """
    Validate session validity and integrity before scoring.

    Checks performed:
    1. Minimum balloon count
    2. Balanced representation of risk profiles (colors)
    3. Timestamp monotonicity
    4. Session pacing (unusual completion speeds)
    5. Pump variance (automated/bot-like uniform inputs)
    """
    if not events:
        return {
            "is_valid": False,
            "warnings": ["Empty event log"],
            "balloon_count": 0,
            "color_distribution": {},
        }

    warnings: list[str] = []
    is_valid = True

    balloons = _segment_balloons(events)
    balloon_count = len(balloons)

    if balloon_count < 15:
        warnings.append(
            f"Critically incomplete session: only {balloon_count}/30 balloons played"
        )
        is_valid = False
    elif balloon_count < 30:
        warnings.append(f"Incomplete session: {balloon_count}/30 balloons played")

    color_counts: dict[str, int] = defaultdict(int)
    for b in balloons:
        color = _extract_balloon_color(b)
        color_counts[color] += 1

    for color in ["purple", "teal", "orange"]:
        count = color_counts.get(color, 0)
        if count < 5:
            warnings.append(f"Too few {color} balloons: {count}/10 played")
        elif count < 10:
            warnings.append(f"Partial {color} balloons: {count}/10 played")

    for i in range(1, len(events)):
        if events[i].timestamp < events[i - 1].timestamp:
            warnings.append(
                f"Out-of-order timestamps at index {i} "
                f"({events[i].timestamp:.1f} < {events[i-1].timestamp:.1f})"
            )
            is_valid = False
            break

    total_time_ms = events[-1].timestamp - events[0].timestamp
    if balloon_count >= 15 and total_time_ms < 30_000:
        warnings.append(
            f"Session completed unusually fast: {total_time_ms / 1000:.1f}s "
            f"for {balloon_count} balloons"
        )

    pump_counts = [sum(1 for e in b if e.type == "pump") for b in balloons]
    if len(pump_counts) >= 10 and float(np.std(pump_counts)) < 0.5:
        warnings.append(
            "Suspicious pump pattern: uniform counts suggest possible automated play"
        )

    return {
        "is_valid": is_valid,
        "warnings": warnings,
        "balloon_count": balloon_count,
        "color_distribution": dict(color_counts),
    }


def _calculate_learning_rate(
    balloon_data: list[tuple[int, str, int, bool]],
    ranking: _RiskRanking = _DEFAULT_RANKING,
) -> float:
    """
    Calculate learning rate using linear regression on pump counts over time.

    Uses non-exploded trials only. Only the lowest- and highest-risk colors count;
    mid-risk colors are excluded because their learning/adaptation direction
    relative to the EV optimum is ambiguous.
    """
    if len(balloon_data) < 3:
        return 0.0

    color_trials_all: dict[str, list[tuple[int, int]]] = defaultdict(list)
    color_trials_collected: dict[str, list[tuple[int, int]]] = defaultdict(list)

    for trial, color, pumps, exploded in balloon_data:
        color_trials_all[color].append((trial, pumps))
        if not exploded:
            color_trials_collected[color].append((trial, pumps))

    learning_slopes = []

    for color in color_trials_all:
        collected = color_trials_collected.get(color, [])
        all_trials = color_trials_all[color]
        trials = collected if len(collected) >= MIN_COLLECTED_FALLBACK else all_trials

        if len(trials) < 2:
            continue

        trial_nums = np.array([t[0] for t in trials])
        pump_counts = np.array([t[1] for t in trials])

        if len(trial_nums) >= 2 and np.std(trial_nums) > 0:
            # OLS slope and Pearson r without scipy (caller guarantees Sxx > 0).
            x = trial_nums.astype(float)
            y = pump_counts.astype(float)
            dx = x - x.mean()
            dy = y - y.mean()
            sxx = float(np.dot(dx, dx))
            syy = float(np.dot(dy, dy))
            sxy = float(np.dot(dx, dy))
            slope = sxy / sxx
            # Match scipy.stats.linregress: r = 0 when the y-variance is 0,
            # otherwise the correlation clamped to [-1, 1].
            r_value = 0.0 if syy == 0.0 else max(-1.0, min(1.0, sxy / math.sqrt(sxx * syy)))
            weighted_slope = slope * (r_value**2)

            # Adjust sign based on adaptive behavior per risk role: on the
            # highest-risk color, learning means pumping *less* over time.
            if color == ranking.high_color:
                learning_slopes.append(-weighted_slope)
            elif color == ranking.low_color:
                learning_slopes.append(weighted_slope)

    if not learning_slopes:
        return 0.0

    mean_slope = float(np.mean(learning_slopes))
    if np.isnan(mean_slope):
        return 0.0
    return float(np.clip(mean_slope, -1.0, 1.0))


def _calculate_half_split_learning_rate(
    balloon_data: list[tuple[int, str, int, bool]],
    ranking: _RiskRanking = _DEFAULT_RANKING,
) -> float:
    """
    Compare average pumps between first-half and second-half trials per color.

    Uses collected trials only (with a fallback if collected < 4) to bypass
    RNG truncation bias. Only the lowest- and highest-risk colors count.
    """
    if len(balloon_data) < 4:
        return 0.0

    color_trials_all: dict[str, list[tuple[int, int]]] = defaultdict(list)
    color_trials_collected: dict[str, list[tuple[int, int]]] = defaultdict(list)

    for trial, color, pumps, exploded in balloon_data:
        color_trials_all[color].append((trial, pumps))
        if not exploded:
            color_trials_collected[color].append((trial, pumps))

    learning_scores = []

    for color in color_trials_all:
        collected = color_trials_collected.get(color, [])
        all_trials = color_trials_all[color]
        trials = collected if len(collected) >= 4 else all_trials

        if len(trials) < 4:
            continue

        sorted_trials = sorted(trials, key=lambda x: x[0])
        half = len(sorted_trials) // 2

        first_half_mean = float(np.mean([t[1] for t in sorted_trials[:half]]))
        second_half_mean = float(np.mean([t[1] for t in sorted_trials[half:]]))
        overall_mean = float(np.mean([t[1] for t in sorted_trials]))

        if overall_mean == 0:
            continue

        delta = (second_half_mean - first_half_mean) / overall_mean

        if color == ranking.high_color:
            learning_scores.append(-delta)
        elif color == ranking.low_color:
            learning_scores.append(delta)

    if not learning_scores:
        return 0.0

    mean_learning = float(np.mean(learning_scores))
    if np.isnan(mean_learning):
        return 0.0
    return float(np.clip(mean_learning, -1.0, 1.0))


def _calculate_tercile_learning_rate(
    balloon_data: list[tuple[int, str, int, bool]],
    ranking: _RiskRanking = _DEFAULT_RANKING,
) -> float:
    """
    Compare average pumps between the first and last third of trials per color.

    Drops the middle third to capture late-stage adaptation trends. Only the
    lowest- and highest-risk colors count.
    """
    if len(balloon_data) < 6:
        return 0.0

    color_trials_all: dict[str, list[tuple[int, int]]] = defaultdict(list)
    color_trials_collected: dict[str, list[tuple[int, int]]] = defaultdict(list)

    for trial, color, pumps, exploded in balloon_data:
        color_trials_all[color].append((trial, pumps))
        if not exploded:
            color_trials_collected[color].append((trial, pumps))

    learning_scores = []

    for color in color_trials_all:
        collected = color_trials_collected.get(color, [])
        all_trials = color_trials_all[color]
        trials = collected if len(collected) >= 3 else all_trials

        if len(trials) < 3:
            continue

        sorted_trials = sorted(trials, key=lambda x: x[0])
        third = max(1, len(sorted_trials) // 3)

        first_third = sorted_trials[:third]
        last_third = sorted_trials[-third:]

        first_mean = float(np.mean([t[1] for t in first_third]))
        last_mean = float(np.mean([t[1] for t in last_third]))
        overall_mean = float(np.mean([t[1] for t in sorted_trials]))

        if overall_mean == 0:
            continue

        delta = (last_mean - first_mean) / overall_mean

        if color == ranking.high_color:
            learning_scores.append(-delta)
        elif color == ranking.low_color:
            learning_scores.append(delta)

    if not learning_scores:
        return 0.0

    result = float(np.mean(learning_scores))
    return 0.0 if np.isnan(result) else float(np.clip(result, -1.0, 1.0))


def _calculate_color_discrimination_trajectory(
    balloon_data: list[tuple[int, str, int, bool]],
    curves: dict[str, BalloonCurve] = _DEFAULT_CURVES,
    ranking: _RiskRanking = _DEFAULT_RANKING,
) -> float | None:
    """
    Track the change in safest-vs-riskiest pump discrimination across session thirds.

    Calculates discrimination = mean(low-risk) - mean(high-risk) per third.
    Returns the change normalized by this study's EV-optimal spread between those
    two colors (low_opt - high_opt) — 9 for the default 128/8 study (issue 52).
    """
    if len(balloon_data) < 6:
        return None

    low_color, high_color = ranking.low_color, ranking.high_color

    sorted_data = sorted(balloon_data, key=lambda x: x[0])
    n = len(sorted_data)
    block_size = max(1, n // 3)

    blocks = [
        sorted_data[:block_size],
        sorted_data[block_size:2 * block_size],
        sorted_data[2 * block_size:],
    ]

    block_disc = []
    for block in blocks:
        low_collected = [pumps for _, color, pumps, exploded in block
                         if color == low_color and not exploded]
        high_collected = [pumps for _, color, pumps, exploded in block
                          if color == high_color and not exploded]

        if not low_collected:
            low_collected = [pumps for _, color, pumps, _ in block if color == low_color]
        if not high_collected:
            high_collected = [pumps for _, color, pumps, _ in block if color == high_color]

        if low_collected and high_collected:
            block_disc.append(float(np.mean(low_collected)) - float(np.mean(high_collected)))
        else:
            block_disc.append(None)

    valid = [(i, d) for i, d in enumerate(block_disc) if d is not None]
    if len(valid) < 2:
        return None

    first_block_disc = valid[0][1]
    last_block_disc = valid[-1][1]
    change = last_block_disc - first_block_disc

    # Normalize by the study's own EV-optimal spread between the safest and
    # riskiest color (was a hardcoded 9.0 = 11 - 2 for the default study), so the
    # metric scales with the configured caps (issue 52). A missing color (e.g. a
    # single-risk-context study) or non-positive spread can't be normalized.
    if low_color not in curves or high_color not in curves:
        return None
    optimal_spread = curves[low_color].optimum - curves[high_color].optimum
    if optimal_spread <= 0:
        return None
    return float(change / optimal_spread)


def _calculate_post_explosion_sensitivity(
    balloon_data: list[tuple[int, str, int, bool]],
    curves: dict[str, BalloonCurve] = _DEFAULT_CURVES,
) -> float | None:
    """
    Measure pump adjustment on the next same-color balloon after an explosion.

    Value is normalized by the color's EV-optimal stopping point.
    Positive values represent adaptive risk reduction.
    """
    sorted_data = sorted(balloon_data, key=lambda x: x[0])
    changes = []

    for i, (trial, color, pumps, exploded) in enumerate(sorted_data):
        if not exploded or pumps == 0:
            continue
        for j in range(i + 1, len(sorted_data)):
            if sorted_data[j][1] == color:
                next_pumps = sorted_data[j][2]
                opt_stop = curves[color].optimum if color in curves else 0
                if opt_stop > 0:
                    change = (pumps - next_pumps) / opt_stop
                else:
                    change = 0.0
                changes.append(change)
                break

    if not changes:
        return None

    result = float(np.mean(changes))
    return None if np.isnan(result) else float(np.clip(result, -1.0, 1.0))


def _calculate_color_discrimination(
    color_pumps: dict[str, list[int]],
    ranking: _RiskRanking = _DEFAULT_RANKING,
) -> float:
    """
    Discriminate the lowest- vs. highest-risk color using Cohen's d effect size.

    Normalized to [0, 1] where d >= 2.0 maps to 1.0. A single-risk-context study
    (no distinct high-risk color) can't discriminate and scores 0.0.
    """
    low_pumps = color_pumps.get(ranking.low_color, [])
    high_pumps = color_pumps.get(ranking.high_color, [])

    if len(low_pumps) < 2 or len(high_pumps) < 2:
        return 0.0

    purple_arr = np.array(low_pumps)
    orange_arr = np.array(high_pumps)

    mean_diff = np.mean(purple_arr) - np.mean(orange_arr)
    pooled_std = np.sqrt(
        (np.var(purple_arr, ddof=1) + np.var(orange_arr, ddof=1)) / 2,
    )

    if pooled_std == 0:
        return 1.0 if mean_diff > 0 else 0.0

    cohens_d = mean_diff / pooled_std
    discrimination = np.clip(cohens_d / 2.0, 0.0, 1.0)

    if np.isnan(discrimination):
        return 0.0
    return float(discrimination)


def _calculate_risk_sensitivity(
    color_pumps: dict[str, list[int]],
    curves: dict[str, BalloonCurve] = _DEFAULT_CURVES,
) -> float:
    """
    Measure alignment between risk limits and pumps using Pearson correlation.
    """
    risk_capacities = []
    user_pumps = []

    for color, pumps in color_pumps.items():
        if color not in curves:
            continue
        capacity = len(curves[color].hazard)
        for p in pumps:
            risk_capacities.append(capacity)
            user_pumps.append(p)

    if len(risk_capacities) < 3:
        return 0.0

    if np.std(user_pumps) == 0 or np.std(risk_capacities) == 0:
        return 0.0

    # Pearson r without scipy; nonzero std (guarded above) keeps it finite.
    r = float(np.corrcoef(risk_capacities, user_pumps)[0, 1])

    if np.isnan(r):
        return 0.0
    return float(r)


def _calculate_risk_adjustment_score(
    color_pumps: dict[str, list[int]],
    curves: dict[str, BalloonCurve] = _DEFAULT_CURVES,
) -> float:
    """
    Score alignment with the config's EV-optimal stopping points.

    Each color's optimum and cap are read from its precomputed curve (for the
    default study these are 11/5/2 with caps 128/32/8). Scores scale linearly
    from 100 at the optimum to 0 at the limits (0 or max_pumps).
    """
    cp = color_pumps
    scores = []

    for color in sorted(cp):
        if color not in curves:
            continue
        if color in cp and len(cp[color]) > 0:
            mean_pumps = np.mean(cp[color])
            curve = curves[color]
            opt = curve.optimum
            mx = len(curve.hazard)

            max_dist = max(opt, mx - opt)
            score = np.clip(1.0 - abs(mean_pumps - opt) / max_dist, 0.0, 1.0) * 100.0
            scores.append(float(score))

    if not scores:
        return 0.0

    result = float(np.mean(scores))
    if np.isnan(result):
        return 0.0
    return result


def _compute_ev_ratio_score(
    color_pumps_collected: dict[str, list[int]],
    color_balloons: dict[str, int],
    curves: dict[str, BalloonCurve] = _DEFAULT_CURVES,
    min_collected: int = MIN_COLLECTED_FALLBACK,
) -> tuple[float, dict[str, float]]:
    """
    Compute EV-Ratio Risk Calibration Score (EV-weighted).

    Calculates participant efficiency (EV achieved vs EV optimal) weighted
    by the expected value of each risk level. Reads each color's precomputed
    EV curve, so it is reward- and hazard-family-agnostic.
    """
    per_color_efficiency: dict[str, float] = {}

    for color in sorted(color_balloons):
        if color not in curves:
            continue
        total = color_balloons.get(color, 0)
        if total == 0:
            continue

        pumps = color_pumps_collected.get(color, [])
        if len(pumps) < min_collected:
            per_color_efficiency[color] = 0.0
            continue

        curve = curves[color]
        optimal_ev = curve.optimal_ev
        if optimal_ev <= 0:
            continue

        cap = len(curve.hazard)
        mean_pumps = float(np.mean(pumps))
        s_low = max(0, int(np.floor(mean_pumps)))
        s_high = min(cap, int(np.ceil(mean_pumps)))

        if s_low == s_high:
            participant_ev = curve.ev[s_low]
        else:
            frac = mean_pumps - s_low
            participant_ev = curve.ev[s_low] + frac * (curve.ev[s_high] - curve.ev[s_low])

        efficiency = min(1.0, participant_ev / optimal_ev)
        per_color_efficiency[color] = efficiency

    if not per_color_efficiency:
        return 0.0, {}

    weighted_sum = 0.0
    weight_total = 0.0
    for color, eff in per_color_efficiency.items():
        optimal_ev = curves[color].optimal_ev
        weighted_sum += eff * optimal_ev
        weight_total += optimal_ev

    overall = (weighted_sum / weight_total) * 100.0 if weight_total > 0 else 0.0
    return overall, per_color_efficiency


def _compute_explosion_penalty(
    color_explosions: dict[str, int],
    color_balloons: dict[str, int],
    curves: dict[str, BalloonCurve] = _DEFAULT_CURVES,
) -> tuple[float, dict[str, float]]:
    """
    Compute explosion rate surplus compared to expected rates under optimal play.
    """
    per_color_excess: dict[str, float] = {}

    for color in sorted(color_balloons):
        if color not in curves:
            continue
        total = color_balloons.get(color, 0)
        if total == 0:
            continue

        explosions = color_explosions.get(color, 0)
        observed_rate = explosions / total

        curve = curves[color]
        optimal_stop = curve.optimum
        expected_rate = 1.0 - curve.survival[optimal_stop]

        excess = max(0.0, observed_rate - expected_rate)
        per_color_excess[color] = excess

    if not per_color_excess:
        return 0.0, {}

    overall = float(np.mean(list(per_color_excess.values())))
    return min(1.0, overall), per_color_excess


def _compute_ev_efficiency_uniformity(
    per_color_efficiency: dict[str, float],
    color_pumps_collected: dict[str, list[int]],
    color_balloons: dict[str, int],
) -> float | None:
    """
    Compute uniformity of EV efficiencies across risk levels: 1 - CV(efficiency).
    """
    effective_efficiency: dict[str, float] = {}

    for color in sorted(color_balloons):
        total = color_balloons.get(color, 0)
        if total == 0:
            continue

        collected = color_pumps_collected.get(color, [])
        if len(collected) >= MIN_COLLECTED_FALLBACK:
            if color in per_color_efficiency:
                effective_efficiency[color] = per_color_efficiency[color]
        else:
            effective_efficiency[color] = 0.0

    if len(effective_efficiency) < 2:
        return None

    values = list(effective_efficiency.values())
    mean_eff = float(np.mean(values))

    if mean_eff <= 0:
        return 0.0

    cv = float(np.std(values) / mean_eff)
    return float(np.clip(1.0 - cv, 0.0, 1.0))


def _detect_flat_strategy(
    color_pumps_all: dict[str, list[int]],
    color_explosions: dict[str, int],
    color_balloons: dict[str, int],
    *,
    tercile_lr: float = 0.0,
    cdt: float | None = None,
    pes: float | None = None,
    between_cv: float = 0.0,
    ranking: _RiskRanking = _DEFAULT_RANKING,
) -> bool:
    """
    Detect if the user utilized an undifferentiated flat strategy across profiles.

    Identified by low variance in targets or a flat target that causes high
    explosion rates on higher-risk balloons. Active learners/explorers are exempted.
    """
    if len(color_pumps_all) < 2:
        return False

    is_learner = (
        tercile_lr > 0.15
        or (cdt is not None and cdt > 0.20)
        or (pes is not None and pes > 0.15)
        or between_cv > 0.45
    )

    raw_means: dict[str, float] = {}
    for color in sorted(color_pumps_all):
        pumps = color_pumps_all.get(color, [])
        if pumps:
            raw_means[color] = float(np.mean(pumps))

    if len(raw_means) < 2:
        return False

    values = list(raw_means.values())
    mean_val = float(np.mean(values))
    if mean_val <= 0:
        return False

    purple_mean = raw_means.get(ranking.low_color, 0)
    orange_mean = raw_means.get(ranking.high_color, 0)

    is_variable = (
        tercile_lr > 0.15
        or (cdt is not None and cdt > 0.20)
        or (pes is not None and pes > 0.15)
        or between_cv > 0.30
        or (orange_mean > 0 and purple_mean / orange_mean >= 1.7)
    )

    if is_variable:
        return False

    if mean_val <= 2.0:
        return True

    cv = float(np.std(values) / mean_val)
    if cv < 0.15 and purple_mean > 0 and purple_mean < 6.0:
        return True

    if cv < 0.25:
        explosion_rates: dict[str, float] = {}
        for color in sorted(color_balloons):
            total = color_balloons.get(color, 0)
            if total > 0:
                explosion_rates[color] = color_explosions.get(color, 0) / total

        orange_exp = explosion_rates.get(ranking.high_color, 0)
        purple_exp = explosion_rates.get(ranking.low_color, 0)
        
        if orange_exp > 0.8 and purple_exp < 0.5:
            return True

    return False


def _is_autorepeat_balloon(balloon_events: list[GameEvent]) -> bool:
    """
    Detect holding down of control keys (OS key-repeating) vs discrete inputs.
    """
    pump_times = [e.timestamp for e in balloon_events if e.type == "pump"]
    if len(pump_times) < 3:
        return False
    diffs = np.diff(pump_times)
    diffs = diffs[diffs < 2000.0]
    if len(diffs) < 2:
        return False
    return float(np.median(diffs)) < 80.0


def _calculate_consistency_breakdown(
    balloons: list[list[GameEvent]],
) -> tuple[float, float]:
    """
    Decompose response consistency into within-balloon and between-balloon elements.

    Returns:
        within_balloon_cv  — Mean coefficient of variation of intra-pump latency.
        between_balloon_cv — Mean coefficient of variation of pumps per trial.
    """
    within_cvs: list[float] = []
    for balloon_events in balloons:
        if _is_autorepeat_balloon(balloon_events):
            continue
        pump_times = [e.timestamp for e in balloon_events if e.type == "pump"]
        if len(pump_times) >= 3:
            diffs = np.diff(pump_times)
            diffs = diffs[diffs < 2000.0]
            if len(diffs) >= 2 and np.mean(diffs) > 0:
                cv = float(np.std(diffs) / np.mean(diffs))
                within_cvs.append(cv)

    within_balloon_cv = float(np.mean(within_cvs)) if within_cvs else 0.0

    color_collected_pumps: dict[str, list[int]] = defaultdict(list)
    color_all_pumps: dict[str, list[int]] = defaultdict(list)

    for b in balloons:
        pumps = sum(1 for e in b if e.type == "pump")
        color = _extract_balloon_color(b)
        color_all_pumps[color].append(pumps)
        terminal = next(
            (e.type for e in reversed(b) if e.type in ("collect", "explode")),
            None,
        )
        if terminal != "explode":
            color_collected_pumps[color].append(pumps)

    per_color_cvs: list[float] = []
    for color in color_all_pumps:
        data = color_collected_pumps.get(color, [])
        if len(data) < 3:
            data = color_all_pumps[color]
        if len(data) < 2:
            continue
        arr = np.array(data, dtype=np.float64)
        mean_val = float(np.mean(arr))
        if mean_val > 0:
            per_color_cvs.append(float(np.std(arr) / mean_val))

    between_balloon_cv = float(np.mean(per_color_cvs)) if per_color_cvs else 0.0

    return within_balloon_cv, between_balloon_cv


def _generate_behavioral_profile(
    metrics: BARTMetrics,
    ranking: _RiskRanking = _DEFAULT_RANKING,
) -> dict[str, Any]:
    """
    Generate a narrative behavioral profile mapped to performance markers.

    Selective-strength and patience markers read per-color EV efficiency by risk
    role (safest / riskiest color) rather than by literal color name.
    """
    profile: dict[str, Any] = {}

    purple_eff = metrics.ev_optimal_stops.get(f"_{ranking.low_color}_efficiency", 0.0)
    orange_eff = metrics.ev_optimal_stops.get(f"_{ranking.high_color}_efficiency", 0.0)
    has_selective_strength = purple_eff >= 0.70 and orange_eff < 0.30

    _tercile_lr = metrics.tercile_learning_rate
    _cdt = metrics.color_discrimination_trajectory
    _has_strong_learning = (
        metrics.half_split_learning_rate > 0.15
        or (_tercile_lr is not None and _tercile_lr > 0.15)
    )
    _has_discrim_growth = _cdt is not None and _cdt > 0.20
    _unif = metrics.ev_efficiency_uniformity

    # ── 1. Flat strategy override ────────────────────────────────────────
    if metrics.flat_strategy_detected:
        risk_style = "Undifferentiated Risk Approach"
        risk_desc = (
            "You applied a similar pumping strategy across all balloon types regardless "
            "of their risk levels. This pattern forgoes additional reward on safer "
            "balloons and incurs avoidable losses on riskier ones."
        )

    # ── 2. Calibrated Risk Optimizer ─────────────────────────────────────
    # _unif is None when the session lacks enough risk contexts to compare;
    # the cross-context styles (2, 3, 5) are then unreachable by design.
    elif (metrics.risk_calibration_score >= 80
          and metrics.explosion_penalty < 0.25
          and _unif is not None and _unif > 0.60):
        risk_style = "Calibrated Risk Optimizer"
        risk_desc = (
            "You calibrated your risk-taking precisely to match actual danger levels. "
            "You pushed when it was safe and pulled back when risk was high — "
            "maximizing expected reward across conditions."
        )

    # ── 3. Selective Over-Optimizer ──────────────────────────────────────
    elif (has_selective_strength
          and _unif is not None and _unif < 0.40
          and metrics.explosion_penalty > 0.25):
        risk_style = "Selective Over-Optimizer"
        risk_desc = (
            "You showed strong calibration on safer balloons, extracting near-optimal "
            "value from low-risk opportunities. However, you pushed too far on the "
            "highest-risk balloons, causing avoidable explosions."
        )

    # ── 4. Persistent Risk Taker ─────────────────────────────────────────
    elif (metrics.rng_normalized_pumps >= 1.0
          and not has_selective_strength
          and metrics.explosion_penalty > 0.20):
        risk_style = "Persistent Risk Taker"
        risk_desc = (
            "You pushed well past optimal stopping points across all balloon types. "
            "This uniformly aggressive approach led to more explosions than an "
            "EV-maximizing strategy would produce."
        )

    # ── 5. Context-Insensitive Risk Taker ────────────────────────────────
    elif (_unif is not None and _unif < 0.35
          and not has_selective_strength
          and metrics.explosion_penalty > 0.15):
        risk_style = "Context-Insensitive Risk Taker"
        risk_desc = (
            "Your pumping varied across balloon types but without matching the "
            "actual risk structure. This pattern suggests difficulty reading which "
            "situations are genuinely dangerous versus which ones reward persistence."
        )

    # ── 6. Loss-Averse Responder ─────────────────────────────────────────
    elif (metrics.rng_normalized_pumps < 0.60
          and metrics.explosion_penalty < 0.16):
        risk_style = "Loss-Averse Responder"
        risk_desc = (
            "You prioritized certainty, stopping well before optimal on most balloons. "
            "This minimized losses but left significant expected reward uncollected."
        )

    # ── 7. Emerging Optimizer ────────────────────────────────────────────
    elif (has_selective_strength
          and metrics.risk_calibration_score >= 75
          and metrics.money_efficiency >= 0.60):
        risk_style = "Emerging Optimizer"
        risk_desc = (
            "You showed a developing sense of risk calibration — your pumping strategy "
            "captured meaningful expected value, especially on safer balloons. While not "
            "yet uniformly optimal across all risk levels, your decisions translated into "
            "solid monetary returns."
        )

    # ── 8. Adaptive Risk Learner ─────────────────────────────────────────
    elif _has_strong_learning and _has_discrim_growth:
        risk_style = "Adaptive Risk Learner"
        risk_desc = (
            "You showed clear improvement across the task. Your strategy evolved as you "
            "gathered experience — you adjusted your pumping to better differentiate "
            "between balloon risk levels."
        )

    # ── 9. Conservative Strategist ───────────────────────────────────────
    elif (metrics.rng_normalized_pumps < 0.75
          and metrics.explosion_penalty < 0.20):
        risk_style = "Conservative Strategist"
        risk_desc = (
            "You employed a cautious approach, consistently stopping below the "
            "optimal pumping level. While this left some expected value uncollected, "
            "it also kept your explosion rate low."
        )

    # ── 10. Balanced Explorer (catch-all) ────────────────────────────────
    else:
        risk_style = "Balanced Explorer"
        risk_desc = (
            "You maintained a moderate balance between safety and exploration. "
            "Your risk-taking was neither strongly conservative nor aggressive."
        )

    profile["risk_style"] = risk_style
    profile["description"] = risk_desc

    traits = []

    if metrics.within_balloon_consistency < 0.2 and metrics.between_balloon_consistency < 0.4:
        traits.append("Highly Consistent")
    elif metrics.within_balloon_consistency > 0.6:
        traits.append("Erratic Within-Balloon")
    elif metrics.between_balloon_consistency > 1.0:
        traits.append("Strategically Variable")

    if metrics.half_split_learning_rate > 0.1:
        traits.append("Improving Over Time")
    elif metrics.half_split_learning_rate < -0.1:
        traits.append("Declining Over Time")

    if metrics.orange_avg_pumps is not None and metrics.orange_avg_pumps > 4.0:
        traits.append("Impulsive on High-Risk")

    _pe = metrics.ev_optimal_stops.get(f"_{ranking.low_color}_efficiency")
    if _pe is not None and _pe > 0.90:
        traits.append("Near-Optimal on Safe Balloons")
    elif metrics.patience_index > 20:
        traits.append("Over-Pumper on Safe Balloons")

    if metrics.flat_strategy_detected:
        traits.append("Flat Strategy")

    if metrics.explosion_penalty > 0.3:
        traits.append("High Explosion Penalty")

    if not traits:
        if metrics.money_efficiency >= 0.70:
            traits.append("Efficient Earner")
        elif metrics.rng_normalized_pumps >= 1.0:
            traits.append("Above-Optimal Pumping")
        elif metrics.rng_normalized_pumps < 0.60:
            traits.append("Cautious Pumping")
        else:
            traits.append("Moderate Risk-Taker")

    profile["dominant_traits"] = traits

    return profile


# ── Main Scoring Function ───────────────────────────────────────────────────


def score_bart(
    events: list[GameEvent],
    config: TaskConfig = DEFAULT_TASK_CONFIG,
) -> BARTMetrics:
    """
    Score a BART session from raw events using NumPy vectorization.

    Analyzes behavioral-intention variables using collected (non-exploded)
    balloons to protect metrics against RNG truncation bias. ``config`` supplies
    the hazard model, per-color EV-optimal stops, and reward; it defaults to the
    validated 128/32/8 linear study.
    """
    if not events:
        raise ValueError("Empty event log")

    curves = config.curves
    ranking = _risk_ranking(curves)

    validation = validate_bart_session(events)
    session_valid = validation["is_valid"]
    session_warnings = list(validation["warnings"])

    balloons = _segment_balloons(events)

    if not balloons:
        raise ValueError("No balloon data found in event log")

    balloon_colors = [_extract_balloon_color(b) for b in balloons]
    color_counts: dict[str, int] = {}
    for color in balloon_colors:
        color_counts[color] = color_counts.get(color, 0) + 1
        
    logger.info(
        "BART color distribution: %s (total %d balloons)", color_counts, len(balloons)
    )

    # Detect auto-repeat anomalies (OS key repeat holding)
    autorepeat_indices: set[int] = set()
    for idx, balloon_events in enumerate(balloons):
        if _is_autorepeat_balloon(balloon_events):
            autorepeat_indices.add(idx)

    if autorepeat_indices:
        logger.info(
            "Auto-repeat detected on %d balloon(s): indices %s",
            len(autorepeat_indices),
            sorted(autorepeat_indices),
        )

    pump_counts: list[int] = []
    non_exploded_pumps: list[int] = []
    total_explosions = 0
    total_collections = 0

    color_pumps_all: dict[str, list[int]] = defaultdict(list)
    color_pumps_collected: dict[str, list[int]] = defaultdict(list)
    color_explosions: dict[str, int] = defaultdict(int)
    color_balloons: dict[str, int] = defaultdict(int)
    balloon_data: list[tuple[int, str, int, bool]] = []

    for trial_idx, balloon_events in enumerate(balloons):
        pumps = sum(1 for e in balloon_events if e.type == "pump")
        pump_counts.append(pumps)
        is_autorepeat = trial_idx in autorepeat_indices

        color = _extract_balloon_color(balloon_events)
        color_balloons[color] += 1

        terminal = next(
            (e.type for e in reversed(balloon_events) if e.type in ("collect", "explode")),
            None,
        )
        exploded = terminal == "explode"
        color_pumps_all[color].append(pumps)

        if exploded:
            total_explosions += 1
            color_explosions[color] += 1
        else:
            total_collections += 1 if terminal == "collect" else 0
            non_exploded_pumps.append(pumps)
            if not is_autorepeat:
                color_pumps_collected[color].append(pumps)

        if not is_autorepeat:
            balloon_data.append((trial_idx, color, pumps, exploded))

    total_balloons = len(balloons)

    if autorepeat_indices:
        session_warnings.append(
            f"Auto-repeat detected: {len(autorepeat_indices)} balloon(s) "
            f"excluded from behavioral-intention metrics."
        )
    all_pumps_array = np.array(pump_counts, dtype=np.float64)
    total_pumps = int(np.sum(all_pumps_array))

    # Calculate earnings performance
    _money_pumps = 0
    money_collected = 0.0
    for evt in events:
        if evt.type == "pump":
            _money_pumps += 1
        elif evt.type == "collect":
            money_collected += _money_pumps * config.reward_per_pump
            _money_pumps = 0
        elif evt.type == "explode":
            _money_pumps = 0

    # Benchmark: the study's expected earnings under EV-optimal play, derived
    # from the config (sum of trials x EV-optimal per color) rather than the old
    # hardcoded 27.25, which only held for the default 3x10 study at $0.25/pump
    # (issue 52). Config-driven, so any reward/cap/trial-count scores coherently.
    optimal_earnings = sum(
        col.trials * curves[col.name].optimal_ev
        for col in config.colors
        if col.name in curves
    )

    money_efficiency = money_collected / optimal_earnings if optimal_earnings > 0 else 0.0
    money_efficiency = float(np.clip(money_efficiency, 0.0, 2.0))

    color_pumps_behavioral: dict[str, list[int]] = {}
    for color in curves:
        collected = color_pumps_collected.get(color, [])
        all_data = color_pumps_all.get(color, [])
        chosen, used_fallback = _prefer_collected(collected, all_data)
        color_pumps_behavioral[color] = chosen
        if used_fallback and len(all_data) > 0:
            session_warnings.append(
                f"RNG fallback: {color} has only {len(collected)} collected "
                f"balloon(s); using all {len(all_data)} trials."
            )

    avg_pumps_all_balloons = float(np.mean(all_pumps_array))

    if non_exploded_pumps:
        adjusted_array = np.array(non_exploded_pumps, dtype=np.float64)
        average_pumps_adjusted = float(np.mean(adjusted_array))
    else:
        average_pumps_adjusted = avg_pumps_all_balloons

    explosion_rate = total_explosions / total_balloons if total_balloons > 0 else 0.0

    all_intra_latencies: list[float] = []
    for balloon_events in balloons:
        if _is_autorepeat_balloon(balloon_events):
            continue
        pump_times = [e.timestamp for e in balloon_events if e.type == "pump"]
        if len(pump_times) >= 2:
            diffs = np.diff(pump_times)
            all_intra_latencies.extend(diffs.tolist())

    intra_balloon_latencies = np.array(all_intra_latencies, dtype=np.float64)
    if intra_balloon_latencies.size > 0:
        intra_balloon_latencies = intra_balloon_latencies[intra_balloon_latencies < 2000.0]

    if intra_balloon_latencies.size > 0:
        mean_latency = float(np.mean(intra_balloon_latencies))
    else:
        mean_latency = 0.0

    ev_optimal_stops: dict[str, int] = {}
    for color, curve in curves.items():
        ev_optimal_stops[color] = curve.optimum

    ev_ratio_score, per_color_efficiency = _compute_ev_ratio_score(
        color_pumps_collected, color_balloons, curves=curves,
    )

    explosion_penalty, per_color_excess = _compute_explosion_penalty(
        color_explosions, color_balloons, curves=curves,
    )

    color_metrics_list: list[ColorMetrics] = []

    # Config order is canonical (the Master CSV derives column order from it);
    # colors played but absent from the config trail alphabetically.
    session_colors = [c for c in curves if c in color_balloons]
    session_colors += sorted(set(color_balloons) - set(curves))

    for color in session_colors:
        balloons_of_color = color_balloons[color]
        pumps_of_color = color_pumps_all.get(color, [])
        collected_of_color = color_pumps_collected.get(color, [])

        avg_pumps = float(np.mean(pumps_of_color)) if pumps_of_color else 0.0
        color_exp_rate = (
            color_explosions[color] / balloons_of_color if balloons_of_color > 0 else 0.0
        )

        behavioral_data, used_fb = _prefer_collected(collected_of_color, pumps_of_color)
        behavioral_avg = float(np.mean(behavioral_data)) if behavioral_data else 0.0

        color_ev_eff = per_color_efficiency.get(color)
        color_ev_optimal = ev_optimal_stops.get(color)
        color_excess_exp = per_color_excess.get(color)

        color_metrics_list.append(
            ColorMetrics(
                color=color,
                average_pumps=round(avg_pumps, 4),
                behavioral_avg_pumps=round(behavioral_avg, 4),
                explosion_rate=round(color_exp_rate, 4),
                total_balloons=balloons_of_color,
                collected_count=len(collected_of_color),
                risk_profile=ranking.risk_label.get(color, "medium"),
                used_fallback=used_fb,
                ev_efficiency=round(color_ev_eff, 4) if color_ev_eff is not None else None,
                ev_optimal_stop=color_ev_optimal,
                excess_explosion_rate=round(color_excess_exp, 4) if color_excess_exp is not None else None,
            ),
        )

    learning_rate = _calculate_learning_rate(balloon_data, ranking)
    half_split_lr = _calculate_half_split_learning_rate(balloon_data, ranking)
    tercile_lr = _calculate_tercile_learning_rate(balloon_data, ranking)
    cdt = _calculate_color_discrimination_trajectory(balloon_data, curves=curves, ranking=ranking)
    pes = _calculate_post_explosion_sensitivity(balloon_data, curves=curves)
    color_discrimination = _calculate_color_discrimination(color_pumps_behavioral, ranking)
    risk_adjustment = _calculate_risk_adjustment_score(color_pumps_behavioral, curves=curves)
    risk_sensitivity = _calculate_risk_sensitivity(color_pumps_behavioral, curves=curves)
    risk_calibration_score = float(np.clip(ev_ratio_score, 0.0, 100.0))

    ev_efficiency_uniformity = _compute_ev_efficiency_uniformity(
        per_color_efficiency, color_pumps_collected, color_balloons,
    )

    within_balloon_cv, between_balloon_cv = _calculate_consistency_breakdown(balloons)

    flat_strategy = _detect_flat_strategy(
        color_pumps_all, color_explosions, color_balloons,
        tercile_lr=tercile_lr,
        cdt=cdt,
        pes=pes,
        between_cv=between_balloon_cv,
        ranking=ranking,
    )

    # ``orange_avg_pumps`` keeps its legacy field name (schema / Master CSV
    # contract) but reads the study's highest-risk color, whatever it is called.
    high_collected_real = color_pumps_collected.get(ranking.high_color, [])
    has_high_data = len(high_collected_real) >= MIN_COLLECTED_FALLBACK
    orange_avg_pumps: float | None = (
        float(np.mean(high_collected_real)) if has_high_data else None
    )

    if intra_balloon_latencies.size > 1:
        cv = float(np.std(intra_balloon_latencies) / np.mean(intra_balloon_latencies))
        response_consistency = cv
    else:
        response_consistency = 0.0

    if mean_latency > 0:
        impulsivity_index = float(np.clip(1.0 - mean_latency / 800.0, 0.0, 1.0))
    else:
        impulsivity_index = 0.0

    # Patience is the mean pumps on the safest (lowest-risk) color: how far the
    # participant is willing to push where pushing is cheap.
    low_behavioral = color_pumps_behavioral.get(ranking.low_color, [])
    patience_index = float(np.mean(low_behavioral)) if low_behavioral else 0.0

    low_ev_efficiency = per_color_efficiency.get(ranking.low_color, 0.0)
    patience_index_normalized = float(np.clip(low_ev_efficiency, 0.0, 1.0))

    safe_hslr = 0.0 if np.isnan(half_split_lr) else half_split_lr
    safe_ev_uniformity = ev_efficiency_uniformity if ev_efficiency_uniformity is not None else 0.0
    safe_ev_ratio = ev_ratio_score / 100.0

    W_CALIBRATION = 0.35
    W_LEARNING = 0.25
    W_UNIFORMITY = 0.25
    W_MONEY = 0.15

    learning_component = (safe_hslr + 1.0) / 2.0
    calibration_component = safe_ev_ratio
    uniformity_component = safe_ev_uniformity
    money_component = min(1.0, money_efficiency)

    adaptive_strategy_score = (
        learning_component * W_LEARNING
        + calibration_component * W_CALIBRATION
        + uniformity_component * W_UNIFORMITY
        + money_component * W_MONEY
    ) * 100.0
    adaptive_strategy_score = float(np.clip(adaptive_strategy_score, 0.0, 100.0))

    per_color_normalized: list[float] = []
    for color in curves:
        behavioral_pumps = color_pumps_behavioral.get(color, [])
        if behavioral_pumps:
            opt_stop = curves[color].optimum
            if opt_stop > 0:
                color_mean = float(np.mean(behavioral_pumps)) / opt_stop
                per_color_normalized.append(color_mean)

    rng_normalized_pumps = (
        float(np.mean(per_color_normalized)) if per_color_normalized else 0.0
    )

    _ev_stops_with_eff = dict(ev_optimal_stops)
    for c, eff in per_color_efficiency.items():
        _ev_stops_with_eff[f"_{c}_efficiency"] = eff

    logger.info(
        "BART scored — balloons=%d pumps=%d explosions=%d "
        "avg_adjusted=%.2f avg_all=%.2f latency=%.1fms "
        "ev_ratio=%.1f explosion_penalty=%.3f risk_cal=%.1f "
        "adaptive_score=%.1f flat_strategy=%s "
        "patience=%.2f rng_norm=%.3f valid=%s warnings=%d",
        total_balloons,
        total_pumps,
        total_explosions,
        average_pumps_adjusted,
        avg_pumps_all_balloons,
        mean_latency,
        ev_ratio_score,
        explosion_penalty,
        risk_calibration_score,
        adaptive_strategy_score,
        flat_strategy,
        patience_index,
        rng_normalized_pumps,
        session_valid,
        len(session_warnings),
    )

    qc_fast_trials, qc_streak, qc_flagged = _compute_qc_flags(
        balloons,
        fast_response_ms=config.qc.fast_response_ms,
        zero_pump_streak=config.qc.zero_pump_streak,
    )

    # Payout conversion (issue 41): the one place the rounding rule lives.
    # Computed from the reported (2-dp) earnings via Decimal so "half-up"
    # means exactly that — float artifacts and banker's rounding never leak
    # into what a participant is owed.
    payout_amount = None
    if config.payout is not None:
        payout_amount = float(
            (Decimal(str(round(money_collected, 2))) * Decimal(str(config.payout.rate)))
            .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )

    metrics_obj = BARTMetrics(
        average_pumps_adjusted=round(average_pumps_adjusted, 4),
        explosion_rate=round(explosion_rate, 4),
        mean_latency_between_pumps=round(mean_latency, 4),
        total_balloons=total_balloons,
        total_pumps=total_pumps,
        total_explosions=total_explosions,
        total_collections=total_collections,
        color_metrics=color_metrics_list,
        learning_rate=round(learning_rate, 4),
        half_split_learning_rate=round(half_split_lr, 4),
        tercile_learning_rate=round(tercile_lr, 4),
        color_discrimination_trajectory=round(cdt, 4) if cdt is not None else None,
        post_explosion_sensitivity=round(pes, 4) if pes is not None else None,
        risk_adjustment_score=round(risk_adjustment, 4),
        color_discrimination_index=round(color_discrimination, 4) if not np.isnan(color_discrimination) else None,
        risk_sensitivity=round(risk_sensitivity, 4),
        ev_ratio_score=round(ev_ratio_score, 4),
        explosion_penalty=round(explosion_penalty, 4),
        risk_calibration_score=round(risk_calibration_score, 4),
        ev_efficiency_uniformity=round(ev_efficiency_uniformity, 4) if ev_efficiency_uniformity is not None else None,
        flat_strategy_detected=flat_strategy,
        money_collected=round(money_collected, 2),
        money_efficiency=round(money_efficiency, 4),
        ev_optimal_stops=_ev_stops_with_eff,
        rng_normalized_pumps=round(rng_normalized_pumps, 4),
        avg_pumps_all_balloons=round(avg_pumps_all_balloons, 4),
        orange_avg_pumps=round(orange_avg_pumps, 4) if orange_avg_pumps is not None else None,
        impulsivity_index=round(impulsivity_index, 4),
        patience_index=round(patience_index, 4),
        patience_index_normalized=round(patience_index_normalized, 4),
        response_consistency=round(response_consistency, 4),
        within_balloon_consistency=round(within_balloon_cv, 4),
        between_balloon_consistency=round(between_balloon_cv, 4),
        adaptive_strategy_score=round(adaptive_strategy_score, 4),
        session_valid=session_valid,
        session_warnings=session_warnings,
        qc_fast_response_trials=qc_fast_trials,
        qc_zero_pump_streak=qc_streak,
        qc_flagged=qc_flagged,
        qc_fast_response_ms=config.qc.fast_response_ms,
        qc_zero_pump_streak_threshold=config.qc.zero_pump_streak,
        payout_amount=payout_amount,
        payout_currency=config.payout.currency if config.payout else None,
        behavioral_profile={},
    )

    profile = _generate_behavioral_profile(metrics_obj, ranking)
    metrics_obj.behavioral_profile = profile

    return metrics_obj
