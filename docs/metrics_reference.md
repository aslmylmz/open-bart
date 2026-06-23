# Metrics Reference

This is the exhaustive list of fields on the
{py:class}`~scoring.schemas.BARTMetrics` object returned by
{py:func}`~scoring.bart.score_bart`. Ranges are the engine's documented output
ranges; conceptual explanations live in [The scoring engine](scoring_engine.md).

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
  - `money_collected` ÷ simulated median optimal earnings (27.25).
* - `patience_index_normalized`
  - 0–1
  - Purple (low-risk) EV efficiency: distinguishes patience from reckless over-pumping.
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
  - $R^2$-weighted regression slope of pumps on trial number, sign-adjusted per profile (teal excluded).
* - `half_split_learning_rate`
  - −1…1
  - First-half vs. second-half mean-pump change per color. Robust at low trial counts.
* - `tercile_learning_rate`
  - −1…1
  - First-third vs. last-third change, dropping the middle third.
* - `color_discrimination_trajectory`
  - ≈−1…1 / None
  - Change in purple-minus-orange separation from first to last third, normalized by the ~9-pump optimal spread.
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
  - **Deprecated** (Cohen's *d* purple-vs-orange). Kept for backward compatibility; use `ev_efficiency_uniformity`.
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
  - Mean pumps on low-risk (purple) balloons (raw, behavioral).
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

```{list-table}
:header-rows: 1
:widths: 32 14 54

* - Field
  - Range
  - Description
* - `adaptive_strategy_score`
  - 0–100
  - Weighted blend: calibration 35%, learning 25%, uniformity 25%, money 15%.
* - `flat_strategy_detected`
  - bool
  - True if pumping is undifferentiated across colors (active learners exempted).
* - `behavioral_profile`
  - dict
  - `risk_style`, `description`, `dominant_traits` — see [Behavioral profiles](scoring_engine.md#behavioral-profiles).
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
  - `purple` / `teal` / `orange`.
* - `risk_profile`
  - str
  - `low` / `medium` / `high`.
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
