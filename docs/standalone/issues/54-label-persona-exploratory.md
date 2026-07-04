# 54 — Mark the persona / composite scores as exploratory

**Feature · depends on: —**

Status: done

## Context

Post-audit hardening (Quality Kaizen cycle 01, finding **F6**;
`docs/standalone/QUALITY-KAIZEN.md`). The scored output mixes two very different
kinds of number without distinguishing them:

- **Defensible primitives** — adjusted pumps on collected balloons, explosion
  rate, per-color EV efficiency, latency. These are standard and analysis-ready.
- **Unnormed heuristics** — `risk_style` (a hand-tuned 10-branch decision tree
  over ~15 magic thresholds) and `adaptive_strategy_score` (an arbitrary
  35/25/25/15 weighted composite). No norming sample, no reliability estimate,
  no citation.

A researcher could easily lift `risk_style` or `adaptive_strategy_score` straight
into a paper as a dependent variable. Additionally, `color_discrimination_index`
is marked DEPRECATED in the schema yet is still exported. This slice is
documentation + provenance, not new computation: make the status legible so the
outputs are used correctly.

## Scope

- [ ] `docs/metrics_reference.md` clearly separates analysis-ready primitives
      from exploratory composites, stating the composites are unnormed and
      should not be used as DVs without independent validation.
- [ ] The schema docstrings for `risk_style` / `behavioral_profile` and
      `adaptive_strategy_score` carry the same "exploratory, unnormed" note.
- [ ] The deprecated `color_discrimination_index` is either removed or given an
      explicit deprecation marker in the docs and schema (no silent export).

## Acceptance

- The metrics documentation lets a researcher tell, at a glance, which columns
  are safe to publish on and which are exploratory.
- The deprecated field's status is unambiguous in both schema and docs.
- `pytest`, `vitest`, `tsc --noEmit`, `vite build` stay green.

## Comments

Source: 2026-07-04 research audit, register row F6. No scoring math changes —
scope is provenance and honest labeling of already-computed fields.

**2026-07-04 — implemented (TDD).** The `adaptive_strategy_score` and
`behavioral_profile` schema descriptions now carry an explicit "Exploratory:
unnormed heuristic — not a validated dependent variable" caveat, which flows into
the auto-generated data dictionary and the API schema. `docs/metrics_reference.md`
gains a note separating analysis-ready primitives (`average_pumps_adjusted`,
`explosion_rate`, `ev_ratio_score`, per-color `ev_efficiency`) from the two
exploratory composites, and marks both rows. `color_discrimination_index` was
**kept** (the issue's "flagged, not removed" option — removing it would churn the
pydantic↔TS contract for a pre-1.0 field) with its existing `DEPRECATED` marker
in schema and docs. New `tests/test_metric_documentation.py`: the two composites
carry the exploratory marker; the deprecated field always carries its marker (no
silent export). Closes kaizen row F6. Gates: pytest 170 ✅, vitest 132 ✅,
tsc ✅, vite build ✅.
