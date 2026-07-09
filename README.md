[![Documentation Status](https://readthedocs.org/projects/open-bart/badge/?version=latest)](https://open-bart.readthedocs.io/en/latest/?badge=latest)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20592164.svg)](https://doi.org/10.5281/zenodo.20592164)
[![Latest release](https://img.shields.io/github/v/release/aslmylmz/open-bart)](https://github.com/aslmylmz/open-bart/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

# Dynamic Hazard Rate BART

**A configurable, offline desktop instrument for the Balloon Analogue Risk Task**

Dynamic Hazard Rate BART is an open-source desktop application that lets a
research lab administer, score, and export Balloon Analogue Risk Task sessions
**without writing any code and without a network connection**. A researcher
designs a study in a point-and-click Study Setup screen — choosing from a
curated library of **11 hazard families** with a live expected-value preview —
saves it as a portable `study.json`, and runs participants through a
conventional BART flow (Consent → ID → Gameplay → Debrief). Every session is
scored locally by a bundled Python engine (40+ psychometric metrics) and
written to per-session files plus a shared **Master CSV** ready for SPSS or R.

The flagship paradigm is the **dynamic hazard rate**: at each pump *k* the
balloon bursts with probability *k / N*, which moves the EV-optimal stopping
point from the classic N/2 down to a psychologically attainable ≈ √N. The
classic uniform (Lejuez) BART and nine other hazard models are available as
configuration choices, so traditional baselines and replications run on the
same instrument.

Developed for a research program at Middle East Technical University (METU).

---

## For researchers: install and run a study

1. **Download** the Windows installer from the
   [latest release](https://github.com/aslmylmz/open-bart/releases/latest).
   It installs per-user (no admin rights) and works fully offline.
   The app is currently unsigned — see
   [docs/standalone/SMARTSCREEN.md](docs/standalone/SMARTSCREEN.md) for the
   one-time SmartScreen bypass.
2. **Design your study** in Study Setup: balloon colors, capacities (*N*),
   trials, reward per pump, language (English/Turkish), and a hazard family
   per color — with a live EV-curve preview showing the optimum as you edit.
   You can also configure experimental **conditions**, a real-world **currency**
   and **payout conversion rate**, and automated **QC thresholds**.
   Save/load the design as `study.json`.
3. **Run participants**: Consent → ID → Gameplay → Debrief. A passcode-gated
   **in-app kiosk lock** (`exit_passcode`) secures the session: it forces
   fullscreen, stays on top, and swallows Escape/F11 so participants cannot
   exit prematurely (when no passcode is set, F11 is a plain fullscreen toggle).
   A **reproducible seed** ensures each participant's random sequence is
   fixed by `(seed, id)`. RAs can use **Test Run** mode (with a persistent banner
   and no-recording debrief) to practice without polluting the data folder.
   Participants see a thank-you screen, never their clinical metrics.
4. **Collect your data** from the configured output directory:
   - `[CandidateID]_[Timestamp]_events.jsonl` — raw pump-level telemetry,
   - `[CandidateID]_[Timestamp]_metrics.json` — the full scored output,
   - a config snapshot of the exact study that produced the session,
   - `[StudyTitle]_results.csv` — the **Master CSV**, one flat row appended
     per session for statistical software; no manual merging.

The step-by-step guide is
[docs/standalone/quickstart.md](docs/standalone/quickstart.md) (also on
[Read the Docs](https://open-bart.readthedocs.io)). Nothing leaves the
machine: the scoring engine runs as a loopback-only local process and the app
makes **zero network requests**.

macOS/Linux are development platforms; build from source with
`npm run tauri dev` in [app/](app/) (see the docs for prerequisites).

---

## The science: a hazard structure worth configuring

The classic BART draws one burst point uniformly from [1, N]; the EV-optimal
strategy (N/2 pumps) sits so far above typical behavior that pump count and
earnings are nearly collinear — the task indexes exposure, not calibration.
The dynamic-hazard model replaces it with sequential per-pump risk:

```
P(burst at pump k) = k / N
```

The expected value of stopping at *s* is `EV(s) = s × ∏(k=1..s)(1 − k/N)`,
whose optimum is ≈ √N — a reachable target, so calibrated and indiscriminate
strategies separate.

### The default study

Three colors, 10 balloons each, $0.25 per banked pump (all configurable):

| Color  | Max Pumps (N) | Risk Tier | EV-Optimal Stop (s*) | Peak EV (reward units) | P(survive s*) |
|--------|:-------------:|-----------|:--------------------:|:----------------------:|:-------------:|
| Purple | 128           | Low       | 11                   | 6.46                   | 0.588         |
| Teal   | 32            | Medium    | 5                    | 3.04                   | 0.608         |
| Orange | 8             | High      | 2                    | 1.31                   | 0.656         |

Neutral colors avoid learned danger associations (e.g., red).

### The hazard-family library

Every color profile selects one of 11 parameterized hazard families, grounded
in survival analysis: **dynamic** (linear, the flagship), **constant**
(Bernoulli), **lejuez** (classic uniform), **rayleigh**, **exponential**,
**weibull**, **gompertz**, **logistic**, **lognormal**, **step**, and a
validated **tabular** escape hatch for arbitrary hazard vectors. Parameters
only — no free-form code — so every configuration is validated before it runs.

Because arbitrary hazards break the closed-form √N result, the engine computes
each configuration's optimum **numerically** from the survival curve, and the
optima are **verified by independent Monte Carlo simulation**:

```bash
python -m scoring.verification   # per-family PASS table, seeded simulation
```

---

## The scoring engine as a Python library

The engine ([scoring/bart.py](scoring/bart.py)) turns raw event telemetry into
40+ metrics: EV-referenced calibration, explosion penalty (reported separately),
three learning estimators, within/between-balloon consistency, per-color
breakdowns, and a narrative behavioral profile. All behavioral-intention
metrics use **collected (non-exploded) balloons only** to avoid RNG-truncation
bias. Core dependencies: `numpy`, `pydantic` (the engine is scipy-free).

```bash
pip install "open-bart @ git+https://github.com/aslmylmz/open-bart"
# or, from a clone:  pip install -e .
```

```python
from scoring.schemas import GameEvent, EventPayload
from scoring.bart import score_bart

events = [
    GameEvent(timestamp=100, type="pump", payload=EventPayload(color="purple")),
    GameEvent(timestamp=300, type="pump", payload=EventPayload(color="purple")),
    GameEvent(timestamp=500, type="collect", payload=EventPayload(color="purple")),
    # ... more balloons
]

metrics = score_bart(events)                  # default 128/32/8 linear study
print(f"EV Ratio Score: {metrics.ev_ratio_score:.1f}")
print(f"Risk Style: {metrics.behavioral_profile.get('risk_style')}")
```

Pass a `TaskConfig` (`score_bart(events, config=...)`) to score against any
study design — the same object the desktop app saves as `study.json`.

### Key metrics

| Metric | Range | Description |
|--------|-------|-------------|
| `ev_ratio_score` | 0–100 | EV(participant) / EV(optimal) × 100, EV-weighted across colors |
| `risk_calibration_score` | 0–100 | Same as ev_ratio_score (explosion penalty reported separately) |
| `explosion_penalty` | 0–1 | Excess explosion rate vs expected at EV-optimal play |
| `rng_normalized_pumps` | ≥0 | Mean pumps as ratio of EV-optimal stop (1.0 = optimal) |
| `half_split_learning_rate` | −1 to 1 | First-half vs second-half improvement |
| `tercile_learning_rate` | −1 to 1 | First-third vs last-third (captures late learners) |
| `post_explosion_sensitivity` | ≈−2 to 2 | Pump change after same-color explosion (positive = adaptive) |
| `ev_efficiency_uniformity` | 0–1 | 1 − CV(per-color EV efficiencies) |
| `adaptive_strategy_score` | 0–100 | Composite: calibration, learning, uniformity, earnings |
| `behavioral_profile` | dict | Narrative risk-style classification with dominant traits |

A validation pipeline flags incomplete, too-fast, non-monotonic, automated,
and OS-key-repeat sessions before scoring. The full metric definitions and
validation rules are in the
[technical documentation](https://open-bart.readthedocs.io).

---

## Repository structure

```
open-bart/
├── scoring/                        Python scoring engine (installable package)
│   ├── bart.py                     Metrics + behavioral profile
│   ├── config/                     TaskConfig, 11 hazard families, numeric optima
│   ├── verification.py             Monte Carlo verification of the optima
│   └── schemas/                    Pydantic models (GameEvent, BARTMetrics, …)
├── app/                            Standalone desktop instrument
│   ├── src/                        React/Vite UI (Study Setup + Run mode)
│   ├── src-tauri/                  Tauri v2 shell (offline CSP, kiosk, dialogs)
│   ├── sidecar/                    FastAPI scoring sidecar (frozen via PyInstaller)
│   └── e2e/                        End-to-end verification scripts
├── scripts/
│   ├── monte_carlo_ev.py           Default-study EV figures + earnings simulation
│   ├── plot_hazard_families.py     EV curves across all 11 families (MC overlay)
│   └── generate_synthetic.py       Synthetic participant datasets
├── docs/                           Sphinx documentation (Read the Docs)
├── docs/standalone/                Researcher quickstart, SmartScreen, Windows verify
├── paper/                          JOSS paper draft
├── tests/                          pytest suites (engine, config, sidecar, verification)
└── pyproject.toml                  Package metadata + extras ([scripts], [sidecar], …)
```

---

## Documentation

Full technical documentation — installation, the mathematical model, metric
definitions, validation rules, and an autogenerated API reference — lives in
[docs/](docs/) and builds on [Read the Docs](https://open-bart.readthedocs.io):

```bash
pip install -r docs/requirements.txt
sphinx-build -b html docs docs/_build/html
```

The Journal of Open Source Software paper draft is in [paper/](paper/).

---

## Scripts

Verification and data tooling (needs the extras: `pip install -e ".[scripts]"`):

```bash
python -m scoring.verification          # Monte Carlo PASS table, all 11 families
python scripts/plot_hazard_families.py  # EV curves across the family library
python scripts/monte_carlo_ev.py        # default-study figures (EV, earnings, fan)
python scripts/generate_synthetic.py --n 60 --seed 42
```

---

## References

- Lejuez, C. W., Read, J. P., Kahler, C. W., Richards, J. B., Ramsey, S. E.,
  Stuart, G. L., Strong, D. R., & Brown, R. A. (2002). Evaluation of a
  behavioral measure of risk taking: The Balloon Analogue Risk Task (BART).
  *Journal of Experimental Psychology: Applied, 8*(2), 75–84.
  <https://doi.org/10.1037/1076-898X.8.2.75>
- Pleskac, T. J. (2008). Decision making and learning while taking sequential
  risks. *Journal of Experimental Psychology: Learning, Memory, and Cognition,
  34*(1), 167–185. <https://doi.org/10.1037/0278-7393.34.1.167>
- Wallsten, T. S., Pleskac, T. J., & Lejuez, C. W. (2005). Modeling behavior in a
  clinically diagnostic sequential risk-taking task. *Psychological Review,
  112*(4), 862–880. <https://doi.org/10.1037/0033-295X.112.4.862>
- Di Plinio, S., Pettorruso, M., & Ebisch, S. J. H. (2022). Appropriately tuning
  stochastic-psychometric properties of the Balloon Analog Risk Task. *Frontiers
  in Psychology, 13*, 881179. <https://doi.org/10.3389/fpsyg.2022.881179>
- Frey, R., Pedroni, A., Mata, R., Rieskamp, J., & Hertwig, R. (2017). Risk
  preference shares the psychometric structure of major psychological traits.
  *Science Advances, 3*(10), e1701381. <https://doi.org/10.1126/sciadv.1701381>
- Pedroni, A., Frey, R., Bruhin, A., Dutilh, G., Hertwig, R., & Rieskamp, J.
  (2017). The risk elicitation puzzle. *Nature Human Behaviour, 1*(11), 803–809.
  <https://doi.org/10.1038/s41562-017-0219-x>
- Weber, E. U., Blais, A.-R., & Betz, N. E. (2002). A domain-specific
  risk-attitude scale: Measuring risk perceptions and risk behaviors. *Journal
  of Behavioral Decision Making, 15*(4), 263–290.
  <https://doi.org/10.1002/bdm.414>
- Blais, A.-R., & Weber, E. U. (2006). A domain-specific risk-taking (DOSPERT)
  scale for adult populations. *Judgment and Decision Making, 1*(1), 33–47.
- Harris, C. R., et al. (2020). Array programming with NumPy. *Nature, 585*,
  357–362. <https://doi.org/10.1038/s41586-020-2649-2>

## Community

Contributions, bug reports, and feature requests are welcome! See
[CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute, where to
get support, and how to report issues.

This project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Citation

If you use this instrument in your research, please cite (see
[CITATION.cff](CITATION.cff)):

```bibtex
@software{yilmaz2026bart,
  author    = {Y{\i}lmaz, Ahmet Selim},
  title     = {Dynamic Hazard Rate BART: A Configurable Offline Desktop
               Instrument for the Balloon Analogue Risk Task},
  year      = {2026},
  version   = {1.0.0},
  doi       = {10.5281/zenodo.20592164},
  url       = {https://github.com/aslmylmz/open-bart}
}
```
