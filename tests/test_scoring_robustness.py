"""Degenerate-but-valid sessions must score, never crash (issue 29).

Any event log the validation pipeline accepts — single-color, single-balloon,
all-explosions, custom color names, any hazard family — must come back from
``score_bart`` as a metrics object with a coherent narrative profile.
"""

from __future__ import annotations

import pytest

from scoring.bart import score_bart, validate_bart_session
from scoring.config import (
    ColorProfile,
    ConstantHazard,
    DynamicHazard,
    ExponentialHazard,
    GompertzHazard,
    LejuezHazard,
    LogisticHazard,
    LognormalHazard,
    RayleighHazard,
    StepHazard,
    TabularHazard,
    TaskConfig,
    WeibullHazard,
)
from tests.test_scoring import build_events, optimal_session, rich_session


def test_single_color_session_scores_with_coherent_style():
    """One risk context can't demonstrate cross-context calibration: uniformity
    is unknowable (None), but the session still scores and gets a risk style."""
    metrics = score_bart(build_events([("purple", 11, True)] * 10))

    assert metrics.ev_efficiency_uniformity is None
    assert metrics.behavioral_profile["risk_style"]
    assert metrics.behavioral_profile["description"]


def test_single_balloon_session_scores():
    """The smallest collectable session: one balloon, collected."""
    metrics = score_bart(build_events([("teal", 5, True)]))

    assert metrics.total_balloons == 1
    assert metrics.behavioral_profile["risk_style"]


def test_all_explosions_session_scores():
    """A session where nothing was banked: no collected balloons at all."""
    metrics = score_bart(build_events([("orange", 3, False)] * 5))

    assert metrics.money_collected == 0.0
    assert metrics.behavioral_profile["risk_style"]


def _custom_color_config():
    """The standard 128/32/8 linear study under custom color names."""
    return TaskConfig(
        title="custom colors",
        reward_per_pump=0.25,
        colors=[
            ColorProfile(name="crimson", label="C", display_hex="#dc2626",
                         max_pumps=128, trials=10, hazard=DynamicHazard()),
            ColorProfile(name="azure", label="A", display_hex="#2563eb",
                         max_pumps=32, trials=10, hazard=DynamicHazard()),
            ColorProfile(name="jade", label="J", display_hex="#059669",
                         max_pumps=8, trials=10, hazard=DynamicHazard()),
        ],
    )


def test_custom_color_names_get_uniformity_score():
    """A study with custom-named color profiles is a first-class citizen:
    with enough risk contexts, uniformity must be computed, not None."""
    balloons = []
    for color, stop in (("crimson", 11), ("azure", 5), ("jade", 2)):
        balloons.extend([(color, stop, True)] * 10)

    metrics = score_bart(build_events(balloons), config=_custom_color_config())

    assert metrics.ev_efficiency_uniformity is not None
    assert metrics.behavioral_profile["risk_style"]
    assert metrics.risk_calibration_score > 50  # optimal play, not zeroed out
    assert metrics.risk_adjustment_score > 50
    assert {cm.color for cm in metrics.color_metrics} == {"crimson", "azure", "jade"}


def test_custom_color_explosions_feed_penalty():
    """Excess explosions on a custom-named color must register in the
    explosion penalty instead of being silently ignored."""
    balloons = [("crimson", 11, True)] * 10 + [("azure", 5, True)] * 10
    balloons += [("jade", 2, True)] * 3 + [("jade", 6, False)] * 7

    metrics = score_bart(build_events(balloons), config=_custom_color_config())

    assert metrics.explosion_penalty > 0.0


# ── Validation follows the configured study shape, not the default (issue 57) ──


def test_validation_warns_on_the_studys_own_colors():
    """Per-color completeness warnings name the study's actual colors and counts
    — a renamed study is told which of *its* colors are under-filled, not warned
    about purple/teal/orange it never had."""
    balloons = (
        [("crimson", 11, True)] * 3  # under-filled (< half of 10)
        + [("azure", 5, True)] * 10
        + [("jade", 2, True)] * 10
    )
    metrics = score_bart(build_events(balloons), config=_custom_color_config())

    assert any("crimson" in w for w in metrics.session_warnings)
    assert not any(
        default in w
        for w in metrics.session_warnings
        for default in ("purple", "teal", "orange")
    )


def test_validation_thresholds_scale_with_configured_trials():
    """Completeness and per-color thresholds derive from the study's configured
    trial counts, not the default 10-per-color / 30-total — a 20-per-color study
    is judged against /20 and /60."""
    config = TaskConfig(
        title="high trial count",
        reward_per_pump=0.25,
        colors=[
            ColorProfile(name="crimson", label="C", display_hex="#dc2626",
                         max_pumps=128, trials=20, hazard=DynamicHazard()),
            ColorProfile(name="azure", label="A", display_hex="#2563eb",
                         max_pumps=32, trials=20, hazard=DynamicHazard()),
            ColorProfile(name="jade", label="J", display_hex="#059669",
                         max_pumps=8, trials=20, hazard=DynamicHazard()),
        ],
    )
    balloons = (
        [("crimson", 11, True)] * 8  # under-filled: 8 < 20/2
        + [("azure", 5, True)] * 20
        + [("jade", 2, True)] * 20
    )
    report = validate_bart_session(build_events(balloons), config)

    assert "Too few crimson balloons: 8/20 played" in report["warnings"]
    assert "Incomplete session: 48/60 balloons played" in report["warnings"]


