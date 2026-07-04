# 60 — Verify kiosk lock + practice banner in a real Tauri run

**Verification · depends on: none**

Status: ready-for-agent

## Context

Cycle-02 audit finding F11 (Check-gap). The kiosk in-app lock (issue 44:
fullscreen + always-on-top + passcode-gated exit + capture-phase Escape/F11 swallow)
and the practice banner (issue 43) have unit tests and were driven via
Playwright-over-Chrome, but the **fullscreen / always-on-top behavior only exists in
a real Tauri window** — it has never been observed in an actual `tauri dev`/build
run. The kaizen §6 "mid-study QA" cadence and the §2 "Check" step both call for a
real end-to-end observation, not just tests.

## Scope

- [ ] Run the app under Tauri (`npm run tauri dev`, or an installed build) with a
      study that sets `exit_passcode`, and observe: fullscreen engages, always-on-top
      holds, Escape/F11 are swallowed, the passcode dialog gates exit, and the lock
      disengages at the debrief.
- [ ] Run a practice session and confirm the "TEST RUN — data not recorded" banner is
      visible on every participant screen and that no data lands outside `practice/`.
- [ ] Record the observation (pass/fail + screenshots or notes) in
      `docs/standalone/VERIFY-WINDOWS.md` (or this issue's `## Comments`).

## Acceptance

- A recorded real-run observation exists; if it surfaces a defect, spin a new
  register row/issue (evidence-first) rather than fixing blind.
- No code change expected unless the run reveals a bug.

## Comments

Source: 2026-07-04 fresh full-audit, register row F11. This is a Check/standardize
gap, not a code defect — its "guard" is the recorded observation + checklist entry.
Needs a real Tauri environment (macOS dev run or a Win11 pass).
