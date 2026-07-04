# 56 — Generalize name-keyed persona metrics onto config risk-ordering

**Feature · depends on: 51**

Status: ready-for-agent

## Context

Follow-up to issue 51 (the guard-and-document slice) and ADR 0004. The EV-based
metrics are already config-agnostic, but the **name-keyed persona metrics** still
resolve behavior by the literal color names `purple` / `teal` / `orange`:

- the learning-rate family (`learning_rate`, `half_split_learning_rate`,
  `tercile_learning_rate`) only accumulates for `orange` / `purple`;
- `color_discrimination_index` and `color_discrimination_trajectory` compute
  `purple` − `orange`;
- `patience_index` reads `purple`; `orange_avg_pumps` reads `orange`;
- `_detect_flat_strategy` and several `risk_style` branches key on
  `_purple_efficiency` / `_orange_efficiency` and the purple/orange means.

For a renamed-color study these read `0`/`None` (issue 51 now warns about it).
This issue makes them **actually compute** by ranking the study's colors by risk
(lowest = highest cap / EV-optimal, highest = lowest cap) instead of by name, so
any color set scores coherently. ADR 0004 records this as the intended end state.

## Scope

- [ ] Introduce a single risk-ranking of the config's colors (lowest → highest
      risk by cap / EV-optimal) and route the name-keyed metrics through it:
      "low-risk color" replaces literal `purple`, "high-risk color" replaces
      literal `orange`, the excluded mid color replaces literal `teal`.
- [ ] `_RISK_BY_COLOR` (low/medium/high labels in `color_metrics`) derives from
      the same ranking rather than a hardcoded name map.
- [ ] The persona-validity `session_warnings` guard from issue 51 is removed or
      narrowed once the metrics are genuinely color-agnostic.
- [ ] `docs/metrics_reference.md` + ADR 0004 updated to reflect the new
      color-agnostic status.

## Acceptance

- A renamed- or re-counted-color study produces non-degenerate learning,
  discrimination, patience, and `risk_style` values (reproduced by tests that
  currently only get `0`/`None`).
- **The default purple/teal/orange study is byte-identical**: every existing
  scoring assertion still passes, plus a fixture-level equality guard on a full
  default session's metrics before/after.
- `pytest`, `vitest`, `tsc --noEmit`, `vite build` stay green.

## Comments

Source: 2026-07-04 research audit, register row F3 (deferred half). Split from
issue 51 per the "B now + A follow-up" decision; the ranking approach is fixed by
ADR 0004. Highest-value once labs actually run non-default color presets.
