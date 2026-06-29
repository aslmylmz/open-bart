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
