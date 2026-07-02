# Local Issues

Breakdown of the [SPEC §17](../SPEC.md) phased plan into discrete, reviewable work
items. These are tracking notes, not GitHub issues.

Work them roughly in order; dependencies are noted per issue. All work happens on
`feat/standalone-instrument`, and **the existing tests must stay green at every step**.

## Phase 0 — Foundations

| # | Issue | Depends on | Touches |
|---|---|---|---|
| [01](01-packaging-pyproject.md) | Packaging: `pyproject.toml`, installable `scoring` | — | `pyproject.toml`, `conftest.py` |
| [02](02-taskconfig-hazard-families.md) | `TaskConfig` + hazard family library | 01 | `scoring/config/` (new), `tests/` |
| [03](03-generalize-engine.md) | Generalize engine off hardcoded constants | 02 | `scoring/bart.py`, `scoring/schemas/`, `tests/` |
| [04](04-vite-spa-decouple.md) | Decouple `BartGame.tsx` into a static Vite SPA | — (parallel) | `app/` (new), `games/bart/` → `app/src/` |

## Phase 0 acceptance (rolls up all four issues)

- `pip install -e .` works.
- New hazard-family tests **and** the 23 existing tests pass.
- The default linear config still yields optima `11/5/2` and the `√N` approximation.
- `vite build` produces a static SPA with no Next.js dependency.

> Out of scope for Phase 0 (later phases): the FastAPI sidecar (Phase 1), the Tauri
> shell (Phase 2), the no-code Study-Setup UI + live EV preview (Phase 3), the Windows
> CI build (Phase 4).

## Phase 1 — Sidecar

The FastAPI sidecar wrapping `scoring`, frozen with PyInstaller. Sequenced
**de-risk-first**: make the engine scipy-free (05), stand up the shell (06), and prove
the freeze runs on Windows (07) **before** building the real endpoints (08).

| # | Issue | Depends on | Touches |
|---|---|---|---|
| [05](05-drop-scipy.md) | Drop scipy from the scoring engine | Phase 0 | `scoring/bart.py`, `scoring/config/hazards.py`, `pyproject.toml` |
| [06](06-sidecar-skeleton.md) | Sidecar skeleton: `/healthz` + launcher + hello-score | 05 | `app/sidecar/` (new), `pyproject.toml`, `conftest.py`, `tests/` |
| [07](07-pyinstaller-windows-ci.md) | PyInstaller freeze + Windows CI (de-risk gate) | 06 | `app/sidecar/*.spec`, `.github/workflows/` (new) |
| [08](08-sidecar-endpoints.md) | Full endpoints + client `/score` alignment + tests | 06 (gated by 07) | `app/sidecar/app.py`, `app/src/lib/api.ts`, `tests/` |

### Phase 1 acceptance (rolls up 05–08)

- The `scoring` package imports and tests pass with **no scipy installed**.
- A frozen "hello-score" sidecar runs on **Windows** (CI).
- The full sidecar scores a sample session **identically** to calling `scoring`
  directly (`/score` == `score_bart`).
- The Vite client posts to `/score`; `npm test`, `tsc`, and `vite build` stay green.

## Phase 2 — Tauri shell

The Tauri v2 desktop shell (`app/src-tauri/`) that loads the Vite SPA, manages the
sidecar lifecycle, and enforces the strict offline posture. Sequenced
**de-risk-first**: freeze the full sidecar (09) and scaffold the shell (10) before
wiring the lifecycle / port-handoff / persistence (11) and the study.json + kiosk
plumbing (12).

