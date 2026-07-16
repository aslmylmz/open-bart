"""Behavior of the TaskConfig + hazard-family library (scoring.config).

Tests exercise the public interface: hazard families produce hazard vectors,
configs expose EV curves with numeric optima, and the default linear study
reproduces the established 128/32/8 -> 11/5/2 result.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from scoring.config import (
    DEFAULT_TASK_CONFIG,
    ColorProfile,
    TaskConfig,
    ConstantHazard,
    ExponentialHazard,
    GompertzHazard,
    HazardSpec,
    DynamicHazard,
    LogisticHazard,
    LognormalHazard,
    RayleighHazard,
    StepHazard,
    TabularHazard,
    LejuezHazard,
    WeibullHazard,
    balloon_curve,
)


def _is_increasing(xs):
    return all(b >= a for a, b in zip(xs, xs[1:]))


def test_dynamic_hazard():
    h = DynamicHazard().hazard_vector(8)
    assert h == [1 / 8, 2 / 8, 3 / 8, 4 / 8, 5 / 8, 6 / 8, 7 / 8, 1.0]

    # EV max for N=128 should be at pump 11
    # Check it using the curve precomputation
    curve = balloon_curve(DynamicHazard().hazard_vector(128), reward_per_pump=1.0)
    assert curve.optimum == 11
    assert curve.optimal_ev == pytest.approx(6.46, abs=0.01)


def test_color_profile_curve_uses_its_cap():
    """A ColorProfile builds its curve from its own max_pumps cap (teal N=32 -> 5)."""
    teal = ColorProfile(
        name="teal",
        label="Teal",
        display_hex="#14b8a6",
        max_pumps=32,
        trials=10,
        hazard=DynamicHazard(),
    )
    assert teal.curve(reward_per_pump=1.0).optimum == 5


def test_default_config_reproduces_established_optima():
    """The shipped default linear study yields the validated optima 11/5/2."""
    assert DEFAULT_TASK_CONFIG.optima == {"purple": 11, "teal": 5, "orange": 2}


def test_study_preset_declares_optional_conditions():
    """A Study Preset may declare the allowed condition names for a
    between-subject design (issue 37). The field is optional: a v1.0.0
    `study.json` without it keeps validating, with no conditions."""
    v1 = DEFAULT_TASK_CONFIG.model_dump()
    v1.pop("conditions", None)  # exactly what a v1.0.0 file contains
    from scoring.config import TaskConfig

    assert TaskConfig.model_validate(v1).conditions == []

    conditioned = TaskConfig.model_validate({**v1, "conditions": ["control", "experimental"]})
    assert conditioned.conditions == ["control", "experimental"]


def test_optimum_is_invariant_to_reward():
    """reward_per_pump scales EV uniformly, so it must not move the optimum."""
    h = DynamicHazard().hazard_vector(64)
    cheap = balloon_curve(h, reward_per_pump=0.25)
    rich = balloon_curve(h, reward_per_pump=4.0)
    assert cheap.optimum == rich.optimum
    assert rich.optimal_ev == pytest.approx(cheap.optimal_ev * (4.0 / 0.25))


def test_constant_hazard_optimum_is_inverse_p():
    """Constant family: flat hazard p, geometric burst-time, optimum ~ 1/p."""
    curve = balloon_curve(ConstantHazard(p=0.1).hazard_vector(60), reward_per_pump=1.0)
    assert all(h == pytest.approx(0.1) for h in curve.hazard)
    assert curve.optimum == pytest.approx(10, abs=1)


def test_lejuez_hazard():
    curve = balloon_curve(LejuezHazard().hazard_vector(64), reward_per_pump=1.0)
    assert curve.optimum == 32  # standard property of the classic BART
    assert curve.hazard[-1] == pytest.approx(1.0)


def test_rayleigh_optimum_is_sigma():
    """h(k)=k/sigma^2; optimum ~ sigma, decoupled from the (larger) pump cap."""
    curve = balloon_curve(RayleighHazard(sigma=10).hazard_vector(50), reward_per_pump=1.0)
    assert curve.optimum == pytest.approx(10, abs=1)


def test_exponential_optimum_is_inverse_rate():
    """Flat hazard 1-e^(-rate); geometric burst-time, optimum ~ 1/rate."""
    curve = balloon_curve(ExponentialHazard(rate=0.1).hazard_vector(60), reward_per_pump=1.0)
    assert curve.optimum == pytest.approx(10, abs=1)


# ── Shape families (no clean closed-form optimum: structural assertions) ──────


def test_weibull_shape_two_is_rising_with_interior_optimum():
    h = WeibullHazard(shape=2).hazard_vector(128)
    assert all(0.0 <= x <= 1.0 for x in h)
    assert _is_increasing(h)
    curve = balloon_curve(h, reward_per_pump=1.0)
    assert 64 < curve.optimum < 128  # ~ N/sqrt(2)


def test_gompertz_hazard_accelerates():
    h = GompertzHazard(a=0.001, b=0.05).hazard_vector(128)
    assert all(0.0 <= x <= 1.0 for x in h)
    assert _is_increasing(h)
    assert h[-1] > h[0]


def test_logistic_hazard_is_a_bounded_s_curve():
    spec = LogisticHazard(h_max=0.9, midpoint=20, steepness=0.3)
    h = spec.hazard_vector(40)
    assert all(0.0 <= x <= 0.9 + 1e-9 for x in h)
    assert _is_increasing(h)
    assert h[0] < 0.1 < h[-1]


def test_lognormal_hazard_is_non_monotone():
    h = LognormalHazard(mu=3.0, sigma=0.5).hazard_vector(60)
    assert all(0.0 <= x <= 1.0 for x in h)
    rises = any(b > a for a, b in zip(h, h[1:]))
    falls = any(b < a for a, b in zip(h, h[1:]))
    assert rises and falls  # the defining feature: rise then fall


def test_lognormal_hazard_matches_scipy_reference():
    """The (scipy-free) lognormal hazard matches scipy.stats.lognorm to fp.

    Guards the math.erfc reimplementation against the original source of truth.
    Runs only where scipy is installed; the engine itself never imports it.
    """
    import math

    stats = pytest.importorskip("scipy.stats")
    mu, sigma, n = 3.0, 0.5, 60
    dist = stats.lognorm(s=sigma, scale=math.exp(mu))
    expected = []
    for k in range(1, n + 1):
        sf = float(dist.sf(k))
        ratio = float(dist.pdf(k)) / sf if sf > 1e-12 else None
        expected.append(1.0 if ratio is None else min(max(ratio, 0.0), 1.0))

    got = LognormalHazard(mu=mu, sigma=sigma).hazard_vector(n)
    assert got == pytest.approx(expected, rel=1e-9, abs=1e-12)


def test_step_hazard_takes_segment_levels():
    h = StepHazard(breakpoints=[10, 20], levels=[0.05, 0.2, 0.6]).hazard_vector(30)
    assert h[4] == pytest.approx(0.05)   # pump 5  -> segment 0
    assert h[14] == pytest.approx(0.2)   # pump 15 -> segment 1
    assert h[24] == pytest.approx(0.6)   # pump 25 -> segment 2


def test_tabular_hazard_returns_its_array():
    h = TabularHazard(values=[0.1, 0.3, 0.7, 1.0]).hazard_vector(4)
    assert h == pytest.approx([0.1, 0.3, 0.7, 1.0])


# ── Deployment & reporting flags (multi-station, schema 1.1) ─────────────────


def test_v10_study_json_loads_with_default_deployment_flags():
    """A pre-split (v1.0) `study.json` lacks `standalone`/`metrics_mode`; the
    pydantic defaults must fill them in — zero migration, byte-for-byte
    v1.0.0 behavior."""
    v1 = DEFAULT_TASK_CONFIG.model_dump()
    v1["schema_version"] = "1.0"  # exactly what a v1.0.0 file contains
    v1.pop("standalone", None)
    v1.pop("metrics_mode", None)

    loaded = TaskConfig.model_validate(v1)
    assert loaded.standalone is False
    assert loaded.metrics_mode == "advanced"
    assert loaded.schema_version == "1.0"  # documentary, not load-bearing


def test_default_schema_version_is_1_1():
    assert DEFAULT_TASK_CONFIG.schema_version == "1.1"


def test_deployment_flags_ride_the_freeze_path():
    """Both flags must land in the distributed `study.json` and each per-session
    `config.json`, which are plain `model_dump_json` snapshots of the config."""
    frozen = json.loads(DEFAULT_TASK_CONFIG.model_dump_json())
    assert frozen["standalone"] is False
    assert frozen["metrics_mode"] == "advanced"


def test_metrics_mode_admits_only_the_two_modes():
    v1 = DEFAULT_TASK_CONFIG.model_dump()
    assert TaskConfig.model_validate({**v1, "metrics_mode": "classic"}).metrics_mode == "classic"
    with pytest.raises(ValidationError):
        TaskConfig.model_validate({**v1, "metrics_mode": "detailed"})


# ── Validation ───────────────────────────────────────────────────────────────


def test_constant_p_must_be_a_probability():
    with pytest.raises(ValidationError):
        ConstantHazard(p=1.5)


def test_tabular_values_must_be_in_unit_interval():
    with pytest.raises(ValidationError):
        TabularHazard(values=[0.5, 1.2])


def test_tabular_length_must_match_cap():
    spec = TabularHazard(values=[0.1, 0.3, 0.7, 1.0])
    with pytest.raises(ValueError):
        spec.hazard_vector(5)


def test_balloon_curve_rejects_non_finite_hazard():
    """A corrupt (NaN/inf) hazard must fail loudly, not skew the optimum silently."""
    with pytest.raises(ValueError):
        balloon_curve([0.1, float("nan"), 0.3], reward_per_pump=1.0)


def test_hazard_spec_is_selected_by_family_tag():
    """A study file names a family; the discriminated union picks the model."""
    cp = ColorProfile.model_validate(
        {
            "name": "x",
            "label": "X",
            "display_hex": "#ffffff",
            "max_pumps": 64,
            "trials": 10,
            "hazard": {"family": "lejuez"},
        }
    )
    assert isinstance(cp.hazard, LejuezHazard)
    assert cp.curve(reward_per_pump=1.0).optimum == 32
