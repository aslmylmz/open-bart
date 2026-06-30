# 14 — Study Setup form + study.json save/load + /validate-config

**Phase 3 · SPEC §6, §7, §11, §17 · depends on: 13**

## Context

The researcher-facing **Study Setup** screen. Pick a hazard family from a dropdown,
edit its validated parameters, set per-color `max_pumps`/`trials` and study-level
`reward_per_pump`/`language`/`seed`/`output_dir`/`title`, and add/remove colors.
Save/load `study.json` through the **already-built** native dialog plumbing —
`saveStudy`/`loadStudy` in [desktop.ts](../../../app/src/lib/desktop.ts) (issue 12).

The Python schema stays authoritative (decision this session: hand-written TS types
+ `/validate-config` as the authority): the candidate config is sent to
[`/validate-config`](../../../app/sidecar/app.py) and its structured errors are
surfaced inline, so the TS types never have to re-encode pydantic's validation
rules. Ships the validated default study from issue 13's `DEFAULT_STUDY`.

## Scope

- [ ] New `app/src/setup/StudySetup.tsx` (+ small param-input subcomponents): the
  study-level fields, a per-color editor list, and per-family parameter inputs driven
  by a family→param-spec table.
- [ ] New `app/src/setup/familyParams.ts`: for each of the 11 families in
  [hazards.py](../../../scoring/config/hazards.py), the param fields with
  labels/defaults/ranges mirroring the pydantic constraints — e.g. constant `p ∈
  (0,1)`; weibull `shape > 0`; gompertz `a,b > 0`; logistic `h_max ≤ 1`, `midpoint`,
  `steepness`; lognormal `mu`, `sigma > 0`; step `breakpoints`/`levels` with
  `len(levels) == len(breakpoints)+1`; tabular `values` whose length must equal the
  color's `max_pumps`. Switching family swaps in that family's default params.
- [ ] Guard against degenerate configs the engine can't score: keep the form within
  the engine's supported range (≥1 color, sane minimum `trials`/`max_pumps`) so a
  saved study doesn't hit the parked single-color/single-balloon crash in
  [scoring/bart.py](../../../scoring/bart.py); `/validate-config` remains the
  backstop.
- [ ] [api.ts](../../../app/src/lib/api.ts): add
  `validateConfig(config): Promise<{ ok: boolean; errors: string[] }>` hitting
  `/validate-config`.
- [ ] Wire save/load: `saveStudy(JSON.stringify(config, null, 2))` and
  `loadStudy()` → parse → run through `validateConfig` → set the active config; a
  load (or edit) that fails validation shows the errors instead of replacing the
  active config.
- [ ] Tests (pure, node — the project has no jsdom/testing-library, so the form
  logic is extracted into pure modules and the React component is a thin
  build/smoke-verified shell, consistent with issues 11–13):
  `familyParams.test.ts` — each family's `defaultHazard` is well-formed (correct
  discriminator, scalar params defaulted, step/tabular arrays sized to `max_pumps`);
  `studyForm.test.ts` — switching family reseeds defaults (immutably), `setHazardParam`
  edits a scalar, `removeColor` keeps ≥1 color, `addColor`/`parseStudy`/`parseNumberList`;
  `api.test.ts` — `validateConfig` POSTs the config and returns the sidecar verdict
  (fetch-mocked). A cross-check validates all 11 family defaults against the real
  pydantic schema. `StudySetup.tsx` (save/load/validate wiring) is build + smoke
  verified via `tsc` + `vite build`.

## Acceptance

- A researcher can pick any of the 11 families, edit its params + per-color
  `max_pumps`/`trials` + reward/language/seed/output dir + title, and **save** a
  `study.json` to a chosen path; **reloading** it repopulates the form.
- Invalid params (tabular length ≠ N, step shape mismatch, out-of-domain values) show
  the sidecar's `/validate-config` messages inline; saving an invalid config is
  blocked or clearly flagged.
- `npm test`, `tsc --noEmit`, and `vite build` stay green.
