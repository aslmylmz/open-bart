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
