# Dynamic Hazard Rate BART

**A Multi-Risk Balloon Analogue Risk Task with Sequential Bernoulli Explosion Model**

An open-source implementation of a modified BART (Balloon Analogue Risk Task) that replaces the classic uniform explosion threshold with a **dynamic hazard rate** — at each pump *k*, the balloon explodes with probability *k / N* (sequential Bernoulli trials with linearly increasing hazard). This creates a fundamentally different risk structure where the optimal stopping point is approximately √N rather than N/2.

The repository includes a complete **React game client**, a **Python scoring engine** with 40+ psychometric metrics, and tools for **Monte Carlo verification** of the theoretical EV-optimal stops.

Developed as part of a research study at Middle East Technical University (METU).

---

## Why Dynamic Hazard Rate?

The classic BART uses a uniform explosion point drawn from [1, N] — giving a constant hazard rate and a trivially optimal strategy of N/2. Our model uses:

```
P(explode at pump k) = k / N
```

This sequential Bernoulli model has key advantages for research:

1. **Increasing hazard** — risk grows with each pump, matching real-world risk accumulation
2. **Non-trivial optimal stopping** — the EV-optimal stop is lower than N/2 and varies non-linearly with N
3. **Multi-risk profiles** — three balloon colors with different N values test risk calibration across contexts

### Three-Color Risk Profiles

| Color  | Max Pumps (N) | Risk Tier | EV-Optimal Stop (s*) | Peak EV   | P(survive s*) |
|--------|:-------------:|-----------|:--------------------:|:---------:|:--------------:|
| Purple | 128           | Low       | 11                   | 6.46      | 0.623          |
| Teal   | 32            | Medium    | 5                    | 3.04      | 0.609          |
| Orange | 8             | High      | 2                    | 1.31      | 0.656          |

Neutral colors are used deliberately to avoid psychological bias (e.g., red = danger).

### EV-Optimal Derivation

The expected value of stopping after *s* pumps on a balloon with capacity *N* is:

```
EV(s, N) = s × ∏(k=1 to s) (1 - k/N)
```

The optimal stopping point s* maximizes this expression. A continuous approximation gives s* ≈ √N, but the exact discrete peaks are 11/5/2 for our three colors. The `scripts/monte_carlo_ev.py` script verifies these analytically-derived values through 100,000-session simulation.

---

## Repository Structure

```
metu-risk-persona/
├── scoring/
│   ├── bart.py                     Scoring engine (2000+ lines, 40+ metrics)
│   └── schemas/
│       ├── __init__.py             Pydantic data models (GameEvent, BARTMetrics, etc.)
│       └── game_events.py          BART event validators
├── games/
│   └── bart/
│       └── BartGame.tsx            React/Next.js game client (complete UI)
├── scripts/
│   ├── monte_carlo_ev.py           EV-curve plots + MC earnings simulation
│   └── generate_synthetic.py       Generate synthetic participant datasets
├── data/
│   └── synthetic/                  Synthetic data output directory
├── README.md
├── LICENSE                         MIT License
└── requirements.txt
```

---

## Scoring Engine

The scoring engine (`scoring/bart.py`) computes metrics from raw event logs. All behavioral-intention metrics use **collected (non-exploded) balloons only** to avoid RNG-truncation bias — on exploded balloons, the pump count is cut short by the random explosion point, not by participant choice.

### Key Metrics

