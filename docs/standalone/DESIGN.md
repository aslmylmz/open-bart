---
orphan: true
---

# Standalone Instrument — Design & Roadmap

**Status:** planning (branch `feat/standalone-instrument`)
**Author:** Ahmet Selim Yılmaz
**Last updated:** 2026-06-23

> **See [`SPEC.md`](SPEC.md) for the authoritative implementation brief.** This
> document is the higher-level rationale; where the two differ (notably the hazard
> model — now a curated family library, not free-form expressions), `SPEC.md` wins.

## 1. Goal

Wrap the existing BART game client and Python scoring engine into a **single,
offline, double-clickable desktop application** that a researcher with no coding
background can install and deploy in a lab, configure the task parameters
(including the hazard structure) through a UI, run participants, and collect
event-level data and computed metrics locally — with no network connection.

This standalone instrument — not the current embeddable React component — is
intended as the eventual **JOSS submission**. It is a stronger statement of need
(a reusable, no-code, reproducible measurement instrument), with clear scholarly
effort and novelty.

## 2. Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| Runtime / packaging | **Tauri + Python sidecar** | Reuses the React UI in the OS webview; small native binaries; keeps the tested Python engine intact as a frozen sidecar. |
| Configurability | **Full hazard-function config — via a *safe* hazard library** | Researchers need real design freedom, but lab machines must never `eval()` user-supplied code. |
| Repository | **Same repo; package `scoring`** | One source of truth; `pyproject.toml` also closes the current JOSS packaging gap. |

### 2.1 Safety constraint on "full hazard config"

"Full configurability" is implemented as a **safe hazard library**, never as
arbitrary code execution:

- **A curated library of ~10 parameterized families** grounded in survival
  analysis (linear/Rayleigh, constant/Bernoulli, Weibull, exponential, Gompertz,
  logistic, log-normal, classic-uniform, step, power) — see `SPEC.md` §7.
- **A tabular escape hatch:** an explicit, validated per-pump hazard array — data,
  not code.

There is **no free-form expression or code entry**: configurability comes entirely
from the curated families' validated parameters. This covers a wide space of hazard
and outcome distributions without any injection surface.

## 3. Target architecture

One pydantic `TaskConfig` is the **single source of truth**. It feeds both the
task UI (how balloons burst) and the scoring engine (where the EV-optimum is), so
changing a parameter propagates everywhere automatically.

```
TaskConfig  (pydantic, in the scoring package)
  colors · N per color · hazard family + params · trials · reward · seed · i18n · output dir
        │
        ├─► React / Vite frontend  (inside the Tauri OS webview)
        │       renders the task from config · bursts client-side from the
        │       precomputed hazard vector · logs pump-level events ·
        │       POSTs the session payload to the local scoring endpoint
        │
        ├─► Python sidecar  (FastAPI on 127.0.0.1, frozen with PyInstaller)
        │       /validate-config · /preview (hazard, survival, EV, optimum) ·
        │       /score · /write-output     — imports the `scoring` package
        │
        └─► Rust  (Tauri core, kept thin)
                window / kiosk mode · load + save study.json · spawn / health-check /
                kill the sidecar · native file dialogs · strict offline CSP + minimal allowlist
```

**Key reuse:** the web client already "submits a typed session payload to a
scoring endpoint." In the desktop app the **sidecar *is* that endpoint**
(localhost), so the web and desktop builds share one contract — the UI is not
forked.

## 4. Repository layout (target)

```
metu-risk-persona/
├── pyproject.toml              # `scoring` installable + versioned (also fixes JOSS gap)
├── scoring/
│   ├── bart.py                 # engine (generalized to numeric optima)
│   ├── config/                 # NEW: TaskConfig, hazard families, safe evaluator
│   └── schemas/
├── app/
│   ├── src/                    # React / Vite SPA (BartGame task UI + Study-Setup)
│   ├── src-tauri/              # Rust shell (lifecycle, files, config)
│   └── sidecar/                # Python entrypoint wrapping `scoring` + PyInstaller spec
├── tests/                      # extended: numeric optima across hazard families
└── docs/standalone/            # this design doc + researcher quickstart
```

## 5. `TaskConfig` schema (sketch)

```
TaskConfig
  schema_version: str
  title: str                       # study label, shown in debrief / data
  language: "tr" | "en" | ...       # i18n for participant-facing text
  reward_per_pump: float            # currency units banked per pump
  seed: int | null                  # RNG seed for reproducible burst sequences
  output_dir: path                  # where session data is written
  colors: list[ColorProfile]

ColorProfile
  name: str                         # e.g. "purple"
  label: str                        # participant-facing label
  N: int                            # max capacity
  trials: int                       # number of balloons of this color
  hazard: HazardSpec

HazardSpec  (discriminated union)
  family: "linear" | "constant" | "power" | "logistic" | "exponential"
          | "tabular" | "expression"
  params: { ... }                   # family-specific, validated
  # expression: a sandboxed formula string over k, N (advanced mode)
```

On load, `TaskConfig` **precomputes and validates** per color:

