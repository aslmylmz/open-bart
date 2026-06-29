# Phase 0 — Local Issues

Breakdown of **Phase 0 ("Foundations")** from [SPEC §17](../SPEC.md) into discrete,
reviewable work items. These are tracking notes, not GitHub issues.

Work them roughly in order; dependencies are noted per issue. All work happens on
`feat/standalone-instrument`, and **the 23 existing tests must stay green at every step**.

| # | Issue | Depends on | Touches |
|---|---|---|---|
| [01](01-packaging-pyproject.md) | Packaging: `pyproject.toml`, installable `scoring` | — | `pyproject.toml`, `conftest.py` |
| [02](02-taskconfig-hazard-families.md) | `TaskConfig` + hazard family library | 01 | `scoring/config/` (new), `tests/` |
| [03](03-generalize-engine.md) | Generalize engine off hardcoded constants | 02 | `scoring/bart.py`, `scoring/schemas/`, `tests/` |
| [04](04-vite-spa-decouple.md) | Decouple `BartGame.tsx` into a static Vite SPA | — (parallel) | `app/` (new), `games/bart/` |

## Phase 0 acceptance (rolls up all four issues)

- `pip install -e .` works.
- New hazard-family tests **and** the 23 existing tests pass.
- The default linear config still yields optima `11/5/2` and the `√N` approximation.
- `vite build` produces a static SPA with no Next.js dependency.

> Out of scope for Phase 0 (later phases): the FastAPI sidecar (Phase 1), the Tauri
> shell (Phase 2), the no-code Study-Setup UI + live EV preview (Phase 3), the Windows
> CI build (Phase 4).
