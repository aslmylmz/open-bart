# 08 — Full sidecar endpoints + client alignment + tests

**Phase 1 · SPEC §9, §11, §13 · depends on: 06 (gated by 07)**

## Context

With the freeze proven (issue 07), implement the real endpoints over the `scoring`
package. This also reconciles two Phase-0 integration mismatches: the Vite client
POSTs to `/assessments/bart` but SPEC §9 names the route `/score`, and the client
expects an `AssessmentResponse`-shaped object while `score_bart` returns a flat
`BARTMetrics`. **Decisions taken:** align the client to `/score`; the sidecar maps
`BARTMetrics → AssessmentResponse`.

## Scope

- [ ] [app/sidecar/app.py](../../../app/sidecar/app.py) — add:
  - `POST /validate-config` — body = `TaskConfig` JSON → `{"ok": bool, "errors": [...]}`
    (catch pydantic `ValidationError`, surface messages).
  - `POST /preview` — body = `TaskConfig` → per-color `{hazard, survival, ev, optimum,
    optimal_ev}` straight from `TaskConfig.curves` (SPEC §7.3).
  - `POST /score` — body = `GameSession` → `AssessmentResponse`. Score with
    `score_bart(events, DEFAULT_TASK_CONFIG)` (config-driven scoring is a later phase).
  - `POST /write-output` — body = session + metrics → writes per SPEC §13 (raw events
    `JSONL`, metrics `JSON`, a **`TaskConfig` snapshot**) under `output_dir`; returns
    the written paths.
- [ ] Mapper `BARTMetrics → AssessmentResponse`: `normalized_scores = []`,
  `profile_traits = {}` (no population norms offline). Reuse
  [scoring.schemas.AssessmentResponse](../../../scoring/schemas/__init__.py).
- [ ] [app/src/lib/api.ts](../../../app/src/lib/api.ts): `scoringEndpoint()` →
  `${resolveApiUrl()}/score`; update
  [api.test.ts](../../../app/src/lib/api.test.ts) accordingly.
- [ ] `tests/test_sidecar.py` — `/score` result **equals** `score_bart(events)` called
  directly (the SPEC §17 acceptance); `/preview` matches `DEFAULT_TASK_CONFIG.curves`
  (optima 11/5/2); `/validate-config` accepts the default and rejects a bad config;
  `/write-output` writes the files and returns their paths.

## Acceptance

- `/score` output is **identical** to calling `scoring.score_bart` directly.
- All sidecar tests pass; the engine tests stay green.
- Client posts to `/score`; `npm test`, `tsc --noEmit`, and `vite build` are green.
