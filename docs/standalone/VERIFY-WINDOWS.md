---
orphan: true
---

# Windows pre-release verification

**Phase 4 · issue 19 · SPEC §12, §15**

The [`windows-release.yml`](../../.github/workflows/windows-release.yml) `smoke-install`
job proves the NSIS installer lays down the right files, but a CI runner is headless and
cannot exercise the participant flow. Before the **first tagged release** (and after any
change to the shell, sidecar packaging, or installer config), one person must run this
checklist end-to-end on a real Windows machine.

- **Target:** a clean **Windows 11** VM or lab machine (no dev toolchain, no prior
  install) — this is what a researcher actually receives.
- **Goal:** confirm the full path works with **zero network**: SmartScreen bypass →
  window opens → Sidecar starts → a Session runs → Session Files are written.

> The Instrument is **unsigned**, so the first launch shows a SmartScreen warning. That is
> expected; the bypass is documented separately.

## Checklist

- [ ] **1. Get the installer.** Download the `bart-installer-windows` artifact from the
  tagged `windows-release.yml` run in GitHub Actions and copy the `.exe` to the test
  machine.

- [ ] **2. Install on a clean Windows 11 machine.** Double-click the installer. It is a
  **per-user** install (no admin prompt) and runs fully offline — the WebView2 runtime is
  embedded, so it must **not** reach the network during install.

- [ ] **3. Bypass SmartScreen.** On "Windows protected your PC", choose
  **More info → Run anyway**. Full instructions for non-technical researchers are in
  [`SMARTSCREEN.md`](SMARTSCREEN.md) (issue 20).

- [ ] **4. Launch and confirm the Sidecar starts.** Open the app. The window should load
  the task UI. Open **Task Manager → Details** and confirm a **`bart-sidecar.exe`** process
  is running alongside the app — this is the local scoring Sidecar (loopback only, never a
  network listener).

- [ ] **5. Run one full Session.** Complete the participant flow start to finish:
  **consent → participant ID entry → pump balloons → collect → debrief**. Pump and collect
  at least one balloon of each color so the run produces scorable trials.

- [ ] **6. Verify Session Files were written.** In Explorer, open
  `%LOCALAPPDATA%\com.metu.bart\sessions\` (paste it into the address bar). Confirm the run
  wrote a `*_events.jsonl`, a `*_metrics.json`, and a `*_config.json`, each prefixed with
  the participant ID. (`%LOCALAPPDATA%` is the Sidecar's working directory, the fallback
  when a Study Preset's `output_dir` is relative.)

- [ ] **7. Verify the config snapshot.** Open the `*_config.json` and confirm it matches
  the Study Preset that was actually run (colors, `max_pumps`, `trials`, hazard family,
  `reward_per_pump`, `language`) — this is the run's reproducible record.

- [ ] **8. Uninstall.** Go to **Windows Settings → Apps → Installed apps**, find
  **BART Instrument**, and choose **Uninstall**. Confirm it removes cleanly.

## Pass criteria

All eight boxes checked: the installer installs per-user and offline, SmartScreen is the
only friction, the Sidecar runs locally, a complete Session writes the three Session Files,
the config snapshot is faithful, and uninstall is clean. Record the tested installer
version and Windows build in the release notes.

## Kiosk lock + practice banner (issue 60 · register F11)

**Phase 4 · issues 43–44 · SPEC §11**

The kiosk in-app lock (fullscreen + always-on-top + passcode-gated exit +
capture-phase Escape/F11 swallow) and the practice banner have unit tests, but the
window-level behavior **only exists in a real Tauri window** — a headless CI runner
and the jsdom tests (which mock `lib/desktop`) cannot exercise it. Run this once on a
real build (`npm run tauri dev` or an installed build) whenever the shell, the window
capabilities, or the kiosk/practice code changes.

> Prerequisite: the window setters must be granted in the capability set. Issue 60's
> static ACL check found them **missing** (`allow-set-fullscreen` /
> `allow-set-always-on-top` not in `capabilities/default.json`) — tracked as issue 64
> (F15). Until 64 lands the lock silently no-ops; run this checklist **after** it.

- [ ] **1. Launch a passcode-locked study.** Run the app with a Study Preset that sets
  `exit_passcode`. Enter the participant flow.

- [ ] **2. Fullscreen engages.** On entering the task the window goes fullscreen (no
  title bar / OS chrome) — not just maximized.

- [ ] **3. Always-on-top holds.** Try to bring another window forward (click another
  app, `Cmd/Alt-Tab`). The task window stays on top / cannot be covered.

- [ ] **4. Escape and F11 are swallowed.** Press **Escape**, then **F11**. Neither
  exits, minimizes, un-fullscreens, nor toggles the shell's own fullscreen — each
  instead opens the researcher passcode prompt.

- [ ] **5. The passcode gates exit.** In the prompt, a wrong code keeps the session
  running (readable error, field cleared); the correct `exit_passcode` exits.

- [ ] **6. The lock disengages at the debrief.** Complete a session to the thank-you
  screen. Fullscreen/always-on-top release and the back control leaves **without**
  asking for the passcode (researcher hand-back).

- [ ] **7. Practice banner on every screen.** Start a **Test Run** (practice). The
  red "TEST RUN — data not recorded" banner is visible on consent, ID, task, and
  debrief, and the debrief shows the no-recording thank-you (issue 59), not "recorded".

- [ ] **8. Practice data stays quarantined.** Confirm the practice session's files
  land under a `practice/` subfolder and **nothing** was appended to the study-wide
  master CSV.

**Pass criteria.** All eight boxes checked on a real Tauri window. Record pass/fail +
the OS/build here or in issue 60's `## Comments`; if anything fails, spin an
evidence-first register row/issue rather than fixing blind.

### Recorded observation — 2026-07-05 (macOS 15, arm64 dev build)

**Fullscreen engagement: PASS (objective, screenshot-verified).** A real
`npm run tauri dev` build (source sidecar on an ephemeral loopback port, healthy at
v1.0.0 → `VersionGuard` passed) was driven into a passcode-locked run and the screen
captured with `screencapture`:

- *Windowed baseline* (Study Setup): the app is a 1280×800 window with the macOS dock,
  menu bar, and other apps all visible behind it.
- *Locked run* (the "Before you begin" screen): the participant view fills the **entire**
  display — no dock, no menu bar, no other windows — i.e. `setKioskLock`'s
  `setFullscreen(true)` visibly engaged. This confirms issue 64's ACL fix end-to-end in
  a real Tauri window (before it, the setter was silently denied).

**always-on-top:** the `core:window:allow-set-always-on-top` grant is validated at the
build/ACL level (issue 64 `cargo check`) and is invoked in the same `setKioskLock` call
whose fullscreen half is now visually confirmed. The "stays in front on Cmd-Tab"
behaviour (box 3) and the passcode/Escape/F11-swallow UX (boxes 4–5) remain a manual
cross-check — they are pure-JS/webview behaviour already covered by the vitest suite.

**Tooling notes for re-runs.** On macOS, `AXFullScreen` / window enumeration is
**unreliable** for a *programmatically* fullscreened window (it moves to its own Space;
reads flip-flop or throw "Invalid index"), and `tauri-driver` is Windows/Linux-only — so
the dependable observable is a screenshot. `app/e2e/verify-kiosk-macos.sh` automates
capturing before/after evidence and reports the Space-membership signal; it needs
Accessibility **and** Screen Recording granted to the terminal/host app.
