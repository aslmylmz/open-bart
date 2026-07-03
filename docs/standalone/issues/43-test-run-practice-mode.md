# 43 — Test Run: practice mode that cannot contaminate the dataset

**Feature · depends on: 38**

Status: ready-for-agent

## Context

Client brief 3B: RAs need to click through the task to test a setup without
polluting the official dataset. The contamination accident runs **both
directions** — a test session landing in the real data, and a real
participant unknowingly run in test mode (data silently lost). The grill
decision covers both: practice output goes to a separate folder so it is
inspectable but never mingles, and the Participant View wears an unmissable
banner for the entire practice session.

## Scope

- [ ] A "Test Run" control in the Researcher View starts a session in
      practice mode; the normal "Start run →" path is untouched.
- [ ] Practice sessions write their session files under a `practice/`
      subfolder of the output directory, stamped `mode: practice` in the
      files; the Master CSV and trials CSV are **never** appended, and
      provenance files (42) are neither created nor refreshed.
- [ ] The participant ID is auto-filled with a test marker (e.g. `TEST`) —
      practice is exempt from the mandatory-ID and duplicate-ID guardrails
      (38), which is why this slice follows it.
- [ ] The Participant View shows a persistent, high-contrast "TEST RUN — data
      not recorded" banner on every screen of a practice session, in both
      languages. It must be visible at a glance from across a lab room.
- [ ] Practice mode exercises the real pipeline end-to-end (gameplay, scoring,
      file writing) — it differs from an official run *only* in destination,
      stamps, and banner, so a passing test run is evidence the real thing
      works.
- [ ] Docs: a short researcher-facing section on when to use Test Run and
      where its files land.

## Acceptance

- A practice session completes end-to-end and its files exist under
  `practice/` with the practice stamp; the Master CSV, trials CSV, and
  provenance files are byte-identical to before the run — covered by tests.
- The banner is present on consent, ID, gameplay, and debrief screens during
  practice, and absent in official runs.
- No path exists from the Test Run control to an unstamped session outside
  `practice/`.
- `pytest`, `npm test`, `tsc`, `vite build` stay green.

## Comments

**2026-07-03 — implemented (TDD + verified in the real app).** Sidecar:
`GameSession.practice` (default False — the envelope is the stamp's
per-session home per the issue-42 plan, so `"practice": true` lands in
`*_session.json` and, automatically, in the generated data dictionary). In
`write_output`, practice redirects the four session files to
`output_dir/practice/` and returns before the single study-wide decision
block, so provenance (42), master CSV, and trials CSV are all skipped at the
one point the block's comment always promised;
`WriteOutputResponse.master_csv/trials_csv` became `str | None` (the TS
client discards response bodies — no client change). Tests pin both
contamination directions: after an official session, a practice run leaves
every top-level file **byte-identical**; practice-first creates nothing but
`practice/` + its four files. No re-freeze needed: `BARTMetrics`/`/score`
untouched, and the frozen binary ignores the extra payload field. Client:
`RunFlow practice` prop — ID pre-filled `TEST`, `/check-id` skipped entirely
(the empty-ID button gate still holds), and a sticky full-width `#b91c1c`
banner (`practiceBanner`, en/tr) on consent/ID/loading/error and around
`BartGame`, which covers gameplay + debrief; payload stamping runs
`buildSessionPayload → BartGame practice prop` (required `practice` on
`SessionPayload`; api.test.ts/session.test.ts literals updated, tsc-caught as
predicted). App: `Mode = "setup" | "run" | "practice"`; amber-outline "Test
run" beside the untouched "Start run →"; new App.test.tsx (api module
mocked; `fetchHealth` rejection leaves VersionGuard open by design). Docs:
"Test Run (practice) sessions" section in `data_outputs.md` (+ envelope
entry updated), guarded by `test_practice_mode_is_documented`. **Verified
live** (real sidecar + vite + Playwright/Chrome): banner on all four screens,
`TEST` prefill, no `/check-id` in practice (request log), `practice/`
isolation on disk both directions, official path unchanged. One deliberate
leftover, flagged from verification: the practice debrief still says "Your
session has been recorded" under the "data not recorded" banner — true (it
went to `practice/`) but juxtaposed oddly; practice-specific debrief copy
would be a small follow-up if wanted. Gates: pytest 163 ✅ (+3 practice, +1
docs), npm test 102 ✅ (+6), tsc ✅, vite build ✅.
