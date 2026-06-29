---
orphan: true
---

# Standalone BART Instrument — Build Specification & Agent Brief

> **Purpose of this document.** This is a self-contained specification for building
> the offline desktop version of the Dynamic Hazard Rate BART. It is written to be
> fed to a coding agent (or a new developer) as the kickoff brief. Read it top to
> bottom; you should not need any other document to start. It supersedes the
> earlier `DESIGN.md` (kept for rationale) wherever they differ — in particular the
> hazard model is now a **curated library of parameterized families**, not a
> free-form expression evaluator.

**Repo:** `metu-risk-persona` · **Work branch:** `feat/standalone-instrument`
(never commit this work to `main`). **Last updated:** 2026-06-29.

---

## 0. How to use this document

1. Work only on branch `feat/standalone-instrument`. Push there; open progress is
   tracked on GitHub. **Do not merge to `main`** unless explicitly told.
2. Develop and test **locally on macOS**. Windows builds are produced by CI (see
   §12). No web deployment is involved at any point.
3. Reuse the existing Python scoring engine and pydantic schemas (§2). Do not
   rewrite them; extend them.
4. Follow the phased plan (§17). Each phase has acceptance criteria — satisfy them
   before moving on.
5. Conventions in §19 are mandatory (commit style; **no `Co-Authored-By` lines**).

---

## 1. Project context & goal

We have a working, validated research instrument — a "dynamic hazard rate"
Balloon Analogue Risk Task (BART) — currently deployed as a full-stack web app.
The burst probability rises with each pump, `P(burst at pump k) = k/N`, which
makes the expected-value-optimal stopping point reachable (≈ `√N`) instead of the
unreachable `N/2` of the classic BART. This lets the task separate *calibrated*
risk-taking from *gross exposure*.

**Goal:** ship a **single, offline, double-clickable desktop application** that a
researcher with no coding background can install on a lab machine, configure
(including the **hazard structure**, chosen from a curated set of parameterized
families), run participants on, and collect event-level data + computed metrics —
all fully offline. This standalone instrument is intended to become the project's
JOSS submission.

Primary target OS: **Windows** (broadest lab adoption). Development machine:
**macOS (Apple Silicon)**. See §12 for how we reconcile that.

---

## 2. What already exists (reuse inventory)

All paths are repo-relative. Verified present and working (23 tests pass, docs
build clean).

| Asset | Path | Notes |
|---|---|---|
| Scoring engine | `scoring/bart.py` (~1355 lines) | EV calibration + 40+ metrics. Has `_compute_ev`, `_compute_ev_optimal`, `COLOR_PROFILES`, and `_calculate_risk_adjustment_score` (⚠ contains hardcoded optima `11/5/2`). |
| Pydantic schemas | `scoring/schemas/__init__.py` (~481 lines) | `GameEvent`, `EventPayload`, `BARTMetrics`, session models. ⚠ still Pydantic-V1-style validators (deprecation warnings). |
| Event validators | `scoring/schemas/game_events.py` | |
| React game client | `app/src/BartGame.tsx` (~1060 lines) | React component (now a Vite SPA); renders the 3-colour task, logs pump-level events via `performance.now()`, **POSTs a typed session payload to a scoring endpoint**. |
| MC verification | `scripts/monte_carlo_ev.py` | Simulates 100k optimal sessions; self-creates `output/figures/`. |
| Synthetic data | `scripts/generate_synthetic.py` | |
| Tests | `tests/test_scoring.py` (23 tests), `conftest.py` | `conftest.py` puts repo root on `sys.path` so `import scoring` works without install. |
| Docs | `docs/` (Sphinx + MyST, Read the Docs) | |
| Deps | `requirements.txt` | numpy, scipy, pydantic (+ matplotlib/pandas for scripts). |

**Not present yet (you will add):** `pyproject.toml`, the `app/` desktop wrapper,
the `TaskConfig`/hazard-family code, and CI workflows.

---

## 3. Honest difficulty assessment

Reusing the engine and the React UI is the easy part — the scoring code is pure
Python and the client already speaks to a "scoring endpoint" we can point at a
local sidecar. The genuinely non-trivial parts are:

1. **Freezing the Python sidecar with PyInstaller including numpy/scipy** and
   having it run on Windows. (Highest risk. De-risk first.) Check whether scipy is
   actually needed by the engine; if not, drop it from the sidecar to shrink the
   binary.
