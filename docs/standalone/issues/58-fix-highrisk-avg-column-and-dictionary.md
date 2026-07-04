# 58 — Fix the high-risk-average CSV column name + data dictionary

**Bug · depends on: none**

Status: ready-for-agent

## Context

Cycle-02 audit finding F9 (D6). Two export-integrity issues left by issue 56:

1. The top-level `orange_avg_pumps` metric keeps its **literal name** but now reads
   the study's **highest-risk** color (issue 56 generalization). In a renamed
   study's Master CSV there is a column literally called `orange_avg_pumps` holding
   (e.g.) jade's average — misleading for anyone reading the sheet.
2. `docs/data_outputs.md:284-287` documents three "legacy convenience columns"
   `purple_avg_pumps`, `teal_avg_pumps`, `orange_avg_pumps` — but only
   `orange_avg_pumps` exists (it is the one top-level scalar field; the per-color
   `{color}_average_pumps` / `{color}_behavioral_avg_pumps` columns come from
   `_flatten_metrics`, `app/sidecar/app.py:62-65`). The other two are documented
   phantoms.

The per-color `{color}_{field}` columns are already config-driven and correct; this
is only the top-level scalar column + its docs.

## Scope

- [ ] Correct `docs/data_outputs.md` to describe the columns that actually exist and
      note that `orange_avg_pumps` is the **highest-risk color's** average regardless
      of its name.
- [ ] Decide (smallest reversible slice): document the caveat only, **or** rename the
      field to a role-based name (`high_risk_avg_pumps`) — a contract change touching
      `scoring/schemas`, the TS interface + contract sentinel, the provenance
      `_flatten_metrics`/`_unflattened_fields` mirror, and a contract regen.

## Acceptance

- The data dictionary matches the actual Master CSV header for both the default and
  a renamed study (guarded by a test that reads a generated row's keys).
- If renamed: the pydantic↔TS contract parity guard (issue 46) stays green and the
  provenance mirror test passes; if documented-only: the doc test stays green.
- `pytest`, `vitest`, `tsc --noEmit`, `vite build` stay green.

## Comments

Source: 2026-07-04 fresh full-audit, register row F9. Evidence: `data_outputs.md:284-287`,
`app/sidecar/app.py:43-66`, the `orange_avg_pumps` field in `scoring/schemas`.
Renaming a published field is a contract change — prefer doc-first unless the rename
is explicitly wanted. Re-freeze the sidecar if the schema changes.
