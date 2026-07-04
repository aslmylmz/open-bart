# Metrics Reference

This is the exhaustive list of fields on the
{py:class}`~scoring.schemas.BARTMetrics` object returned by
{py:func}`~scoring.bart.score_bart`. Ranges are the engine's documented output
ranges; conceptual explanations live in [The scoring engine](scoring_engine.md).

```{note}
**Color-name independence.** Every metric is now config-agnostic. The **EV-based
metrics** — `risk_calibration_score`, `ev_ratio_score`,
`ev_efficiency_uniformity`, `explosion_penalty`, `risk_adjustment_score`, and the
per-color breakdown — are computed from each color's precomputed survival/EV
curve, valid for any color names, counts, caps, and hazard families. The
**persona metrics** — the learning-rate family (`learning_rate`,
`half_split_learning_rate`, `tercile_learning_rate`), `color_discrimination_index`,
`color_discrimination_trajectory`, `patience_index`, `orange_avg_pumps`, and the
`risk_style` classifications — resolve behavior by **risk role** rather than by
literal color name: the study's colors are ranked by EV-optimal stop (safest =
highest optimum, riskiest = lowest), and the two-color contrasts run between that
safest and riskiest color, excluding the mid-risk ones. A renamed, re-counted, or
re-ordered study therefore has all of these metrics computed coherently, and the
`session_warnings` completeness/balance checks are judged against the study's own
colors and trial counts (issue 57). `orange_avg_pumps` keeps its legacy field name
but reports the study's highest-risk color. See ADR 0004
(`docs/adr/0004-persona-metrics-default-color-triad.md`; issue 56).
```

## Volume & outcome

```{list-table}
:header-rows: 1
:widths: 32 14 54

* - Field
  - Range
  - Description
* - `total_balloons`
  - int
  - Number of balloons in the session.
* - `total_pumps`
  - int
  - Total pump events across all balloons.
* - `total_explosions`
  - int
  - Balloons that burst.
* - `total_collections`
  - int
  - Balloons successfully banked.
* - `explosion_rate`
  - 0–1
  - Fraction of balloons that exploded (gross, uncensored).
* - `average_pumps_adjusted`
  - ≥0
  - Mean pumps per **non-exploded** balloon (adjusted BART score).
* - `avg_pumps_all_balloons`
  - ≥0
  - Mean pumps across **all** balloons, including exploded — not subject to censoring bias.
* - `money_collected`
  - ≥0
  - Total earned: banked pumps × \$0.25.
```

## Calibration (sequential EV)

```{list-table}
:header-rows: 1
:widths: 32 14 54

* - Field
  - Range
  - Description
* - `ev_ratio_score`
  - 0–100
  - EV(participant) / EV(optimal) × 100, EV-weighted across colors. Primary calibration measure.
* - `risk_calibration_score`
  - 0–100
  - Identical to `ev_ratio_score`; the explosion penalty is reported separately to avoid double-penalizing.
* - `explosion_penalty`
  - 0–1
  - Mean excess burst rate beyond the rate expected at EV-optimal play.
* - `rng_normalized_pumps`
  - ≥0
  - Mean collected stop ÷ EV-optimal stop, averaged across colors. 1.0 = optimal, <1 conservative, >1 over-pumping.
* - `ev_efficiency_uniformity`
  - 0–1 / None
  - `1 − CV` of per-color EV efficiencies (consistency across hazard levels). `None` if <2 colors have usable data.
* - `money_efficiency`
  - 0–2
  - `money_collected` ÷ the study's expected EV-optimal earnings (Σ trials × EV-optimal per color, config-derived; ≈27.03 for the default study).
* - `patience_index_normalized`
  - 0–1
  - Lowest-risk color's EV efficiency: distinguishes patience from reckless over-pumping.
* - `ev_optimal_stops`
  - dict
  - EV-optimal stop per color, plus per-color efficiency entries (`_purple_efficiency`, etc.).
```

## Learning & adaptation

