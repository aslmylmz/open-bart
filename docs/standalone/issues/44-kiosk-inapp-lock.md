# 44 — Kiosk in-app lock: passcode-gated exit

**Feature · depends on: none**

Status: done

## Context

Kiosk today is a fullscreen toggle plus an exit button offered between
trials — nothing stops a curious participant from leaving the task. Client
brief 3B asks to "completely lock the OS", which is not achievable from user
space (Ctrl+Alt+Del and Win+L are untouchable; true kiosk on Windows is
Assigned Access, an OS feature) and global keyboard hooks buy AV flags and
macOS accessibility prompts for partial coverage. Grill decision: an honest
**in-app lock** — passcode-gated exit, no global hooks — plus documentation
for labs that need the real OS kiosk.

## Scope

- [ ] The Study Preset gains an optional exit passcode. Documented stance: it
      is stored in `study.json` as **deterrence, not security** — it stops a
      participant, not an attacker with the preset file. Optional — absent
      passcode means today's behavior.
- [ ] While a session is running with a passcode set, the window is
      fullscreen and always-on-top, and every in-app exit path (the exit
      button, Escape/F11 handling) opens a passcode prompt instead of
      leaving; a wrong entry returns to the session unharmed.
- [ ] The lock disengages automatically at debrief (researcher hand-back) —
      the passcode gates mid-session escape, not normal completion.
- [ ] No global keyboard hooks, no OS-level shortcut suppression — in-app
      swallowing only.
- [ ] A docs page explains the in-app lock's honest limits and walks a lab
      through pairing the instrument with Windows Assigned Access for a true
      OS kiosk (companion to the SmartScreen page in tone and audience).

## Acceptance

- With a passcode configured, a running session cannot be exited from the
  Participant View without entering it; wrong entries stay in-session;
  correct entry exits — covered by tests.
- Without a passcode, behavior is unchanged from v1.0.0.
- Session completion (debrief) never asks for the passcode.
- The Assigned Access docs page builds warning-free into the docs site.
- `pytest`, `npm test`, `tsc`, `vite build` stay green.

## Comments

**2026-07-03 — implemented (TDD + verified in the real app).** Preset:
`TaskConfig.exit_passcode` (optional; stripped; blank / >64 chars rejected by
`/validate-config` with errors naming the field — the conditions-validator
pattern; the field's "deterrence, not security" stance lives in its model
description and so lands in the generated data dictionary automatically).
Client: the lock is wholly owned by `RunFlow` — a single `requestExit()`
funnel that both its own back bar and `BartGame`'s exit button leave through,
so no path can bypass it; a capture-phase window keydown listener swallows
Escape/F11 into the prompt while engaged (capture, so the app shell's F11
fullscreen toggle never sees the event — in-app swallowing only, no global
hooks per the grill decision); the prompt is a fixed overlay rendered outside
`BartGame`'s container, so keys typed into it can't reach the task's own
key handling. Wrong entry → localized `role=alert` + cleared entry, session
unharmed; cancel returns; correct entry exits. `lockEngaged =
Boolean(exit_passcode) && !completed`, with `completed` set by `BartGame`'s
existing `onComplete` — the debrief hand-back disengages the passcode gate,
the key swallowing, and the window state all at once. New
`desktop.setKioskLock(locked)` holds fullscreen + always-on-top together
(Tauri-only; the browser rejection is deliberately swallowed — verified no
unhandled rejection). Study Setup gains the Exit passcode field
(`parseExitPasscode` in studyForm: trim, blank → null; committed on blur like
conditions so the trim never fights typing). i18n: five `lock*` keys, en/tr.
Docs: `docs/standalone/KIOSK.md` (SmartScreen-page tone) — honest limits
(plain-text passcode, Ctrl+Alt+Del/Win+L/Cmd+Tab untouched) + a true OS
kiosk via Windows 11 Assigned Access with Win32 `<AllowedApps>` or Shell
Launcher v2 (the instrument is Win32, so the classic UWP-only path is
called out as inapplicable) + macOS MDM note; in the researcher toctree,
guarded by `test_kiosk_page_covers_the_lock_and_the_real_os_kiosk`. No
sidecar behavior change beyond validation — no re-freeze (old binaries
ignore the extra config key). **Verified live** (sidecar + vite +
Playwright/Chrome): padded-passcode trim, back-button/Escape/F11 → prompt,
wrong stays + clears, cancel returns, correct exits, 30-balloon run to
debrief exits unprompted, unlocked run byte-for-byte v1.0.0 (Escape/F11
untouched). Fullscreen/always-on-top itself is untestable outside Tauri —
worth one glance in the next real bundle. Gates: pytest 167 ✅ (+4), npm
test 112 ✅ (+10), tsc ✅, vite build ✅.
