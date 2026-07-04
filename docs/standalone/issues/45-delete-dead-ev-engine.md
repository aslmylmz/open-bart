# 45 — Delete the dead family-blind EV engine in the scoring engine

**Refactor · depends on: none**

Status: done

## Context

`scoring/bart.py` carries three private EV helpers — `_compute_ev`,
`_compute_ev_optimal`, `_compute_survival_probability` — that hard-code the
dynamic-hazard `k/N` model (P(burst at pump k) = k/N). They predate
`scoring/config/curve.py`'s `balloon_curve`, which derives survival / EV / the
numeric optimum from *any* hazard family's vector. `score_bart` reads
`config.curves` (i.e. `balloon_curve`) exclusively; the three helpers are called
by **nothing in production** — only by tests, which import them past the
engine's public surface. They are a family-blind duplicate of `curve.py`:
correct for the dynamic family, latent traps for the other ten. Deleting them
concentrates EV / survival math in one owner and lets the tests assert against
the real production path. While here, declare the engine's public interface,
which is currently discovered by convention (`scoring/__init__.py` exports only
`__version__`; `bart.py` has no `__all__`).

Grill decisions: scalpel scope (these three functions only); repoint the
reusable math tests rather than delete them; retire the completed migration
test outright.

## Scope

- [ ] Delete `_compute_ev`, `_compute_ev_optimal`,
      `_compute_survival_probability` and their `EV Computation (Sequential
      Model)` section header from `scoring/bart.py`. Leave `COLOR_PROFILES`,
      `MIN_COLLECTED_FALLBACK`, and `_DEFAULT_CURVES` untouched — all are live.
- [ ] Repoint the four dynamic-model math tests in `tests/test_scoring.py` onto
      `balloon_curve(DynamicHazard().hazard_vector(n), reward_per_pump=1.0)`,
      keeping identical golden expectations (`reward_per_pump=1.0` preserves the
      6.46 / 3.04 / 1.31 peak-EV values): discrete optima 11/5/2, peak EV,
      survival monotonicity, and s\* = ⌊√N⌋. Drop the now-unused imports of the
      three deleted functions.
- [ ] Delete `test_ev_zero_outside_domain` (asserts only the deleted function's
      internal domain guard) and `test_linear_curve_agrees_with_existing_engine`
      in `tests/test_config.py` — a completed migration test that existed to
      prove `curve.py` reproduced the old engine; moot once the old engine is
      gone. Remove the orphaned `from scoring.bart import _compute_ev_optimal`.
- [ ] Add `__all__ = ["score_bart", "trial_table", "validate_bart_session"]` to
      `scoring/bart.py`.

## Acceptance

- No production path changes: `score_bart` / `BARTMetrics` output is unchanged,
  so the frozen-sidecar parity test needs **no re-freeze**.
- The dynamic paradigm's core facts (optima 11/5/2, peak EV, s\* ≈ √N) remain
  asserted — now through `balloon_curve`, the production path.
- `python -m pytest -q` green (case count drops by the deleted tests; expected).
- A repo-wide search finds no remaining reference to the three deleted
  functions.

## Comments

**2026-07-03 — implemented (TDD; math tests repointed onto the production
path).** Deleted `_compute_ev` / `_compute_ev_optimal` /
`_compute_survival_probability` and the `EV Computation (Sequential Model)`
section header from `scoring/bart.py` — they were unreferenced in production
(`score_bart` reads `config.curves` / `balloon_curve`), a family-blind `k/N`
duplicate of `scoring/config/curve.py`. Repointed the four dynamic-model math
tests in `tests/test_scoring.py` onto
`balloon_curve(DynamicHazard().hazard_vector(n), reward_per_pump=1.0)` with the
same goldens (optima 11/5/2, peak EV 6.46/3.04/1.31, survival monotonicity,
s\* = ⌊√N⌋), so they now assert through the real interface. Dropped
`test_ev_zero_outside_domain` (tested only the deleted function's own domain
guard) and the completed migration test
`test_linear_curve_agrees_with_existing_engine`; removed the orphaned
`_compute_ev_optimal` import from `tests/test_config.py`. Added
`__all__ = ["score_bart", "trial_table", "validate_bart_session"]` to
`bart.py`. `COLOR_PROFILES` / `MIN_COLLECTED_FALLBACK` / `_DEFAULT_CURVES` kept
(all live). No `score_bart` / `BARTMetrics` output change → **no re-freeze**
(the frozen-sidecar parity test passed in the run). Gates: `pytest` **160** ✅
(−7 deleted cases from 167). Python-only change; webview gates unaffected.
