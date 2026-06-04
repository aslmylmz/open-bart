"""
BART Scoring Engine — NumPy Vectorized with Multi-Risk Profiles

Calculates psychometric metrics from raw BART event logs:
- Overall metrics: Average Pumps, Explosion Rate, Latency
- Color-based metrics: Performance by balloon color (purple/teal/orange)
- Learning metrics: Adaptation, risk adjustment, color discrimination
- Behavioral indices: Impulsivity, patience, consistency

Multi-Risk Profile System (Pymetrics-inspired):
- Purple balloons: Low risk (max 128 pumps) — rewards patience
- Teal balloons: Medium risk (max 32 pumps) — standard risk
- Orange balloons: High risk (max 8 pumps) — tests impulse control

Note: Uses neutral colors to avoid psychological bias (e.g., red = danger).

Explosion model (frontend):
    At each pump attempt k the balloon explodes with P(explode) = k / maxPumps
    (sequential independent Bernoulli trials with linearly increasing probability).
    This is NOT a pre-drawn uniform distribution — the optimal stopping point under
    this model is lower than maxPumps / 2.  For orange (N=8) the EV-maximizing
    stop is ~2 pumps; for teal (N=32) ~6 pumps; for purple (N=128) ~12 pumps.
    (Optimal stops are approximately sqrt(N), derived from the EV-curve peak of
    the sequential Bernoulli model — not maxPumps/4 as previously documented.)

RNG-Truncation Robustness:
    All behavioral-intention metrics use COLLECTED (non-exploded) balloons only.
    On an exploded balloon the pump count is truncated by RNG — the participant
    may have intended to pump further.  Using collected balloons ensures we
    measure what the participant CHOSE, not what RNG allowed.  When too few
    collected balloons are available for a given color (< MIN_COLLECTED_FALLBACK),
    the engine falls back to all balloons with a session warning.

References:
    Lejuez et al. (2002). Evaluation of a behavioral measure of risk taking:
    The Balloon Analogue Risk Task (BART).

    Pymetrics Multi-Risk BART: Measures learning and adaptability through
    varying risk profiles.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import numpy as np
from scipy import stats

from schemas.game_events import BARTMetrics, ColorMetrics, GameEvent

logger = logging.getLogger(__name__)


# ── Color Profile Constants ──────────────────────────────────────────────────

COLOR_PROFILES = {
    "purple": {"risk": "low", "max_pumps": 128},
    "teal": {"risk": "medium", "max_pumps": 32},
    "orange": {"risk": "high", "max_pumps": 8},
}

# Minimum collected (non-exploded) balloons per color before falling back
# to all balloons.  With 10 balloons per color, orange typically yields
# only 1-3 collected (P(survive) at 4 pumps ≈ 16%).  A threshold of 2
# ensures we have at least some variance estimate; below that, we fall
# back to all balloons (truncated but better than nothing).
MIN_COLLECTED_FALLBACK = 2


# ── EV Computation (Sequential Bernoulli Model) ─────────────────────────────


def _compute_ev(s: int, max_pumps: int) -> float:
    """
    Compute expected value of stopping after s pumps under the sequential
    Bernoulli explosion model: P(explode at pump k) = k / maxPumps.

    EV(s) = s × ∏(k=1 to s) (1 - k/N)

    Parameters
    ----------
    s : int
        Number of pumps before collecting.
    max_pumps : int
        Maximum pumps for this balloon color (N).

    Returns
    -------
    float
        Expected value (reward units = pump count × survival probability).
    """
    if s <= 0 or s > max_pumps:
        return 0.0
    survival = 1.0
    for k in range(1, s + 1):
        survival *= (1.0 - k / max_pumps)
        if survival <= 0:
            return 0.0
    return s * survival


def _compute_ev_optimal(max_pumps: int) -> tuple[int, float]:
    """
    Find the pump count that maximizes EV under P(explode at k) = k/N.

    Returns
    -------
    tuple[int, float]
        (optimal_stop, max_ev)
    """
    best_s = 0
    best_ev = 0.0
    for s in range(1, max_pumps + 1):
        ev = _compute_ev(s, max_pumps)
        if ev > best_ev:
            best_ev = ev
            best_s = s
        elif ev < best_ev * 0.5:
            # Past the peak and declining fast — stop searching
            break
    return best_s, best_ev


def _compute_survival_probability(s: int, max_pumps: int) -> float:
    """
    Compute probability of surviving s pumps: ∏(k=1 to s) (1 - k/N).
    """
    if s <= 0:
        return 1.0
    survival = 1.0
    for k in range(1, s + 1):
        survival *= (1.0 - k / max_pumps)
    return max(0.0, survival)


# Cache optimal stops so we don't recompute every call
_EV_OPTIMAL_CACHE: dict[int, tuple[int, float]] = {}


def _get_ev_optimal(max_pumps: int) -> tuple[int, float]:
    """Get cached EV-optimal stop for a given max_pumps."""
    if max_pumps not in _EV_OPTIMAL_CACHE:
        _EV_OPTIMAL_CACHE[max_pumps] = _compute_ev_optimal(max_pumps)
    return _EV_OPTIMAL_CACHE[max_pumps]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _segment_balloons(events: list[GameEvent]) -> list[list[GameEvent]]:
    """
    Split a flat event list into per-balloon segments.

    A new balloon starts after every 'collect' or 'explode' event.
    Returns a list of lists, one per balloon.
    """
    balloons: list[list[GameEvent]] = []
    current: list[GameEvent] = []

    for event in events:
        current.append(event)
        if event.type in ("collect", "explode"):
            balloons.append(current)
            current = []

    # Include any trailing pumps (incomplete final balloon)
    if current:
        balloons.append(current)

    return balloons


def _extract_balloon_color(balloon_events: list[GameEvent]) -> str:
    """
    Extract balloon color from event payload.

    Looks for 'color' or 'balloon_color' in the event payload.
    Defaults to 'teal' (medium risk) if not specified.
    """
    for event in balloon_events:
        if hasattr(event.payload, "color") and event.payload.color:
            return event.payload.color.lower()
        if hasattr(event.payload, "balloon_color") and event.payload.balloon_color:
            return event.payload.balloon_color.lower()

    # Fallback to teal (medium risk) if no color specified
    return "teal"


def _prefer_collected(
    collected: list[int],
    all_data: list[int],
    min_count: int = MIN_COLLECTED_FALLBACK,
) -> tuple[list[int], bool]:
    """
    Use collected (non-exploded) balloon data when available, else fall back.

    Parameters
    ----------
    collected : list[int]
        Pump counts from collected (non-exploded) balloons only.
    all_data : list[int]
        Pump counts from all balloons (including truncated/exploded).
    min_count : int
        Minimum collected balloons required; below this, fall back to all.

    Returns
    -------
    tuple[list[int], bool]
        (data_to_use, used_fallback)
    """
    if len(collected) >= min_count:
        return collected, False
    return all_data, True


def validate_bart_session(events: list[GameEvent]) -> dict[str, Any]:
    """
    Validate a BART session before scoring and flag potentially invalid data.

    Checks performed:
    1. Minimum balloon count  — < 15 -> invalid, 15-29 -> warning
    2. Color balance          — each color should have ~10 balloons
    3. Timestamp monotonicity — out-of-order timestamps indicate corruption
    4. Session speed          — < 30 s for a 30-balloon session is suspicious
    5. Pump uniformity        — near-zero std across all balloons suggests automation

    Parameters
    ----------
    events : list[GameEvent]
        Chronologically ordered BART events.

    Returns
    -------
    dict[str, Any]
        Keys:
          is_valid          (bool)
          warnings          (list[str])
          balloon_count     (int)
          color_distribution (dict[str, int])
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

    # 1. Minimum balloon count
    if balloon_count < 15:
        warnings.append(
            f"Critically incomplete session: only {balloon_count}/30 balloons played"
        )
        is_valid = False
    elif balloon_count < 30:
        warnings.append(f"Incomplete session: {balloon_count}/30 balloons played")

    # 2. Color balance
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

    # 3. Timestamp monotonicity
    for i in range(1, len(events)):
        if events[i].timestamp < events[i - 1].timestamp:
            warnings.append(
                f"Out-of-order timestamps at event index {i} "
                f"({events[i].timestamp:.1f} < {events[i-1].timestamp:.1f})"
            )
            is_valid = False
            break

    # 4. Session speed (suspicious if < 30 s for >= 15 balloons)
    total_time_ms = events[-1].timestamp - events[0].timestamp
    if balloon_count >= 15 and total_time_ms < 30_000:
        warnings.append(
            f"Session completed unusually fast: {total_time_ms / 1000:.1f}s "
            f"for {balloon_count} balloons"
        )

    # 5. Near-uniform pump counts (bot detection)
    pump_counts = [sum(1 for e in b if e.type == "pump") for b in balloons]
    if len(pump_counts) >= 10 and float(np.std(pump_counts)) < 0.5:
        warnings.append(
            "Suspicious: nearly identical pump counts across all balloons "
            "(possible automation or non-genuine engagement)"
        )

    return {
        "is_valid": is_valid,
        "warnings": warnings,
        "balloon_count": balloon_count,
        "color_distribution": dict(color_counts),
    }


