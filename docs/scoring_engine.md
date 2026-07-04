# The Scoring Engine

The scoring engine ([`scoring/bart.py`](api.rst)) turns a raw event log into a
{py:class}`~scoring.schemas.BARTMetrics` object. This page explains *how* the
headline metrics are computed; for the exhaustive field-by-field list see the
[Metrics Reference](metrics_reference.md).

## Pipeline overview

{py:func}`~scoring.bart.score_bart` runs the following stages:

1. **Validate** the session ({py:func}`~scoring.bart.validate_bart_session`) and
   record `session_valid` / `session_warnings`. See [Validation](validation.md).
2. **Segment** the flat event list into per-balloon event groups
   ({py:func}`~scoring.bart._segment_balloons`). A balloon ends at its `collect`
   or `explode` event.
3. **Flag auto-repeat balloons** ({py:func}`~scoring.bart._is_autorepeat_balloon`)
   — runs of pumps at OS key-repeat speed (median inter-pump interval < 80 ms)
   are excluded from behavioral-intention metrics.
4. **Aggregate** per-color pump counts, explosions, collections, latencies, and
   money.
5. **Compute** the calibration, learning, consistency, and composite metrics.
6. **Classify** the session into a narrative behavioral profile
   ({py:func}`~scoring.bart._generate_behavioral_profile`).

## The censoring correction (collected-only metrics)

The single most important methodological choice in the engine is that all
**behavioral-intention** metrics are computed from **collected (non-exploded)
balloons only**.

On an exploded balloon the recorded pump count is the point at which the random
number generator ended the trial — *not* the participant's intended stopping
point. Including these right-censored values would bias intention metrics
sharply downward. The engine therefore prefers collected balloons and only falls
back to all balloons when a color has fewer than
{py:data}`~scoring.bart.MIN_COLLECTED_FALLBACK` (2) collected trials, recording
an `RNG fallback` warning when it does
({py:func}`~scoring.bart._prefer_collected`).

Two fields deliberately keep the *uncensored* view for contrast:
`avg_pumps_all_balloons` (mean over every balloon) and `explosion_rate` (gross
burst fraction).

## Calibration metrics (the sequential EV core)

### EV ratio score

`ev_ratio_score` ({py:func}`~scoring.bart._compute_ev_ratio_score`) is the
engine's primary calibration measure. For each color it computes the
participant's expected value at their mean collected stop (linearly interpolated
between the two bracketing integer pumps), divides by the optimal
$\mathrm{EV}(s^*)$, and clamps to 1.0:

$$e_c = \min\!\left(1,\ \frac{\mathrm{EV}(\bar p_c)}{\mathrm{EV}(s^*_c)}\right).$$

The overall score weights each color by its reward potential $\mathrm{EV}(s^*_c)$:

$$\mathrm{EVRatio} = 100 \cdot \frac{\sum_c e_c\, \mathrm{EV}(s^*_c)}{\sum_c \mathrm{EV}(s^*_c)}.$$

Because $\mathrm{EV}(s^*)$ is 6.46 / 3.04 / 1.31 for purple / teal / orange, the
weights are approximately **60% / 28% / 12%**. A value of 100 means perfectly
EV-optimal play across all hazard levels. `risk_calibration_score` is the same
quantity, exposed under a second name; the explosion penalty is kept separate so
calibration and over-pumping are not conflated.

### Explosion penalty

`explosion_penalty` ({py:func}`~scoring.bart._compute_explosion_penalty`) is the
mean across colors of the *excess* burst rate beyond what EV-optimal play would
produce:

$$\text{excess}_c = \max\!\left(0,\ \text{observed rate}_c - \bigl(1 - P(\text{survive } s^*_c)\bigr)\right).$$

The expected-at-optimal rates are about 0.41 / 0.39 / 0.34. A penalty of 0 means
no excess explosions; higher values flag over-pumping.

### RNG-normalized pumps

`rng_normalized_pumps` expresses each color's mean collected stop as a fraction
of its EV-optimal stop, averaged across colors:

$$\mathrm{RNGNorm} = \frac{1}{|C|}\sum_{c \in C}\frac{\bar p_c}{s^*_c}.$$

`1.0` is exactly optimal; below 1 is conservative, above 1 is over-pumping.

### EV-efficiency uniformity

`ev_efficiency_uniformity` ({py:func}`~scoring.bart._compute_ev_efficiency_uniformity`)
is `1 - CV` of the per-color EV efficiencies — a measure of how *evenly* a
participant performs across hazard levels (high = consistent across colors, not
necessarily high-scoring). A color with too few collected balloons contributes a
zero efficiency. Returns `None` if fewer than two colors have usable data.

### Money efficiency

`money_collected` is simply $0.25 \times$ banked pumps. `money_efficiency`
divides it by the **simulated median** earnings under optimal play (27.25),
clamped to `[0, 2]`. The median — rather than the analytic mean EV — is used
because roughly half of optimally played sessions earn below the mean EV, so the
median is the fairer reference point.