```{list-table}
:header-rows: 1
:widths: 32 14 54

* - Field
  - Range
  - Description
* - `learning_rate`
  - −1…1
  - $R^2$-weighted regression slope of pumps on trial number, sign-adjusted by risk role (mid-risk colors excluded).
* - `half_split_learning_rate`
  - −1…1
  - First-half vs. second-half mean-pump change per color. Robust at low trial counts.
* - `tercile_learning_rate`
  - −1…1
  - First-third vs. last-third change, dropping the middle third.
* - `color_discrimination_trajectory`
  - ≈−1…1 / None
  - Change in safest-minus-riskiest separation from first to last third, normalized by the study's EV-optimal spread (`low_opt − high_opt`; 9 for the default study).
* - `post_explosion_sensitivity`
  - ≈−2…2 / None
  - Mean pump reduction on the next same-color balloon after a burst, normalized by $s^*$. Positive = adaptive.
* - `risk_adjustment_score`
  - 0–100
  - Linear distance-to-optimum alignment, referenced to the EV-optimal stops (11 / 5 / 2). Diagnostic only.
* - `risk_sensitivity`
  - −1…1
  - Pearson correlation between balloon capacity and pumps.
* - `color_discrimination_index`
  - 0–1 / None
  - **Deprecated** (Cohen's *d*, safest vs. riskiest color). Kept for backward compatibility; use `ev_efficiency_uniformity`.
```

## Behavioral indices

```{list-table}
:header-rows: 1
:widths: 32 14 54

* - Field
  - Range
  - Description
* - `impulsivity_index`
  - 0–1
  - $1 - \mathrm{clip}(\text{mean latency}/800\text{ ms})$. Higher = faster, more reflexive pumping.
* - `patience_index`
  - ≥0
  - Mean pumps on the lowest-risk color (raw, behavioral).
* - `within_balloon_consistency`
  - ≥0
  - Mean CV of inter-pump latencies *within* balloons.
* - `between_balloon_consistency`
  - ≥0
  - CV of pump counts *across* balloons (high = erratic strategy).
* - `response_consistency`
  - ≥0
  - CV of all inter-pump latencies (lower = more consistent).
* - `mean_latency_between_pumps`
  - ms
  - Mean inter-pump interval (intervals ≥ 2000 ms are dropped as off-task).
```

## Composite, profile & validity

```{note}
**Analysis-ready primitives vs. exploratory composites.** `adaptive_strategy_score`
and `behavioral_profile` (`risk_style`) are **unnormed heuristics**, not validated
psychometric constructs: the score is an arbitrarily fixed-weighted composite and
the risk style is a hand-tuned decision tree — neither has a norming sample or a
reliability estimate. Use the analysis-ready primitives as dependent variables —
`average_pumps_adjusted`, `explosion_rate`, `ev_ratio_score`, and the per-color
`{color}_ev_efficiency` — and treat these two composites as descriptive summaries
only, validating independently before reporting them. `color_discrimination_index`
is deprecated (see below); prefer `ev_efficiency_uniformity`.
```

```{list-table}
:header-rows: 1
:widths: 32 14 54

* - Field
  - Range
  - Description
* - `adaptive_strategy_score`
  - 0–100
  - **Exploratory** (unnormed composite). Weighted blend: calibration 35%, learning 25%, uniformity 25%, money 15%.
* - `flat_strategy_detected`
  - bool
  - True if pumping is undifferentiated across colors (active learners exempted).
* - `behavioral_profile`
  - dict
  - **Exploratory** (unnormed heuristic). `risk_style`, `description`, `dominant_traits` — see [Behavioral profiles](scoring_engine.md#behavioral-profiles).
* - `session_valid`
  - bool
  - True if the session passes all validity checks.
* - `session_warnings`
  - list[str]
  - Human-readable validation warnings (empty if fully valid).
* - `color_metrics`
  - list
  - Per-color breakdown; see below.
```

## Per-color metrics

Each entry of `color_metrics` is a {py:class}`~scoring.schemas.ColorMetrics`:

```{list-table}
:header-rows: 1
:widths: 32 14 54

* - Field
  - Range
  - Description
* - `color`
  - str
  - The study's color name (default `purple` / `teal` / `orange`).
* - `risk_profile`
  - str
  - `low` / `medium` / `high`, assigned by EV-optimal risk rank (safest = `low`).
* - `average_pumps`
  - ≥0
  - Mean pumps over **all** balloons of this color.
* - `behavioral_avg_pumps`
  - ≥0
  - Mean pumps over **collected** balloons (falls back to all if <2 collected).
* - `explosion_rate`
  - 0–1
  - Burst rate for this color.
* - `total_balloons`
  - int
  - Balloons of this color.
* - `collected_count`
  - int
  - Non-exploded balloons of this color.
* - `used_fallback`
  - bool
  - True if `behavioral_avg_pumps` fell back to all balloons.
* - `ev_efficiency`
  - 0–1 / None
  - EV(behavioral mean) / EV(optimal) for this color.
* - `ev_optimal_stop`
  - int / None
  - EV-optimal pump count for this color (11 / 5 / 2).
* - `excess_explosion_rate`
  - float / None
  - Observed minus expected-at-optimal burst rate. Positive = over-pumping.
```