- the hazard vector `h[1..N]` with `0 ≤ h(k) ≤ 1` for all `k`,
- the survival vector `S(s) = ∏_{k=1}^{s} (1 − h(k))`,
- the expected value `EV(s) = value(s) · S(s)` where `value(s) = s · reward_per_pump`,
- the **numeric** EV-optimum `s* = argmax_s EV(s)`.

Both the task (stochastic bursting) and the scoring engine consume these
precomputed vectors, guaranteeing they agree.

## 6. Scoring changes (what full hazard config forces)

The closed-form `s* = √N` holds **only** for the linear hazard `k/N`. With
arbitrary families the optimum must be computed **numerically**:

- Generalize `_compute_ev` / `_compute_ev_optimal` to take a `HazardSpec` (or the
  precomputed vectors) and return `argmax_s EV(s)`.
- **Audit out** hardcoded constants (`128 / 32 / 8` and `11 / 5 / 2`, e.g. in
  `_calculate_risk_adjustment_score`) so every reference flows from `TaskConfig`.
- Documentation reframes `√N` as the **documented special case** of linear hazard;
  the general statement is "the optimum is the numeric maximizer of `EV(s)`."
- **Regression guard:** tests assert the linear family still reproduces `11 / 5 / 2`
  and the `√N` approximation — the existing behavior must not change.

A live **EV-curve + optimum preview** in the Study-Setup screen (the researcher
sees their design before running) becomes a headline feature.

## 7. Data & offline model

- **No network.** Strict Tauri CSP blocks remote origins; the sidecar binds only
  to `127.0.0.1`; the Tauri allowlist is minimal.
- Per session, written to the configured output directory:
  - raw pump-level event log (JSONL),
  - session metadata (config snapshot, participant ID, timestamps),
  - computed metrics (JSON + CSV),
  - optional personalized debrief (HTML/PDF) — engagement only, as today.
- The config snapshot embedded in each session makes a study **reproducible and
  self-documenting**: the exact parameters travel with the data.

## 8. Distribution

- Tauri bundles: Windows (`.msi`/`.exe`), macOS (`.dmg`/`.app`), Linux
  (`.AppImage`/`.deb`).
- The PyInstaller sidecar is bundled via Tauri's `externalBin` (sidecar) mechanism;
  **a per-OS sidecar must be built on each OS** → GitHub Actions matrix
  (windows / macos / ubuntu runners) on tagged releases.
- Webview runtimes: WebView2 (Windows, bootstrapper for old machines), WKWebView
  (macOS), WebKitGTK (Linux).

## 9. Top risks (de-risk early, before UI work)

1. **PyInstaller + numpy/scipy sidecar** across all three OSes — scipy freezing
   needs hooks and bloats binaries. Prove a "hello-score" sidecar bundles and runs
   on Win/macOS/Linux *before* building UI. **(Highest technical risk.)**
2. **Signing / notarization** for a clean non-coder double-click — macOS needs an
   Apple Developer account ($99/yr) + notarization; Windows wants a code-signing
   cert or users hit SmartScreen. Procurement lead-time, not code — decide owner now.
3. **Safe hazard evaluator** — the sandboxed expression mode must be airtight
   (whitelisted AST; fuzz-tested).

## 10. Out of scope (for now)

- **fMRI/EEG-grade timing.** Webview timing is fine for behavioral labs but not for
  sub-frame neuroimaging precision; that would argue for a PsychoPy path and is a
  separate future track.
- Multi-participant networking / central data collection — the instrument is
  single-machine and offline by design.

## 11. Phased plan

- **Phase 0 — Foundations** *(pure Python + React; also upgrades current JOSS readiness)*
  `pyproject.toml`; extract `TaskConfig`; generalize EV/optimum to safe hazard
  families with numeric optima; audit out hardcoded constants; decouple the client
  from Next.js into a static Vite build. Tests prove the linear case is unchanged.
- **Phase 1 — Sidecar**
  FastAPI wrapping `scoring` (`/validate-config`, `/preview`, `/score`,
  `/write-output`); PyInstaller freeze proven on three OSes.
- **Phase 2 — Tauri shell**
  Load the Vite frontend; sidecar lifecycle + health check; native file dialogs;
  kiosk/fullscreen; strict offline CSP.
- **Phase 3 — No-code config UX**
  Study-Setup (hazard picker + params, N/trials/reward/i18n/output, live EV-curve
  preview, save/load `study.json`) and Run mode (consent → participant ID → task →
  local data + debrief).
- **Phase 4 — Distribution**
  CI matrix builds + installers + signing; WebView2 handling; researcher quickstart.
- **Phase 5 — JOSS**
  Rewrite paper/docs around the instrument; new Zenodo archive.

## 12. Open questions

- Who owns the macOS Apple Developer account and the Windows code-signing cert?
- Config file format for `study.json`: JSON (machine-first) vs YAML (human-first)?
- Default shipped study = the validated `128 / 32 / 8` linear configuration.
- Frontend build tool confirmed as Vite (decouples cleanly from Next.js)?
