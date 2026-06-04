"""
Monte Carlo simulation of EV-optimal play on the three-colour BART.

Generates three figures for the technical reference:
  04_ev_curves.png        – EV(s,N) curves for all three colours with optimal stops marked
  05_mc_earnings.png      – Histogram of simulated session earnings under optimal play
  06_mc_trajectories.png  – Fan plot of cumulative earnings trajectories across sessions

Usage:
    python scripts/monte_carlo_ev.py
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# ── Configuration ────────────────────────────────────────────────────────
N_SESSIONS = 100_000
SEED = 42
COLORS = {
    "Purple": {"N": 128, "s_star": 11, "hex": "#A855F7", "balloons": 10},
    "Teal":   {"N": 32,  "s_star": 5,  "hex": "#14B8A6", "balloons": 10},
    "Orange": {"N": 8,   "s_star": 2,  "hex": "#F97316", "balloons": 10},
}
REWARD_PER_PUMP = 0.25
OUTPUT_DIR = "output/figures"


# ── EV computation ───────────────────────────────────────────────────────
def ev(s: int, N: int) -> float:
    """Expected value at stopping point s for a balloon with capacity N."""
    prod = 1.0
    for k in range(1, s + 1):
        prod *= (1 - k / N)
    return s * prod


def survival_prob(s: int, N: int) -> float:
    """Probability of surviving through s pumps."""
    prod = 1.0
    for k in range(1, s + 1):
        prod *= (1 - k / N)
    return prod


# ── Figure 1: EV curves ─────────────────────────────────────────────────
def plot_ev_curves():
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))

    for ax, (name, cfg) in zip(axes, COLORS.items()):
        N = cfg["N"]
        s_star = cfg["s_star"]
        color = cfg["hex"]

        # Compute EV for all valid s
        max_s = min(N - 1, s_star * 4)  # show enough of the curve
        ss = np.arange(1, max_s + 1)
        evs = np.array([ev(s, N) for s in ss])

        ax.plot(ss, evs, color=color, linewidth=2, zorder=3)
        ax.fill_between(ss, 0, evs, color=color, alpha=0.10)

        # Mark the optimal stop
        ev_star = ev(s_star, N)
        ax.plot(s_star, ev_star, "o", color=color, markersize=10,
                markeredgecolor="black", markeredgewidth=1.2, zorder=5)
        ax.annotate(
            f"$s^* = {s_star}$\nEV = {ev_star:.2f}",
            xy=(s_star, ev_star),
            xytext=(s_star + max_s * 0.12, ev_star * 0.85),
            fontsize=10,
            arrowprops=dict(arrowstyle="->", color="black", lw=1),
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.9),
        )

        ax.set_title(f"{name} ($N = {N}$)", fontsize=13, fontweight="bold")
        ax.set_xlabel("Stopping point $s$", fontsize=11)
        ax.set_ylabel("EV($s$, $N$)", fontsize=11)
        ax.set_xlim(0, max_s + 1)
        ax.set_ylim(0, ev_star * 1.35)
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        ax.grid(True, alpha=0.3)

    fig.suptitle("Expected Value Curves by Balloon Colour", fontsize=15,
                 fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(f"{OUTPUT_DIR}/04_ev_curves.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {OUTPUT_DIR}/04_ev_curves.png")


# ── Simulation ───────────────────────────────────────────────────────────
def run_simulation():
    """Run MC simulation, returning final earnings and per-balloon trajectories."""
    rng = np.random.default_rng(SEED)
    earnings = np.zeros(N_SESSIONS)
    per_colour_earnings = {}

    # Track cumulative earnings after each balloon (30 total)
    total_balloons = sum(cfg["balloons"] for cfg in COLORS.values())
    trajectories = np.zeros((N_SESSIONS, total_balloons + 1))  # col 0 = start at $0
    balloon_idx = 0

    # Build balloon order: all purple, then teal, then orange (matches task order)
    balloon_order = []
    for name, cfg in COLORS.items():
        for _ in range(cfg["balloons"]):
            balloon_order.append(name)

    for name, cfg in COLORS.items():
        N = cfg["N"]
        s_star = cfg["s_star"]
        n_balloons = cfg["balloons"]
        colour_earnings = np.zeros(N_SESSIONS)

        for b in range(n_balloons):
            rolls = rng.random((N_SESSIONS, s_star))
            thresholds = np.arange(1, s_star + 1) / N
            exploded = np.any(rolls < thresholds, axis=1)
            survived = ~exploded
            reward = survived * s_star * REWARD_PER_PUMP

            colour_earnings += reward
            balloon_idx += 1
            trajectories[:, balloon_idx] = trajectories[:, balloon_idx - 1] + reward

        per_colour_earnings[name] = colour_earnings
        earnings += colour_earnings

    return earnings, per_colour_earnings, trajectories


def plot_mc_histogram(earnings, per_colour_earnings):
    analytical = sum(
        cfg["balloons"] * ev(cfg["s_star"], cfg["N"]) * REWARD_PER_PUMP
        for cfg in COLORS.values()
    )
    mc_mean = np.mean(earnings)
    mc_sd = np.std(earnings)
    mc_median = np.median(earnings)
    p5 = np.percentile(earnings, 5)
    p95 = np.percentile(earnings, 95)

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5),
                             gridspec_kw={"width_ratios": [3, 2]})

    # ── Left panel: overall earnings histogram ───────────────────────────
    ax = axes[0]

    # Histogram with finer bins and softer colour
    n, bin_edges, patches = ax.hist(
        earnings, bins=80, color="#5B9BD5", edgecolor="white",
        linewidth=0.4, alpha=0.80, density=True,
    )

    # Shade the 5th-95th percentile region (subtle)
    ax.axvspan(p5, p95, alpha=0.08, color="#333333",
               label=f"90% interval: \${p5:.0f}\u2013\${p95:.0f}")

    # Analytical EV line
    ax.axvline(analytical, color="#E74C3C", linewidth=2.2, linestyle="--",
               label=f"Analytical EV = \${analytical:.2f}", zorder=4)

    # MC mean line
    ax.axvline(mc_mean, color="#27AE60", linewidth=2.2, linestyle="-",
               label=f"MC mean = \${mc_mean:.2f}", zorder=4)

    # Annotate SD on the plot directly
    ax.annotate(
        f"SD = \${mc_sd:.2f}",
        xy=(mc_mean + mc_sd, max(n) * 0.55),
        fontsize=10, color="#555555",
        ha="left",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#cccccc", alpha=0.85),
    )
    # Draw a double-headed arrow for 1 SD
    ax.annotate(
        "", xy=(mc_mean + mc_sd, max(n) * 0.50),
        xytext=(mc_mean, max(n) * 0.50),
        arrowprops=dict(arrowstyle="<->", color="#555555", lw=1.2),
    )

    ax.set_xlabel("Session Earnings ($)", fontsize=12)
    ax.set_ylabel("Density", fontsize=12)
    ax.set_title(
        f"Simulated Earnings Under EV-Optimal Play ({N_SESSIONS:,} sessions)",
        fontsize=13, fontweight="bold",
    )
    ax.legend(fontsize=9.5, loc="upper left", framealpha=0.9)
    ax.grid(True, alpha=0.25, linewidth=0.5)
    ax.set_xlim(5, 48)

    # ── Right panel: per-colour violin + strip ───────────────────────────
    ax2 = axes[1]

    colour_names = list(COLORS.keys())
    colour_hexes = [COLORS[c]["hex"] for c in colour_names]
    colour_data = [per_colour_earnings[c] for c in colour_names]
    colour_means = [np.mean(d) for d in colour_data]
    colour_sds = [np.std(d) for d in colour_data]

    positions = [1, 2, 3]

    # Violin plots for shape
    parts = ax2.violinplot(colour_data, positions=positions, showmeans=False,
                           showmedians=False, showextrema=False, widths=0.7)
    for pc, c in zip(parts["bodies"], colour_hexes):
        pc.set_facecolor(c)
        pc.set_alpha(0.35)
        pc.set_edgecolor(c)
        pc.set_linewidth(1.2)

    # Box plots overlaid (narrow)
    bp = ax2.boxplot(
        colour_data, positions=positions, widths=0.25, patch_artist=True,
        showfliers=False,
        medianprops=dict(color="black", linewidth=1.5),
        whiskerprops=dict(color="gray", linewidth=1),
        capprops=dict(color="gray", linewidth=1),
    )
    for patch, c in zip(bp["boxes"], colour_hexes):
        patch.set_facecolor(c)
        patch.set_alpha(0.6)
        patch.set_edgecolor("black")
        patch.set_linewidth(0.8)

    # Mean markers with value labels
    for i, (m, sd, c) in enumerate(zip(colour_means, colour_sds, colour_hexes)):
        ax2.plot(positions[i], m, "D", color="black", markersize=7, zorder=5)
        ax2.annotate(
            f"\${m:.2f}\n(\u00b1{sd:.2f})",
            xy=(positions[i], m),
            xytext=(positions[i] + 0.38, m),
            fontsize=9, ha="left", va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#cccccc", alpha=0.85),
        )

    ax2.set_xticks(positions)
    ax2.set_xticklabels(colour_names, fontsize=11)
    ax2.set_ylabel("Earnings per colour ($)", fontsize=12)
    ax2.set_title("Per-Colour Breakdown", fontsize=13, fontweight="bold")
    ax2.grid(True, alpha=0.25, axis="y", linewidth=0.5)
    ax2.set_xlim(0.3, 3.9)

    fig.tight_layout(w_pad=3)
    fig.savefig(f"{OUTPUT_DIR}/05_mc_earnings.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {OUTPUT_DIR}/05_mc_earnings.png")

    # Print summary stats
    print(f"\n{'='*50}")
    print(f"Monte Carlo Simulation Results ({N_SESSIONS:,} sessions)")
    print(f"{'='*50}")
    print(f"  Analytical EV:  ${analytical:.2f}")
    print(f"  MC Mean:        ${mc_mean:.2f}")
    print(f"  MC Median:      ${mc_median:.2f}")
    print(f"  MC SD:          ${mc_sd:.2f}")
    print(f"  MC Min:         ${np.min(earnings):.2f}")
    print(f"  MC Max:         ${np.max(earnings):.2f}")
    print(f"  5th percentile: ${np.percentile(earnings, 5):.2f}")
    print(f"  95th percentile:${np.percentile(earnings, 95):.2f}")
    print()
    for name, cfg in COLORS.items():
        ce = per_colour_earnings[name]
        ev_star = ev(cfg["s_star"], cfg["N"])
        surv = survival_prob(cfg["s_star"], cfg["N"])
        expected_collections = cfg["balloons"] * surv
        print(f"  {name} (N={cfg['N']}, s*={cfg['s_star']}):")
        print(f"    Survival prob per balloon: {surv:.4f}")
        print(f"    Expected collections:      {expected_collections:.2f} / {cfg['balloons']}")
        print(f"    Mean earnings:             ${np.mean(ce):.2f}")
        print(f"    SD:                        ${np.std(ce):.2f}")


# ── Figure 3: Trajectory fan plot ────────────────────────────────────────
def plot_trajectories(trajectories):
    """Fan plot of cumulative earnings across balloons, styled after MC price sims."""
    from matplotlib.collections import LineCollection
    from matplotlib.colors import Normalize

    n_sessions, n_steps = trajectories.shape
    x = np.arange(n_steps)

    # Monotone interpolation to smooth discrete steps without artifacts
    from scipy.interpolate import PchipInterpolator
    x_smooth = np.linspace(0, n_steps - 1, 300)

    N_PATHS = 800
    rng_draw = np.random.default_rng(99)
    sample_idx = rng_draw.choice(n_sessions, size=N_PATHS, replace=False)

    fig, ax = plt.subplots(figsize=(15, 7))

    # ── Percentile envelope (gradient fill) ───────────────────────────
    pct_pairs = [(5, 95), (10, 90), (20, 80), (30, 70), (40, 60)]
    n_bands = len(pct_pairs)
    for i, (lo, hi) in enumerate(pct_pairs):
        p_lo = np.percentile(trajectories, lo, axis=0)
        p_hi = np.percentile(trajectories, hi, axis=0)
        # Smooth the envelopes too
        spl_lo = PchipInterpolator(x, p_lo)
        spl_hi = PchipInterpolator(x, p_hi)
        alpha = 0.06 + 0.04 * (n_bands - i) / n_bands
        ax.fill_between(x_smooth, spl_lo(x_smooth), spl_hi(x_smooth),
                         alpha=alpha, color="#60A5FA", linewidth=0)

    # ── Individual paths colored by final earnings ────────────────────
    final_earnings = trajectories[sample_idx, -1]
    norm = Normalize(vmin=np.percentile(final_earnings, 2),
                     vmax=np.percentile(final_earnings, 98))
    cmap = plt.cm.plasma

    # Sort so extreme paths draw on top
    sort_order = np.argsort(np.abs(final_earnings - np.median(final_earnings)))
    for rank, idx in enumerate(sample_idx[sort_order]):
        y = trajectories[idx]
        spl = PchipInterpolator(x, y)
        y_smooth = np.clip(spl(x_smooth), 0, None)
        c = cmap(norm(trajectories[idx, -1]))
        ax.plot(x_smooth, y_smooth, color=c,
                alpha=0.12 + 0.10 * (rank / N_PATHS),
                linewidth=0.4 + 0.3 * (rank / N_PATHS), zorder=2)

    # ── Median and mean (bold, with halo) ─────────────────────────────
    median_line = np.median(trajectories, axis=0)
    mean_line = np.mean(trajectories, axis=0)

    spl_med = PchipInterpolator(x, median_line)
    spl_mean = PchipInterpolator(x, mean_line)

    ax.plot(x_smooth, spl_med(x_smooth), color="#0f172a", linewidth=4, zorder=4)
    ax.plot(x_smooth, spl_med(x_smooth), color="#38BDF8", linewidth=2.2,
            label=f"Median = ${median_line[-1]:.2f}", zorder=5)
    ax.plot(x_smooth, spl_mean(x_smooth), color="#0f172a", linewidth=4, zorder=4)
    ax.plot(x_smooth, spl_mean(x_smooth), color="#FB923C", linewidth=2.2,
            linestyle="--", label=f"Mean = ${mean_line[-1]:.2f}", zorder=5)

    # ── Phase dividers (subtle vertical bands) ────────────────────────
    phase_cfg = [
        (0, 10, "#A855F7", "Purple"),
        (10, 20, "#14B8A6", "Teal"),
        (20, 30, "#F97316", "Orange"),
    ]
    for start, end, color, label in phase_cfg:
        ax.axvspan(start, end, alpha=0.04, color=color, zorder=0)
        if end < 30:
            ax.axvline(end, color=color, alpha=0.3, linewidth=0.8,
                       linestyle="--", zorder=1)
        ax.text((start + end) / 2, 1.01, label, ha="center", fontsize=9,
                color=color, fontweight="bold", alpha=0.8,
                transform=ax.get_xaxis_transform())

    # ── Colorbar for path earnings ────────────────────────────────────
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.02, aspect=30, shrink=0.85)
    cbar.set_label("Final Session Earnings ($)", fontsize=10, color="#d1d5db")
    cbar.ax.tick_params(colors="#d1d5db", labelsize=8)
    cbar.outline.set_edgecolor("#374151")

    # ── Axes and styling ──────────────────────────────────────────────
    ax.set_xlabel("Balloon Number", fontsize=12)
    ax.set_ylabel("Cumulative Earnings ($)", fontsize=12)
    ax.set_title(
        f"Monte Carlo Earnings Trajectories  ({N_PATHS:,} of {N_SESSIONS:,} sessions)",
        fontsize=14, fontweight="bold", pad=18,
    )
    ax.set_xlim(0, n_steps - 1)
    ax.set_ylim(bottom=0)

    # Dark theme
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#1e293b")
    ax.tick_params(colors="#94A3B8", labelsize=9)
    ax.xaxis.label.set_color("#CBD5E1")
    ax.yaxis.label.set_color("#CBD5E1")
    ax.title.set_color("#F1F5F9")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.grid(True, alpha=0.10, color="#475569", linewidth=0.5)
    ax.legend(fontsize=10, loc="upper left", framealpha=0.85,
              facecolor="#1e293b", edgecolor="#475569", labelcolor="#E2E8F0")

    fig.tight_layout()
    fig.savefig(f"{OUTPUT_DIR}/06_mc_trajectories.png", dpi=250,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Saved {OUTPUT_DIR}/06_mc_trajectories.png")


if __name__ == "__main__":
    plot_ev_curves()
    earnings, per_colour_earnings, trajectories = run_simulation()
    plot_mc_histogram(earnings, per_colour_earnings)
    plot_trajectories(trajectories)
