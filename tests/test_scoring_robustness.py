"""Degenerate-but-valid sessions must score, never crash (issue 29).

Any event log the validation pipeline accepts — single-color, single-balloon,
all-explosions, custom color names, any hazard family — must come back from
``score_bart`` as a metrics object with a coherent narrative profile.
"""

from __future__ import annotations

import pytest

from scoring.bart import score_bart
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
from tests.test_scoring import build_events, optimal_session


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


def test_flat_strategy_detected_for_custom_color_names():
    """Undifferentiated pumping is flagged regardless of what the study's
    colors are called."""
    balloons = []
    for color in ("crimson", "azure", "jade"):
        balloons.extend([(color, 2, True)] * 10)

    metrics = score_bart(build_events(balloons), config=_custom_color_config())

    assert metrics.flat_strategy_detected is True


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
