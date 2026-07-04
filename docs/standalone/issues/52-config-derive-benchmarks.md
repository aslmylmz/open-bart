# 52 — Config-derive the money/discrimination benchmarks

**Feature · depends on: —**

Status: done

## Context

Post-audit hardening (Quality Kaizen cycle 01, finding **F4**;
`docs/standalone/QUALITY-KAIZEN.md`). Two scoring benchmarks are hardcoded to
the default study:

- `_OPTIMAL_MEDIAN_EARNINGS = 27.25` — the divisor for `money_efficiency`. It
  assumes `reward_per_pump = 0.25` **and a complete 30-balloon session**. Change
  the reward, caps, or trial counts and it is wrong; even for the default study
  an *incomplete* session is scored against a full-session benchmark and comes
  out artificially deflated. `money_efficiency` feeds `adaptive_strategy_score`
  at 15% weight, so the error propagates.
- `optimal_spread = 9.0` — the purple−orange EV-optimal gap used to normalize
  the color-discrimination trajectory. Config-specific.

Both are already computable from `TaskConfig.curves` (per-color optima, survival,
and EV vectors are precomputed on construction), so the fix is to derive them
rather than assume them.

## Scope

- [ ] `money_efficiency` normalizes against a benchmark derived from the config
      (per-color optimal EV × trial counts, or a documented derivation), not a
      literal — or is explicitly gated to complete sessions of the config it is
      valid for, with the gating recorded in the metrics.
- [ ] The discrimination-trajectory normalizer is derived from the two relevant
      colors' EV-optimal spread in `curves`, not `9.0`.
- [ ] Any remaining unavoidable constant is documented at its definition with
      the assumption it encodes.

## Acceptance

- A config with a different reward / N / trial count yields a sensible
  `money_efficiency` (or a documented `None`/flag), verified by a test on a
  non-default config.
- The default study's values are unchanged within rounding on a fixture session.
- `pytest`, `vitest`, `tsc --noEmit`, `vite build` stay green.

## Comments

Source: 2026-07-04 research audit, register row F4. Touches `scoring/bart.py`
alongside issue 51 — coordinate to avoid overlapping edits; the two are
otherwise independent and can be worked in parallel.

**2026-07-04 — implemented (TDD).** Both hardcoded benchmarks are now
config-derived. `money_efficiency` divides by the study's expected EV-optimal
earnings (Σ `trials × optimal_ev` per color, straight off `TaskConfig.curves`)
instead of the literal `27.25`; `color_discrimination_trajectory` normalizes by
`curves["purple"].optimum − curves["orange"].optimum` (guarded for a missing
color / non-positive spread) instead of the literal `9.0`. Tests:
`money_efficiency` is now invariant to reward scaling (identical optimal play
scores the same at $0.25 and $1.00/pump — the old fixed total pinned the richer
study to the `[0, 2]` clip); the trajectory scales with a compressed optima
spread (`2/9` → `2/3`). **Intentional default-study shift:** the analytic
EV-optimal total is `27.034` vs the old Monte-Carlo estimate `27.25`, so a
default-study `money_efficiency` moves ~0.8% (a principled correction, not
silent — the two were always within noise; the "median" rationale barely held).
No published data depends on it (pre-1.0). The stale frozen sidecar was
re-frozen (PyInstaller 6.18.0) so `/score` parity holds; docs (schema +
metrics reference) updated. Closes kaizen row F4. Gates: pytest 165 ✅,
vitest 132 ✅, tsc ✅, vite build ✅.
