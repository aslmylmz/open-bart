# 30 — Monte Carlo verification across the hazard-family library

**Tooling · depends on: none**

Status: ready-for-agent

## Context

The current [scripts/monte_carlo_ev.py](../../../scripts/monte_carlo_ev.py)
verifies only the classic linear (`dynamic`) configuration: the three hardcoded
colors and their 11/5/2 optima. The engine now computes EV optima **numerically**
(`balloon_curve`) for the whole curated hazard library (10 parameterized families
plus the tabular escape hatch).

The rewritten JOSS paper wants to claim that the numeric optima are
**simulation-verified for every family**, not just the linear special case. That
claim needs tooling behind it.

## Scope

- [ ] Generalize the Monte Carlo tooling to accept a `HazardSpec`/`TaskConfig`
      instead of the hardcoded three-color table: simulate sessions under optimal
      play for a representative parameterization of each curated family and
      confirm the empirical EV-argmax matches the `balloon_curve` numeric optimum.
- [ ] One command runs the full sweep and prints a per-family pass/fail table.
- [ ] A fast, seeded pytest version (reduced session count) guards the agreement
      in CI so the claim cannot silently rot.
- [ ] Produce an EV-curves-across-families figure suitable for the docs and as a
      candidate paper figure.
- [ ] scipy/matplotlib stay confined to the `[scripts]` extra — the engine and
      sidecar remain scipy-free.

## Acceptance

- The sweep passes for every curated family (empirical optimum == numeric optimum).
- CI test asserts the agreement with a fixed seed.
- Figure artifact is generated and referenced from the docs.
- `pytest`, `npm test`, `tsc`, `vite build` stay green.