2. **Producing Windows binaries from a Mac.** PyInstaller and Tauri do **not**
   cross-compile; Windows artifacts must be built on Windows (we use CI). See §12.
3. **The no-code config UX** (hazard family picker with a live EV-curve preview).

Everything else is standard wiring.

---

## 4. Locked technical decisions

| Decision | Choice |
|---|---|
| Desktop runtime | **Tauri** (Rust shell + OS webview) |
| Scoring runtime | **Python sidecar** (FastAPI on `127.0.0.1`, frozen with PyInstaller) |
| Frontend | **React + Vite** (decouple `BartGame.tsx` from Next.js into a static SPA) |
| Repo | **Same repo, separate branch**; package `scoring` via `pyproject.toml` |
| Hazard config | **Curated library of parameterized families** (≈10 + tabular escape hatch); **no free-form code/expression entry** |
| Dev / target | Develop+test on **macOS**; ship **Windows** via CI |
| Network | **Fully offline.** Sidecar binds to localhost only; strict CSP. |

---

## 5. Architecture

A single pydantic `TaskConfig` is the **one source of truth**: it drives both how
balloons burst (task) and where the EV-optimum sits (scoring). Change a parameter
and everything downstream follows.

```
TaskConfig  (pydantic, in the scoring package)
  colors · per-color N · hazard family + params · trials · reward · seed · i18n · output dir
        │
        ├─► React/Vite frontend  (inside the Tauri OS webview)
        │       renders task from config · bursts client-side from the precomputed
        │       hazard vector · logs pump-level events · POSTs session to local endpoint
        │
        ├─► Python sidecar  (FastAPI @ 127.0.0.1, PyInstaller-frozen)
        │       /healthz · /validate-config · /preview · /score · /write-output
        │       imports the existing `scoring` package
        │
        └─► Rust (Tauri core, thin)
                window/kiosk · load+save study.json · spawn/health-check/kill sidecar
                native file dialogs · strict offline CSP + minimal allowlist
```

**Key reuse:** the web client already POSTs its session payload to a scoring
endpoint. In the desktop app, the **sidecar is that endpoint** (localhost), so the
UI contract is unchanged.

---

## 6. `TaskConfig` schema (single source of truth)

Implement as pydantic v2 models in `scoring/config/` (new subpackage). Sketch:

```
TaskConfig
  schema_version: str
  title: str                      # study label, embedded in every data file
  language: "tr" | "en"           # participant-facing i18n
  reward_per_pump: float          # currency units per banked pump (does NOT affect optimum)
  seed: int | null                # RNG seed → reproducible burst sequences
  output_dir: str                 # local folder for session data
  colors: list[ColorProfile]      # typically 3, but allow 1..K

ColorProfile
  name: str                       # internal id, e.g. "purple"
  label: str                      # participant-facing
  display_hex: str
  max_pumps: int                  # N — hard cap on pumps for this color
  trials: int                     # number of balloons of this color
  hazard: HazardSpec

HazardSpec (discriminated union on `family`)
  family: one of the families in §7
  params: { family-specific, validated }
```

**On load**, `TaskConfig` precomputes and caches, per color, over `k = 1..N`:

- hazard vector `h[k]`, validated to `0 ≤ h[k] ≤ 1`;
- survival `S(s) = Π_{k=1..s} (1 − h[k])`, with `S(0)=1`;
- expected value `EV(s) = reward_per_pump · s · S(s)`;
- numeric optimum `s* = argmax_{1≤s≤N} EV(s)`.

Both the task (stochastic bursting) and scoring (optimum reference) consume these
**same** cached vectors, so they cannot disagree.

---

## 7. Hazard model — survival framing + the curated family library

### 7.1 Framing (this is the robust, defensible structure)

Treat each pump as a step in a discrete **survival process**. The per-pump
*conditional hazard* `h(k) = P(burst exactly at pump k | survived pumps 1..k-1)`
fully determines the **burst-pump distribution** `f(k) = S(k-1)·h(k)` and hence the
EV landscape. Different hazard shapes correspond to different classical lifetime
distributions. By offering a curated set of hazard families — each with a few
validated numeric parameters — we cover a wide space of "outcome distributions"
(Bernoulli/geometric, Rayleigh, Weibull, Gompertz, log-normal, …) **without ever
executing user-supplied code**. The optimum is always found numerically, so no
family needs a closed form.

