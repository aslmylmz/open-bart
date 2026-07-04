# Quality Kaizen — Continuous Improvement Framework for the Instrument

A standing, repeatable way to keep the Dynamic-Hazard BART instrument **stable,
accurate, and scientifically valid** as it evolves. Kaizen = small, reversible,
standardized improvements, each one leaving behind a guard so the same defect
cannot silently return.

This is a *framework document*, not a one-off report. The findings from the
2026-07-04 research audit are seeded into the register below as the first cycle;
every later audit appends its findings the same way.

---

## 1. Why kaizen here

A research instrument has an unusual quality bar: a bug that merely *looks*
fine is worse than one that crashes, because **silently wrong data gets
published**. So the framework treats three things as first-class quality
characteristics, alongside "does it run":

- **Scientific validity** — does the number mean what a researcher thinks it means?
- **Data integrity** — is every consented session actually captured, once, intact?
- **Methodological neutrality** — does the instrument avoid biasing the behavior it measures?

Kaizen fits because these are not one-time fixes: configs grow, hazard families
are added, RAs find new ways to hold it wrong. The answer is a **loop** with a
**standard** at the end of each turn.

## 2. The improvement loop (PDCA on this repo's rails)

The repo already has the machinery; kaizen just names the loop and refuses to
skip the last step.

| PDCA | What it is here | Artifact |
|---|---|---|
| **Plan** | A finding becomes a numbered issue with Context / Scope / Acceptance | `docs/standalone/issues/NN-*.md` |
| **Do** | Implement test-first (red → green), smallest reversible slice | the code change |
| **Check** | The four gates + the change's own regression test + a real end-to-end observation | `pytest` · `vitest` · `tsc` · `vite build` |
| **Act (standardize)** | The behavior is pinned by a test/contract and written into the docs, so it becomes the new baseline | test + `docs/` update + issue `## Comments` |

**The non-negotiable:** an improvement is not "done" when the code works — it is
done when a **regression guard exists** so the defect cannot return unnoticed.
This is the kaizen "standardize" step, and it is where quality compounds instead
of eroding.

## 3. The standing audit rubric (the reusable part)

Re-run this rubric on the triggers in §6. Each dimension lists what to inspect
and the red flags that turn into register rows. Capture **evidence** (a file:line,
a generated CSV row, a failing repro) for every finding — a finding without
evidence is a rumor.

| # | Dimension | Inspect | Red flags |
|---|---|---|---|
| D1 | **Protocol fidelity** | consent copy, instruction wording, trial flow, per-color balance | in-app "consent" mistaken for IRB consent; instructions leak the hazard structure; unbalanced color exposure |
| D2 | **Measurement neutrality** | button symmetry, theme/arousal, feedback visibility | UI primes pump-vs-collect; participant sees their own risk metrics mid-study; gaming-arousal cues |
| D3 | **Determinism & reproducibility** | seed handling, RNG scope, scoring purity | same event log re-scores differently; "reproducible" seed silently fixes presentation order for all participants |
| D4 | **Data integrity under load** | save path, failure surfacing, concurrency, file locks | write failures swallowed; sidecar warnings dropped by UI; "recorded" shown before the write is confirmed |
| D5 | **Scientific validity of derived metrics** | hardcoded constants, config-scaling, validation status of composites | benchmark magic numbers that don't scale with config; metrics hardwired to default color names; unnormed "persona" used as a DV |
| D6 | **Export integrity** | flat CSV shape, cell types, R/SPSS readiness | non-scalar cells (dict/list blobs); columns redundant with scalar ones; booleans/None that import as junk |

## 4. Classification & severity taxonomy

Every finding is tagged with **class** (what kind of problem) and **severity**
(how much it threatens a study). Class matters because the fix differs: a *bug*
is repaired; a *design-flaw* is a deliberate trade-off to re-decide; a
*validity-limitation* is often fixed by **scoping + documentation**, not code.

**Class:** `bug` · `design-flaw` · `validity-limitation` · `usability`

**Severity:**

- **Critical** — can lose data or produce silently wrong published results. Fix before next data collection.
- **Medium** — degrades validity or analyst experience but is detectable/recoverable. Fix this cycle.
- **Low** — cosmetic or narrow-impact. Fix opportunistically.

## 5. Improvement register (A3-style)

