# 31 — README rewrite around the standalone instrument

**Docs · depends on: none**

Status: done

## Context

[README.md](../../../README.md) still tells the original story: a fixed linear
three-color task (11/5/2 table), an embeddable React client, and Monte Carlo
tooling. The product is now a **standalone, offline, configurable desktop
instrument** (v0.2.0 shipped a Windows installer), and the README is the first
thing a JOSS reviewer reads — they check it for a statement of need, install
instructions, and example usage.

## Scope

- [ ] Reposition the header: what the instrument is (offline desktop BART with a
      curated hazard-family library and numeric EV optima), who it is for
      (labs without developers), and what it outputs.
- [ ] Installation section: download the Windows installer from GitHub Releases
      (link SmartScreen bypass doc); `pip install` for the scoring engine as a
      library; local dev setup pointer.
- [ ] Researcher workflow section: Study Setup → live EV preview → `study.json` →
      Run mode → outputs (events JSONL, metrics JSON, config snapshot, and the
      per-study Master CSV for SPSS/R).
- [ ] Reframe the science: the linear dynamic-hazard model with 11/5/2 becomes the
      documented **default configuration**, one member of the configurable family
      library — not the whole story.
- [ ] Refresh the repository-structure block and badges; remove stale
      web-deployment/Next.js remnants.

## Acceptance

- README accurately describes the current instrument and its outputs.
- Install path for a non-coder researcher is complete and all links resolve.
- Default-config optima (11/5/2, √N) remain documented as the linear special case.
- No stale claims (Next.js, scipy in the engine, fixed-task-only framing).