def _calculate_learning_rate(
    balloon_data: list[tuple[int, str, int, bool]],
) -> float:
    """
    Calculate learning rate using linear regression on pump counts over time.

    Uses COLLECTED (non-exploded) balloons only to avoid RNG truncation bias.
    On exploded balloons the pump count is cut short by RNG, which can fake
    a learning trend if explosions cluster in one half of the session.
    Falls back to all balloons per color if fewer than MIN_COLLECTED_FALLBACK
    collected balloons are available.

    For each color, fits a line to pump counts across trials to detect whether
    the participant adapts: pumping more on purple over time (exploitation) or
    pumping less on orange over time (risk avoidance).

    Teal is excluded because the direction of "learning" is ambiguous —
    increasing pumps is correct when starting below EV-optimal (5 pumps),
    decreasing is correct when starting above. Only purple and orange have
    unambiguous directionality.

    Note: With only 10 trials per color this regression is noisy — a single
    outlier trial can significantly shift the slope.  See half_split_learning_rate
    for a more robust alternative at this sample size.

    Parameters
    ----------
    balloon_data : list[tuple[int, str, int, bool]]
        List of (trial_number, color, pumps, exploded) tuples.

    Returns
    -------
    float
        Learning rate coefficient (-1 to 1). Positive = adaptive learning.
    """
    if len(balloon_data) < 3:
        return 0.0

    # Separate by color, keeping exploded flag
    color_trials_all: dict[str, list[tuple[int, int]]] = defaultdict(list)
    color_trials_collected: dict[str, list[tuple[int, int]]] = defaultdict(list)

    for trial, color, pumps, exploded in balloon_data:
        color_trials_all[color].append((trial, pumps))
        if not exploded:
            color_trials_collected[color].append((trial, pumps))

    learning_slopes = []

    for color in color_trials_all:
        # Prefer collected, fall back to all if insufficient
        collected = color_trials_collected.get(color, [])
        all_trials = color_trials_all[color]
        trials = collected if len(collected) >= MIN_COLLECTED_FALLBACK else all_trials

        if len(trials) < 2:
            continue

        trial_nums = np.array([t[0] for t in trials])
        pump_counts = np.array([t[1] for t in trials])

        # Linear regression: pumps ~ trial_number
        if len(trial_nums) >= 2 and np.std(trial_nums) > 0:
            slope, _intercept, r_value, _p_value, _std_err = stats.linregress(
                trial_nums,
                pump_counts,
            )

            # Weight by R^2 (how well the trend fits)
            weighted_slope = slope * (r_value**2)

            # For orange balloons, negative slope is good (learning to reduce risk)
            # For purple balloons, positive slope is good (learning to maximize)
            # Teal excluded: direction is ambiguous relative to EV-optimal
            if color == "orange":
                learning_slopes.append(-weighted_slope)
            elif color == "purple":
                learning_slopes.append(weighted_slope)

    if not learning_slopes:
        return 0.0

    mean_slope = float(np.mean(learning_slopes))
    if np.isnan(mean_slope):
        return 0.0
    return float(np.clip(mean_slope, -1.0, 1.0))


def _calculate_half_split_learning_rate(
    balloon_data: list[tuple[int, str, int, bool]],
) -> float:
    """
    Calculate learning rate by comparing first-half vs second-half trials per color.

    Uses COLLECTED (non-exploded) balloons only to avoid RNG truncation bias.
    If the first half of a color's balloons happen to explode early due to bad
    RNG, their pump counts are artificially lower, faking a "learning" signal
    in the second half.  Using collected-only removes this confound.
    Falls back to all balloons per color if fewer than 4 collected are available.

    More robust than regression-based learning_rate at N=10 per color because:
    - No single outlier trial can dominate the result.
    - Directly interpretable: a positive value means behavior improved in the
      second half relative to the first.

    Improvement direction per color:
    - Orange: pumping LESS in the second half = learning (delta negated).
    - Purple: pumping MORE in the second half = learning (delta kept).
    - Teal:   excluded — direction is ambiguous relative to EV-optimal (5 pumps).
              Increasing toward optimal from below would be correct, but
              decreasing from above would also be correct.

    Parameters
    ----------
    balloon_data : list[tuple[int, str, int, bool]]
        List of (trial_number, color, pumps, exploded) tuples.

    Returns
    -------
    float
        Learning rate (-1 to 1). Positive = improved adaptive behavior in second half.
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
        # Prefer collected, fall back to all if insufficient
        collected = color_trials_collected.get(color, [])
        all_trials = color_trials_all[color]
        trials = collected if len(collected) >= 4 else all_trials

        if len(trials) < 4:  # Need at least 4 trials to form a meaningful split
            continue

        sorted_trials = sorted(trials, key=lambda x: x[0])
        half = len(sorted_trials) // 2

        first_half_mean = float(np.mean([t[1] for t in sorted_trials[:half]]))
        second_half_mean = float(np.mean([t[1] for t in sorted_trials[half:]]))
        overall_mean = float(np.mean([t[1] for t in sorted_trials]))

        if overall_mean == 0:
            continue

        # Relative change: positive = pumped more in second half
        delta = (second_half_mean - first_half_mean) / overall_mean

        # Teal excluded: direction is ambiguous relative to EV-optimal
        if color == "orange":
            learning_scores.append(-delta)  # Less pumping = improvement
        elif color == "purple":
            learning_scores.append(delta)   # More pumping = improvement

    if not learning_scores:
        return 0.0

    mean_learning = float(np.mean(learning_scores))
    if np.isnan(mean_learning):
        return 0.0
    return float(np.clip(mean_learning, -1.0, 1.0))


def _calculate_tercile_learning_rate(
    balloon_data: list[tuple[int, str, int, bool]],
) -> float:
    """
    Learning rate comparing first-third vs last-third trials per color.

    Drops the noisy middle third to capture late learners more sharply.
    With 10 trials per color: first 3 vs last 3 (middle 4 excluded).
    Same directional logic as half-split: orange less = learning, purple more = learning.
    Teal excluded: direction is ambiguous relative to EV-optimal.

    Uses COLLECTED (non-exploded) balloons only; falls back to all if < 3 collected.
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

        # Teal excluded: direction is ambiguous relative to EV-optimal
        if color == "orange":
            learning_scores.append(-delta)
        elif color == "purple":
            learning_scores.append(delta)

    if not learning_scores:
        return 0.0

    result = float(np.mean(learning_scores))
    return 0.0 if np.isnan(result) else float(np.clip(result, -1.0, 1.0))


def _calculate_color_discrimination_trajectory(
    balloon_data: list[tuple[int, str, int, bool]],
) -> float | None:
    """
    Track how purple-vs-orange discrimination changes across session thirds.

    Splits the full session (all 30 balloons in chronological order) into 3 blocks
    of ~10 balloons. For each block, computes discrimination = mean(purple_pumps)
    - mean(orange_pumps). Returns the change from block 1 to block 3, normalized
    by the EV-optimal discrimination (≈ 9 pumps: purple_opt ≈ 11, orange_opt ≈ 2).

    Interpretation:
      +1.0 = gained one full optimal-spread of discrimination
       0.0 = no change in discrimination across session
      -1.0 = lost one full optimal-spread (e.g., converged from over-spread)

    Prefers collected (non-exploded) balloons per block to avoid RNG-truncation
    inflation of orange discrimination. Falls back to all balloons per color
    within a block if none were collected.
    Returns None if purple or orange appear in fewer than 2 blocks.
    """
    if len(balloon_data) < 6:
        return None

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
        purple_collected = [pumps for _, color, pumps, exploded in block
                           if color == "purple" and not exploded]
        orange_collected = [pumps for _, color, pumps, exploded in block
                           if color == "orange" and not exploded]
        # Fall back to all if no collected data for a color in this block
        if not purple_collected:
            purple_collected = [pumps for _, color, pumps, _ in block if color == "purple"]
        if not orange_collected:
            orange_collected = [pumps for _, color, pumps, _ in block if color == "orange"]
        if purple_collected and orange_collected:
            block_disc.append(float(np.mean(purple_collected)) - float(np.mean(orange_collected)))
        else:
            block_disc.append(None)

    # Use the earliest and latest blocks that have both colors.
    # Some participants have 0 purple in Block 1 due to random sequencing.
    valid = [(i, d) for i, d in enumerate(block_disc) if d is not None]
    if len(valid) < 2:
        return None

    first_block_disc = valid[0][1]
    last_block_disc = valid[-1][1]
    change = last_block_disc - first_block_disc

    # Normalize by EV-optimal discrimination (purple≈11, orange≈2 → spread≈9)
    # This is stable across participants and interpretable:
    # +1 = gained one optimal-spread of discrimination across the session.
    optimal_spread = 9.0
    return float(change / optimal_spread)


def _calculate_post_explosion_sensitivity(
    balloon_data: list[tuple[int, str, int, bool]],
) -> float | None:
    """
    Measure pump change on the next same-color balloon after an explosion.

    For each explosion event, find the next balloon of the SAME color.
    Compute the change normalized by EV-optimal stop for that color:
    (pumps_before - pumps_after) / ev_optimal_stop.
    Positive = participant reduced pumps after a pop (adaptive behavior).

    Normalized by EV-optimal stop for the balloon color, ensuring equal
    weighting across risk levels. Without this, orange (optimal=2) would
    dominate: a 1-pump change is 50% proportionally but only ~11% when
    normalized by EV-optimal.

    Returns the mean across all same-color explosion→follow-up pairs.
    Returns None if no same-color follow-ups exist after explosions.
    """
    sorted_data = sorted(balloon_data, key=lambda x: x[0])

    changes = []
    for i, (trial, color, pumps, exploded) in enumerate(sorted_data):
        if not exploded or pumps == 0:
            continue
        # Find next balloon of the same color
        for j in range(i + 1, len(sorted_data)):
            if sorted_data[j][1] == color:
                next_pumps = sorted_data[j][2]
                # Normalize by EV-optimal for this color, not by pre-explosion pumps
                opt_stop, _ = _get_ev_optimal(
                    COLOR_PROFILES.get(color, {}).get("max_pumps", 32)
                )
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
) -> float:
    """
    Calculate color discrimination index using effect size (Cohen's d).

    Measures how well the user discriminates between purple (safe) and orange (risky)
    balloons. Higher values indicate stronger behavioral differentiation.

    Expects collected-only pump data to avoid RNG truncation bias on orange.

    Parameters
    ----------
    color_pumps : dict[str, list[int]]
        Pump counts grouped by color (should be collected-only for accuracy).

    Returns
    -------
    float
        Discrimination index (0-1). 1 = perfect discrimination (d >= 2.0).
    """
    purple_pumps = color_pumps.get("purple", [])
    orange_pumps = color_pumps.get("orange", [])

    # Need at least 2 samples of each color for variance calculation
    if len(purple_pumps) < 2 or len(orange_pumps) < 2:
        return 0.0

    purple_arr = np.array(purple_pumps)
    orange_arr = np.array(orange_pumps)

    mean_diff = np.mean(purple_arr) - np.mean(orange_arr)
    pooled_std = np.sqrt(
        (np.var(purple_arr, ddof=1) + np.var(orange_arr, ddof=1)) / 2,
    )

    if pooled_std == 0:
        # If variance is zero, discrimination is perfect only if means differ
        return 1.0 if mean_diff > 0 else 0.0

    cohens_d = mean_diff / pooled_std

    # Normalize to [0, 1]: d >= 2.0 is considered very strong discrimination
    discrimination = np.clip(cohens_d / 2.0, 0.0, 1.0)

    if np.isnan(discrimination):
        return 0.0
    return float(discrimination)


