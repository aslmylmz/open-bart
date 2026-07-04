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

**2026-07-04 — static ACL verification (defect found; live GUI observation still
owed).** Before a live run, a static check of the Tauri capability ACL surfaced a
real defect this verification exists to catch — recorded evidence-first rather than
fixing blind (see acceptance). Finding: the only capability
(`app/src-tauri/capabilities/default.json`) grants `core:default`, whose
`core:window:default` set is getters-only — `allow-set-fullscreen` and
`allow-set-always-on-top` are absent (evidence:
`app/src-tauri/gen/schemas/acl-manifests.json`). So in a real build `setKioskLock`'s
`win.setFullscreen`/`win.setAlwaysOnTop` (and the F11 `toggleFullscreen`) are
ACL-denied and rejected; `RunFlow.tsx` swallows the rejection (`.catch(() => {})`),
so **fullscreen + always-on-top never engage** — the window is not actually locked.
The JS Escape/F11 key swallow and the passcode gate are unaffected (not window APIs).
Spun as a new register row **F15 / issue [64](64-kiosk-window-permissions.md)**
(bug · Medium). A standardized real-run checklist for the kiosk lock + practice
banner was added to `docs/standalone/VERIFY-WINDOWS.md`.

This issue stays `ready-for-agent`: the deliverable — a recorded *real-run*
observation of the engaging lock — still requires a human at a real Tauri window
(macOS dev run or Win11) and should be completed **after** issue 64 grants the
permissions, then recorded against the new checklist.

**Update 2026-07-04:** issue [64](64-kiosk-window-permissions.md) has landed (the two
window setters are granted; `cargo check` validates the ACL accepts them), so this
verification is now **unblocked** — the live GUI run against the `VERIFY-WINDOWS.md`
checklist is all that remains.
