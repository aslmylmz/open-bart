# 57 — Generalize `validate_bart_session` off the default study shape

**Validity-limitation · depends on: none**

Status: done

## Context

Cycle-02 audit finding F8 (D5/D1). Issue 56 generalized the persona *metrics* onto
config risk-ordering, but the **validation layer is still hardwired to the default
purple/teal/orange 3×10 study**. `validate_bart_session` (`scoring/bart.py:231-249`):

- flags completeness against a hardcoded 30-balloon total (`< 15`, `< 30`, messages
  `"…/30 balloons played"`);
- loops `for color in ["purple", "teal", "orange"]` and checks each against a
  hardcoded `10` (`< 5`, `< 10`, messages `"…/10 played"`).

So a renamed study (e.g. crimson/azure/jade) gets three spurious
`"Too few purple balloons: 0/10 played"` warnings and **no** warning about its
actual colors being under-counted; a re-counted study (e.g. 20 trials/color) gets
the wrong `/10` and `/30` denominators. `validate_bart_session` currently takes
only `events` — the config (which knows the expected colors and per-color `trials`)
is not threaded in. This is the validation-layer sibling of F3/issue 56; ADR 0004
scoped it out of issue 56 deliberately.

## Scope

- [ ] Thread the `TaskConfig` (or its expected color→trials map + total) into
      `validate_bart_session`; keep a default so direct/legacy calls still work.
- [ ] Derive the completeness threshold and total from the config's colors
      (`sum(c.trials)`), not a literal 30/15.
- [ ] Check per-color counts against each color's configured `trials` and the
      study's actual color names, not the literal triad / `10`.
- [ ] `score_bart` passes its `config` through to the validator.

## Acceptance

- A renamed or re-counted study produces per-color completeness warnings for its
  **own** colors and counts, and no longer emits `purple/teal/orange` warnings it
  has no colors for (reproduced by a test that currently gets the spurious set).
- The **default purple/teal/orange 3×10 study is byte-identical** — every existing
  validation assertion still passes.
- `pytest`, `vitest`, `tsc --noEmit`, `vite build` stay green.

## Comments

Source: 2026-07-04 fresh full-audit, register row F8. Evidence: `scoring/bart.py:231-249`;
flagged in the issue-56 comment and `docs/metrics_reference.md` as a separate limitation.
Re-freeze the sidecar if `/score`/validation output changes for the default study
(it should not).

---

**Implemented 2026-07-04 (test-first, `/tdd`).**

`validate_bart_session` gained an optional `config: TaskConfig = DEFAULT_TASK_CONFIG`
param, threaded through from `score_bart`. Completeness derives from
`total_expected = sum(c.trials for c in config.colors)` — critical below
`total_expected // 2`, incomplete below `total_expected` — and the per-color loop
iterates `config.colors`, checking each `count` against `color_profile.trials`
(too few below `trials // 2`, partial below `trials`). For the default 3×10 study
that is 30/15 and 10/5, so the strings are **byte-identical**. The out-of-order,
pacing (`< 30_000 ms`), and pump-uniformity heuristics were left as-is —
out of scope for F8, and separately default-calibrated.

Tests (`tests/test_scoring_robustness.py`, `tests/test_scoring.py`):
- a renamed study's warnings name its own colors, never purple/teal/orange;
- a 20-per-color study is judged against `/20` and `/60`;
- a byte-identical lock on a partial default session's exact warning strings.

Gates: `pytest` **181** ✅, `tsc --noEmit` ✅, `vitest` ✅, `vite build` ✅; sidecar
re-frozen (default `/score` unchanged; non-default `session_warnings` now correct).
No `TaskConfig` schema change → no contract regen. `metrics_reference.md` note updated.