def _calculate_risk_sensitivity(
    color_pumps: dict[str, list[int]],
) -> float:
    """
    Calculate risk sensitivity using Pearson correlation.

    Measures alignment between balloon risk capacity and pumping behavior.
    High correlation (r > 0.8) indicates the participant understands the risk
    model and adjusts behavior proportionally (purple > teal > orange).

    Expects collected-only pump data to avoid RNG truncation bias.

    Note: If the participant uses a flat strategy (same pumps for all colors),
    variance in risk_capacities will not correlate with behavior and r ~ 0.
    This is a known limitation — a flat strategy is ambiguous (risk-neutral or
    unresponsive), so a near-zero score should not be interpreted as a failure.

    Parameters
    ----------
    color_pumps : dict[str, list[int]]
        Pump counts separated by color (should be collected-only for accuracy).

    Returns
    -------
    float
        Correlation coefficient (-1 to 1).
    """
    risk_capacities = []
    user_pumps = []

    for color, pumps in color_pumps.items():
        if color not in COLOR_PROFILES:
            continue
        capacity = COLOR_PROFILES[color]["max_pumps"]
        for p in pumps:
            risk_capacities.append(capacity)
            user_pumps.append(p)

    if len(risk_capacities) < 3:
        return 0.0

    # Constant inputs yield undefined correlation (all pumps identical across colors)
    if np.std(user_pumps) == 0 or np.std(risk_capacities) == 0:
        return 0.0

    r, _p = stats.pearsonr(risk_capacities, user_pumps)

    if np.isnan(r):
        return 0.0
    return float(r)


def _calculate_risk_adjustment_score(
    color_pumps: dict[str, list[int]],
) -> float:
    """
    Calculate risk adjustment score based on EV-optimal behavior per color.

    Scores the participant on whether their average pumps are calibrated to the
    true EV-optimal stopping point for each balloon color.  The optimal stops are
    derived from the peak of the EV curve under the sequential Bernoulli model
    (P(explode at pump k) = k / maxPumps) and are approximately sqrt(N):

    - Purple (N=128): EV-optimal = 12 pumps
    - Teal   (N=32):  EV-optimal = 6 pumps
    - Orange (N=8):   EV-optimal = 2 pumps

    Each color is scored by absolute distance from its optimal stop, scaled so
    that score = 100 at the optimum and decreases linearly to 0 at the extremes
    (either 0 pumps or maxPumps for that color).  This correctly penalises both
    under-pumping AND over-pumping — the old asymmetric np.clip formulas rewarded
    maxing out purple and zeroing out orange, which is inconsistent with the
    EV-curve shape.

    Returns
    -------
    float
        Risk adjustment score (0-100). 100 = perfectly calibrated.
    """
    cp = color_pumps  # local alias to match caller convention

    optimal_stops = {"purple": 12.0, "teal": 6.0, "orange": 2.0}
    max_pumps_caps = {"purple": 128, "teal": 32, "orange": 8}
    scores = []

    for color in ["purple", "teal", "orange"]:
        if color in cp and len(cp[color]) > 0:
            mean_pumps = np.mean(cp[color])
            opt = optimal_stops[color]
            mx = max_pumps_caps[color]

            # Max possible distance from optimal (either down to 0, or up to max_pumps)
            max_dist = max(opt, mx - opt)

            # Score is 100 at optimal, scaling linearly down to 0 at the extremes
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
    min_collected: int = MIN_COLLECTED_FALLBACK,
) -> tuple[float, dict[str, float]]:
    """
    Compute EV-Ratio Risk Calibration Score (EV-weighted).

    For each color with sufficient COLLECTED data, computes:
        EV(round(mean_behavioral_pumps)) / EV(optimal)

    Colors where balloons existed but none were collected (all exploded)
    receive efficiency = 0.

    The overall score is a WEIGHTED average of per-color efficiencies,
    where each color's weight is its EV-optimal value. This means
    high-reward colors (purple, EV≈6.46) contribute more than low-reward
    colors (orange, EV≈1.31), reflecting actual reward potential.

    Weights: purple ≈ 60%, teal ≈ 28%, orange ≈ 12%.

    Parameters
    ----------
    color_pumps_collected : dict[str, list[int]]
        Pump counts per color — COLLECTED ONLY (not fallback).
    color_balloons : dict[str, int]
        Total balloons per color (including exploded).
    min_collected : int
        Minimum collected balloons required per color.

    Returns
    -------
    tuple[float, dict[str, float]]
        (overall_score, {color: efficiency})
        efficiency values are in [0, 1], overall_score in [0, 100].
    """
    per_color_efficiency: dict[str, float] = {}

    for color in ["purple", "teal", "orange"]:
        if color not in COLOR_PROFILES:
            continue
        total = color_balloons.get(color, 0)
        if total == 0:
            continue  # Color not in session

        pumps = color_pumps_collected.get(color, [])
        if len(pumps) < min_collected:
            # Balloons existed but insufficient collected — participant failed
            # to adapt. EV-efficiency = 0 (earned nothing from this risk level).
            per_color_efficiency[color] = 0.0
            continue

        max_p = COLOR_PROFILES[color]["max_pumps"]
        optimal_stop, optimal_ev = _get_ev_optimal(max_p)

        if optimal_ev <= 0:
            continue

        mean_pumps = float(np.mean(pumps))
        # Use floor and ceil to interpolate EV for non-integer mean
        s_low = max(0, int(np.floor(mean_pumps)))
        s_high = min(max_p, int(np.ceil(mean_pumps)))

        if s_low == s_high:
            participant_ev = _compute_ev(s_low, max_p)
        else:
            frac = mean_pumps - s_low
            ev_low = _compute_ev(s_low, max_p)
            ev_high = _compute_ev(s_high, max_p)
            participant_ev = ev_low + frac * (ev_high - ev_low)

        efficiency = min(1.0, participant_ev / optimal_ev)
        per_color_efficiency[color] = efficiency

    if not per_color_efficiency:
        return 0.0, {}

    # EV-weighted average: weight each color by its optimal EV value
    weighted_sum = 0.0
    weight_total = 0.0
    for color, eff in per_color_efficiency.items():
        max_p = COLOR_PROFILES[color]["max_pumps"]
        _, optimal_ev = _get_ev_optimal(max_p)
        weighted_sum += eff * optimal_ev
        weight_total += optimal_ev

    overall = (weighted_sum / weight_total) * 100.0 if weight_total > 0 else 0.0
    return overall, per_color_efficiency


