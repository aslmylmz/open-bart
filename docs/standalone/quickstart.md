# Quickstart: the Windows desktop instrument

This guide takes a researcher with **no coding background** from a downloaded file to
collected participant data — without ever opening a terminal.

:::{note}
The instrument is a self-contained Windows desktop application: a Tauri shell that hosts
the task UI, with a local Python **Sidecar** that scores each session on the same machine.
Everything runs **offline** — no participant data ever leaves the computer.
:::

## 1. Download

- **Tagged release (recommended).** Download the latest installer from the project's
  **GitHub Releases** page — the Windows asset is named `bart-installer-windows` (a single
  `.exe`).
- **Development build.** If you need an unreleased build, open the most recent
  **`Windows release`** run in the repository's GitHub **Actions** tab and download the
  `bart-installer-windows` artifact.

## 2. Install

Double-click the installer. It is a **per-user** install — **no administrator rights are
required** — and it runs fully offline, because the WebView2 runtime is embedded in the
installer.

Because the app is currently **unsigned**, Windows SmartScreen shows a one-time warning the
first time you launch it. This is expected for in-house research software; follow the
[SmartScreen bypass guide](SMARTSCREEN.md) — in short, click **"More info" → "Run anyway."**

## 3. Create a study

Launch **Dynamic Hazard Rate BART**. It opens in **Study Setup** mode, where you design the task:

1. **Pick a hazard family.** Choose the burst-probability model from the dropdown (for
   example the linear dynamic-hazard model, or a constant-probability baseline).
2. **Set parameters per color.** For each balloon color, set `max_pumps` (the cap $N$) and
   the number of `trials`, along with that family's own parameters. Set the study-level
   `reward_per_pump`, `language`, and an optional RNG `seed`.
3. **Watch the live EV preview.** As you edit, the preview redraws the expected-value curve
   and marks the EV-optimal stop $s^*$ for each color, so you can see your design before
   running a single participant.
4. **Save the study.** Save your design to a `study.json` file via the native file dialog.
   This file is your portable, reusable study definition.

## 4. Run participants

Switch to **Run** mode. RAs can click **Test Run** to practice the flow (a persistent
banner appears and the debrief notes that no data is recorded), or click **Start
real run** for a participant. Each run walks through the full flow:

> **consent → participant ID → balloon task → debrief**

Run **one participant per launch** — when the debrief screen appears the session is
complete, so relaunch the app for the next participant. The balloon sequence is reproducible
from the study's `seed` and the participant's `ID`, so a fixed seed gives every participant
a unique but reproducible sequence.

## 5. Collect data

By default the instrument writes output to:

`%LOCALAPPDATA%\com.metu.bart\sessions\`

(or to the folder set in the study's `output_dir`). Paste that path into File Explorer's
address bar to open it. Each completed session writes **three files**, each prefixed with
the participant ID and a timestamp:

- `*_events.jsonl` — the raw pump-level event log (one JSON object per event).
- `*_metrics.json` — the computed behavioral metrics for that session.
- `*_config.json` — a snapshot of the exact study configuration that was run, so every
  data file is self-describing and reproducible.

## 6. Customize

To run a different design, **load another `study.json`** from Study Setup (or edit the
current one and re-save). The parameters you will adjust most often:

- **Hazard family** — the burst-probability model. See the hazard-family table in
  [the technical documentation](../hazard_families.md) for all available families and their parameters.
- **`max_pumps`** ($N$) — the per-color pump cap; it sets where the EV-optimal stop $s^*$
  sits.
- **`reward_per_pump`** — currency banked per collected pump (it does **not** move the
  optimum).
- **`language`** — participant-facing language, `tr` or `en`.
- **`seed`** — the RNG seed; fix it to give each participant a reproducible balloon sequence,
  or clear it for a completely fresh random run each time.

## 7. Troubleshooting

- **SmartScreen warning on launch.** Expected for an unsigned app — see the
  [SmartScreen bypass guide](SMARTSCREEN.md).
- **WebView2 on older Windows 10.** The task UI needs the Microsoft WebView2 runtime. The
  installer embeds the offline bootstrapper, so this is normally handled automatically; on
  very old, un-updated Windows 10 machines, install the WebView2 Evergreen Runtime from
  Microsoft if the window fails to render.
- **Antivirus quarantines `bart-sidecar.exe`.** The Sidecar is a PyInstaller binary that
  some antivirus engines flag as a generic false positive. If scoring fails to start, add an
  exclusion for it — see [Antivirus false positives](SMARTSCREEN.md#antivirus-false-positives).