# ── Rename-invariance: name-keyed persona metrics follow risk role (issue 56) ──
#
# The same behavior, scored under the default triad vs. renamed colors with the
# same caps and risk ordering, must produce identical name-keyed persona metrics —
# and they must be the genuine non-degenerate values, not 0/None. These pin the
# generalization from literal purple/teal/orange onto the config's risk ranking.


def test_learning_family_is_rename_invariant():
    """The learning-rate family keys on risk role, not color name: renamed
    colors reproduce the default study's non-zero learning values."""
    default = score_bart(rich_session())
    renamed = score_bart(
        rich_session("crimson", "azure", "jade"), config=_custom_color_config()
    )

    assert renamed.learning_rate == default.learning_rate != 0.0
    assert renamed.half_split_learning_rate == default.half_split_learning_rate != 0.0
    assert renamed.tercile_learning_rate == default.tercile_learning_rate != 0.0


def test_color_discrimination_index_is_rename_invariant():
    """color_discrimination_index (Cohen's d, safest vs. riskiest color) keys on
    risk role: renamed colors reproduce the default's non-degenerate value."""
    default = score_bart(rich_session())
    renamed = score_bart(
        rich_session("crimson", "azure", "jade"), config=_custom_color_config()
    )

    assert default.color_discrimination_index not in (None, 0.0)
    assert renamed.color_discrimination_index == default.color_discrimination_index


def test_color_discrimination_trajectory_is_rename_invariant():
    """The discrimination trajectory (safest-minus-riskiest separation across
    thirds, normalized by the EV-optimal spread) keys on risk role: renamed
    colors reproduce the default's non-degenerate value instead of reading None."""
    default = score_bart(rich_session())
    renamed = score_bart(
        rich_session("crimson", "azure", "jade"), config=_custom_color_config()
    )

    assert default.color_discrimination_trajectory not in (None, 0.0)
    assert renamed.color_discrimination_trajectory == default.color_discrimination_trajectory


def test_patience_and_high_risk_average_are_rename_invariant():
    """patience_index / patience_index_normalized (safest color) and
    orange_avg_pumps (riskiest color, keeping its legacy field name) key on risk
    role: renamed colors reproduce the default's non-degenerate values instead of
    reading 0/None."""
    default = score_bart(rich_session())
    renamed = score_bart(
        rich_session("crimson", "azure", "jade"), config=_custom_color_config()
    )

    assert default.patience_index not in (None, 0.0)
    assert renamed.patience_index == default.patience_index
    assert renamed.patience_index_normalized == default.patience_index_normalized

    assert default.orange_avg_pumps is not None
    assert renamed.orange_avg_pumps == default.orange_avg_pumps


def test_flat_strategy_detection_is_rename_invariant():
    """Flat-strategy detection keys on risk role: a low-but-discriminating session
    (safe color pumped well above the riskiest) is exempted from the
    'undifferentiated' flag under any color names, not just the default triad."""
    def sess(low, mid, high):
        b = []
        for _ in range(10):
            b.append((low, 3, True))
            b.append((mid, 2, True))
            b.append((high, 1, True))
        return build_events(b)

    default = score_bart(sess("purple", "teal", "orange"))
    renamed = score_bart(sess("crimson", "azure", "jade"), config=_custom_color_config())

    assert default.flat_strategy_detected is False
    assert renamed.flat_strategy_detected == default.flat_strategy_detected
    assert renamed.behavioral_profile["risk_style"] == default.behavioral_profile["risk_style"]


def test_behavioral_profile_selective_strength_is_rename_invariant():
    """The profile's selective-strength branches (Emerging/Selective Optimizer,
    the 'Near-Optimal on Safe Balloons' trait) read per-color EV efficiency by
    risk role: a near-optimal-on-safe / over-pumping-risky session classifies the
    same and carries the same traits under renamed colors."""
    def selective(low, mid, high):
        b = []
        for _ in range(10):
            b.append((low, 11, True))
            b.append((mid, 5, True))
            b.append((high, 6, False))
        return build_events(b)

    default = score_bart(selective("purple", "teal", "orange"))
    renamed = score_bart(selective("crimson", "azure", "jade"), config=_custom_color_config())

    assert default.behavioral_profile["risk_style"] == "Emerging Optimizer"
    assert renamed.behavioral_profile["risk_style"] == default.behavioral_profile["risk_style"]
    assert renamed.behavioral_profile["dominant_traits"] == default.behavioral_profile["dominant_traits"]