The current task (`h(k)=k/N`, optimum ≈ `√N`) is exactly the **linear / Rayleigh**
member of this family — the `√N` result becomes a documented special case, not the
only option.

### 7.2 The families (≈10 + a tabular escape hatch)

`r` = `reward_per_pump`. All hazards are clamped to `[0,1]`; pumps are capped at
`max_pumps` (and effectively at the point where `S` reaches ~0). Optima below are
sanity-check closed forms; the engine computes them numerically.

| # | Family | Conditional hazard `h(k)` | Parameters | Burst-time law | Hazard shape | Optimum (sanity) |
|---|---|---|---|---|---|---|
| 1 | **Linear** (default) | `k / N` | `N` | ≈ Rayleigh | linear ↑ | `≈ √N` |
| 2 | **Constant / Bernoulli** | `p` | `p ∈ (0,1)` | Geometric | flat | `≈ 1/p` |
| 3 | **Weibull (power)** | `(m/N)·(k/N)^(m-1)` | `N`, shape `m>0` | Weibull | `m<1` ↓, `m=1` flat, `m=2` linear, `m>2` accel. | numeric |
| 4 | **Rayleigh** | `k / σ²` | `σ` | Rayleigh | linear ↑ | `≈ σ` |
| 5 | **Exponential** | `1 − e^(−λ)` (const) | rate `λ>0` | Geometric | flat | `≈ 1/(1−e^(−λ))` |
| 6 | **Gompertz** | `a·e^(b·k)` | `a>0`, `b>0` | Gompertz | exponential ↑ | numeric |
| 7 | **Logistic / sigmoid** | `H_max / (1 + e^(−r_s(k − k0)))` | `H_max≤1`, midpoint `k0`, steepness `r_s` | logistic | S-curve (safe→ramp) | numeric |
| 8 | **Log-normal** | hazard of a log-normal burst time | `μ`, `σ` | Log-normal | rise then fall (non-monotone) | numeric |
| 9 | **Classic uniform (Lejuez)** | `1 / (N − k + 1)` | `N` | Uniform{1..N} | ↑ to 1 | `≈ N/2` |
| 10 | **Step / piecewise-constant** | level `p_i` on segment `i` | breakpoints `[b1,…]`, levels `[p1,…]` | mixture | regime steps | numeric |
| 11 | **Tabular** (escape hatch) | explicit `h[1..N]` array | validated array in `[0,1]` | arbitrary (data, not code) | any | numeric |

Implementation notes for each family:
- Each family is its own pydantic model with typed, range-validated params and a
  `hazard_vector(N) -> list[float]` method. The discriminated union picks the model
  from `family`.
- **Validation:** reject configs where any `h(k) > 1` before the intended
  `max_pumps`, where `S` collapses to 0 before the optimum is meaningful, or where
  params are out of domain. Surface clear error messages (the UI shows them).
- **Reproducible bursting:** the task draws `u ~ Uniform(0,1)` per pump (seeded RNG)
  and bursts when `u < h(k)`. Same RNG, same seed ⇒ same sequence (for replay/QA).
- `reward_per_pump` scales EV uniformly and therefore does **not** move the
  optimum; keep that explicit in code and docs.

### 7.3 Live preview (a headline feature)

The Study-Setup screen calls `/preview` and plots, for the chosen family+params:
the hazard `h(k)`, the survival `S(s)`, the EV curve, and the marked numeric
optimum `s*`. Researchers *see* their design before running a single participant.

---

## 8. Scoring engine changes

The engine currently assumes the linear model with hardcoded optima. Generalize it
without regressing existing behavior:

1. Route all optima through the precomputed `TaskConfig` vectors (§6). Generalize
   `_compute_ev` / `_compute_ev_optimal` to accept a `HazardSpec` / precomputed
   vectors and return the **numeric** `argmax`.
2. **Audit out** hardcoded constants `128/32/8` and `11/5/2` (notably in
   `_calculate_risk_adjustment_score` and `COLOR_PROFILES`); derive everything from
   config.
3. **Regression guard (must pass):** with the default linear config
   (`N = 128/32/8`), the engine still yields optima `11/5/2` and the `√N`
   approximation, and all 23 existing tests still pass. Add new tests covering each
   hazard family's numeric optimum (e.g. constant-`p` ⇒ `≈ 1/p`; uniform ⇒ `≈ N/2`).
4. While here, migrate the Pydantic V1-style validators to V2 (`@field_validator`,
   `min_length`) to clear the deprecation warnings.

