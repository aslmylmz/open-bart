"""Monte Carlo verification of the numeric EV optima.

``balloon_curve`` finds each color's EV-optimal stop by a numeric scan of the
analytic curve. This module confirms those optima by independent stochastic
simulation: balloons are burst directly from the hazard vector, the survival
and EV curves are rebuilt empirically, and the empirical argmax is compared to
the numeric optimum. The two paths share nothing but the hazard vector itself.

Numpy-only: safe to import in CI and inside the frozen sidecar environment
(no scipy/matplotlib).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from scoring.config.curve import BalloonCurve, balloon_curve
from scoring.config.hazards import (
    ConstantHazard,
    DynamicHazard,
    ExponentialHazard,
    GompertzHazard,
    HazardSpec,
    LejuezHazard,
    LogisticHazard,
    LognormalHazard,
    RayleighHazard,
    StepHazard,
    TabularHazard,
    WeibullHazard,
)
from scoring.config.task_config import TaskConfig

DEFAULT_N_SIMS = 100_000

# One representative, well-peaked parameterization per curated family:
# (spec, max_pumps). Parameters are chosen so the discrete EV optimum is
# clearly separated from its neighbors (no near-ties), making the seeded
# simulation check sharp.
REPRESENTATIVE_SPECS: dict[str, tuple[HazardSpec, int]] = {
    "dynamic": (DynamicHazard(), 32),
    "constant": (ConstantHazard(p=0.18), 32),
    "lejuez": (LejuezHazard(), 32),
    # sigma=5.0 at N=32 is an exact EV(4)=EV(5) tie; 4.5 gives a 5.9% peak gap.
    "rayleigh": (RayleighHazard(sigma=4.5), 32),
    "exponential": (ExponentialHazard(rate=0.3), 32),
    # Weibull's hazard is (m/N)(k/N)^(m-1): larger caps flatten the EV peak,
    # so the representative uses a small cap where the optimum is sharp.
    "weibull": (WeibullHazard(shape=3.0), 8),
    "gompertz": (GompertzHazard(a=0.02, b=0.3), 32),
    "logistic": (LogisticHazard(h_max=0.6, midpoint=6.0, steepness=0.8), 32),
    "lognormal": (LognormalHazard(mu=1.5, sigma=0.6), 32),
    "step": (StepHazard(breakpoints=[6], levels=[0.02, 0.4]), 32),
    "tabular": (TabularHazard(values=[round(0.05 * k, 2) for k in range(1, 13)]), 12),
}


@dataclass(frozen=True)
class OptimumVerification:
    """Outcome of simulating one color's curve.

    ``matches`` is the headline: the empirical EV argmax landed exactly on the
    numeric optimum.
    """

    numeric_optimum: int
    empirical_optimum: int
    matches: bool
    max_abs_survival_error: float


def _simulate_burst_points(
    hazard: tuple[float, ...], n_sims: int, rng: np.random.Generator
) -> np.ndarray:
    """Burst pump per simulated balloon (1-based); N+1 means never burst."""
    h = np.asarray(hazard, dtype=np.float64)
    n = len(h)
    rolls = rng.random((n_sims, n))
    burst = rolls < h
    first = np.where(burst.any(axis=1), burst.argmax(axis=1) + 1, n + 1)
    return first


def _empirical_curves(
    hazard: tuple[float, ...], n_sims: int, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Empirical (survival, EV) curves indexed by stop s = 0..N.

    S_hat(s) = P(balloon survives s pumps); reward cancels in the argmax,
    so the empirical EV curve is built in pump units: EV_hat(s) = s * S_hat(s).
    """
    n = len(hazard)
    burst_points = _simulate_burst_points(hazard, n_sims, np.random.default_rng(seed))
    burst_counts = np.bincount(burst_points, minlength=n + 2)
    survival_hat = 1.0 - np.cumsum(burst_counts)[: n + 1] / n_sims
    return survival_hat, np.arange(n + 1) * survival_hat


def empirical_ev_curve(
    hazard: list[float] | tuple[float, ...],
    n_sims: int = DEFAULT_N_SIMS,
    seed: int = 42,
) -> np.ndarray:
    """Simulated EV(s) in pump units for s = 0..N (for plots and inspection)."""
    _, ev_hat = _empirical_curves(tuple(hazard), n_sims, seed)
    return ev_hat


def verify_curve(
    curve: BalloonCurve,
    n_sims: int = DEFAULT_N_SIMS,
    seed: int = 42,
) -> OptimumVerification:
    """Confirm a curve's numeric optimum by seeded Monte Carlo simulation."""
    survival_hat, ev_hat = _empirical_curves(curve.hazard, n_sims, seed)

    empirical_optimum = int(ev_hat[1:].argmax()) + 1
    survival_error = float(np.abs(survival_hat - np.asarray(curve.survival)).max())
    return OptimumVerification(
        numeric_optimum=curve.optimum,
        empirical_optimum=empirical_optimum,
        matches=empirical_optimum == curve.optimum,
        max_abs_survival_error=survival_error,
    )


def verify_config(
    config: TaskConfig,
    n_sims: int = DEFAULT_N_SIMS,
    seed: int = 42,
) -> dict[str, OptimumVerification]:
    """Verify every color of a study, keyed by color name (config order)."""
    return {
        color: verify_curve(curve, n_sims=n_sims, seed=seed)
        for color, curve in config.curves.items()
    }


def verify_families(
    n_sims: int = DEFAULT_N_SIMS,
    seed: int = 42,
) -> dict[str, OptimumVerification]:
    """Verify the representative parameterization of every curated family."""
    results: dict[str, OptimumVerification] = {}
    for family, (spec, max_pumps) in REPRESENTATIVE_SPECS.items():
        curve = balloon_curve(spec.hazard_vector(max_pumps), 1.0)
        results[family] = verify_curve(curve, n_sims=n_sims, seed=seed)
    return results


def main() -> int:
    """Run the full sweep and print a per-family pass/fail table."""
    print(f"Monte Carlo verification of numeric EV optima "
          f"({DEFAULT_N_SIMS:,} simulated balloons per family, seed 42)\n")
    header = f"{'family':<12} {'N':>4} {'numeric':>8} {'empirical':>10} {'max |dS|':>10}  result"
    print(header)
    print("-" * len(header))

    results = verify_families()
    for family, result in results.items():
        max_pumps = REPRESENTATIVE_SPECS[family][1]
        print(
            f"{family:<12} {max_pumps:>4} {result.numeric_optimum:>8} "
            f"{result.empirical_optimum:>10} {result.max_abs_survival_error:>10.4f}  "
            f"{'PASS' if result.matches else 'FAIL'}"
        )

    return 0 if all(r.matches for r in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