def test_risk_profile_labels_follow_ranking_not_config_position():
    """risk_profile is derived from the EV-optimal risk ranking, so a study that
    declares its colors riskiest-first still labels the safest color 'low' and the
    riskiest 'high', and the persona metrics resolve by that ranking rather than
    by config position."""
    config = TaskConfig(  # declared high-risk (N=8) first, low-risk (N=128) last
        title="reversed order",
        reward_per_pump=0.25,
        colors=[
            ColorProfile(name="jade", label="J", display_hex="#059669",
                         max_pumps=8, trials=10, hazard=DynamicHazard()),
            ColorProfile(name="azure", label="A", display_hex="#2563eb",
                         max_pumps=32, trials=10, hazard=DynamicHazard()),
            ColorProfile(name="crimson", label="C", display_hex="#dc2626",
                         max_pumps=128, trials=10, hazard=DynamicHazard()),
        ],
    )
    metrics = score_bart(
        rich_session(low="crimson", mid="azure", high="jade"), config=config
    )
    labels = {cm.color: cm.risk_profile for cm in metrics.color_metrics}

    assert labels == {"crimson": "low", "azure": "medium", "jade": "high"}
    # Persona metrics resolve by risk role, so they match the default triad's.
    assert metrics.patience_index == score_bart(rich_session()).patience_index


def test_flat_strategy_detected_for_custom_color_names():
    """Undifferentiated pumping is flagged regardless of what the study's
    colors are called."""
    balloons = []
    for color in ("crimson", "azure", "jade"):
        balloons.extend([(color, 2, True)] * 10)

    metrics = score_bart(build_events(balloons), config=_custom_color_config())

    assert metrics.flat_strategy_detected is True


def test_non_default_color_names_carry_no_persona_caveat():
    """The name-keyed persona metrics now resolve by risk role, so a renamed-color
    study scores them for real and carries no 'validated only for the default
    study' caveat (issue 56 completes the deferred half of issue 51 / kaizen F3)."""
    metrics = score_bart(
        rich_session("crimson", "azure", "jade"), config=_custom_color_config()
    )

    assert not any("persona" in w.lower() for w in metrics.session_warnings)
    # And the metrics are genuinely computed, not degraded to 0/None.
    assert metrics.learning_rate != 0.0
    assert metrics.color_discrimination_index not in (None, 0.0)
    assert metrics.patience_index > 0.0


def test_two_color_custom_study_discriminates():
    """A two-color custom study (safest + riskiest, no mid) resolves the
    safest-vs-riskiest discrimination by ranking — the metric is non-degenerate
    for any names, not just a purple/orange pair."""
    config = TaskConfig(
        title="two custom colors",
        reward_per_pump=0.25,
        colors=[
            ColorProfile(name="crimson", label="C", display_hex="#dc2626",
                         max_pumps=128, trials=10, hazard=DynamicHazard()),
            ColorProfile(name="jade", label="J", display_hex="#059669",
                         max_pumps=8, trials=10, hazard=DynamicHazard()),
        ],
    )
    balloons = [("crimson", 11, True)] * 10 + [("jade", 2, True)] * 10

    metrics = score_bart(build_events(balloons), config=config)

    assert metrics.color_discrimination_index not in (None, 0.0)
    assert not any("persona" in w.lower() for w in metrics.session_warnings)


def test_color_metrics_follow_configured_color_order():
    """The per-color breakdown lists colors in the study's configured order
    (the Master CSV derives its column order from it), not event order."""
    metrics = score_bart(optimal_session())

    assert [cm.color for cm in metrics.color_metrics] == ["purple", "teal", "orange"]


HAZARD_SPECS = [
    DynamicHazard(),
    ConstantHazard(p=0.1),
    LejuezHazard(),
    RayleighHazard(sigma=3.0),
    ExponentialHazard(rate=0.2),
    WeibullHazard(shape=1.5),
    GompertzHazard(a=0.05, b=0.4),
    LogisticHazard(h_max=0.8, midpoint=4.0, steepness=1.0),
    LognormalHazard(mu=1.0, sigma=0.5),
    StepHazard(breakpoints=[4], levels=[0.05, 0.5]),
    TabularHazard(values=[0.05] * 8),
]


@pytest.mark.parametrize("hazard", HAZARD_SPECS, ids=lambda h: h.family)
def test_every_hazard_family_scores_a_session(hazard):
    """Every curated hazard family scores a (degenerate, single-color)
    session without raising."""
    config = TaskConfig(
        title="family sweep",
        reward_per_pump=0.25,
        colors=[
            ColorProfile(name="solo", label="S", display_hex="#888888",
                         max_pumps=8, trials=6, hazard=hazard),
        ],
    )
    balloons = [("solo", 2, True)] * 5 + [("solo", 3, False)]

    metrics = score_bart(build_events(balloons), config=config)

    assert metrics.behavioral_profile["risk_style"]