## Learning and adaptation

Because colors at different risk levels reward different responses, the
*directional* meaning of a learning slope depends on a color's risk role. The
engine ranks the study's colors by EV-optimal stop (issue 56): the highest-risk
color rewards *fewer* pumps over time, the lowest-risk color rewards *more*, and
the mid-risk colors are excluded because their direction is ambiguous. This
resolves by risk role rather than by literal color name, so a renamed or
re-ordered study is scored the same. The engine offers three complementary
learning estimators, all computed on collected balloons:

- **`learning_rate`** ({py:func}`~scoring.bart._calculate_learning_rate`) —
  per-color linear regression of pumps on trial number, each slope weighted by
  its $R^2$ to suppress noise, sign-adjusted by risk role, then averaged.
- **`half_split_learning_rate`** — first-half vs. second-half mean pumps per
  color (more robust than regression at ~10 trials per color, since no single
  outlier dominates).
- **`tercile_learning_rate`** — first-third vs. last-third, dropping the noisy
  middle third to sharpen detection of late learners.

Two further adaptation metrics capture within-session dynamics:

- **`color_discrimination_trajectory`** — the change in safest-minus-riskiest
  pump separation from the first to the last third of the session, normalized by
  the EV-optimal spread between those two colors (~9 pumps for the default study).
- **`post_explosion_sensitivity`** — the mean pump reduction on the next
  same-color balloon following a burst, normalized by that color's $s^*$.
  Positive values indicate adaptive risk reduction.

## Consistency and timing

{py:func}`~scoring.bart._calculate_consistency_breakdown` decomposes response
consistency into:

- **`within_balloon_consistency`** — mean coefficient of variation (CV) of
  inter-pump latencies *inside* a single balloon (immune to between-balloon
  strategy shifts); and
- **`between_balloon_consistency`** — CV of pump counts *across* balloons (high =
  erratic strategy).

`impulsivity_index` is a latency index, $1 - \mathrm{clip}(\text{mean latency} /
800\text{ ms}, 0, 1)$ — higher means faster, more reflexive pumping. This follows
Lejuez et al. (2002), who identify pump latency as the primary BART correlate of
trait impulsivity.

## The composite score

`adaptive_strategy_score` (0–100) is a fixed-weight blend:

| Component   | Source                               | Weight |
|-------------|--------------------------------------|:------:|
| Calibration | `ev_ratio_score / 100`               | 0.35   |
| Learning    | `(half_split_learning_rate + 1) / 2` | 0.25   |
| Uniformity  | `ev_efficiency_uniformity`           | 0.25   |
| Money       | `min(1, money_efficiency)`           | 0.15   |

The learning term is rescaled from its $[-1, 1]$ range onto $[0, 1]$ before
weighting.

## Flat-strategy detection

`flat_strategy_detected` ({py:func}`~scoring.bart._detect_flat_strategy`) flags
participants who pump nearly identically across colors — forgoing
reward on safe balloons and over-exploding on risky ones. The detector exempts
participants who show genuine adaptation (positive tercile learning, color
discrimination growth, post-explosion sensitivity, or high between-balloon
variability) so that active explorers are not misclassified as flat.

## Behavioral profiles

Finally, {py:func}`~scoring.bart._generate_behavioral_profile` assigns a
narrative `risk_style` from the computed metrics, evaluated in priority order
(first match wins):

```{list-table}
:header-rows: 1
:widths: 30 70

* - Risk style
  - Triggered when…
* - **Undifferentiated Risk Approach**
  - `flat_strategy_detected` is true (overrides all others).
* - **Calibrated Risk Optimizer**
  - `risk_calibration_score ≥ 80`, `explosion_penalty < 0.25`, uniformity > 0.60.
* - **Selective Over-Optimizer**
  - Strong on the safest color (eff ≥ 0.70) but weak on the riskiest (eff < 0.30); low uniformity; penalty > 0.25.
* - **Persistent Risk Taker**
  - `rng_normalized_pumps ≥ 1.0` across the board with penalty > 0.20.
* - **Context-Insensitive Risk Taker**
  - Uniformity < 0.35, not selectively strong, penalty > 0.15.
* - **Loss-Averse Responder**
  - `rng_normalized_pumps < 0.60` with penalty < 0.16.
* - **Emerging Optimizer**
  - Selective strength, `risk_calibration_score ≥ 75`, `money_efficiency ≥ 0.60`.
* - **Adaptive Risk Learner**
  - Strong learning *and* discrimination growth across the session.
* - **Conservative Strategist**
  - `rng_normalized_pumps < 0.75` with penalty < 0.20.
* - **Balanced Explorer**
  - Catch-all when no other style matches.
```

The profile also includes a plain-language `description` and a list of
`dominant_traits` (e.g. *Highly Consistent*, *Improving Over Time*, *Impulsive on
High-Risk*, *Near-Optimal on Safe Balloons*).
