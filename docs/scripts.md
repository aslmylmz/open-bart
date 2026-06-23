# Scripts

Two helper scripts live in [`scripts/`](https://github.com/aslmylmz/metu-risk-persona/tree/main/scripts).
Neither is imported by the engine; both are standalone command-line tools.

## Monte Carlo EV verification

[`scripts/monte_carlo_ev.py`](https://github.com/aslmylmz/metu-risk-persona/blob/main/scripts/monte_carlo_ev.py)
empirically confirms the analytic EV-optimal stops and characterizes the
earnings distribution under optimal play. It simulates 100,000 sessions
(`N_SESSIONS`, seed 42) and produces three figures.

```bash
python scripts/monte_carlo_ev.py
```

```{admonition} Output location
:class: note

The script creates `output/figures/` automatically and writes its three figures
there. (`output/` is git-ignored.)
```

Outputs:

```{list-table}
:header-rows: 1
:widths: 34 66

* - File
  - Contents
* - `04_ev_curves.png`
  - $\mathrm{EV}(s, N)$ for each color with the optimal stop $s^*$ marked.
* - `05_mc_earnings.png`
  - Histogram of simulated session earnings under optimal play, with analytical EV and MC mean overlaid, plus a per-color breakdown.
* - `06_mc_trajectories.png`
  - Fan plot of cumulative-earnings trajectories across balloons (median, mean, and percentile envelopes).
```

The script also prints summary statistics — analytical EV, MC mean/median/SD,
the 5th–95th percentile band, and per-color survival probability and expected
collections — to stdout. The MC median (~27.25) is the reference value behind the
engine's `money_efficiency` metric.

Requires `numpy`, `scipy`, and `matplotlib`.

## Synthetic data generation

[`scripts/generate_synthetic.py`](https://github.com/aslmylmz/metu-risk-persona/blob/main/scripts/generate_synthetic.py)
generates synthetic participant records — DOSPERT subscale means and summary
BART metrics — drawn from parameterized distributions chosen to approximate
realistic ranges.

```{admonition} Synthetic, not real
:class: warning

The output does **not** represent real participants. The distributions are not
fit to any real dataset; the script exists for testing, demos, and pipeline
development. Real participant data is never committed to this repository.
```

```bash
python scripts/generate_synthetic.py                 # 60 participants, seed 42
python scripts/generate_synthetic.py --n 120         # 120 participants
python scripts/generate_synthetic.py --n 60 --seed 99
```

The result is written to `data/synthetic/synthetic_metu_{n}.csv`. Each row
carries demographics (age, gender, faculty, degree, employment, prior-task
exposure), five DOSPERT subscale means on a 1–7 scale (financial, health/safety,
recreational, ethical, social), and seven summary BART metrics
(`bart_rng_normalized_pumps`, `bart_impulsivity_index`,
`bart_patience_normalized`, `bart_mean_latency`, `bart_between_consistency`,
`bart_adaptive_strategy`, `bart_risk_sensitivity`).

Requires `numpy` and `pandas`.
