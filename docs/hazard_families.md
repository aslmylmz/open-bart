# Hazard-Family Reference

Every balloon color in a study selects one **hazard family** and its
parameters. A family defines the per-pump conditional hazard

$$h(k) = P(\text{burst at pump } k \mid \text{survived pumps } 1..k-1),
\qquad k = 1..N,$$

where $N$ is the color's `max_pumps` cap. From the hazard vector the engine
derives the survival curve $S(s) = \prod_{k=1}^{s}(1 - h(k))$ and the
expected value of stopping at $s$, $\mathrm{EV}(s) = r \cdot s \cdot S(s)$
(with $r$ the reward per pump). Hazards are clamped to $[0, 1]$; parameters
are validated by the configuration layer before a study can run.

Because arbitrary hazards have no closed-form optimum, the EV-optimal stop
$s^*$ is found **numerically** — a full scan of $\mathrm{EV}(s)$ over
$1 \le s \le N$, taking the smallest $s$ on ties. The reward $r$ scales the
EV curve uniformly and never moves $s^*$. For the default linear
(dynamic-hazard) study this reproduces the classic $11/5/2$ optima and the
$\sqrt{N}$ approximation.

```{figure} _static/hazard_families_ev.png
:alt: EV curves for all eleven hazard families with numeric optima marked and Monte Carlo estimates overlaid

Expected-value curves for a representative parameterization of each family
(unit reward). The dot marks the numeric optimum $s^*$; the overlaid points
are seeded Monte Carlo estimates. Regenerate with
`python scripts/plot_hazard_families.py`.
```

## Simulation-verified optima

The numeric optima are confirmed by independent Monte Carlo simulation —
balloons are burst directly from the hazard vector and the EV curve is
rebuilt empirically, sharing nothing with the analytic path but the hazards
themselves:

```bash
python -m scoring.verification
```

prints a per-family PASS table (100,000 simulated balloons per family,
seeded). The same check runs in the test suite (`tests/test_verification.py`),
so the claim cannot silently rot as families evolve.

## The families

### dynamic — linear hazard (the flagship)

$$h(k) = \frac{k}{N}$$

The paradigm the instrument is named for: hazard grows with every pump,
burst-time is approximately Rayleigh, and the optimum sits near $\sqrt{N}$ —
a reachable target that separates calibrated from indiscriminate play.
No parameters; the risk profile is set entirely by the cap $N$.

### constant — flat per-pump probability

$$h(k) = p$$

Burst-time is geometric; the EV-optimum is approximately $1/p$ (the
continuous optimum is $-1/\ln(1-p)$).

| Parameter | Constraint | Meaning |
|-----------|------------|---------|
| `p` | $0 < p < 1$ | per-pump burst probability |

### lejuez — classic uniform BART

$$h(k) = \frac{1}{N - k + 1}$$

The original Lejuez et al. (2002) model: the burst point is uniform on
$\{1..N\}$, survival is $(N - s)/N$, and the optimum sits at $N/2$. Use it to
run traditional baselines or replicate classic studies on the same
instrument. No parameters.

### rayleigh — linear hazard with an explicit scale

$$h(k) = \frac{k}{\sigma^2}$$

Equivalent to the dynamic family with an effective $N = \sigma^2$, decoupling
the hazard's slope from the color's cap; the optimum is approximately
$\sigma$.

| Parameter | Constraint | Meaning |
|-----------|------------|---------|
| `sigma` | $\sigma > 0$ | Rayleigh scale; optimum $\approx \sigma$ |

### exponential — memoryless burst-time

$$h(k) = 1 - e^{-\lambda}$$

A flat hazard expressed through a rate: burst-time is geometric and the
optimum is approximately $1/\lambda$.

| Parameter | Constraint | Meaning |
|-----------|------------|---------|
| `rate` | $\lambda > 0$ | hazard rate |

### weibull — tunable rising or falling hazard

$$h(k) = \frac{m}{N}\left(\frac{k}{N}\right)^{m-1}$$

The scale is tied to the cap $N$; the shape $m$ tunes the profile: $m < 1$
decreasing, $m = 1$ flat, $m = 2$ linearly rising, $m > 2$ accelerating.
Note the hazard magnitude is $O(1/N)$, so large caps produce gentle, flat EV
peaks.

| Parameter | Constraint | Meaning |
|-----------|------------|---------|
| `shape` | $m > 0$ | Weibull shape |

### gompertz — exponentially accelerating hazard

$$h(k) = a\,e^{bk}$$

Risk compounds sharply late in the balloon — a "cliff" that punishes
overshooting harder than the linear model.

| Parameter | Constraint | Meaning |
|-----------|------------|---------|
| `a` | $a > 0$ | baseline hazard scale |
| `b` | $b > 0$ | exponential growth rate |

### logistic — safe-then-ramp S-curve

$$h(k) = \frac{h_{\max}}{1 + e^{-r_s (k - k_0)}}$$

Hazard stays low through an initial safe zone, then ramps toward a ceiling —
useful for designs with an explicit "point of no return".

| Parameter | Constraint | Meaning |
|-----------|------------|---------|
| `h_max` | $0 < h_{\max} \le 1$ | asymptotic hazard ceiling |
| `midpoint` | $k_0 > 0$ | pump at which hazard is $h_{\max}/2$ |
| `steepness` | $r_s > 0$ | logistic slope |

### lognormal — rise-then-fall (non-monotone)

The hazard of a log-normal burst time, $h(k) = f(k)/S(k)$: it rises to a
mode and then *falls*, so surviving deep into a balloon genuinely signals
safety. Computed with the standard library (no scipy).

| Parameter | Constraint | Meaning |
|-----------|------------|---------|
| `mu` | — | log-scale location |
| `sigma` | $\sigma > 0$ | log-scale shape |

### step — piecewise-constant hazard

`levels[i]` applies on the segment delimited by ascending `breakpoints`
(segment 0 runs up to and including the first breakpoint). Encodes discrete
regime changes: calm, then dangerous.

| Parameter | Constraint | Meaning |
|-----------|------------|---------|
| `breakpoints` | ≥ 1 strictly ascending positive pump counts | segment boundaries |
| `levels` | ≥ 2 values in $[0, 1]$, `len(levels) == len(breakpoints) + 1` | hazard per segment |

### tabular — explicit hazard vector (the escape hatch)

`values[k-1]` $= h(k)$, given directly as data — no formula at all. The
vector's length must equal the color's cap $N$ exactly, and every value must
lie in $[0, 1]$. Use it to reproduce a hazard schedule from another study's
materials when no parametric family fits.

| Parameter | Constraint | Meaning |
|-----------|------------|---------|
| `values` | length $= N$, each in $[0, 1]$ | per-pump hazards |

## Choosing a family

- **Replicating the classic BART?** `lejuez`.
- **Want calibration sensitivity (the instrument's purpose)?** `dynamic`, or
  `rayleigh` when the hazard slope should not depend on the cap.
- **Simple stochastic baseline?** `constant` / `exponential`.
- **Late-risk designs?** `gompertz` (smooth) or `logistic` / `step`
  (thresholded).
- **A published hazard schedule?** `tabular`.

Study files (`study.json`) name a family and its parameters — never code —
and the configuration layer rejects invalid parameters with structured
errors before a session can start.