Cycle 01 · seeded from the 2026-07-04 research audit. One row per finding:
current state → the standard we want → the countermeasure → its issue → status.
Close a row only when its issue's regression guard is green.

| ID | Finding (current state) | Target standard | Class · Severity | Issue | Status |
|---|---|---|---|---|---|
| F1 | Disk write is fire-and-forget (`void persistSession().catch(console.error)`); participant sees "Your session has been recorded" even when nothing was written. | No "recorded" message until the write is confirmed; failures are researcher-visible. | bug · **Critical** | [49](issues/49-confirm-write-before-recorded.md) | **done** 2026-07-04 |
| F2 | `/write-output` returns `warnings[]` (Excel-locked CSV → sibling fork, migration) but the UI discards the response body. | Every write warning surfaces in the UI during the session. | bug · **Critical** | [50](issues/50-surface-write-output-warnings.md) | **done** 2026-07-04 |
| F3 | Persona/learning/discrimination logic hardwired to literal `purple`/`teal`/`orange`; renaming or re-counting colors silently returns `0.0`/`None`. | Derived metrics follow config risk-ordering, **or** the persona is loudly scoped to the default study. | validity-limitation · **Critical** | [51](issues/51-generalize-persona-off-color-literals.md) | **done** 2026-07-04 (guard; full generalization → [56](issues/56-generalize-persona-by-risk-ranking.md)) |
| F4 | Benchmarks `_OPTIMAL_MEDIAN_EARNINGS=27.25`, `optimal_spread=9.0` are hardcoded to the default study; wrong for any other config (and any incomplete session). | Benchmarks derived from `TaskConfig.curves`, or the metric is gated to the config it's valid for. | validity-limitation · Medium | [52](issues/52-config-derive-benchmarks.md) | **done** 2026-07-04 |
| F5 | Master CSV carries `ev_optimal_stops` and `session_warnings` as Python-`repr` dict/list blobs (invalid JSON, embedded commas, redundant with scalar columns). | Flat CSV is scalar-only; nested data stays in the JSON. | bug · Medium | [53](issues/53-drop-nonscalar-csv-columns.md) | **done** 2026-07-04 |
| F6 | `risk_style` / `adaptive_strategy_score` are unnormed heuristics but are exported alongside defensible primitives with no "exploratory" marking. | Composites documented as exploratory (no norming/reliability); deprecated fields removed or flagged. | validity-limitation · Medium | [54](issues/54-label-persona-exploratory.md) | **done** 2026-07-04 |
| F7 | Debrief hardcodes `$` regardless of currency/language; in-app consent is a single sentence. | Currency-correct debrief; consent copy that doesn't impersonate an IRB form. | usability · Low | [55](issues/55-debrief-currency-consent-copy.md) | open |

**Credited as already-good (protect these; don't regress):** neutral
symmetric Pump/Collect controls, sterile light posture (anti-arousal),
participant never sees their own metrics, collected-only scoring against
truncation bias, header-versioned CSV writer, long-format trials CSV.

## 6. Cadence — when to run a cycle

Kaizen is continuous, but the full rubric (§3) runs on **triggers**, not a
calendar:

- **Before every release / tag** (JOSS/Zenodo especially) — full rubric.
- **On any change to the config surface** (new hazard family, new color semantics, new CSV column) — D5 + D6 at minimum, because that is where validity silently drifts.
- **Mid-study QA** — D3 + D4 (a dry run of the exact preset + output path the lab will use), because integrity failures only appear on real hardware/paths.
- **On any reported anomaly** — start a new register row immediately; evidence first.

## 7. Definition of Done for a kaizen item

A register row closes only when **all** hold:

- [ ] A test fails without the fix and passes with it (the standardize guard).
- [ ] The four gates are green: `pytest`, `vitest`, `tsc --noEmit`, `vite build`.
- [ ] The behavior is written into the relevant `docs/` (data outputs, metrics reference, or this file's "credited as good" list).
- [ ] The issue `## Comments` records what changed and any side effects.
- [ ] The register row's status is set to `done` with the closing date.

## 8. Adding a finding later

1. Give it the next `F<n>` id and a register row (§5) with evidence.
2. Open an issue in `docs/standalone/issues/` (house style: `# NN — Title`, `**Class · depends on: …**`, `Status:`, `## Context / Scope / Acceptance / Comments`).
3. Work the PDCA loop (§2); standardize; close the row.

The register is the memory. If it isn't in the register, the improvement didn't happen.
