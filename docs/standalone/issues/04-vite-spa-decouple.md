# 04 — Decouple `BartGame.tsx` into a static Vite SPA

**Phase 0 · SPEC §11, §16 · depends on: none (parallelizable with 01–03)**

## Context

[games/bart/BartGame.tsx](../../../games/bart/BartGame.tsx) (~1060 lines) is a Next.js
component that renders the 3-colour task, logs pump-level events via `performance.now()`,
and **POSTs a typed session payload to a scoring endpoint**. The desktop app needs it as
a standalone **React + Vite** SPA: the Tauri webview will load the Vite build, and the
Python sidecar becomes that scoring endpoint (Phases 1–2).

## Scope

- [ ] Scaffold `app/` with Vite + React + TypeScript (`app/src/`).
- [ ] Port `BartGame.tsx` off Next.js: drop `next/*` imports; replace router / `next/image`
  / `next/font` usages with plain React + Vite equivalents.
- [ ] Make the scoring endpoint URL configurable (injected port / env) instead of a
  hardcoded Next API route — the sidecar port is handed in at launch (Phase 2); use a
  dev default for now.
- [ ] Preserve the event-logging contract and POST payload shape exactly — it must keep
  matching `scoring.schemas` (`GameEvent` / `GameSession`).
- [ ] `vite build` emits a static SPA to `app/dist/`.

## Acceptance

- `vite build` produces a static SPA with **no** Next.js dependency.
- `vite dev` renders the task and logs pump events via `performance.now()`.
- The POST payload shape is unchanged versus the Next.js version.

## Notes

- The no-code config UX (Study Setup, family picker, **live EV-curve preview**) is
  **Phase 3** — out of scope here. This issue is only the participant-facing task UI
  decoupling.
