# 46 — Guard the pydantic↔TypeScript contract with a parity test

**Refactor · depends on: none**

Status: ready-for-agent

## Context

The study / session domain is modeled once in pydantic (`scoring/config`,
`scoring/schemas`) and re-modeled by hand in the webview's TypeScript
(`app/src/lib`). The Python models are the single source of truth and the
Sidecar stays the sole validation authority (CONTEXT.md) — but the *shapes* are
mirrored across the language seam with almost no drift guard, and they have
already drifted: `TaskConfig` gained `qc` (`QCThresholds`, issue 40) and
`payout` (`PayoutConversion`, issue 41) on the Python side, but the TS
`TaskConfig` never did, so Study Setup can neither see nor configure them.
Because both are optional, nothing broke — the gap is silent.

Chosen approach (grilled): **detect** drift with a cheap two-sided contract test
rather than **generate** the TS types from the schema. This adds no Python→TS
build dependency and keeps the offline / minimal-dependency ethos (ADR 0002); if
"drift-impossible" codegen is ever wanted it can replace the guard later without
changing the interface (worth an ADR then). Scope is the round-trip **input**
contracts — the shapes where a missing TS field is a real defect (an
unconfigurable setting, or a payload the Sidecar rejects). Read-only projections
(`Debrief`'s `AssessmentResult`, the `api.ts` response DTOs) are deliberate
subsets and are explicitly out of scope.

## Scope

- [ ] A Python test derives each guarded model's field inventory from
      `model_json_schema()` and **asserts** it equals a committed contract file
      (assert-and-fail with a named regeneration command — not a silent
      auto-rewrite). Guarded shapes: `TaskConfig`, `ColorProfile`, the
      `HazardSpec` union (each family's parameter **names**, not numeric ranges),
      and `GameSession`.
- [ ] The TS side gains a compile-time sentinel per guarded shape
      (`const … : Record<keyof T, true>`, extending the existing
      `HAZARD_FAMILY_SET` idiom in `app/src/lib/config.ts`) plus a vitest test
      asserting the sentinel's keys equal the committed contract inventory.
      Two-sided: a pydantic-only field fails vitest until TS adds it; a TS-only
      field fails vitest because the inventory lacks it.
- [ ] Bring the TS types into parity so the guard ships green: add `qc` and
      `payout` to the TS `TaskConfig` (types only — extra keys already survive a
      load→save round-trip at runtime), and audit the guarded shapes for any
      other gap.
- [ ] Record, in the contract/test, that the output / display mirrors are
      subsets-by-design and intentionally unguarded.

## Acceptance

- Deleting `qc` from the TS `TaskConfig`, or adding a stray key to either side of
  a guarded shape, turns the guard red.
- Adding a new field to a guarded pydantic model fails the Python contract test
  with a clear regenerate instruction.
- `pytest`, `npm test` (vitest), `tsc --noEmit`, and `vite build` all green after
  type parity.
- Body notes the known limitation: no unified CI runs both suites today, so the
  guard enforces locally until issue 48.

## Comments

**2026-07-03 — implemented (TDD; guard demonstrated red→green in both
directions).** Python: `tests/test_ts_contract.py` derives each guarded model's
field inventory from `model_json_schema()` and asserts it equals the committed
`app/src/lib/contract.generated.json`; a stale file fails with the named regen
command `python tests/test_ts_contract.py` (the script bootstraps the repo root
onto `sys.path` so it runs standalone, not only under pytest). Guarded shapes:
`TaskConfig`, `ColorProfile`, `QCThresholds`, `PayoutConversion`, `GameSession`,
and each of the 11 `HazardSpec` families' parameter names. TS:
`app/src/lib/contract.test.ts` — one `Record<keyof T, true>` sentinel per guarded
shape (`tsc` errors on a missing/excess key) plus a vitest assert that the
sentinel's keys equal the contract inventory; extends the `HAZARD_FAMILY_SET`
idiom in config.ts. Two-sided: a pydantic-only field fails vitest until the TS
type gains it; a TS-only field fails vitest because the contract lacks it.
Parity fix: added `QCThresholds` / `PayoutConversion` interfaces and `qc?` /
`payout?` to the TS `TaskConfig` (types only — extra keys already round-trip at
runtime; the Study Setup controls to edit them are issue 47). No other guarded
shape had drifted. The output/display mirrors (`Debrief`'s `AssessmentResult`,
the api.ts response DTOs) are documented as subsets-by-design and left
unguarded. Known limitation: no unified CI runs both suites today, so the guard
enforces locally (issue 48). **Verified:** the initial TS sentinel without
`qc`/`payout` went red (contract had them); a temporarily injected pydantic
field turned both the Python test and vitest red, and the regen command restored
green. Gates: pytest **161** ✅ (+1), vitest **118** ✅ (+6), tsc ✅, vite build ✅.
