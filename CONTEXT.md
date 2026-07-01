# Dynamic Hazard Rate BART

A research platform for administering and scoring Balloon Analogue Risk Tasks with configurable hazard models, developed at Middle East Technical University (METU).

## Language

### Scientific paradigm

**Dynamic-Hazard BART:**
The core methodological contribution — a modified BART where the conditional burst probability rises linearly within each trial: P(burst at pump k) = k/N. "Dynamic" refers to the hazard increasing with every successive pump, forcing continuous cognitive adaptation and establishing the √N optimal stopping point. This is the project's scientific identity.
_Avoid_: "configurable BART", "multi-hazard BART" (those describe the platform, not the paradigm)

**Hazard Rate:**
The conditional probability of bursting on pump k given survival through pumps 1..k−1. In the dynamic-hazard paradigm this is h(k) = k/N; other hazard families define it differently.
_Avoid_: "explosion probability" (informal and ambiguous about whether it means conditional or cumulative)

**EV-Optimal Stop (s\*):**
The pump count that maximizes expected value for a given balloon capacity N. Under the dynamic-hazard model, s* ≈ √N (exact discrete values: 11/5/2 for N = 128/32/8).
_Avoid_: "optimal strategy", "best number of pumps"

### Platform

**Instrument:**
The standalone Tauri/FastAPI desktop application that administers BART sessions and scores them locally. It is a generalizable, configurable platform supporting 11 hazard families — including static ones like constant-probability and classic uniform — so researchers can run traditional baselines and replicate classic studies alongside the dynamic-hazard paradigm.
_Avoid_: "game", "app" (in formal contexts — "game client" is acceptable for the React component specifically)

**Hazard Family:**
One of the 11 pluggable burst-probability models (linear, constant, uniform, Rayleigh, exponential, Weibull, Gompertz, logistic, lognormal, step, tabular). A study configuration selects a family and its parameters per color; the family's `hazard_vector(n)` method produces the per-pump conditional hazards.
_Avoid_: "explosion model", "burst model"

**Sidecar:**
The Python scoring engine running as a local process alongside the Tauri webview, communicating only over loopback. It owns scoring, validation, hazard-curve computation, and file I/O. The webview never imports Python directly.
_Avoid_: "backend", "server" (implies network-accessible; the sidecar is strictly local)

**Study Preset:**
A saved `study.json` configuration that packages a complete experimental design: color profiles (N, trial count, hazard family per color), reward amount, language, and seed. "Neuroimaging compatibility" is achieved by choosing presets with low N values and fewer trials to produce short session runtimes (<3 min) — it is a configuration concern, not a hardware-synchronization feature. TTL triggers, TR-alignment, and scanner timing are out of scope.
_Avoid_: "template", "profile" (a profile is a per-color config; a preset is the whole study)

**Study Setup:**
The interactive configuration screen in the webview where researchers design their study. It operates through a three-part flow: (1) the UI form collects parameters (colors, hazard families, trial counts, reward), (2) the sidecar validates the candidate config (`/validate-config`) and returns live hazard/survival/EV curve previews (`/preview`) as the researcher edits, (3) the researcher saves the final configuration as a portable `study.json` file via native OS file dialogs. The sidecar is the sole validation authority — the webview never re-encodes pydantic rules.
_Avoid_: "settings", "configuration page"

### Session and scoring

**Session:**
One participant's complete run through the balloon sequence — from the first pump of balloon 1 to submission. A session produces a `GameEvent[]` log and is identified by a `session_id` (UUID).
_Avoid_: "game", "trial" (a trial is a single balloon, not the whole run)

**Trial:**
A single balloon within a session. Each trial ends in either a collect or an explode. A standard session contains 30 trials (10 per color).
_Avoid_: "round", "balloon" (in analytical contexts — "balloon" is acceptable in UI copy)

**Collected Trial:**
A trial where the participant chose to stop and bank their pumps. All behavioral-intention metrics (mean pumps, EV ratio, etc.) use collected trials only, to avoid RNG-truncation bias.
_Avoid_: "successful trial", "cashed-in balloon"

**Color Profile:**
A balloon color's full configuration: display name, hex color, max pumps (N), trial count, and hazard family with parameters. The three default profiles are purple (N=128, low risk), teal (N=32, medium risk), and orange (N=8, high risk).
_Avoid_: "risk tier" (acceptable as informal shorthand but not a defined model concept)

### UI/UX

