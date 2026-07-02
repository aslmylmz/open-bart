# Task Design

```{admonition} The default among eleven
:class: note

This page derives the **dynamic-hazard model** — the instrument's flagship
paradigm and its default study configuration ($11/5/2$ optima, $\sqrt{N}$
approximation). The instrument can equally run the classic uniform model and
nine other hazard structures; see the
[hazard-family reference](hazard_families.md).
```

## The problem with the standard BART

In the classic BART, a balloon's burst point is drawn once from a uniform
distribution over its capacity $N$ (typically $N = 128$). This gives a constant
hazard rate and an expected-value optimum at $N/2 \approx 64$ pumps — a target so
high that essentially no participant reaches it. Because almost everyone stops
well short of the optimum, the number of pumps and the money earned become
nearly collinear (a correlation of about 0.93 in large cohorts), and the task
degrades into a one-dimensional measure of raw risk exposure rather than
calibrated risk-taking.

## The dynamic-hazard model

This implementation replaces the single uniform draw with a sequence of
independent trials whose per-pump hazard increases linearly. At pump
attempt $k$,

$$P(\text{explode at pump } k) = \frac{k}{N},$$

where $N$ is the maximum pump capacity for the balloon's color. The probability
of surviving $s$ successive pumps is the product of the per-pump survival
probabilities:

$$P(\text{survive } s) = \prod_{k=1}^{s} \left(1 - \frac{k}{N}\right).$$

By convention this returns $1.0$ for $s \le 0$ and is floored at $0.0$ once the
product reaches zero, which caps the distribution at $N$.

With a reward of one unit per pump, the expected value of intending to stop at
$s$ is

$$\mathrm{EV}(s) = s \cdot \prod_{k=1}^{s}\left(1 - \frac{k}{N}\right).$$

This is implemented exactly in {py:func}`scoring.bart._compute_ev`.

## Why the optimum is $\sqrt{N}$

Taking the logarithm of the survival product and keeping the leading term,

$$\ln P(\text{survive } s) \approx -\sum_{k=1}^{s}\frac{k}{N} \approx -\frac{s^2}{2N},$$

so survival is approximately Gaussian in $s$, $P(\text{survive } s) \approx
\exp(-s^2 / 2N)$, and

$$\mathrm{EV}(s) \approx s \cdot \exp\!\left(-\frac{s^2}{2N}\right).$$

Differentiating and setting the result to zero yields the closed-form optimum

$$s^* = \sqrt{N}.$$

This is the central design property: EV-optimal play is **psychologically
attainable** (roughly 11, 5, and 2 pumps for the three colors) without the
fatigue of dozens of pumps, so the task can separate overly conservative,
optimal, and reckless participants.

## Discrete optima

The continuous approximation omits higher-order terms that make survival decay
slightly faster, so the realized integer optima are the floor of $\sqrt{N}$
rather than its rounded value. {py:func}`scoring.bart._compute_ev_optimal`
maximizes the exact discrete $\mathrm{EV}(s)$ and returns:

| Color  | $N$ | $\sqrt{N}$ | Discrete $s^*$ | $\mathrm{EV}(s^*)$ | $P(\text{survive } s^*)$ |
|--------|:---:|:----------:|:--------------:|:------------------:|:------------------------:|
| Purple | 128 | 11.31      | **11**         | 6.463              | 0.588                    |
| Teal   | 32  | 5.66       | **5**          | 3.038              | 0.608                    |
| Orange | 8   | 2.83       | **2**          | 1.313              | 0.656                    |

```{admonition} Two scoring paths, one set of optima
:class: note

The primary calibration metrics (`ev_ratio_score`, `risk_calibration_score`,
`rng_normalized_pumps`) reference the EV-optima computed dynamically by
{py:func}`~scoring.bart._compute_ev_optimal` (11 / 5 / 2). The diagnostic
`risk_adjustment_score`, produced by
{py:func}`~scoring.bart._calculate_risk_adjustment_score`, applies a simpler
*linear* distance-to-optimum scoring referenced to the same 11 / 5 / 2 stops.
The two paths therefore agree on the optimal targets and differ only in how
distance from them is penalized (EV-curve vs. linear).
```

## Monte Carlo verification

The analytic optima are independently confirmed by simulation in
[`scripts/monte_carlo_ev.py`](scripts.md): for each candidate stopping
threshold on each color, 100,000 sequential sessions are simulated,
the realized payoffs are averaged, and the maximizing threshold is recorded. The
simulation reproduces the integer optima 11 / 5 / 2 and confirms the $\sqrt{N}$
approximation as an accurate description of the continuous landscape.

## The three-color profiles

Three balloon colors are presented in an unpredictable order across a 30-trial
session (10 balloons per color). The differentiated hazard schedules let the
engine measure *calibration to the risk level* rather than gross risk-taking
alone, and they penalize participants who apply a single, invariant strategy
across heterogeneous conditions.

```{list-table}
:header-rows: 1

* - Color
  - Capacity $N$
  - Risk tier
  - $s^*$
  - What it probes
* - **Purple**
  - 128
  - Low
  - 11
  - Patience, prolonged engagement, willingness to exploit a forgiving hazard.
* - **Teal**
  - 32
  - Medium
  - 5
  - The baseline benchmark linking the two extremes.
* - **Orange**
  - 8
  - High
  - 2
  - Acute impulse control and sensitivity to rapid hazard escalation.
```

The color profiles are defined once in
{py:data}`scoring.bart.COLOR_PROFILES` and shared throughout the engine.

## Reward structure

Each pump on a *collected* balloon pays **\$0.25**; a burst forfeits the entire
balloon. Because overshooting the optimum is punished endogenously through
forfeited earnings — rather than through an arbitrary programmatic cap — the
`money_collected` metric becomes an indicator of EV calibration and payoff
efficiency instead of a redundant proxy for raw exposure.
