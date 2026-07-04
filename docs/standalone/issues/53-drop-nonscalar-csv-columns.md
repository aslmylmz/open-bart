# 53 — Drop non-scalar columns from the flat master CSV

**Bugfix · depends on: —**

Status: ready-for-agent

## Context

Post-audit hardening (Quality Kaizen cycle 01, finding **F5**;
`docs/standalone/QUALITY-KAIZEN.md`). The master CSV is otherwise clean —
one row per session, per-color metrics correctly exploded to `{color}_{field}`
scalar columns — but the flattener leaves two fields as non-scalar cells:

- `ev_optimal_stops` → a Python-`repr` dict, e.g.
  `{'purple': 11.0, 'teal': 5.0, '_purple_efficiency': 0.98…}`
- `session_warnings` → a Python-`repr` list of strings

Both land as `str(value)` blobs with single quotes and embedded commas: **not
valid JSON** (so a researcher cannot even parse them), messy single character
columns in R/SPSS, and **fully redundant** — every `ev_optimal_stops` value
already exists as a clean scalar column (`{color}_ev_optimal_stop`,
`{color}_ev_efficiency`). Verified on a generated 73-column row. The flattener
already drops `behavioral_profile` and `color_metrics` for exactly this reason;
these two were missed.

## Scope

- [ ] The flattener pops `ev_optimal_stops` and `session_warnings` from the flat
      CSV row (both remain in the per-session metrics JSON, unchanged).
- [ ] The master-CSV contract test asserts every column is scalar (no
      dict/list cells).
- [ ] `docs/data_outputs.md` reflects the final column set.

## Acceptance

- A freshly generated master-CSV row contains only scalar cells; a test fails if
  a dict/list value is ever written to the flat CSV.
- The metrics JSON still contains `ev_optimal_stops` and `session_warnings` in
  full.
- `pytest`, `vitest`, `tsc --noEmit`, `vite build` stay green.

## Comments

Source: 2026-07-04 research audit, register row F5. Same rationale and mechanism
as the existing `behavioral_profile`/`color_metrics` pops in the flattener.
