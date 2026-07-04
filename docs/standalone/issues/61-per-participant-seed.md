# 61 — Per-participant sequences from a reproducible study seed

**Design-flaw · depends on: none**

Status: ready-for-agent

## Context

Cycle-02 audit finding F12 (D3). One seeded RNG drives both the color shuffle and the
per-pump burst draws for a run (`app/src/BartGame.tsx:107-112`):

```ts
const seed = config.seed ?? ((Math.random() * 2 ** 32) >>> 0);
const rng = mulberry32(seed);
```

`config.seed` is a **study-level** field. So a researcher who sets a seed for
"reproducibility" gives **every participant the identical shuffle and identical
burst sequence** — the exact D3 red flag ("a reproducible seed silently fixes
presentation order for all participants"). That turns order effects into a confound
and is not per-participant reproducibility. With `seed` null each run is fresh, but
the moment a seed is set the whole study collapses onto one sequence.

The wanted property: a study is **reproducible from `seed` + the participant IDs**,
while each participant gets an **independent** sequence.

## Scope

- [ ] Derive the per-run seed from the study seed **and** the participant ID (e.g.
      `mulberry32(mix(config.seed, candidateId))`), so identical `(seed, id)` replays
      exactly but different participants diverge.
- [ ] Preserve an explicit escape hatch for a single shared sequence when that is
      actually intended (demo/replay) — documented, not the default.
- [ ] Document the seed semantics (study.json field docs + `docs/`); update the
      seeded-replay tests to assert per-participant divergence + per-(seed,id) replay.

## Acceptance

- Two participants under the same fixed `seed` get **different** sequences; the same
  `(seed, candidateId)` replays byte-identically (new tests, red before the change).
- A null seed still yields fresh independent runs (unchanged).
- `vitest`, `tsc --noEmit`, `vite build`, `pytest` stay green.

## Comments

Source: 2026-07-04 fresh full-audit, register row F12. Evidence: `app/src/BartGame.tsx:109`;
`buildSequence` + `mulberry32` in `app/src/run/sequence.ts`. Highest regression risk in
the cycle — it touches burst determinism and the seeded-replay guarantee (SPEC §7.2),
so confirm the reproducibility contract is re-stated, not lost. Webview-only unless the
seed model is pushed into the sidecar.