**Researcher View:**
The Study Setup + EV Preview screens where researchers design experiments. Follows Apple Human Interface Guidelines–inspired design: information-dense but clean, with precise typography, generous whitespace, subtle depth cues, and polished controls. Prioritizes user adoption — a non-technical researcher should feel the tool is professional and trustworthy at first glance. Layout: single scrollable card with clear section dividers — "Study Info" at top, then "Color Profiles" as stacked sub-cards (each with a colored left-border accent matching the balloon's display_hex), then "Save/Load" at bottom. EV Preview curves sit directly below the color profiles. No tabs, no sidebar — everything visible at once so researchers can compare color profiles side by side.
_Avoid_: "admin panel", "dashboard"

**Participant View:**
The Consent → ID → Gameplay → Debrief screens a participant sees during a session. Follows BART research instrument conventions: minimal, high-contrast, distraction-free. Academic legibility is the top priority — large readable text, a centered balloon, clearly labeled action buttons, and no extraneous UI chrome. The participant should never see researcher controls or feel like they are using a developer tool.
_Avoid_: "player view", "game screen"

**Mode Switch:**
The visual transition when the researcher clicks "Start run →" and hands the machine to a participant. The screen should change dramatically enough to signal "this is the participant's view now" — different visual density, different atmosphere, kiosk-like focus. The dark→light theme change is the primary perceptual cue (see ADR 0003).
_Avoid_: "page navigation" (it is a role transition, not just a route change)

**Dark Posture (Researcher):**
The `#0f0f23` deep navy/charcoal background used for the Researcher View. Makes SVG curves and validation errors highly readable; communicates a premium analytical-tool feel following Apple HIG conventions.

**Light Posture (Participant):**
The `#f8f9fa` sterile off-white background with dark text used for the Participant View. Matches BART research instrument conventions: maximal legibility under variable lab lighting, avoids the gaming-prime arousal confound that a dark UI introduces to risk-taking data.

**Familiarity on the Outside, Revolution on the Inside:**
Core design rule for the Participant View. The interaction surface — balloon visual, input mapping, feedback nomenclature, trial sequence — must be instantly recognizable to any cognitive or behavioral researcher who has run a BART before. The methodological innovation (dynamic hazard, configurable families, per-color EV optimization) lives underneath, invisible to the participant. This eliminates learning curves and maximizes comparability with existing BART literature.

Three sub-conventions enforce this:

1. **Standardized Input Mapping.** Space → Pump, Enter → Collect. These are the canonical BART key bindings. They also minimize physical motor-movement artifacts in fMRI/EEG scanner environments (only right-thumb and right-index-finger responses needed).

2. **Canonical Nomenclature.** All participant-facing labels and scored CSV column names use standard BART terminology: "Balloon", "Pump", "Collect", "Pop", "Total Earnings". This ensures output files are instantly recognizable in SPSS, R, or Excel without a codebook.

3. **Default Paradigm Sequence.** The out-of-the-box study loads the validated 3-color randomized block sequence (Purple N=128, Teal N=32, Orange N=8, 10 trials each) representing distinct low/medium/high-hazard risk environments. A researcher can run a valid study without changing any settings.

**Gameplay Layout:**
The canonical screen arrangement during active gameplay, following jsPsych/PEBL BART conventions. Vertically stacked, horizontally centered:
1. **Top bar** — understated gray; trial counter left (`Balloon s/N`), cumulative earnings right (`Total $X`).
2. **Balloon** — centered colored shape that grows with each pump; the largest visual element; no text inside.
3. **Current earnings** — large bold counter below the balloon, outside the stimulus (`Current: $X`). Displayed separately for legibility at all balloon sizes.
4. **Action buttons** — centered, standard-sized, neutral styling with keyboard hints on the labels: `Pump (Space)` / `Collect (Enter)`.
5. **Progress dots** — horizontal timeline at the bottom; green = collected, red = exploded, hollow = upcoming. Gives the participant a sense of session progress without being distracting.

### Persistence

**Session Files:**
The per-participant output written to disk on session completion: a raw event telemetry file (`.jsonl`, one JSON object per GameEvent) and a scored metrics file (`.json`, the full BARTMetrics output). Each is uniquely named as `[CandidateID]_[Timestamp]_events.jsonl` / `[CandidateID]_[Timestamp]_metrics.json` to prevent overwriting.
_Avoid_: "log file", "results file" (ambiguous — distinguish between raw telemetry and scored output)

**Master CSV:**
A single shared spreadsheet (`[StudyTitle]_results.csv`) in the output directory. The sidecar appends one row per completed session, creating the file with a header row if it does not yet exist. This eliminates manual post-study merging for researchers using Excel or SPSS.
_Avoid_: "results CSV", "output CSV" (use "master CSV" to distinguish from the per-session metrics JSON)

**Output Directory:**
The researcher-configured path where session files and the master CSV are written. Read from `TaskConfig.output_dir`. Falls back to the OS-native application data directory on permission errors or unresolvable relative paths.
_Avoid_: "data folder", "save location"
