"""
EV curves across the curated hazard-family library.

Generates one figure for the technical reference / paper:
  07_hazard_families_ev.png – analytic EV(s) per family (unit reward) with the
  numeric optimum marked and seeded Monte Carlo estimates overlaid.

The analytic curves and optima come from ``balloon_curve``; the overlaid points
come from ``scoring.verification`` (independent stochastic simulation). Uses
the same representative parameterizations as ``python -m scoring.verification``.

Usage:
    python scripts/plot_hazard_families.py

Requires the ``[scripts]`` extra (matplotlib).
"""

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from scoring.config.curve import balloon_curve
from scoring.verification import REPRESENTATIVE_SPECS, empirical_ev_curve

SEED = 42
N_SIMS = 100_000
OUTPUT_DIR = "output/figures"
ACCENT = "#0F766E"
MC_DOT = "#9333EA"


def plot_families():
    fig, axes = plt.subplots(3, 4, figsize=(16, 10.5))

    for ax, (family, (spec, n)) in zip(axes.flat, REPRESENTATIVE_SPECS.items()):
        hazard = spec.hazard_vector(n)
        curve = balloon_curve(hazard, 1.0)
        ss = np.arange(1, n + 1)

        ax.plot(ss, curve.ev[1:], color=ACCENT, linewidth=2, zorder=3,
                label="analytic EV")
        ax.fill_between(ss, 0, curve.ev[1:], color=ACCENT, alpha=0.08)

        ev_hat = empirical_ev_curve(hazard, n_sims=N_SIMS, seed=SEED)
        ax.plot(ss, ev_hat[1:], "o", color=MC_DOT, markersize=3.5, alpha=0.75,
                zorder=4, label="Monte Carlo")

        s_star = curve.optimum
        ax.axvline(s_star, color="black", linewidth=0.9, linestyle=":", zorder=2)
        ax.plot(s_star, curve.ev[s_star], "o", color=ACCENT, markersize=8,
                markeredgecolor="black", markeredgewidth=1.1, zorder=5)

        ax.set_title(f"{family}  ($N={n}$, $s^*={s_star}$)", fontsize=12,
                     fontweight="bold")
        ax.set_xlabel("Stopping point $s$", fontsize=10)
        ax.set_ylabel("EV($s$) / reward", fontsize=10)
        ax.set_xlim(0, n + 1)
        ax.set_ylim(bottom=0)
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        ax.grid(True, alpha=0.3)

    # 11 families on a 3x4 grid: the last panel carries the legend.
    spare = axes.flat[len(REPRESENTATIVE_SPECS)]
    spare.axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    spare.legend(handles, labels, loc="center", fontsize=12, frameon=False)

    fig.suptitle(
        "Expected-Value Curves Across the Curated Hazard-Family Library\n"
        f"(numeric optima marked; {N_SIMS:,} simulated balloons per family, seed {SEED})",
        fontsize=15, fontweight="bold", y=1.0,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    out = f"{OUTPUT_DIR}/07_hazard_families_ev.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {out}")


if __name__ == "__main__":
    plot_families()