---

## 9. Python sidecar (`app/sidecar/`)

- FastAPI app bound to `127.0.0.1` on an ephemeral port; the port is handed to the
  frontend by the Rust layer at launch.
- Endpoints: `GET /healthz`; `POST /validate-config` (→ ok/errors);
  `POST /preview` (→ hazard/survival/EV vectors + `s*`); `POST /score` (→
  `BARTMetrics`); `POST /write-output` (→ writes session files, returns paths).
- Imports the installed `scoring` package (no code duplication).
- Frozen with PyInstaller into a per-OS sidecar binary, bundled via Tauri's
  `externalBin` (sidecar) mechanism. Build a tiny "hello-score" sidecar and prove
  it freezes + runs on Windows **before** building any UI.

---

## 10. Tauri shell (`app/src-tauri/`)

Keep Rust thin. Responsibilities:
- Create the window; offer a **kiosk/fullscreen** run mode for labs.
- Load/save `study.json` (the serialized `TaskConfig`) via native file dialogs.
- Spawn the sidecar on launch, health-check it (`/healthz`), pass its port to the
  frontend, and kill it on exit.
- **Strict offline posture:** CSP blocks all remote origins; Tauri allowlist
  minimal (no shell/http to the internet); sidecar reachable only on localhost.

---

## 11. Config UX (frontend)

Two modes in the Vite SPA:
- **Study Setup** (for the researcher): pick a hazard family from a dropdown, edit
  its parameters with validated inputs, set per-color `N`/trials, reward, language,
  RNG seed, and output folder; see the **live EV-curve + optimum preview**; save /
  load `study.json`. Ship a default study = the validated `128/32/8` linear config.
- **Run** (for the participant): consent screen → participant ID → the task
  (reuse `BartGame.tsx` logic) → local data write → optional personalized debrief
  (engagement only, as today).

---

## 12. Cross-platform strategy (macOS dev → Windows target)

**The constraint:** neither PyInstaller nor Tauri cross-compiles cleanly from
macOS to Windows. So:

- **Daily development & functional testing → macOS, fast loop.**
  - Engine: `pytest`. Frontend: `vite dev` (hot reload). Whole app:
    `tauri dev` runs natively on macOS with a Mac-native sidecar. ~95% of logic and
    UX work and testing happens here, quickly.
- **Windows product builds → GitHub Actions (`windows-latest` runner).**
  - CI builds the PyInstaller **Windows** sidecar `.exe`, bundles it into Tauri,
    and produces a Windows installer (`.msi` via WiX, or NSIS `.exe`). Artifacts are
    uploaded on every push to the branch (this also *is* the open progress record).
  - The CI Windows build is the **source of truth** for the shipped product, since
    the Mac dev build uses a different toolchain (WKWebView vs WebView2).
- **Local Windows verification (periodic, before releases).** Recommended:
  - A **Windows 11 VM on the Mac** — Parallels Desktop (best on Apple Silicon) or
    free UTM. On Apple Silicon this is Windows-on-ARM, which runs the x64 build
    under emulation — fine for functional smoke tests. WebView2 ships with Win11.
  - And/or download the CI artifact and test on a **real lab-like Windows machine**
    before any release (it is the actual deployment target).
- **Keep platform-specific code minimal**; rely on Tauri's cross-platform APIs.
  Expect differences in file paths, the webview engine, and signing.

You do **not** need a Windows machine to *develop*; you need CI to *build* and a VM
/ lab box to *verify*.

---

## 13. Data & offline model

- **No network, ever.** Per session, write to the configured output dir:
  - raw pump-level event log (JSONL),
  - session metadata **including a snapshot of the full `TaskConfig`** (makes each
    dataset reproducible and self-documenting),
  - computed metrics (JSON + CSV),
  - optional debrief (HTML/PDF) — engagement only.
- Filenames namespaced by study title + participant id + timestamp.

---

## 14. Distribution & signing

- Tauri bundles per OS; Windows is the priority (`.msi`/`.exe`).
- **Code signing decision (flag to project owner):** unsigned Windows builds
  trigger SmartScreen ("More info → Run anyway"). For internal lab use that may be
  acceptable at first; a proper OV/EV code-signing cert removes the warning
  (procurement lead time — decide early). macOS notarization only matters if a Mac
  build is also distributed (Apple Developer account, $99/yr).

---

## 15. Testing strategy

