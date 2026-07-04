# 33 — JOSS paper rewrite + paper-build CI

**Paper · depends on: 30, 31, 32**

Status: done

## Context

[paper/paper.md](../../../paper/paper.md) (dated 2026-06-20) describes the
pre-instrument repo: a "React/Next.js game client" (stale — Vite SPA inside a
Tauri shell), scipy cited as a dependency of the numerical core (dropped in
issue 05), a fixed 30-balloon linear task, and no mention of the standalone
offline instrument, the configurable hazard library, or numeric optima.
`paper/paper.tex` is a separate 230-line tech-report whose fate needs deciding.

JOSS wants 250–1000 words: summary, statement of need, and references, about the
software as submitted.

## Scope

- [ ] Rewrite `paper.md` around the instrument: summary (configurable offline
      desktop BART; curated hazard-family library; numerically computed EV optima
      with the linear √N case as the closed-form special case; transparent
      scoring engine; Master CSV outputs); statement of need (calibration-
      sensitive BART generalized beyond one hazard, non-coder lab deployment,
      offline data sovereignty, scarcity of open configurable BART instruments);
      design/functionality (Tauri + frozen Python sidecar in one paragraph,
      family library, simulation verification from issue 30).
- [ ] Update `paper.bib`: remove or re-scope the scipy citation (scripts-only),
      add references the new claims need; keep pydantic/numpy.
- [ ] Consider the EV-curves-across-families figure from issue 30 as the paper
      figure.
- [ ] Decide `paper.tex`: update it as the extended technical report or delete it
      with a pointer to the docs — no half-stale duplicate.
- [ ] Add a CI workflow that compiles `paper.md` → PDF with the Open Journals
      draft action on changes under `paper/`, uploading the PDF as an artifact.

## Acceptance

- Word count within JOSS bounds; no stale technical claims anywhere in `paper/`.
- The paper's install/docs pointers resolve to the rewritten README and docs.
- CI produces a compiled PDF artifact from a clean run.
- `pytest`, `npm test`, `tsc`, `vite build` stay green.
