# 51 — Generalize the persona layer off literal color names

**Feature · depends on: —**

Status: ready-for-human

## Context

Post-audit hardening (Quality Kaizen cycle 01, finding **F3**;
`docs/standalone/QUALITY-KAIZEN.md`). The instrument advertises 11 hazard
families and fully configurable color profiles, but the scoring engine
hard-codes the literal color keys `purple` / `teal` / `orange` and their
low/med/high semantics in ~22 places — learning rate, color discrimination,
flat-strategy detection, and the whole behavioral profile all key on those
strings. If a researcher renames colors or uses a different count, these
derived metrics **silently return `0.0` / `None`**: the CSV looks populated but
the persona is meaningless. Today the risk persona is only valid for the exact
default 3-color study. This echoes the original engine-generalization work
(issue 03), which generalized caps/optima but left the persona layer keyed on
color literals.

**Decision required (why `ready-for-human`):** choose the scope before
implementation —

- **(A) Full generalization** — drive every derived metric off config-declared
  risk ordering (e.g. rank by cap or an explicit per-color risk rank), so any
  color set scores coherently. Larger, touches most of the persona layer.
- **(B) Guard-and-document** — detect a non-default color configuration and emit
  an explicit "persona metrics are only validated for the default study"
  warning + documentation, leaving the primitives (adjusted pumps, explosion
  rate, per-color EV efficiency) as the supported outputs. Small, safe, honest.

A reasonable path is B now (closes the silent-failure trap immediately) and A as
a tracked follow-up.

## Scope

- [ ] Decision recorded (A vs B, or B-then-A) — ideally as an ADR since it sets
      the boundary of what "configurable" means for scored output.
- [ ] Chosen path implemented so a renamed- or re-counted-color study is **never
      silently zeroed**: it either scores coherently (A) or is loudly flagged in
      `session_warnings` + docs (B).
- [ ] `docs/metrics_reference.md` states which derived metrics are color-agnostic
      vs. default-study-only.

## Acceptance

- Scoring a 2-color or renamed-color config yields either coherent persona
  metrics (A) or an explicit warning that they are unsupported for this config
  (B) — reproduced by a regression test on a non-default config.
- The default `purple/teal/orange` study is unchanged (byte-identical metrics on
  a fixture session).
- `pytest`, `vitest`, `tsc --noEmit`, `vite build` stay green.

## Comments

Source: 2026-07-04 research audit, register row F3 (Critical). Related work:
issue 03 (engine generalization). Marked `ready-for-human` for the A/B scoping
decision; once decided, the implementation is agent-workable.