- **Engine:** extend `tests/` — regression (linear ⇒ `11/5/2`, `√N`) + a case per
  hazard family (numeric optimum vs closed-form sanity value).
- **Sidecar:** API tests hitting the FastAPI endpoints with sample configs/sessions.
- **Frontend:** component/interaction tests for the task and the Study-Setup form
  validation.
- **End-to-end (macOS):** `tauri dev`, run a full session, confirm data files +
  metrics are written and match the engine's direct output.
- **Windows smoke (CI artifact / VM):** install, launch, run one session, confirm
  output before tagging a release.

---

## 16. Target repo layout

```
metu-risk-persona/
├── pyproject.toml              # makes `scoring` installable + versioned
├── scoring/
│   ├── bart.py                 # generalized to numeric optima
│   ├── config/                 # NEW: TaskConfig + hazard families (§6, §7)
│   └── schemas/
├── app/
│   ├── src/                    # React/Vite SPA (BartGame task UI + Study Setup + Run)
│   ├── src-tauri/              # Rust shell
│   └── sidecar/                # Python FastAPI entrypoint + PyInstaller spec
├── .github/workflows/          # NEW: Windows build + (optional) docs/CI
├── tests/                      # extended
└── docs/standalone/            # this SPEC + DESIGN + researcher quickstart
```

---

## 17. Phased plan (with acceptance criteria)

- **Phase 0 — Foundations** *(pure Python/React; no Rust/PyInstaller yet)*
  - Add `pyproject.toml`; make `scoring` installable. Extract `TaskConfig` +
    implement all §7 hazard families with validation + numeric optima. Audit out
    hardcoded constants. Decouple `BartGame.tsx` into a static Vite build.
  - **Done when:** `pip install -e .` works; new family tests + the 23 existing
    tests pass; the default linear config still gives `11/5/2` and `√N`;
    `vite build` produces a static SPA.
- **Phase 1 — Sidecar**
  - FastAPI wrapping `scoring`; PyInstaller freeze.
  - **Done when:** a frozen "hello-score" sidecar runs on Windows (CI) **and** the
    full sidecar scores a sample session identically to calling `scoring` directly.
- **Phase 2 — Tauri shell**
  - Load the Vite SPA; sidecar lifecycle + health check; file dialogs; kiosk mode;
    strict offline CSP.
  - **Done when:** `tauri dev` on macOS runs a full session end-to-end with data
    written locally and zero network calls.
- **Phase 3 — Config UX**
  - Study Setup (family picker + params + **live EV-curve preview** + save/load
    `study.json`) and Run mode (consent → ID → task → data → debrief).
  - **Done when:** a non-coder can change the hazard family + parameters in the UI,
    see the optimum update, save a study, and run it.
- **Phase 4 — Distribution**
  - GitHub Actions Windows build → installer artifact; signing decision; researcher
    quickstart docs.
  - **Done when:** a tagged push yields a downloadable Windows installer that
    installs and runs a session on a clean Windows VM.
- **Phase 5 — JOSS**
  - Rewrite paper/docs around the configurable offline instrument; new Zenodo
    archive.

---

## 18. Risks (most → least dangerous)

1. PyInstaller bundling numpy/scipy on Windows — prove early; trim scipy if unused.
2. Tauri sidecar lifecycle/port handoff and the macOS-dev / Windows-CI split.
3. Hazard-family validation gaps producing invalid `h(k)` — fuzz the validators.
4. Webview behavior differences (WKWebView vs WebView2).
5. Signing/SmartScreen friction for non-coder install.

---

## 19. Conventions (mandatory)

- **Branch:** `feat/standalone-instrument`. Never commit to `main`.
- **Commits:** focused, imperative subject lines; explain the *why* in the body.
  **Never include `Co-Authored-By` lines.**
- Push the branch to GitHub for open progress tracking; optionally open a **draft
  PR** into `main` purely for a review surface (do not merge).
- Test locally on macOS at every step; CI for Windows artifacts.
- Keep `main` green and reviewer-ready at all times.

---

## 20. Open decisions for the implementer / owner

- `study.json` format: JSON (default, machine-first) — confirm vs YAML.
- Windows code-signing cert: buy now, or ship unsigned initially?
- Final family list: the §7.2 set is the proposal — trim/extend to taste, but keep
  it a fixed curated set (no free-form code).
- i18n scope at launch: Turkish + English assumed.
- Whether the branch ever merges to `main`, or stays a parallel product line.