def _compute_explosion_penalty(
    color_explosions: dict[str, int],
    color_balloons: dict[str, int],
) -> tuple[float, dict[str, float]]:
    """
    Compute explosion penalty: excess explosion rate vs expected at EV-optimal.

    For each color, the expected explosion rate at optimal play is:
        1 - ∏(k=1 to s*) (1 - k/N)
    where s* is the EV-optimal stop.

    Excess = max(0, observed_rate - expected_rate).
    Final penalty = mean of per-color excess rates.

    Returns
    -------
    tuple[float, dict[str, float]]
        (overall_penalty in [0,1], {color: excess_rate})
    """
    per_color_excess: dict[str, float] = {}

    for color in ["purple", "teal", "orange"]:
        if color not in COLOR_PROFILES:
            continue
        total = color_balloons.get(color, 0)
        if total == 0:
            continue

        explosions = color_explosions.get(color, 0)
        observed_rate = explosions / total

        max_p = COLOR_PROFILES[color]["max_pumps"]
        optimal_stop, _ = _get_ev_optimal(max_p)
        expected_rate = 1.0 - _compute_survival_probability(optimal_stop, max_p)

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
    Compute EV-efficiency uniformity: 1 - CV(per_color_efficiencies).

    Measures how uniform EV-efficiency is across risk levels.
    High score = participant achieves similar EV-efficiency across colors
    (but not necessarily high efficiency).
    """
    effective_efficiency: dict[str, float] = {}

    for color in ["purple", "teal", "orange"]:
        total = color_balloons.get(color, 0)
        if total == 0:
            continue  # Color not present in session

        collected = color_pumps_collected.get(color, [])

        if len(collected) >= MIN_COLLECTED_FALLBACK:
            # Use computed EV-efficiency
            if color in per_color_efficiency:
                effective_efficiency[color] = per_color_efficiency[color]
        else:
            # Balloons existed but insufficient collected — participant failed
            # to adapt to this risk level. EV-efficiency = 0 (earned nothing).
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
) -> bool:
    """
    Detect if participant uses an undifferentiated flat pumping strategy.

    A flat strategy is indicated by:
    1. Low CV of per-color RAW mean pumps (similar target across colors)
    2. Explosion rate increasing sharply with risk level (confirming the
       flat target exceeds safe capacity on riskier colors)

    The raw means (not collected-only) are used here because collected-only
    on orange would hide the flat target (truncated by explosions).

    Temporal Learning Exemption
    --------------------------
    Participants who *start* with similar low pumps across colors but then
    explore and adapt should NOT be labeled flat. We check learning signals
    (tercile improvement, discrimination trajectory, post-explosion
    sensitivity, between-balloon variability) and exempt learners.
    """
    if len(color_pumps_all) < 2:
        return False

    # ── Temporal learning exemption ──────────────────────────────────────
    # If ANY strong learning signal is present, the participant is exploring
    # and adapting, not playing a genuinely flat strategy.
    is_learner = (
        tercile_lr > 0.15                            # improved from 1st→3rd third
        or (cdt is not None and cdt > 0.20)           # learned to differentiate colors
        or (pes is not None and pes > 0.15)           # reduced pumps after explosions
        or between_cv > 0.45                          # high strategy variation = experimenting
    )

    # Compute raw means per color
    raw_means: dict[str, float] = {}
    for color in ["purple", "teal", "orange"]:
        pumps = color_pumps_all.get(color, [])
        if pumps:
            raw_means[color] = float(np.mean(pumps))

    if len(raw_means) < 2:
        return False

    values = list(raw_means.values())
    mean_val = float(np.mean(values))
    if mean_val <= 0:
        return False

    purple_mean = raw_means.get("purple", 0)
    orange_mean = raw_means.get("orange", 0)

    # ── Temporal learning & Variability exemption ────────────────────────
    # If ANY strong learning signal is present, OR if the participant's
    # pumping varies significantly (not a flat line), they are exploring
    # or being erratic, which is fundamentally NOT a flat strategy.
    is_variable = (
        tercile_lr > 0.15                            # improved from 1st→3rd third
        or (cdt is not None and cdt > 0.20)          # learned to differentiate colors
        or (pes is not None and pes > 0.15)          # reduced pumps after explosions
        or between_cv > 0.30                         # high strategy variation = experimenting, not flat
        or (orange_mean > 0 and purple_mean / orange_mean >= 1.7) # clear cross-color differentiation
    )

    if is_variable:
        return False

    # Check 1: Extremely low flat pumping (e.g. always pump 1-2 and collect).
    # Pumping <= 2 on average across all colors is clearly undifferentiated.
    if mean_val <= 2.0:
        return True

    # Check 2: Moderate flat pumping that ignores color risk levels.
    # To avoid false positives on conservative learners who differentiate slightly,
    # we require very tight grouping (CV < 0.15) and a mean well below optimal.
    cv = float(np.std(values) / mean_val)
    if cv < 0.15 and purple_mean > 0 and purple_mean < 6.0:
        return True

    # Check 3: Does explosion rate increase with risk while pumps remain flat?
    # A flat target X produces low exp on purple, high on orange.
    # We only consider this if their pumps are reasonably flat (CV < 0.25).
    # If CV > 0.25, they are differentiating, so explosion gradient is outcome, not strategy.
    if cv < 0.25:
        explosion_rates: dict[str, float] = {}
        for color in ["purple", "teal", "orange"]:
            total = color_balloons.get(color, 0)
            if total > 0:
                explosion_rates[color] = color_explosions.get(color, 0) / total

        orange_exp = explosion_rates.get("orange", 0)
        purple_exp = explosion_rates.get("purple", 0)
        
        if orange_exp > 0.8 and purple_exp < 0.5:
            return True

    return False


def _is_autorepeat_balloon(balloon_events: list[GameEvent]) -> bool:
    """Detect balloons where the participant held spacebar (OS auto-repeat).

    Auto-repeat produces pump events at the OS key-repeat rate (~30-50 ms)
    with near-zero variance.  Real individual key presses average ≥ 100 ms
    with higher variance.  We flag a balloon if its median inter-pump
    latency is below 80 ms — physically impossible for discrete presses.
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
    Decompose response consistency into within-balloon and between-balloon components.

    The single global `response_consistency` CV cannot distinguish two very
    different participant profiles:
    - A strategically variable participant who pumps fast on some balloons and
      slow on others (high between-balloon CV, low within-balloon CV).
    - An erratic participant who is inconsistent even during a single balloon
      (high within-balloon CV regardless of between-balloon variation).

    Between-balloon CV uses COLLECTED (non-exploded) balloons only.
    Exploded balloons have truncated pump counts that introduce artificial
    variability not reflecting the participant's actual strategic consistency.
    Falls back to all balloons if fewer than 5 collected balloons available.

    Within-balloon CV is NOT affected by explosion truncation — it measures
    intra-pump latency timing, which is the same regardless of whether the
    balloon later explodes.

    Parameters
    ----------
    balloons : list[list[GameEvent]]
        Per-balloon event segments from _segment_balloons.

    Returns
    -------
    tuple[float, float]
        (within_balloon_cv, between_balloon_cv)

        within_balloon_cv  — mean CV of intra-pump latencies within each balloon
                             that had >= 3 pumps; 0.0 if no qualifying balloons.
        between_balloon_cv — CV of pump counts across collected balloons; 0.0 if
                             fewer than 2 balloons or zero mean.
    """
    # Within-balloon: average of per-balloon latency CVs (not affected by truncation)
    # Skip auto-repeat balloons (spacebar held down → OS key repeat ≈ 30-50 ms)
    within_cvs: list[float] = []
    for balloon_events in balloons:
        if _is_autorepeat_balloon(balloon_events):
            continue
        pump_times = [e.timestamp for e in balloon_events if e.type == "pump"]
        if len(pump_times) >= 3:
            diffs = np.diff(pump_times)
            diffs = diffs[diffs < 2000.0]  # Filter outlier pauses > 2 s
            if len(diffs) >= 2 and np.mean(diffs) > 0:
                cv = float(np.std(diffs) / np.mean(diffs))
                within_cvs.append(cv)

    within_balloon_cv = float(np.mean(within_cvs)) if within_cvs else 0.0

    # Between-balloon: CV of pump counts WITHIN each color, then averaged.
    # This isolates genuine strategic inconsistency from appropriate
    # cross-color variation (pumping more on purple than orange is correct,
    # not inconsistent).
    # Uses collected-only balloons per color to avoid truncation variance.
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
        # Prefer collected, fall back to all if too few
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
) -> dict[str, Any]:
    """
    Generate narrative behavioral profile from EV-efficiency-based metrics.

    Uses scientifically grounded thresholds tied to the Bernoulli explosion
    model rather than arbitrary raw pump count cutoffs.

    Dimensions:
    - Risk Style         (risk_calibration_score, ev_efficiency, flat_strategy)
    - Adaptability       (half_split_learning_rate)
    - Consistency        (within_balloon_consistency, between_balloon_consistency)
    """
    profile: dict[str, Any] = {}

    # 1. Risk Style — use EV-based metrics instead of raw pump counts
    # NOTE: These labels describe observed task behavior only. They do not
    # predict real-world risk attitudes or occupational fit (Lauriola et al., 2014).

    # Per-color efficiency for differentiated-profile detection
    purple_eff = metrics.ev_optimal_stops.get("_purple_efficiency", 0.0)
    teal_eff = metrics.ev_optimal_stops.get("_teal_efficiency", 0.0)
    orange_eff = metrics.ev_optimal_stops.get("_orange_efficiency", 0.0)
    # A participant who is efficient on safe balloons but blows up on risky ones
    # is differentiated — they just over-calibrate on the high-risk end.
    has_selective_strength = purple_eff >= 0.70 and orange_eff < 0.30

    # Learning signal flags (used in multiple cascade branches)
    _tercile_lr = metrics.tercile_learning_rate
    _cdt = metrics.color_discrimination_trajectory
    _has_strong_learning = (
        metrics.half_split_learning_rate > 0.15
        or (_tercile_lr is not None and _tercile_lr > 0.15)
    )
    _has_discrim_growth = _cdt is not None and _cdt > 0.20

    # Uniformity (ev_efficiency_uniformity) is the primary differentiator:
    #   high (>0.60) = performs similarly across all balloon colors
    #   low  (<0.40) = divergent strategy across colors
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
    #    Uniformly excellent: high calibration + good across ALL colors
    elif (metrics.risk_calibration_score >= 80
          and metrics.explosion_penalty < 0.25
          and _unif > 0.60):
        risk_style = "Calibrated Risk Optimizer"
        risk_desc = (
            "You calibrated your risk-taking precisely to match actual danger levels. "
            "You pushed when it was safe and pulled back when risk was high — "
            "maximizing expected reward across conditions."
        )

    # ── 3. Selective Over-Optimizer ──────────────────────────────────────
    #    Clearly differentiated (low uniformity) + selective pattern + costly
    elif (has_selective_strength
          and _unif < 0.40
          and metrics.explosion_penalty > 0.25):
        risk_style = "Selective Over-Optimizer"
        risk_desc = (
            "You showed strong calibration on safer balloons, extracting near-optimal "
            "value from low-risk opportunities. However, you pushed too far on the "
            "highest-risk balloons, causing avoidable explosions. Your strategy is "
            "differentiated — the opportunity is in pulling back earlier when "
            "hazard rates are steepest."
        )

    # ── 4. Persistent Risk Taker ─────────────────────────────────────────
    #    Over-pumps across ALL colors uniformly (not selective)
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
    #    Low uniformity but NOT selectively good — confused/random strategy
    elif (_unif < 0.35
          and not has_selective_strength
          and metrics.explosion_penalty > 0.15):
        risk_style = "Context-Insensitive Risk Taker"
        risk_desc = (
            "Your pumping varied across balloon types but without matching the "
            "actual risk structure. This pattern suggests difficulty reading which "
            "situations are genuinely dangerous versus which ones reward persistence."
        )

    # ── 6. Loss-Averse Responder ─────────────────────────────────────────
    #    Uniformly cautious — stops well below optimal everywhere
    elif (metrics.rng_normalized_pumps < 0.60
          and metrics.explosion_penalty < 0.16):
        risk_style = "Loss-Averse Responder"
        risk_desc = (
            "You prioritized certainty, stopping well before optimal on most balloons. "
            "This minimized losses but left significant expected reward uncollected."
        )

    # ── 7. Emerging Optimizer ────────────────────────────────────────────
    #    Selective pattern but PRODUCTIVE — decent calibration + money
    elif (has_selective_strength
          and metrics.risk_calibration_score >= 75
          and metrics.money_efficiency >= 0.60):
        risk_style = "Emerging Optimizer"
        risk_desc = (
            "You showed a developing sense of risk calibration — your pumping strategy "
            "captured meaningful expected value, especially on safer balloons. While not "
            "yet uniformly optimal across all risk levels, your decisions translated into "
            "solid monetary returns, indicating an intuitive grasp of the risk-reward "
            "structure."
        )

    # ── 8. Adaptive Risk Learner ─────────────────────────────────────────
    #    Clear learning trajectory across the task
    elif _has_strong_learning and _has_discrim_growth:
        risk_style = "Adaptive Risk Learner"
        risk_desc = (
            "You showed clear improvement across the task. Your strategy evolved as you "
            "gathered experience — you adjusted your pumping to better differentiate "
            "between balloon risk levels. This learning trajectory is a strong signal "
            "of feedback-driven adaptation."
        )

    # ── 9. Conservative Strategist ───────────────────────────────────────
    #    Cautious overall — low pumping, low explosions
    elif (metrics.rng_normalized_pumps < 0.75
          and metrics.explosion_penalty < 0.20):
        risk_style = "Conservative Strategist"
        risk_desc = (
            "You employed a cautious approach, consistently stopping below the "
            "optimal pumping level. While this left some expected value uncollected, "
            "it also kept your explosion rate low. Your strategy favored certainty "
            "and loss avoidance over maximum expected gain."
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

    # 2. Key Traits — EV-efficiency based
    # Each trait should be informative and non-contradictory with the main profile.
    traits = []

    # Consistency traits
    if metrics.within_balloon_consistency < 0.2 and metrics.between_balloon_consistency < 0.4:
        traits.append("Highly Consistent")
    elif metrics.within_balloon_consistency > 0.6:
        traits.append("Erratic Within-Balloon")
    elif metrics.between_balloon_consistency > 1.0:
        traits.append("Strategically Variable")

    # Learning trajectory
    if metrics.half_split_learning_rate > 0.1:
        traits.append("Improving Over Time")
    elif metrics.half_split_learning_rate < -0.1:
        traits.append("Declining Over Time")

    # Orange handling
    if metrics.orange_avg_pumps is not None and metrics.orange_avg_pumps > 4.0:
        traits.append("Impulsive on High-Risk")

    # Purple mastery: only flag if genuinely near-optimal (top quartile)
    _pe = metrics.ev_optimal_stops.get("_purple_efficiency")
    if _pe is not None and _pe > 0.90:
        traits.append("Near-Optimal on Safe Balloons")
    elif metrics.patience_index > 20:
        traits.append("Over-Pumper on Safe Balloons")

    if metrics.flat_strategy_detected:
        traits.append("Flat Strategy")

    if metrics.explosion_penalty > 0.3:
        traits.append("High Explosion Penalty")

    # Ensure at least one descriptive trait based on overall behavior
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


def enrich_profile_with_dospert(
    profile: dict[str, Any],
    metrics: BARTMetrics,
    dospert: dict[str, float],
) -> dict[str, Any]:
    """
    Generate attitude-behavior congruence reflections by comparing 
    DOSPERT self-report domains with BART behavioral metrics.

    Uses a Mutually Exclusive and Completely Exhaustive (MECE) 3x3 grid
    mapping DOSPERT tertiles against Bayes-optimal RNP thresholds.
    """
    reflections: list[dict[str, str]] = []

    fin = dospert.get("financial", 0)
    rec = dospert.get("recreational", 0)
    hs = dospert.get("health_safety", 0)
    eth = dospert.get("ethical", 0)
    soc = dospert.get("social", 0)

    # Guard: skip if DOSPERT is missing
    if not any([fin, rec, hs, eth, soc]):
        profile["personality_reflections"] = []
        profile["convergence_label"] = None
        profile["congruence_class"] = None
        return profile

    rnp = metrics.rng_normalized_pumps

    # ── 1. The MECE Congruence Classifier ──────────────────────────────
    # Thresholds strictly grounded in Bayes-optimal EV and sample tertiles

    exp_pen = metrics.explosion_penalty
    
    # Axis 1: DOSPERT Financial
    is_high_dospert = fin > 4
    is_mid_dospert = 3 <= fin <= 4
    is_low_dospert = fin < 3

    # Axis 2: Behavioral Execution (RNP + Explosion Penalty)
    
    # 1. If you push past optimal OR you blow up constantly, you are Risk-Seeking.
    is_seeking_behavior = (rnp > 1.05) or (exp_pen > 0.20)
    
    # 2. If you are NOT risk-seeking, but you stop early (under-leverage), you are Cautious.
    is_cautious_behavior = (rnp < 0.90) and not is_seeking_behavior
    
    # 3. If you don't trigger the extremes, you are in the balanced/optimal zone.
    is_optimal_behavior = not is_seeking_behavior and not is_cautious_behavior

    # Assign single source-of-truth class
    if is_high_dospert and is_seeking_behavior:
        congruence_class = "Congruent Risk-Seeker"
        convergence_label = "Tutarlı Risk Alıcı"
    elif is_high_dospert and is_cautious_behavior:
        congruence_class = "Anxious Claimant"
        convergence_label = "Çelişkili İhtiyatlı"
    elif is_mid_dospert and is_optimal_behavior:
        congruence_class = "Congruent Calculator"
        convergence_label = "Rasyonel İyileştirici"
    elif (is_low_dospert or is_mid_dospert) and is_seeking_behavior:
        congruence_class = "Covert Risk-Taker"
        convergence_label = "Gizli Risk Alıcı"
    elif (is_low_dospert or is_mid_dospert) and is_cautious_behavior:
        congruence_class = "Congruent Cautious"
        convergence_label = "Tutarlı İhtiyatlı"
    else:
        congruence_class = "Unexpected Optimizer" 
        convergence_label = "Dengeli"

    profile["congruence_class"] = congruence_class
    profile["convergence_label"] = convergence_label

    # ── 2. Unified Narrative Generation ─────────────────────────────────

    if congruence_class == "Congruent Risk-Seeker":
        reflections.append({
            "domain": "Finansal Risk Uyumu",
            "insight": "Ankette finansal riskler konusunda açık olduğunuzu belirttiniz ve oyundaki kararlarınız da bunu destekliyor. Optimal sınırların ötesine geçerek ödül fırsatlarını zorlamaya isteklisiniz.",
            "actionable": "Araştırmalar, öz-bildirim ile davranışsal ölçümler arasındaki tutarlılığın, kararlarda yüksek öngörülebilirliğe işaret ettiğini göstermektedir (Frey ve ark., 2017)."
        })
    elif congruence_class == "Anxious Claimant":
        reflections.append({
            "domain": "Finansal Risk Algı Farkı",
            "insight": "Ankette kendinizi risk almaya açık olarak tanımladınız, ancak gerçek zamanlı oyunda oldukça temkinli bir strateji izlediniz. Bu, hayali senaryolar ile gerçek kayıp riski (balonun patlaması) arasında ilginç bir algı farkına işaret ediyor.",
            "actionable": "Öz-bildirim ile davranış arasındaki farklar yaygındır ve 'tanım-deneyim boşluğu' (description-experience gap) olarak bilinir. Gerçek zamanlı görevlerdeki anlık kayıp ihtimali, teorik anketlere kıyasla beyni daha temkinli olmaya iter. (Hertwig ve ark., 2004)."
        })
    elif congruence_class == "Congruent Calculator":
        reflections.append({
            "domain": "Rasyonel Kalibrasyon",
            "insight": "Ankette ılımlı bir risk profiliniz olduğunu belirttiniz ve oyunu mükemmele yakın bir matematiksel kalibrasyonla (beklenen değer optimizasyonu) oynadınız.",
            "actionable": "Bu, riskleri ne aşırı büyüttüğünüzü ne de küçümsediğinizi; bunun yerine duruma göre rasyonel hesaplamalar yapabildiğinizi gösteriyor."
        })
    elif congruence_class == "Covert Risk-Taker":
        reflections.append({
            "domain": "Gizli Risk Alma Eğilimi",
            "insight": "Ankette kendinizi temkinli veya ılımlı tanımladınız, ancak oyun içinde limitleri zorlamaya çok istekliydiniz. Kurallar net olduğunda ve gerçek dünya sonuçları soyutlandığında daha cesur kararlar alıyorsunuz.",
            "actionable": "Bu profil, riskin anlık ve eyleme dayalı olarak değerlendirildiği durumlarda, beyninizin rasyonel öz-inançlarınızı aşıp 'hissedilen riske' (risk as feelings) göre daha cesur hareket ettiğini gösteriyor (Loewenstein ve ark., 2001)."
        })
    elif congruence_class == "Congruent Cautious":
        reflections.append({
            "domain": "Tutarlı İhtiyatlılık",
            "insight": "Hem ankette hem de oyundaki kararlarınız temkinli bir yaklaşıma işaret ediyor. Ödülü maksimize etmek yerine kayıplardan kaçınmayı (güvenliği) önceliklendiriyorsunuz.",
            "actionable": "Söyledikleriniz ile yaptıklarınızın örtüşmesi, gerçek hayattaki finansal kararlarınızda da kararlı ve öngörülebilir bir temkin örüntüsüne işaret eder (Mishra & Lalumière, 2011)."
        })
    elif congruence_class == "Unexpected Optimizer":
        reflections.append({
            "domain": "Dengeli Optimizasyon",
            "insight": "Kendinizi risk algısında uç noktalarda tanımlamış olsanız da, oyun içindeki davranışınız matematiksel olarak en kârlı ve dengeli noktada gerçekleşti.",
            "actionable": "Bu, kişisel hislerinizden bağımsız olarak çevreye uyum sağlama ve sistemi en verimli şekilde okuma becerinizin yüksek olduğunu gösteriyor."
        })

    # ── 2. Domain-Specific Risk Profile ─────────────────────────────────
    domains = [
        ("recreational", rec, "Eğlence"),
        ("health_safety", hs, "Sağlık ve Güvenlik"),
        ("social", soc, "Sosyal"),
        ("ethical", eth, "Etik"),
    ]

    # Find highest and lowest non-financial domains
    sorted_domains = sorted(domains, key=lambda x: x[1], reverse=True)
    highest = sorted_domains[0]
    lowest = sorted_domains[-1]
    spread = highest[1] - lowest[1]

    if highest[1] >= 4.0 and lowest[1] <= 3.0 and spread >= 1.5:
        reflections.append({
            "domain": "Risk Alanları Profili",
            "insight": (
                f"Risk toleransınız hayatın farklı alanlarında belirgin "
                f"farklılıklar gösteriyor. {highest[2]} alanında daha açık, "
                f"{lowest[2].lower()} alanında ise daha temkinlisiniz. "
                f"Bu aslında çoğu insanda görülen doğal bir örüntüdür: "
                f"risk tek boyutlu bir özellik değildir (Blais & Weber, 2006)."
            ),
            "actionable": (
                f"Her yaşam alanında farklı bir risk değerlendirme süreciniz "
                f"aktif. Bu, karar verme tarzınızın bağlama duyarlı olduğunu "
                f"gösteriyor."
            ),
        })
    elif all(d[1] > 4.0 for d in domains):
        reflections.append({
            "domain": "Risk Alanları Profili",
            "insight": (
                "Hayatın farklı alanlarında (eğlence, sosyal ilişkiler, "
                "sağlık, etik kararlar) genel olarak yeni deneyimlere ve "
                "risklere açık bir profiliniz var. Bu geniş açıklık, kişilik "
                "araştırmalarında deneyime açıklık ile ilişkilendirilmektedir."
            ),
            "actionable": (
                "Alanlar arası yüksek risk toleransı, belirsiz durumlarda "
                "rahat karar verebilme becerisi ile korelasyon göstermektedir "
                "(Nicholson ve ark., 2005)."
            ),
        })
    elif all(d[1] < 3.0 for d in domains):
        reflections.append({
            "domain": "Risk Alanları Profili",
            "insight": (
                "Hayatın farklı alanlarında (eğlence, sosyal ilişkiler, "
                "sağlık, etik kararlar) tutarlı bir şekilde temkinli bir "
                "yaklaşım benimsiyorsunuz. Bu profil, kişilik literatüründe "
                "yüksek sorumluluk bilinci ile ilişkilendirilmektedir."
            ),
            "actionable": (
                "Bu tutarlı temkin, dikkatli değerlendirme eğilimini yansıtan "
                "kararlı bir özellik örüntüsüdür (Weber ve ark., 2002)."
            ),
        })

    # ── 3. Learning Style Reflection ────────────────────────────────────
    lr = metrics.tercile_learning_rate
    if lr > 0.1: # This now covers both EV ratio cases below
        if metrics.ev_ratio_score < 70:
            # Player improved, but overall score is still not top-tier.
            # Implies they started sub-optimally.
            reflections.append({
                "domain": "Öğrenme ve Uyum",
                "insight": (
                    "Oyunun başında stratejiniz optimal değildi, ancak oyun "
                    "ilerledikçe deneyimlerinizden öğrenerek kararlarınızı "
                    "belirgin şekilde iyileştirdiniz."
                ),
                "actionable": (
                    "Bu öğrenme eğrisi, sonuçlardan çıkarım yapma becerinizin "
                    "güçlü olduğuna işaret ediyor. Araştırmalar bu tür geri "
                    "bildirim duyarlılığını ardışık kararlarda daha iyi uyum "
                    "sağlama ile ilişkilendirmektedir (Pleskac, 2008)."
                ),
            })
        else: # metrics.ev_ratio_score >= 70
            # Player improved, and overall score is already top-tier.
            # We remove the "already started well" assumption.
            reflections.append({
                "domain": "Öğrenme ve Uyum",
                "insight": (
                    "Yüksek bir genel performans sergilemenize rağmen, stratejinizi "
                    "oyun boyunca deneyimlerinizden öğrenerek daha da iyileştirmeye "
                    "devam ettiniz. Mevcut bir gücün üzerine inşa etme yeteneği "
                    "nadir görülen bir örüntüdür."
                ),
                "actionable": (
                    "Bu, performansınız zaten yeterli olduğunda bile sürekli "
                    "öğrenme ve adaptasyon yeteneğinizin güçlü olduğunu gösteriyor."
                ),
            })
    elif lr < -0.1:
        if metrics.explosion_penalty > 0.20:
            # SCENARIO A: The Traumatized Flincher (Negative LR + High Explosions)
            reflections.append({
                "domain": "Öğrenme ve Uyum (Risk Yayılımı)",
                "insight": (
                    "Oyun boyunca stratejiniz daha temkinli bir yöne kaydı, ancak veriler yüksek riskli balonlardaki "
                    "patlamaların stratejinizi etkilediğini gösteriyor. "
                    "Tehlikeli balonlardaki kayıplarınız, güvenli balonlarda potansiyelinizi tam olarak "
                    "kullanmanızı engelleyecek bir çekingenlik yaratmış olabilir."
                ),
                "actionable": (
                    "Bu durum karar biliminde 'genellenmiş kayıptan kaçınma' olarak bilinir. "
                    "Bir alandaki olumsuz sonuçların etkisi, diğer alanlardaki kararları da "
                    "temkinli hale getirebilir."
                ),
            })
        else:
            # SCENARIO B: The Careful Adjuster (Negative LR + Low Explosions)
            reflections.append({
                "domain": "Öğrenme ve Uyum",
                "insight": (
                    "Stratejiniz oyun boyunca daha temkinli bir yöne kaydı. Erken aşamalardaki "
                    "patlama deneyimlerinden ders çıkararak stratejinizi güvenli bir seviyede "
                    "yeniden ayarladınız."
                ),
                "actionable": (
                    "Bu tür bir strateji değişikliği, olumsuz sonuçlara dikkatli ve rasyonel "
                    "bir şekilde tepki verdiğinizi, riskleri başarıyla yönettiğinizi göstermektedir (Wallsten ve ark., 2005)."
                ),
            })

    # ── 4. Money Efficiency Insight ─────────────────────────────────────
    eff_pct = metrics.money_efficiency * 100
    if metrics.money_efficiency >= 0.85:
        reflections.append({
            "domain": "Sonuç Etkinliği",
            "insight": (
                f"Optimal oyun stratejisiyle kazanılabilecek miktarın %{eff_pct:.0f}'ini "
                f"elde ettiniz. Kararlarınız somut kazanç olarak güçlü sonuçlar üretti."
            ),
            "actionable": (
                "Bu, risk ve ödül arasındaki dengeyi iyi kurduğunuzu "
                "ve stratejinizin gerçek performansa dönüştüğünü gösteriyor."
            ),
        })
    elif metrics.money_efficiency <= 0.5:
        reflections.append({
            "domain": "Sonuç Etkinliği",
            "insight": (
                f"Optimal oyun stratejisiyle kazanılabilecek miktarın %{eff_pct:.0f}'ini "
                f"elde ettiniz. Stratejiniz ile ideal durma noktaları arasında "
                f"bir fark bulunuyor."
            ),
            "actionable": (
                "Bu fark genellikle deneyimle kapanır. Araştırmalar, "
                "tekrarlanan uygulamaların çoğu katılımcı için strateji "
                "kalibrasyonunu iyileştirdiğini göstermektedir "
                "(Lejuez ve ark., 2002)."
            ),
        })

    profile["personality_reflections"] = reflections

    return profile


# ── Main Scoring Function ───────────────────────────────────────────────────


def score_bart(events: list[GameEvent]) -> BARTMetrics:
    """
    Score a BART session from raw events using NumPy vectorization.

    Multi-Risk Profile Analysis:
    - Calculates overall metrics (pumps, explosions, latency)
    - Breaks down performance by balloon color (purple/teal/orange)
    - Computes learning rate and adaptation metrics
    - Provides behavioral indices (impulsivity, patience, consistency)
    - Runs session validation and flags anomalies

    RNG-Truncation Robustness:
    All behavioral-intention metrics (impulsivity, patience, risk calibration,
    learning rate, color discrimination, rng_normalized_pumps, between-balloon
    consistency) use COLLECTED (non-exploded) balloons only.  Exploded balloons
    have their pump counts truncated by RNG, which does not reflect the
    participant's intended pumping strategy.

    Parameters
    ----------
    events : list[GameEvent]
        Chronologically ordered BART events (already validated).

    Returns
    -------
    BARTMetrics
        Computed psychometric metrics including color-based and learning metrics.

    Raises
    ------
    ValueError
        If event log is empty or contains no balloon data.
    """
    if not events:
        raise ValueError("Empty event log")

    # ── Session validation ────────────────────────────────────────────────────
    validation = validate_bart_session(events)
    session_valid = validation["is_valid"]
    session_warnings = list(validation["warnings"])

    balloons = _segment_balloons(events)

    if not balloons:
        raise ValueError("No balloon data found in event log")

    # DEBUG: Log color extraction
    balloon_colors = [_extract_balloon_color(b) for b in balloons]
    color_counts: dict[str, int] = {}
    for color in balloon_colors:
        color_counts[color] = color_counts.get(color, 0) + 1
    logger.info(
        "BART color distribution: %s (total %d balloons)", color_counts, len(balloons)
    )
    logger.debug("First 5 balloon colors: %s", balloon_colors[:5])

    # ── Auto-Repeat Detection (pre-pass) ────────────────────────────────────
    # Identify balloons where the participant held spacebar (OS auto-repeat).
    # These have artificially inflated pump counts that don't reflect discrete
    # decisions — one keypress produced many pump events at ~30-50 ms intervals.
    # We exclude them from behavioral-intention metrics (pump counts, EV scores,
    # color discrimination, learning rate) but keep them in descriptive totals.
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

    # ── Data Collection ──────────────────────────────────────────────────────
    pump_counts: list[int] = []
    non_exploded_pumps: list[int] = []
    total_explosions = 0
    total_collections = 0

    # Color-based tracking: ALL balloons (descriptive metrics)
    color_pumps_all: dict[str, list[int]] = defaultdict(list)
    # Color-based tracking: COLLECTED only (behavioral-intention metrics)
    color_pumps_collected: dict[str, list[int]] = defaultdict(list)
    color_explosions: dict[str, int] = defaultdict(int)
    color_balloons: dict[str, int] = defaultdict(int)

    # Learning rate data: (trial_number, color, pumps, exploded)
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

        # Track ALL balloon pump counts (for descriptive metrics — includes auto-repeat)
        color_pumps_all[color].append(pumps)

        if exploded:
            total_explosions += 1
            color_explosions[color] += 1
        else:
            # Collected or incomplete — reflects full behavioral intention
            total_collections += 1 if terminal == "collect" else 0
            non_exploded_pumps.append(pumps)
            # Exclude auto-repeat balloons from collected behavioral data.
            # Their pump counts are OS key-repeat artifacts, not deliberate decisions.
            if not is_autorepeat:
                color_pumps_collected[color].append(pumps)

        # Exclude auto-repeat from learning rate data — inflated pump counts
        # would distort first-half vs second-half comparisons.
        if not is_autorepeat:
            balloon_data.append((trial_idx, color, pumps, exploded))

    total_balloons = len(balloons)

    if autorepeat_indices:
        session_warnings.append(
            f"Auto-repeat detected: {len(autorepeat_indices)} balloon(s) "
            f"(indices {sorted(autorepeat_indices)}) excluded from behavioral-intention "
            f"metrics (pump counts inflated by OS key-repeat, not discrete decisions)"
        )
    all_pumps_array = np.array(pump_counts, dtype=np.float64)
    total_pumps = int(np.sum(all_pumps_array))

    # ── Money collected ───────────────────────────────────────────────────────
    # Each pump on a collected balloon is worth $0.25.
    _money_pumps = 0
    money_collected = 0.0
    for evt in events:
        if evt.type == "pump":
            _money_pumps += 1
        elif evt.type == "collect":
            money_collected += _money_pumps * 0.25
            _money_pumps = 0
        elif evt.type == "explode":
            _money_pumps = 0

    # Simulated median earnings at optimal play (10k sessions, seed=42).
    # Using median instead of EV because ~50% of optimal-play sessions
    # earn less than EV due to explosion RNG. Median is a fairer benchmark.
    # Recompute if COLOR_PROFILES or balloon counts change.
    _OPTIMAL_MEDIAN_EARNINGS = 27.25  # from 10k Monte Carlo simulation

    # Use simulated median as denominator — fairer than EV since ~50% of
    # optimal-play sessions earn below EV due to explosion RNG.
    money_efficiency = money_collected / _OPTIMAL_MEDIAN_EARNINGS if _OPTIMAL_MEDIAN_EARNINGS > 0 else 0.0
    # Cap at reasonable upper bound (lucky sessions can exceed median)
    money_efficiency = float(np.clip(money_efficiency, 0.0, 2.0))

    # ── Resolve collected-vs-all per color ────────────────────────────────────
    # For each color, prefer collected (non-exploded) pump data for behavioral
    # metrics.  Fall back to all balloons if too few collected are available,
    # and emit a warning so downstream consumers know the metric is degraded.
    color_pumps_behavioral: dict[str, list[int]] = {}
    for color in COLOR_PROFILES:
        collected = color_pumps_collected.get(color, [])
        all_data = color_pumps_all.get(color, [])
        chosen, used_fallback = _prefer_collected(collected, all_data)
        color_pumps_behavioral[color] = chosen
        if used_fallback and len(all_data) > 0:
            session_warnings.append(
                f"RNG-truncation fallback: {color} has only {len(collected)} collected "
                f"balloon(s) (< {MIN_COLLECTED_FALLBACK}); using all {len(all_data)} "
                f"balloons (includes truncated pump counts from explosions)"
            )

    # ── Overall Metrics ──────────────────────────────────────────────────────

    # Average Pumps (all balloons) — descriptive, includes RNG-truncated counts.
    # Useful for comparison with other studies but NOT recommended for behavioral
    # intention measurement.  Use rng_normalized_pumps (collected-only) instead.
    avg_pumps_all_balloons = float(np.mean(all_pumps_array))

    # Average Pumps Adjusted (non-exploded only) — classic BART censoring correction.
    # Note: This metric excludes exploded balloons to avoid right-censoring bias
    # (we don't know how many more times an exploded balloon would have been pumped).
    if non_exploded_pumps:
        adjusted_array = np.array(non_exploded_pumps, dtype=np.float64)
        average_pumps_adjusted = float(np.mean(adjusted_array))
    else:
        # All balloons exploded — fall back to overall mean (no censoring to correct for)
        average_pumps_adjusted = avg_pumps_all_balloons

    # Explosion Rate
    explosion_rate = total_explosions / total_balloons if total_balloons > 0 else 0.0

    # Mean Inter-Pump Latency — computed per-balloon to exclude cross-balloon gaps.
    # Not affected by RNG truncation: the timing between pumps 1->2->3 is the same
    # regardless of whether the balloon later explodes.
    # Skip auto-repeat balloons (spacebar held → OS key repeat artifacts).
    all_intra_latencies: list[float] = []
    for balloon_events in balloons:
        if _is_autorepeat_balloon(balloon_events):
            continue
        pump_times = [e.timestamp for e in balloon_events if e.type == "pump"]
        if len(pump_times) >= 2:
            diffs = np.diff(pump_times)
            all_intra_latencies.extend(diffs.tolist())

    intra_balloon_latencies = np.array(all_intra_latencies, dtype=np.float64)
    # Filter remaining within-balloon outliers (hesitation pauses > 2 seconds)
    if intra_balloon_latencies.size > 0:
        intra_balloon_latencies = intra_balloon_latencies[intra_balloon_latencies < 2000.0]

    if intra_balloon_latencies.size > 0:
        mean_latency = float(np.mean(intra_balloon_latencies))
    else:
        mean_latency = 0.0

    # ── EV-Based Metrics (scientifically rigorous, v3) ───────────────────────
    # Computed early so per-color results are available for ColorMetrics.

    # Compute dynamic EV-optimal stops
    ev_optimal_stops: dict[str, int] = {}
    for color, profile in COLOR_PROFILES.items():
        opt_stop, _ = _get_ev_optimal(profile["max_pumps"])
        ev_optimal_stops[color] = opt_stop

    # EV-Ratio Score: EV(participant) / EV(optimal) per color
    # Uses COLLECTED-ONLY data — never fallback/truncated data.
    ev_ratio_score, per_color_efficiency = _compute_ev_ratio_score(
        color_pumps_collected, color_balloons,
    )

    # Explosion Penalty: excess explosion rate vs expected at optimal
    explosion_penalty, per_color_excess = _compute_explosion_penalty(
        color_explosions, color_balloons,
    )

    # ── Color-Based Metrics (descriptive, uses ALL balloons) ─────────────────
    color_metrics_list: list[ColorMetrics] = []

    for color in ["purple", "teal", "orange"]:
        if color not in color_balloons:
            continue

        balloons_of_color = color_balloons[color]
        pumps_of_color = color_pumps_all.get(color, [])
        collected_of_color = color_pumps_collected.get(color, [])

        avg_pumps = float(np.mean(pumps_of_color)) if pumps_of_color else 0.0
        color_exp_rate = (
            color_explosions[color] / balloons_of_color if balloons_of_color > 0 else 0.0
        )

        # Behavioral avg: prefer collected-only, fallback to all
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
                risk_profile=COLOR_PROFILES[color]["risk"],
                used_fallback=used_fb,
                ev_efficiency=round(color_ev_eff, 4) if color_ev_eff is not None else None,
                ev_optimal_stop=color_ev_optimal,
                excess_explosion_rate=round(color_excess_exp, 4) if color_excess_exp is not None else None,
            ),
        )

    # ── Learning & Adaptation Metrics (use collected-only internally) ────────

    # Learning Rate — regression-based (preserved for backward compat; noisy at N=10)
    learning_rate = _calculate_learning_rate(balloon_data)

    # Half-Split Learning Rate — more robust at N=10 per color
    half_split_lr = _calculate_half_split_learning_rate(balloon_data)

    # Tercile Learning Rate — first-third vs last-third, captures late learners
    tercile_lr = _calculate_tercile_learning_rate(balloon_data)

    # Color Discrimination Trajectory — did they learn to differentiate colors?
    cdt = _calculate_color_discrimination_trajectory(balloon_data)

    # Post-Explosion Sensitivity — do they reduce pumps after a pop?
    pes = _calculate_post_explosion_sensitivity(balloon_data)

    # Color Discrimination (LEGACY — Cohen's d, kept for backward compat)
    color_discrimination = _calculate_color_discrimination(color_pumps_behavioral)

    # Risk Adjustment Score (LEGACY — kept for backward compat)
    risk_adjustment = _calculate_risk_adjustment_score(color_pumps_behavioral)

    # Risk Sensitivity (Pearson r — kept for descriptive use)
    risk_sensitivity = _calculate_risk_sensitivity(color_pumps_behavioral)

    # Risk Calibration Score: ev_ratio_score alone captures calibration quality.
    # Explosion penalty is reported separately — multiplicative combination
    # double-penalizes over-pumping and conflates calibration with RNG luck.
    risk_calibration_score = float(np.clip(ev_ratio_score, 0.0, 100.0))

    # EV-Efficiency Uniformity (replaces Cohen's d)
    ev_efficiency_uniformity = _compute_ev_efficiency_uniformity(
        per_color_efficiency, color_pumps_collected, color_balloons,
    )

    # Consistency breakdown (within-balloon vs between-balloon)
    # Computed here (before flat detection) so between_cv is available
    # for the temporal learning exemption in _detect_flat_strategy.
    within_balloon_cv, between_balloon_cv = _calculate_consistency_breakdown(balloons)

    # Flat Strategy Detection — with temporal learning exemption.
    # Participants who start low but show learning/experimentation signals
    # are NOT genuinely flat (e.g. P14 who explored aggressively in the
    # middle third and then adapted).
    flat_strategy = _detect_flat_strategy(
        color_pumps_all, color_explosions, color_balloons,
        tercile_lr=tercile_lr,
        cdt=cdt,
        pes=pes,
        between_cv=between_balloon_cv,
    )

    # ── Behavioral Indices (use collected-only data) ─────────────────────────

    # Orange average pumps — None when insufficient collected data
    orange_collected_real = color_pumps_collected.get("orange", [])
    has_orange_data = len(orange_collected_real) >= MIN_COLLECTED_FALLBACK
    orange_avg_pumps: float | None = (
        float(np.mean(orange_collected_real)) if has_orange_data else None
    )

    # Response Consistency — global CV of all intra-balloon latencies.
    # Not affected by RNG truncation (measures timing, not pump counts).
    if intra_balloon_latencies.size > 1:
        cv = float(np.std(intra_balloon_latencies) / np.mean(intra_balloon_latencies))
        response_consistency = cv
    else:
        response_consistency = 0.0

    # NOTE: within_balloon_cv and between_balloon_cv are computed above
    # (before flat detection) so they are available for the
    # temporal learning exemption in _detect_flat_strategy.

    # Impulsivity Index — based on inter-pump latency.
    # Fast pumping (low latency) is the most established behavioral correlate
    # of impulsivity in the BART literature (Lejuez et al., 2002).
    # Normalized: 0 = very slow/deliberate (>= 800ms), 1 = very fast/reflexive (0ms).
    # This is a single-signal metric with clear construct validity,
    # avoiding the arbitrary weight problem of multi-component composites.
    if mean_latency > 0:
        impulsivity_index = float(np.clip(1.0 - mean_latency / 800.0, 0.0, 1.0))
    else:
        impulsivity_index = 0.0

    # Patience Index — mean pumps on collected purple balloons
    purple_behavioral = color_pumps_behavioral.get("purple", [])
    patience_index = float(np.mean(purple_behavioral)) if purple_behavioral else 0.0

    # Patience Index Normalized — purple EV-efficiency.
    # Peaks at optimal play (11 pumps) and decreases with both under- and over-pumping.
    # This distinguishes genuine patience from reckless over-pumping.
    purple_ev_efficiency = per_color_efficiency.get("purple", 0.0)
    patience_index_normalized = float(np.clip(purple_ev_efficiency, 0.0, 1.0))

    # ── Composite Metrics ────────────────────────────────────────────────────

    # Adaptive Strategy Score — fixed weights for cross-participant comparability.
    # Calibration gets highest weight as the primary behavioral measure.
    # Learning and uniformity get equal weight as secondary signals.
    # Money efficiency is outcome-grounding.
    safe_hslr = 0.0 if np.isnan(half_split_lr) else half_split_lr
    safe_ev_uniformity = ev_efficiency_uniformity if ev_efficiency_uniformity is not None else 0.0
    safe_ev_ratio = ev_ratio_score / 100.0  # Normalize to [0, 1]

    W_CALIBRATION = 0.35
    W_LEARNING = 0.25
    W_UNIFORMITY = 0.25
    W_MONEY = 0.15

    learning_component = (safe_hslr + 1.0) / 2.0  # [-1, 1] -> [0, 1]
    calibration_component = safe_ev_ratio           # [0, 1]
    uniformity_component = safe_ev_uniformity       # [0, 1]
    money_component = money_efficiency              # [0, 1] (can be > 1 now, capped at 2)
    money_component = min(1.0, money_component)     # Cap at 1.0 for composite

    adaptive_strategy_score = (
        learning_component * W_LEARNING
        + calibration_component * W_CALIBRATION
        + uniformity_component * W_UNIFORMITY
        + money_component * W_MONEY
    ) * 100.0
    adaptive_strategy_score = float(np.clip(adaptive_strategy_score, 0.0, 100.0))

    # RNG-Normalized Pumps — normalized by EV-optimal stop per color.
    # Average WITHIN each color first (per-color mean / optimal_stop),
    # then average across colors. This gives equal weight to each risk level
    # regardless of collection rates. Uses collected-only data where available.
    # 1.0 = pumping at exactly EV-optimal. >1.0 = over-pumping. <1.0 = conservative.
    # RNG-Normalized Pumps — normalized by EV-optimal stop per color.
    per_color_normalized: list[float] = []
    for color in COLOR_PROFILES:
        # FIX: Use behavioral_pumps (which includes fallback data) so 
        # extreme risk-takers who pop everything don't get their data erased.
        behavioral_pumps = color_pumps_behavioral.get(color, [])
        if behavioral_pumps:
            opt_stop, _ = _get_ev_optimal(COLOR_PROFILES[color]["max_pumps"])
            if opt_stop > 0:
                color_mean = float(np.mean(behavioral_pumps)) / opt_stop
                per_color_normalized.append(color_mean)

    rng_normalized_pumps = (
        float(np.mean(per_color_normalized)) if per_color_normalized else 0.0
    )

    # Store per-color efficiency in ev_optimal_stops dict for profile access
    _ev_stops_with_eff = dict(ev_optimal_stops)
    for c, eff in per_color_efficiency.items():
        _ev_stops_with_eff[f"_{c}_efficiency"] = eff

    # ── Logging ──────────────────────────────────────────────────────────────
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

    # ── Assemble metrics object ───────────────────────────────────────────────
    metrics_obj = BARTMetrics(
        # Core
        average_pumps_adjusted=round(average_pumps_adjusted, 4),
        explosion_rate=round(explosion_rate, 4),
        mean_latency_between_pumps=round(mean_latency, 4),
        total_balloons=total_balloons,
        total_pumps=total_pumps,
        total_explosions=total_explosions,
        total_collections=total_collections,
        # Color breakdown
        color_metrics=color_metrics_list,
        # Learning (legacy + robust + v4)
        learning_rate=round(learning_rate, 4),
        half_split_learning_rate=round(half_split_lr, 4),
        tercile_learning_rate=round(tercile_lr, 4),
        color_discrimination_trajectory=round(cdt, 4) if cdt is not None else None,
        post_explosion_sensitivity=round(pes, 4) if pes is not None else None,
        # Legacy risk calibration (kept for backward compat)
        risk_adjustment_score=round(risk_adjustment, 4),
        color_discrimination_index=round(color_discrimination, 4) if not np.isnan(color_discrimination) else None,
        risk_sensitivity=round(risk_sensitivity, 4),
        # EV-based metrics (scientifically rigorous, v3)
        ev_ratio_score=round(ev_ratio_score, 4),
        explosion_penalty=round(explosion_penalty, 4),
        risk_calibration_score=round(risk_calibration_score, 4),
        ev_efficiency_uniformity=round(ev_efficiency_uniformity, 4) if ev_efficiency_uniformity is not None else None,
        flat_strategy_detected=flat_strategy,
        money_collected=round(money_collected, 2),
        money_efficiency=round(money_efficiency, 4),
        ev_optimal_stops=_ev_stops_with_eff,
        # Behavioral intention metrics (RNG-robust, collected-only)
        rng_normalized_pumps=round(rng_normalized_pumps, 4),
        avg_pumps_all_balloons=round(avg_pumps_all_balloons, 4),
        orange_avg_pumps=round(orange_avg_pumps, 4) if orange_avg_pumps is not None else None,
        impulsivity_index=round(impulsivity_index, 4),
        # Patience
        patience_index=round(patience_index, 4),
        patience_index_normalized=round(patience_index_normalized, 4),
        # Consistency
        response_consistency=round(response_consistency, 4),
        within_balloon_consistency=round(within_balloon_cv, 4),
        between_balloon_consistency=round(between_balloon_cv, 4),
        # Composite
        adaptive_strategy_score=round(adaptive_strategy_score, 4),
        # Session validity
        session_valid=session_valid,
        session_warnings=session_warnings,
        # Narrative profile (populated below)
        behavioral_profile={},
    )

    # Generate narrative profile using validated metrics
    profile = _generate_behavioral_profile(metrics_obj)
    metrics_obj.behavioral_profile = profile

    return metrics_obj
