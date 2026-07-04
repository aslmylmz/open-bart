# 49 — Confirm the save before the "recorded" debrief

**Bugfix · depends on: —**

Status: ready-for-agent

## Context

Post-audit hardening (Quality Kaizen cycle 01, finding **F1**;
`docs/standalone/QUALITY-KAIZEN.md`). On session completion the client awaits
`/score` (which returns metrics but writes nothing to disk), then fires
`persistSession` — the actual `/write-output` disk write — **fire-and-forget**,
catching failures only into `console.error`. The debrief then tells the
participant "Your session has been recorded." So if the write fails (output
directory unmounted/full/unwritable, invalid path), the participant sees a
clean thank-you while **nothing was persisted**, and the only trace is a console
log no one is watching. Over a 500-participant study a mid-day drive hiccup
silently drops sessions. This is the single highest-value data-integrity fix:
the tool's most reassuring message is currently the one it cannot guarantee.

## Scope

- [ ] The finished → debrief transition awaits the `/write-output` result; the
      "recorded" confirmation renders only after the write is confirmed.
- [ ] A failed persist surfaces a **researcher-visible** error state (not a
      thank-you) with a retry affordance, reusing the existing error/retry
      pattern where possible.
- [ ] The participant-facing "recorded" copy is never shown for an unconfirmed
      or failed write.
- [ ] `/score` (results display) and `/write-output` (persistence) stay distinct;
      this issue changes *sequencing and failure handling*, not the scoring path.

## Acceptance

- With the study's `output_dir` forced unwritable, a completed session shows an
  error with retry — not the debrief; retry after restoring the path succeeds
  and then shows the debrief.
- The happy path is unchanged: a normal session persists, then debriefs.
- An end-to-end/UI test covers the failed-write branch.
- `pytest`, `vitest`, `tsc --noEmit`, `vite build` stay green.

## Comments

Source: 2026-07-04 research audit, register row F1. Pairs with issue 50
(surfacing the write's `warnings[]`), which builds on the awaited result this
issue introduces.

**2026-07-04 — implemented (TDD).** `handleSubmit` now awaits `persistSession`
(`/write-output`) **before** rendering the debrief: `setResults` / `onComplete`
run only after the write is confirmed. A failed write is caught and shown as a
retryable error (new `saveError` i18n key, en + tr) on the finished screen — the
participant never sees the "recorded" debrief for a lost session, and the
existing submit button re-runs the save. Replaced the prior fire-and-forget
`void persistSession().catch(console.error)`. Two behavior tests: a failed save
keeps the participant off the thank-you screen; a retried save that succeeds
reaches it. Gates: pytest 161 ✅, vitest 130 ✅, tsc ✅, vite build ✅.
