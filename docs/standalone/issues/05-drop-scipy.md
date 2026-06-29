# 05 — Drop scipy from the scoring engine (de-risk freezing)

**Phase 1 · SPEC §3, §18 · depends on: Phase 0**

## Context

The #1 project risk (SPEC §18) is **PyInstaller bundling numpy+scipy on Windows**.
SPEC §3 says to drop scipy from the sidecar if feasible. scipy is used in only three
spots in `scoring`, all replaceable, so we make the whole `scoring` package scipy-free.
This shrinks the frozen sidecar binary and removes the riskiest native dependency
before any freezing work begins.

## Uses to replace (numeric parity required)

- [ ] `stats.linregress` — [bart.py:241](../../../scoring/bart.py#L241). Only `slope`
  and `r_value` are consumed (for `slope * r²`). Replace with numpy: `slope =
  Sxy/Sxx`, `r = Sxy/√(Sxx·Syy)` clamped to [-1, 1] (r = 0 when `Syy == 0`, matching
  scipy). The caller already guards `np.std(x) > 0`.
- [ ] `stats.pearsonr` — [bart.py:516](../../../scoring/bart.py#L516). Only `r` is
  consumed. Replace with `np.corrcoef(x, y)[0, 1]`. Callers already guard `len ≥ 3`
  and nonzero std.
- [ ] `stats.lognorm` — [hazards.py:125](../../../scoring/config/hazards.py#L125).
  Reimplement `LognormalHazard.hazard_vector` with `math`: `sf(k) =
  ½·erfc((ln k − μ)/(σ√2))`, `pdf(k) = exp(−½z²)/(k·σ·√(2π))` with `z = (ln k − μ)/σ`.
  Remove the local `from scipy import stats`.

## Scope

- [ ] Remove `from scipy import stats` from [bart.py](../../../scoring/bart.py).
- [ ] In [pyproject.toml](../../../pyproject.toml): drop `scipy` from core
  `dependencies`; add it to the `scripts` extra (`scripts/monte_carlo_ev.py` still
  uses `scipy.interpolate.PchipInterpolator`).

## Acceptance

- All **54** existing tests pass; `pytest` emits **0** warnings.
- `python -c "import scoring.bart, scoring.config"` works in an env **without** scipy.
- The lognormal hazard's numeric optimum is unchanged (parity with scipy to fp).
- Default linear config still yields optima `11/5/2`.
