# 64 — Kiosk lock silently no-ops: window setters are not in the Tauri capability set

**Bug · depends on: none · found by: [60](60-kiosk-real-run-verification.md)**

Status: done

## Context

Cycle-02 audit finding F15. Surfaced by issue 60's real-run verification — via a
static ACL check rather than a live GUI run, so it is evidence-first, not a blind
fix.

The kiosk in-app lock (issue 44) engages the native window through
`setKioskLock` (`app/src/lib/desktop.ts:44`), which calls `win.setFullscreen()` and
`win.setAlwaysOnTop()`. The app shell's F11 toggle (`toggleFullscreen`, same file)
calls `win.setFullscreen()` too. In Tauri v2 every core-plugin command is gated by
the capability ACL, and the only capability file
(`app/src-tauri/capabilities/default.json`) grants `core:default`, whose
`core:window:default` set is **28 getters only** (`allow-is-fullscreen`,
`allow-is-always-on-top`, …). The setters `core:window:allow-set-fullscreen` and
`core:window:allow-set-always-on-top` exist as grantable permissions but are **not**
in the default set and are not added anywhere.

Runtime consequence in a real build: both calls are **ACL-denied and rejected**.
`setKioskLock`'s callers swallow the rejection (`.catch(() => {})`,
`app/src/run/RunFlow.tsx:95,97`), so **fullscreen and always-on-top never engage** —
the participant window is not actually locked. `toggleFullscreen`'s F11 path is
likewise inert. The JS-level Escape/F11 key swallow and the passcode gate still work
(they are not window APIs), so the lock looks partially functional. The webview unit
tests miss all of this because they mock `lib/desktop` (`RunFlow.test.tsx`,
`desktop.test.ts`) — the behavior only exists in a real Tauri window.

Evidence: `app/src-tauri/gen/schemas/acl-manifests.json` → `core:window`
`default_permission` is getters-only; `allow-set-fullscreen` /
`allow-set-always-on-top` present as grantable but ungranted.
`app/src-tauri/capabilities/default.json` lists no window setter.

## Scope

- [ ] Add `core:window:allow-set-fullscreen` and `core:window:allow-set-always-on-top`
      to `app/src-tauri/capabilities/default.json` (keep the capability set minimal —
      only the two setters the kiosk lock and F11 toggle actually invoke).
- [ ] Guard against silent regression: prefer a check that fails if the capability
      set drops a window permission `setKioskLock`/`toggleFullscreen` depend on
      (e.g. a test asserting `default.json` grants the two setters), since the
      webview mocks can't see the ACL.

## Acceptance

- In a real Tauri run (issue 60's checklist) the kiosk lock engages fullscreen +
  always-on-top and F11 toggles fullscreen; the ACL no longer rejects the calls.
- The capability set stays minimal (no shell/net/extra window powers); the four
  gates stay green.

## Comments

Source: 2026-07-04, surfaced by issue 60's real-run verification (register row F11 →
new row F15). This is the defect issue 60 was created to catch. Not fixed blind: the
grant is justified by the ACL manifest, but recording it as its own slice keeps the
one-change-at-a-time discipline and lets issue 60's live GUI observation confirm the
fix end-to-end. Left `ready-for-agent` for an explicit implement command.

**Done 2026-07-04.** Added `core:window:allow-set-fullscreen` and
`core:window:allow-set-always-on-top` to `app/src-tauri/capabilities/default.json`
(only those two — the capability set stays minimal; description updated). Regression
guard: `app/src/lib/capabilities.test.ts` imports the shipped capability file and
asserts both setters are granted; it fails red without them (the webview mocks can't
see the ACL). No `/score` or `TaskConfig` change → no re-freeze.

Verified at the ACL level, not just the schema: `cargo check` in `app/src-tauri`
re-ran `build.rs`/`tauri-codegen` (which validate capabilities) and finished clean, so
the two permission ids are accepted by a real Tauri build. Four gates green (`vitest`
138, `tsc --noEmit`, `vite build`, `pytest` 182). The remaining live GUI observation
that the lock now visibly engages fullscreen + always-on-top is issue 60's owed
human step — now unblocked.
