"""The scoring engine is driven by a TaskConfig (no hardcoded optima/reward).

score_bart accepts a config; with the default config it reproduces the validated
128/32/8 -> 11/5/2 behavior (the existing suite guards that), and with a custom
config its optima and reward follow the config.
"""

from __future__ import annotations

import pytest

from scoring.bart import score_bart
from scoring.config import (
    ColorProfile,
    LinearHazard,
    TaskConfig,
    UniformHazard,
)
from tests.test_scoring import optimal_session


def _config(purple_hazard, reward=0.25):
    """A 3-color study (purple varies) with the standard caps/trials."""
    return TaskConfig(
        title="test study",
        reward_per_pump=reward,
        colors=[
            ColorProfile(name="purple", label="P", display_hex="#7c3aed",
                         max_pumps=128, trials=10, hazard=purple_hazard),
            ColorProfile(name="teal", label="T", display_hex="#14b8a6",
                         max_pumps=32, trials=10, hazard=LinearHazard()),
            ColorProfile(name="orange", label="O", display_hex="#f97316",
                         max_pumps=8, trials=10, hazard=LinearHazard()),
        ],
    )


def test_score_bart_uses_config_optima():
    """Switching purple to the uniform (Lejuez) hazard moves its optimum to N/2."""
    metrics = score_bart(optimal_session(), config=_config(UniformHazard()))
    assert metrics.ev_optimal_stops["purple"] == 64   # uniform N=128 -> N/2
    assert metrics.ev_optimal_stops["teal"] == 5       # unchanged linear
    assert metrics.ev_optimal_stops["orange"] == 2


def test_default_config_still_yields_established_optima():
    """With no config (the default study), score_bart still reports 11/5/2."""
    stops = score_bart(optimal_session()).ev_optimal_stops
    assert (stops["purple"], stops["teal"], stops["orange"]) == (11, 5, 2)


def test_money_collected_uses_config_reward():
    """money_collected scales with reward_per_pump, not a hardcoded $0.25."""
    events = optimal_session()
    cheap = score_bart(events, config=_config(LinearHazard(), reward=0.25))
    rich = score_bart(events, config=_config(LinearHazard(), reward=1.0))
    # 10 balloons/color collected at 11/5/2 -> 180 banked pumps.
    assert cheap.money_collected == pytest.approx(45.0)
    assert rich.money_collected == pytest.approx(180.0)