| Metric | Range | Description |
|--------|-------|-------------|
| `ev_ratio_score` | 0–100 | EV(participant) / EV(optimal) × 100, EV-weighted across colors |
| `risk_calibration_score` | 0–100 | Same as ev_ratio_score (explosion penalty reported separately) |
| `explosion_penalty` | 0–1 | Excess explosion rate vs expected at EV-optimal play |
| `rng_normalized_pumps` | ≥0 | Mean pumps as ratio of EV-optimal stop (1.0 = optimal) |
| `impulsivity_index` | 0–1 | Latency-based: 1 - clamp(latency/800ms, 0, 1) |
| `half_split_learning_rate` | -1 to 1 | First-half vs second-half improvement |
| `tercile_learning_rate` | -1 to 1 | First-third vs last-third (captures late learners) |
| `color_discrimination_trajectory` | ≈-1 to 1 | Change in purple-vs-orange differentiation across session |
| `post_explosion_sensitivity` | ≈-2 to 2 | Pump change after same-color explosion (positive = adaptive) |
| `ev_efficiency_uniformity` | 0–1 | 1 - CV(per-color EV efficiencies) |
| `money_efficiency` | 0–2 | Money collected / MC-simulated median at optimal play |
| `adaptive_strategy_score` | 0–100 | Composite: calibration 35%, learning 25%, uniformity 25%, money 15% |
| `flat_strategy_detected` | bool | Undifferentiated pumping across all colors |
| `behavioral_profile` | dict | Narrative risk style classification with dominant traits |

### Quick Start

```python
from scoring.schemas import GameEvent, EventPayload
from scoring.bart import score_bart

# Build events from your data
events = [
    GameEvent(timestamp=100, type="pump", payload=EventPayload(color="purple")),
    GameEvent(timestamp=300, type="pump", payload=EventPayload(color="purple")),
    GameEvent(timestamp=500, type="collect", payload=EventPayload(color="purple")),
    # ... more balloons
]

metrics = score_bart(events)
print(f"EV Ratio Score: {metrics.ev_ratio_score:.1f}")
print(f"Risk Style: {metrics.behavioral_profile.get('risk_style')}")
```

### Session Validation

The engine validates sessions before scoring:
- Minimum balloon count (< 15 → invalid, 15–29 → warning)
- Color balance (each color should have ~10 balloons)
- Timestamp monotonicity
- Session speed (< 30s for 30 balloons → suspicious)
- Pump uniformity (near-zero std → possible automation)
- Auto-repeat detection (OS key-repeat at ~30–50ms intervals)

---

## Game Client

`games/bart/BartGame.tsx` is a complete React/Next.js component implementing the three-color BART with:
- Animated balloon inflation with color-coded risk tiers
- Real-time pump counter and reward display
- Sequential Bernoulli explosion model (P = k/N)
- Event logging with `performance.now()` timestamps
- Collect/explode animations and session summary

---

## Scripts

### Monte Carlo EV Verification

```bash
python scripts/monte_carlo_ev.py
```

Generates three figures verifying the EV-optimal derivation:
- **EV curves** — EV(s, N) for each color with optimal stops marked
- **Earnings histogram** — Distribution of session earnings at optimal play (100K sessions)
- **Trajectory fan plot** — Cumulative earnings paths showing variance structure

### Synthetic Data Generation

```bash
python scripts/generate_synthetic.py --n 60 --seed 42
```

Generates synthetic participant records with realistic BART metric distributions for testing and demonstration.

---

## Installation

```bash
pip install -r requirements.txt
```

Core dependencies: `numpy`, `scipy`, `pydantic`

---

## References

- Lejuez, C.W., Read, J.P., Kahler, C.W., et al. (2002). Evaluation of a behavioral measure of risk taking: The Balloon Analogue Risk Task (BART). *Journal of Experimental Psychology: Applied*, 8(2), 75–84.
- Pleskac, T.J. (2008). Decision making and learning while taking sequential risks. *Journal of Experimental Psychology: Learning, Memory, and Cognition*, 34(1), 167–185.
- Wallsten, T.S., Pleskac, T.J., & Lejuez, C.W. (2005). Modeling behavior in a clinically diagnostic sequential risk-taking task. *Psychological Review*, 112(4), 862–880.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Citation

If you use this implementation in your research, please cite:

```bibtex
@software{yilmaz2026bart,
  author    = {Y{\i}lmaz, Ahmet Selim},
  title     = {Dynamic Hazard Rate BART: A Multi-Risk Balloon Analogue Risk Task
               with Sequential Bernoulli Explosion Model},
  year      = {2026},
  url       = {https://github.com/aslmylmz/metu-risk-persona},
  note      = {Open-source software, MIT License}
}
```
