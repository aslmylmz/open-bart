# 52 — Config-derive the money/discrimination benchmarks

**Feature · depends on: —**

Status: ready-for-agent

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