| # | Issue | Depends on | Touches |
|---|---|---|---|
| [09](09-full-frozen-sidecar.md) | Full frozen sidecar (`bart-sidecar`) | Phase 1 | `app/sidecar/sidecar.spec` (new), `.gitignore` |
| [10](10-tauri-shell-scaffold.md) | Tauri v2 shell scaffold (window + offline CSP) | Phase 0/1 (parallel to 09) | `app/src-tauri/` (new), `app/package.json`, `app/vite.config.ts` |
| [11](11-sidecar-lifecycle-port-handoff.md) | Sidecar lifecycle + port handoff + session persistence | 10 (09 for release verify) | `app/src-tauri/src/`, `app/src/lib/api.ts`, `app/src/main.tsx`, `app/src/BartGame.tsx`, `app/sidecar/{app,models}.py`, `tests/` |
| [12](12-studyjson-plumbing-kiosk.md) | study.json dialog/fs plumbing + kiosk/fullscreen | 10 | `app/src-tauri/` (commands + capabilities) |

### Phase 2 acceptance (rolls up 09–12)

- A frozen full `bart-sidecar` runs on macOS: prints `PORT=<n>`, serves `/healthz`.
- `tauri dev` on macOS opens the SPA with a strict offline CSP (no remote origins).
- A full session runs end-to-end and writes `*_events.jsonl`, `*_metrics.json`,
  `*_config.json` locally; displayed metrics match `score_bart`; **zero network**.
- The sidecar is spawned, health-checked, and killed by the shell (no orphans).
- study.json load/save plumbing + kiosk/fullscreen exist; `npm test`, `tsc`,
  `vite build`, and `pytest` stay green.

> Out of scope for Phase 2 (later phases): the no-code Study-Setup UI + live EV
> preview (Phase 3), the Windows CI `tauri build` + installer + signing (Phase 4),
> and the JOSS rewrite (Phase 5).

## Phase 3 — Config UX

The no-code **Study Setup** + **Run** modes in the Vite SPA (SPEC §11). The sidecar
endpoints already exist (`/validate-config`, `/preview`, `/score`, `/write-output`),
so this phase is frontend + thin wiring. Sequenced foundation-first: stand up mode
routing + the typed config store (13) before the researcher form (14) and the live EV
preview (15), then the config-driven Run mode + per-study scoring (16) that satisfies
the §17 acceptance. Decisions taken at kickoff: hand-rolled SVG preview (no charting
dep), hand-written TS config types with `/validate-config` as the authority, config
threaded into both `/score` and `/write-output`, a tr/en string table extracted from
the task, and the existing results screen reused as the debrief.

| # | Issue | Depends on | Touches |
|---|---|---|---|
| [13](13-config-ux-app-shell.md) | App shell: mode routing + active-config store + TS config types | Phase 2 | `app/src/App.tsx`, `app/src/lib/config.ts` (new), `tests/` |
| [14](14-study-setup-form.md) | Study Setup form + `study.json` save/load + `/validate-config` | 13 | `app/src/setup/` (new), `app/src/lib/api.ts`, `app/src/lib/desktop.ts` (reuse) |
| [15](15-live-ev-preview.md) | Live EV-curve + optimum preview (hand-rolled SVG) | 13 (parallel to 14) | `app/src/setup/` (new), `app/src/lib/api.ts` |
| [16](16-run-mode-config-driven-task.md) | Run mode: config-driven task + consent/ID/debrief + per-study scoring | 13, 14 | `app/src/BartGame.tsx`, `app/src/run/` (new), `app/src/lib/{api,i18n}.ts`, `app/sidecar/{app,models}.py`, `tests/` |

### Phase 3 acceptance (rolls up 13–16)

- A non-coder can change the hazard family + parameters in Study Setup, **see the
  optimum update** (live EV preview), **save a study** to `study.json`, switch to Run,
  and **run it**.
- The run uses the configured colors / `max_pumps` / `trials` / hazard / reward /
  language; a seeded run replays identically.
