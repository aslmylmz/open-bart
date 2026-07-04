# 56 — Generalize name-keyed persona metrics onto config risk-ordering

**Feature · depends on: 51**

Status: done

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

- [x] Introduce a single risk-ranking of the config's colors (lowest → highest
      risk by cap / EV-optimal) and route the name-keyed metrics through it:
      "low-risk color" replaces literal `purple`, "high-risk color" replaces
      literal `orange`, the excluded mid color replaces literal `teal`.
- [x] `_RISK_BY_COLOR` (low/medium/high labels in `color_metrics`) derives from
      the same ranking rather than a hardcoded name map.
- [x] The persona-validity `session_warnings` guard from issue 51 is removed or
      narrowed once the metrics are genuinely color-agnostic.
- [x] `docs/metrics_reference.md` + ADR 0004 updated to reflect the new
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

---

**Implemented 2026-07-04 (test-first, `/tdd`).**

A single `_RiskRanking` seam (`scoring/bart.py`) ranks the config's colors by
EV-optimal stop (`curve.optimum`, descending; config order breaks ties) into
`low_color` (safest, the ex-`purple` role), `high_color` (riskiest, the
ex-`orange` role), and a `low`/`medium`/`high` `risk_label` map. Every name-keyed
metric now routes through it: the learning-rate family, `color_discrimination_index`,
`color_discrimination_trajectory`, `patience_index`/`patience_index_normalized`,
`orange_avg_pumps` (legacy field name kept; now reads `high_color`),
`_detect_flat_strategy`, `_generate_behavioral_profile` (selective-strength and
"Near-Optimal on Safe Balloons" markers), and `ColorMetrics.risk_profile`. A
single-color study has `high_color=None`, so the discrimination metrics stay
degenerate rather than comparing a color to itself.

The issue-51 `_persona_validity_warning` was removed (metrics are now genuinely
color-agnostic); its two tests were repurposed to assert the caveat is gone and
the renamed metrics are non-degenerate.

Verification:
- Byte-identical default study — new golden-snapshot regression test
  (`test_default_session_metrics_are_byte_identical_to_golden`,
  `tests/fixtures/default_session_metrics_golden.json`) freezes a full
  non-degenerate default session's `model_dump()`; every existing scoring
  assertion still passes.
- Rename-invariance / non-degenerate — new tests in
  `tests/test_scoring_robustness.py` score the same behavior under `crimson/azure/
  jade` and prove learning, discrimination, trajectory, patience, high-risk
  average, `risk_style`, traits, and flat-strategy all match the default and are
  non-zero; a reversed-order config confirms labels/metrics follow the ranking,
  not config position.
- All four gates green (`pytest` 178, `tsc --noEmit`, `vitest` 134, `vite build`);
  sidecar re-frozen.

Out of scope (kept tight per ADR 0004's name-keyed list): `validate_bart_session`
still name-keys its per-color balloon-count warnings on `purple/teal/orange` and
assumes the 30/10 default study shape, so a renamed study gets spurious "Too few
purple balloons" warnings. That's a distinct validation-layer limitation, not a
persona metric — a candidate follow-up issue.
