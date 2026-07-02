"""Monte Carlo verification of the numeric EV optima (issue 30).

The numeric optima from ``balloon_curve`` are confirmed by independent
stochastic simulation: balloons are burst directly from the hazard vector and
the EV curve is rebuilt empirically. Seeded, so deterministic in CI.
"""

from __future__ import annotations

import subprocess
import sys

from scoring.config import DEFAULT_TASK_CONFIG
from scoring.verification import verify_config, verify_curve, verify_families


def test_default_purple_optimum_confirmed_by_simulation():
    """The flagship claim: the linear N=128 optimum (11 pumps) is reproduced
    by simulation, not just by the numeric scan that defined it."""
    curve = DEFAULT_TASK_CONFIG.curves["purple"]

    result = verify_curve(curve, seed=42)

    assert result.numeric_optimum == 11
    assert result.empirical_optimum == 11
    assert result.matches


def test_empirical_survival_tracks_analytic_curve():
    """Beyond the argmax: the whole simulated survival curve stays within
    sampling tolerance of the analytic one (the two share only the hazards)."""
    curve = DEFAULT_TASK_CONFIG.curves["teal"]

    result = verify_curve(curve, seed=42)

    assert result.max_abs_survival_error < 0.01


def test_verify_config_covers_every_color_of_the_default_study():
    """A whole study verifies in one call: 11/5/2 all reproduced."""
    results = verify_config(DEFAULT_TASK_CONFIG, seed=42)

    assert set(results) == {"purple", "teal", "orange"}
    assert all(r.matches for r in results.values())
    assert [results[c].numeric_optimum for c in ("purple", "teal", "orange")] == [11, 5, 2]


def test_every_curated_family_optimum_is_reproduced():
    """The paper's claim: for a representative parameterization of each of the
    11 curated hazard families, simulation lands on the numeric optimum."""
    results = verify_families(seed=42)

    assert len(results) == 11
    mismatches = {
        family: (r.numeric_optimum, r.empirical_optimum)
        for family, r in results.items()
        if not r.matches
    }
    assert mismatches == {}


def test_one_command_sweep_prints_pass_table():
    """`python -m scoring.verification` is the reproducible one-command sweep:
    a PASS row per curated family, exit code 0."""
    proc = subprocess.run(
        [sys.executable, "-m", "scoring.verification"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0
    assert proc.stdout.count("PASS") == 11
    assert "FAIL" not in proc.stdout