- The persisted `*_events.jsonl` / `*_metrics.json` / `*_config.json` reflect **that**
  study (scored against its optima; config snapshot is the run's config).
- `npm test`, `tsc --noEmit`, `vite build`, and `pytest` all stay green.

> Out of scope for Phase 3 (later phases): the Windows CI `tauri build` + installer +
> signing (Phase 4) and the JOSS rewrite (Phase 5).

## Phase 4 — Distribution

The Windows release pipeline: freeze the full sidecar on Windows CI, build a Tauri
NSIS per-user installer (no admin rights), smoke-test it, and document the
unsigned-app experience + a researcher quickstart. Sequenced **de-risk-first**: prove
the full sidecar freezes on Windows (17) before wiring the Tauri bundle (18) and
installer verification (19). Documentation (20, 21) runs in parallel once the
installer exists. Decisions locked at kickoff: NSIS per-user install, unsigned with
SmartScreen docs, embedded WebView2 offline bootstrapper, tag-triggered
`windows-release.yml` workflow, quickstart in Sphinx/MyST for Read the Docs.

| # | Issue | Depends on | Touches |
|---|---|---|---|
| [17](17-windows-ci-sidecar.md) | Windows CI: full sidecar freeze + smoke test | Phase 3 | `.github/workflows/sidecar-windows.yml` |
| [18](18-tauri-windows-bundle.md) | Tauri Windows bundle + NSIS per-user installer | 17 | `.github/workflows/windows-release.yml` (new), `app/src-tauri/tauri.conf.json`, `app/src-tauri/src/lib.rs` |
| [19](19-installer-smoke-test.md) | Installer smoke test + manual verification checklist | 18 | `.github/workflows/windows-release.yml`, `docs/standalone/VERIFY-WINDOWS.md` (new) |
| [20](20-smartscreen-docs.md) | SmartScreen bypass documentation | — (parallel) | `docs/standalone/SMARTSCREEN.md` (new) |
| [21](21-quickstart-guide.md) | Researcher quickstart guide (Sphinx / MyST → Read the Docs) | 18, 19, 20 | `docs/standalone/quickstart.md` (new), `docs/` (toctree), this README |

### Phase 4 acceptance (rolls up 17–21)

- A tagged push (`v*`) yields a downloadable NSIS installer artifact in GitHub Actions.
- The installer is per-user (no admin rights) and embeds the WebView2 offline
  bootstrapper (no network during install).
- The full frozen `bart-sidecar.exe` passes `/healthz` + `/score` smoke tests on
  `windows-latest` CI.
- Silent install on CI lays down the app executable + sidecar in the expected paths.
- A manual test on a Windows 11 VM (following `VERIFY-WINDOWS.md`) completes a full
  session end-to-end: SmartScreen bypass → launch → consent → ID → task → debrief →
  data files written.
- `SMARTSCREEN.md` lets a non-technical researcher bypass the unsigned-app warning.
- `docs/standalone/quickstart.md` compiles to Read the Docs; a researcher can follow
  it to install, configure, run, and collect data.
- `npm test`, `tsc --noEmit`, `vite build`, and `pytest` stay green locally.

> Out of scope for Phase 4 (later phases): code signing (documented as future
> enhancement), macOS distribution/notarization, auto-update, and the JOSS rewrite
> (Phase 5).

## Phase 5 — UI Polish

The visual overhaul: create a global dark-theme stylesheet (the app currently has **no
CSS file**), then restyle every screen for a professional, modern look. Sequenced
foundation-first: the global stylesheet (24) provides the base; the three screen-level
issues (25–27) depend on it and can be worked in parallel.

| # | Issue | Depends on | Touches |
|---|---|---|---|
| [24](24-dark-theme-global-css.md) | Global CSS stylesheet + dark theme foundation | — | `app/src/index.css` (new), `app/src/main.tsx`, `app/index.html` |
| [25](25-study-setup-styling.md) | StudySetup + EvPreview styling | 24 | `app/src/setup/StudySetup.tsx`, `app/src/setup/EvPreview.tsx`, `app/src/App.tsx` |
| [26](26-runflow-screen-styling.md) | RunFlow consent / ID / loading / error screen styling | 24 | `app/src/run/RunFlow.tsx` |
| [27](27-bartgame-layout-fixes.md) | BartGame gameplay + finished screen layout fixes | 24 | `app/src/BartGame.tsx` |
| [28](28-debrief-screen-ux.md) | Debrief screen UX: participant vs researcher modes | 24 | `app/src/run/Debrief.tsx` |

### Phase 5 acceptance (rolls up 24–28)

- The application uses the system sans-serif font stack.
- The Researcher View (Study Setup, EV Preview) renders on a dark background.
- The Participant View (Consent, ID, Gameplay, Debrief) renders on a sterile light background.
- All form controls, buttons, inputs, and fieldsets are styled and readable.
- Every screen looks polished and professional.
- Layout is centered and responsive at the Tauri default window size (1280×800).
- `npm test`, `tsc --noEmit`, `vite build`, and `pytest` stay green.

## Phase 6 — JOSS (SPEC §17 "Phase 5")

The JOSS submission rewrite: reposition the paper, README, and docs around the
configurable offline instrument, back the paper's verification claims with
tooling, and cut an archived release. Sequenced **claims-first**: harden the
engine (29) and generalize the Monte Carlo verification (30) so the reviewer-
facing prose (31–33) describes software that holds up, then archive (34).
29–31 have no blockers and can be worked in parallel.

| # | Issue | Depends on | Touches |
|---|---|---|---|
| [29](29-engine-degenerate-session-crash.md) | Engine hardening: degenerate-session scoring crash | — | `scoring/bart.py`, `tests/` |
| [30](30-monte-carlo-all-families.md) | Monte Carlo verification across the hazard-family library | — | `scripts/monte_carlo_ev.py`, `tests/` |
| [31](31-readme-instrument-rewrite.md) | README rewrite around the standalone instrument | — | `README.md` |
| [32](32-sphinx-docs-instrument-first.md) | Sphinx docs restructure: instrument-first | 30 | `docs/` (toctree + new pages) |
| [33](33-joss-paper-rewrite.md) | JOSS paper rewrite + paper-build CI | 30, 31, 32 | `paper/`, `.github/workflows/` |
| [34](34-release-zenodo-joss-checklist.md) | Release, Zenodo archive, JOSS pre-submission checklist | 29–33 | version manifests, `CITATION.cff` |

### Phase 6 acceptance (rolls up 29–34)

- `score_bart` never raises on a validator-accepted session; per-family sweep green.
- Numeric optima are simulation-verified for **every** curated hazard family,
  guarded by a seeded CI test.
- README, docs (0 Sphinx warnings), and `paper.md` all describe the standalone
  configurable instrument with no stale claims (Next.js, engine scipy, fixed task).
- CI compiles the paper to a PDF artifact.
- A tagged release passes the Windows manual verification and is archived on
  Zenodo; the version DOI is cited consistently. Submission itself stays manual.
- `pytest`, `npm test`, `tsc --noEmit`, and `vite build` stay green throughout.

## Bugfixes

Cross-cutting fixes discovered during end-to-end testing.

| # | Issue | Depends on | Touches |
|---|---|---|---|
| [22](22-sidecar-cors-localhost-fix.md) | Sidecar CORS middleware + `localhost` → `127.0.0.1` fix | 08, 15, 16 | `app/sidecar/app.py`, `app/src/lib/api.ts`, `tests/` |
| [23](23-runflow-error-retry.md) | RunFlow error recovery: retry instead of re-enter ID | 16, 22 | `app/src/run/RunFlow.tsx`, `app/src/lib/i18n.ts` |
| [35](35-stale-sidecar-bundle-guard.md) | Stale-bundle guard: version handshake + readable 422s | — | `app/src/VersionGuard.tsx`, `app/src/lib/api.ts`, `app/src/App.tsx`, `app/vite.config.ts` |
