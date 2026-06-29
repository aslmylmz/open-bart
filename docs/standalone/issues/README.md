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
