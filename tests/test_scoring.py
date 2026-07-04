"""Tests for the Dynamic Hazard Rate BART scoring engine.

Run with ``pytest`` from the repository root.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from scoring.bart import (
    COLOR_PROFILES,
    score_bart,
    validate_bart_session,
)
from scoring.config import DynamicHazard, balloon_curve
from scoring.schemas import EventPayload, GameEvent, GameSession
from scoring.schemas.game_events import validate_bart_events

OPTIMA = {"purple": 11, "teal": 5, "orange": 2}
CAPS = {"purple": 128, "teal": 32, "orange": 8}


# ── Helpers ──────────────────────────────────────────────────────────────────


def build_events(balloons):
    """Build a chronological event log from ``(color, pumps, collected)`` tuples."""
    events: list[GameEvent] = []
    t = 0.0
    for color, pumps, collected in balloons:
        for _ in range(pumps):
            t += 300.0
            events.append(GameEvent(timestamp=t, type="pump", payload=EventPayload(color=color)))
        t += 200.0
        terminal = "collect" if collected else "explode"
        events.append(GameEvent(timestamp=t, type=terminal, payload=EventPayload(color=color)))
    return events


def optimal_session():
    """A full 30-balloon session, every balloon collected at its EV-optimal stop."""
    balloons = []
    for color in ("purple", "teal", "orange"):
        balloons.extend([(color, OPTIMA[color], True)] * 10)
    return build_events(balloons)


# A discriminating, learning session spec keyed by risk role (low/mid/high). The
# low-risk color is pumped near its high optimum and improves over the run; the
# high-risk color starts reckless (early explosions) then calms — so every
# name-keyed persona metric (learning, discrimination, patience, high-risk
# average) lands non-trivially. Reused under renamed colors to prove that
# scoring is invariant to color names once risk ordering is preserved.
_RICH_LOW = [(8, True), (9, True), (7, True), (10, True), (9, True),
             (11, True), (12, True), (11, True), (13, True), (12, True)]
_RICH_MID = [(4, True), (5, True), (3, True), (6, True), (5, True),
             (5, True), (4, True), (6, True), (5, True), (5, True)]
_RICH_HIGH = [(5, False), (4, False), (6, False), (3, True), (3, True),
              (2, True), (2, True), (2, True), (2, True), (2, True)]


def rich_session(low="purple", mid="teal", high="orange"):
    """A full 30-balloon session interleaving low/mid/high-risk colors, with
    genuine discrimination, learning, and patience signal. ``low``/``mid``/``high``
    name the colors by risk role so the same behavior can be scored under the
    default triad or any renamed/re-ordered study."""
    balloons = []
    for i in range(10):
        balloons.append((low, _RICH_LOW[i][0], _RICH_LOW[i][1]))
        balloons.append((mid, _RICH_MID[i][0], _RICH_MID[i][1]))
        balloons.append((high, _RICH_HIGH[i][0], _RICH_HIGH[i][1]))
    return build_events(balloons)


# ── Expected-value mathematics ───────────────────────────────────────────────


@pytest.mark.parametrize("n, expected_s", [(128, 11), (32, 5), (8, 2)])
def test_discrete_optima(n, expected_s):
    curve = balloon_curve(DynamicHazard().hazard_vector(n), reward_per_pump=1.0)
    assert curve.optimum == expected_s


@pytest.mark.parametrize("n, expected_ev", [(128, 6.46), (32, 3.04), (8, 1.31)])
def test_peak_ev_values(n, expected_ev):
    curve = balloon_curve(DynamicHazard().hazard_vector(n), reward_per_pump=1.0)
    assert curve.optimal_ev == pytest.approx(expected_ev, abs=0.01)


def test_survival_is_monotonically_decreasing():
    curve = balloon_curve(DynamicHazard().hazard_vector(32), reward_per_pump=1.0)
    probs = curve.survival[0:10]
    assert probs[0] == 1.0
    assert all(later <= earlier for earlier, later in zip(probs, probs[1:]))


def test_sqrt_n_approximation():
    # The discrete optimum should sit at floor(sqrt(N)) for these capacities.
    for n in (128, 32, 8):
        curve = balloon_curve(DynamicHazard().hazard_vector(n), reward_per_pump=1.0)
        assert curve.optimum == math.floor(math.sqrt(n))


def test_color_profiles_constant():
    assert COLOR_PROFILES["purple"]["max_pumps"] == 128
    assert COLOR_PROFILES["teal"]["max_pumps"] == 32
    assert COLOR_PROFILES["orange"]["max_pumps"] == 8


# ── End-to-end scoring ───────────────────────────────────────────────────────


def test_optimal_session_scores_perfectly():
    metrics = score_bart(optimal_session())
    assert metrics.ev_ratio_score == pytest.approx(100.0, abs=0.5)
    assert metrics.risk_calibration_score == pytest.approx(100.0, abs=0.5)
    assert metrics.rng_normalized_pumps == pytest.approx(1.0, abs=0.01)
    assert metrics.explosion_penalty == 0.0
    assert metrics.total_balloons == 30
    assert metrics.total_explosions == 0


def test_optimal_session_is_calibrated_optimizer():
    metrics = score_bart(optimal_session())
    assert metrics.behavioral_profile["risk_style"] == "Calibrated Risk Optimizer"
    assert isinstance(metrics.behavioral_profile["dominant_traits"], list)


def test_default_session_metrics_are_byte_identical_to_golden():
    """Regression lock for the risk-ranking generalization (issue 56): a full
    default purple/teal/orange session with genuine learning, discrimination,
    and patience signal must serialize *exactly* as the committed golden. This
    is the byte-identical guarantee — routing name-keyed metrics through the
    risk ranking must not move a single default-study number."""
    golden = json.loads(
        (Path(__file__).parent / "fixtures" / "default_session_metrics_golden.json").read_text()
    )
    assert score_bart(rich_session()).model_dump() == golden


def test_money_collected_matches_reward_rule():
    metrics = score_bart(optimal_session())
    # 10 balloons per color collected at s*: (11 + 5 + 2) * 10 pumps * $0.25
    expected = (11 + 5 + 2) * 10 * 0.25
    assert metrics.money_collected == pytest.approx(expected)


def test_conservative_session_underpumps():
    balloons = []
    for color in ("purple", "teal", "orange"):
        balloons.extend([(color, 1, True)] * 10)  # stop at a single pump everywhere
    metrics = score_bart(build_events(balloons))
    assert metrics.rng_normalized_pumps < 1.0
    assert metrics.ev_ratio_score < 100.0


def test_empty_log_raises():
    with pytest.raises(ValueError):
        score_bart([])


# ── Right-censoring (collected-only) correction ──────────────────────────────


def test_exploded_balloons_excluded_from_adjusted_mean():
    # 10 purple collected at 11 pumps; 10 purple "exploded" at 30 pumps.
    # average_pumps_adjusted uses collected only -> should equal 11, not 20.5.
    balloons = [("purple", 11, True)] * 10 + [("purple", 30, False)] * 10
    # pad with teal/orange so the session validates
    balloons += [("teal", 5, True)] * 10
    metrics = score_bart(build_events(balloons))
    purple = next(c for c in metrics.color_metrics if c.color == "purple")
    assert purple.behavioral_avg_pumps == pytest.approx(11.0)
    assert purple.average_pumps == pytest.approx(20.5)  # all-balloon mean is biased


# ── Session validation ───────────────────────────────────────────────────────


def test_full_session_is_valid():
    report = validate_bart_session(optimal_session())
    assert report["is_valid"] is True
    assert report["balloon_count"] == 30
    assert report["color_distribution"] == {"purple": 10, "teal": 10, "orange": 10}


def test_too_few_balloons_is_invalid():
    balloons = [("teal", 5, True)] * 10  # only 10 balloons
    report = validate_bart_session(build_events(balloons))
    assert report["is_valid"] is False
    assert any("incomplete" in w.lower() for w in report["warnings"])


def test_out_of_order_timestamps_invalid():
    events = optimal_session()
    events[5].timestamp = events[4].timestamp - 100.0  # break monotonicity
    report = validate_bart_session(events)
    assert report["is_valid"] is False


def test_default_study_validation_warnings_are_byte_identical():
    """Regression lock for issue 57: deriving the shape from config must not move
    a single default-study warning. A partial purple/teal/orange session produces
    exactly the strings the former hardcoded 30/10 literals did."""
    balloons = [("purple", 11, True)] * 10 + [("teal", 5, True)] * 3  # 13/30
    report = validate_bart_session(build_events(balloons))

    assert report["is_valid"] is False
    assert report["warnings"] == [
        "Critically incomplete session: only 13/30 balloons played",
        "Too few teal balloons: 3/10 played",
        "Too few orange balloons: 0/10 played",
    ]


def test_score_bart_records_validity():
    metrics = score_bart(optimal_session())
    assert metrics.session_valid is True
    assert metrics.session_warnings == []


# ── Schema-level validation ──────────────────────────────────────────────────


def test_game_session_rejects_unordered_events():
    events = [
        GameEvent(timestamp=500, type="pump", payload=EventPayload(color="teal")),
        GameEvent(timestamp=100, type="collect", payload=EventPayload(color="teal")),
    ]
    with pytest.raises(ValueError):
        GameSession(session_id="s", game_type="BART_RISK", events=events)


def test_validate_bart_events_rejects_unknown_type():
    events = [GameEvent(timestamp=1, type="teleport", payload=EventPayload(color="teal"))]
    with pytest.raises(ValueError):
        validate_bart_events(events)


def test_validate_bart_events_rejects_zero_pump_terminal():
    events = [GameEvent(timestamp=1, type="collect", payload=EventPayload(color="teal"))]
    with pytest.raises(ValueError):
        validate_bart_events(events)


# ── Trial table (issue 39) ───────────────────────────────────────────────────


def test_trial_table_yields_one_record_per_balloon():
    """`trial_table` turns an event log into the long-format trial rows analysts
    feed to mixed models: one record per balloon, in session order, with pumps,
    outcome, and this trial's earnings (pumps × reward when collected, 0 when
    popped) — computed in the engine so CLI users get the same table (issue 39)."""
    from scoring.bart import trial_table
    from scoring.config import DEFAULT_TASK_CONFIG

    events = build_events([("teal", 3, True), ("orange", 2, False)])
    trials = trial_table(events, DEFAULT_TASK_CONFIG)

    assert [t.trial for t in trials] == [1, 2]
    assert [t.balloon_color for t in trials] == ["teal", "orange"]
    assert [t.pumps for t in trials] == [3, 2]
    assert [t.outcome for t in trials] == ["collected", "exploded"]
    assert trials[0].trial_earnings == pytest.approx(3 * DEFAULT_TASK_CONFIG.reward_per_pump)
    assert trials[1].trial_earnings == 0.0


def test_trial_table_carries_design_and_latency_columns():
    """Each trial row names the hazard family its color ran under (from the
    study config — the design column mixed models condition on) and summarizes
    response latency as the mean gap between that trial's pumps in ms; a trial
    with fewer than two pumps has no gaps, so its summary is honestly empty."""
    from scoring.bart import trial_table
    from scoring.config import DEFAULT_TASK_CONFIG

    # build_events spaces pumps 300 ms apart.
    events = build_events([("teal", 3, True), ("orange", 1, True)])
    trials = trial_table(events, DEFAULT_TASK_CONFIG)

    assert [t.hazard_family for t in trials] == ["dynamic", "dynamic"]
    assert trials[0].mean_latency_between_pumps == pytest.approx(300.0)
    assert trials[1].mean_latency_between_pumps is None


# ── QC flags (issue 40) ──────────────────────────────────────────────────────


def test_clean_session_trips_no_qc_flags():
    """A session with unhurried pumping (300 ms gaps) and engagement on every
    balloon carries QC fields that all read clean: flags annotate data quality,
    and clean data is visibly clean (issue 40)."""
    events = build_events([("teal", 4, True), ("orange", 2, True), ("purple", 8, True)])
    metrics = score_bart(events)

    assert metrics.qc_fast_response_trials == 0
    assert metrics.qc_zero_pump_streak == 0
    assert metrics.qc_flagged is False


def test_sub_threshold_latency_trips_the_fast_response_rule():
    """One trial with a 50 ms inter-pump gap (default threshold: 100 ms) is
    counted and flags the session; the rule counts trials, not gaps, so a
    single bad trial reads as 1 regardless of how many fast gaps it holds."""
    events = build_events([("teal", 4, True), ("orange", 2, True)])
    # Splice in one hurried trial: three pumps 50 ms apart, then collect.
    t = events[-1].timestamp
    for _ in range(3):
        t += 50.0
        events.append(GameEvent(timestamp=t, type="pump", payload=EventPayload(color="teal")))
    events.append(GameEvent(timestamp=t + 200.0, type="collect", payload=EventPayload(color="teal")))

    metrics = score_bart(events)

    assert metrics.qc_fast_response_trials == 1
    assert metrics.qc_flagged is True
    # Annotation only: the flagged trial still counts everywhere else.
    assert metrics.total_balloons == 3


def test_zero_pump_streak_rule_trips_at_the_threshold():
    """Five consecutive zero-pump trials (default threshold) read as disengagement
    and flag the session; four in a row stay below the line. The streak length is
    reported either way, so the analyst sees exactly what happened."""
    engaged = [("teal", 3, True)]
    zero = ("orange", 0, False)  # explode logged with no pumps: pure disengagement

    below = score_bart(build_events(engaged + [zero] * 4 + engaged))
    assert below.qc_zero_pump_streak == 4
    assert below.qc_flagged is False

    tripped = score_bart(build_events(engaged + [zero] * 5 + engaged))
    assert tripped.qc_zero_pump_streak == 5
    assert tripped.qc_flagged is True


def test_preset_qc_thresholds_change_outcomes_and_are_recorded():
    """Labs align flags with their preregistration by declaring thresholds in
    the Study Preset; the thresholds actually used are recorded in the metrics,
    so a flag's criteria can be stated post hoc. A v1.0.0 preset without a `qc`
    block keeps validating and gets the literature defaults (100 ms / 5)."""
    from scoring.config import DEFAULT_TASK_CONFIG, TaskConfig

    v1 = DEFAULT_TASK_CONFIG.model_dump()
    v1.pop("qc", None)  # exactly what a v1.0.0 study.json contains
    defaults = TaskConfig.model_validate(v1)
    assert defaults.qc.fast_response_ms == 100.0
    assert defaults.qc.zero_pump_streak == 5

    # build_events paces pumps 300 ms apart — clean under the default
    # threshold, hurried under a strict preregistration of 400 ms.
    events = build_events([("teal", 3, True), ("teal", 4, True)])
    strict = TaskConfig.model_validate({**v1, "qc": {"fast_response_ms": 400.0}})

    clean = score_bart(events, defaults)
    assert clean.qc_flagged is False
    assert clean.qc_fast_response_ms == 100.0
    assert clean.qc_zero_pump_streak_threshold == 5

    flagged = score_bart(events, strict)
    assert flagged.qc_fast_response_trials == 2
    assert flagged.qc_flagged is True
    assert flagged.qc_fast_response_ms == 400.0


# ── Payout conversion (issue 41) ─────────────────────────────────────────────


def test_payout_block_converts_earnings_half_up():
    """A study with a payout block converts session earnings to the amount owed
    (earnings × rate) rounded HALF-UP to 2 decimals — one rule, applied once in
    the engine, so the debrief and the CSV can never disagree (issue 41).
    29 collected pumps × $0.25 = 7.25 earnings; × 0.1 = 0.725 → 0.73 (a case
    banker's rounding would turn into 0.72)."""
    from scoring.config import DEFAULT_TASK_CONFIG, TaskConfig

    events = build_events([("teal", 29, True)])
    paid = TaskConfig.model_validate(
        {**DEFAULT_TASK_CONFIG.model_dump(), "payout": {"rate": 0.1, "currency": "₺"}}
    )

    metrics = score_bart(events, paid)
    assert metrics.money_collected == pytest.approx(7.25)
    assert metrics.payout_amount == 0.73
    assert metrics.payout_currency == "₺"


def test_no_payout_block_means_no_payout_anywhere():
    """Without a payout block (every v1.0.0 preset) the payout fields stay
    empty — today's behavior, unchanged."""
    metrics = score_bart(build_events([("teal", 4, True)]))
    assert metrics.payout_amount is None
    assert metrics.payout_currency is None
