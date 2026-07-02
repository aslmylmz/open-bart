# 32 — Sphinx docs restructure: instrument-first

**Docs · depends on: 30**

Status: ready-for-agent

## Context

The Read the Docs site ([docs/](../../../docs/)) is scoring-engine-first and
predates the instrument: `game_client.md` / `task_design.md` describe the fixed
linear task, there is no reference for the curated hazard-family library, and the
Master CSV added in issue 28 is documented nowhere researcher-facing. The
researcher quickstart from Phase 4 ([docs/standalone/quickstart.md](../quickstart.md))
exists but the main toctree does not lead with it.

JOSS requires documentation with installation instructions, example usage, and
API documentation; ours must now serve two audiences — researchers (non-coders
running studies) and engineers (using `scoring` as a library).

## Scope

- [ ] Restructure the toctree into a researcher guide (install, quickstart,
      SmartScreen, configuring studies) and an engine reference (metrics,
      validation, schemas, API) — promote existing pages, don't rewrite what is
      still accurate.
- [ ] New hazard-family reference: one section per curated family with its
      hazard `h(k)`, survival and EV forms, parameters and validation ranges, and
      how the numeric optimum is obtained; embed the EV-curves figure and link
      the Monte Carlo verification from issue 30.
- [ ] New data-outputs reference: the per-session files (`*_events.jsonl`,
      `*_metrics.json`, `*_config.json`) and a column dictionary for the Master
      CSV (`[slug]_results.csv`), including the `{color}_{field}` flattening and
      the `behavioral_profile`-is-JSON-only rule.
- [ ] Update stale fixed-task pages so 11/5/2 / √N are presented as the default
      linear configuration; purge Next.js/scipy-in-engine claims.

## Acceptance

- `sphinx-build` completes with **0 warnings** (the Phase 4 standard) and the
  site builds on Read the Docs.
- A non-coder can go from the docs landing page to a running study without
  touching the engine pages.
- Every curated hazard family and every Master CSV column is documented.
- `pytest`, `npm test`, `tsc`, `vite build` stay green.
