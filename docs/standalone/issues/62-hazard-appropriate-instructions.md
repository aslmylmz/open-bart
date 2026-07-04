# 62 — Hazard-appropriate participant instructions (stop assuming dynamic)

**Validity-limitation · depends on: none**

Status: ready-for-agent

## Context

Cycle-02 audit finding F13 (D1/D2). The consent and instruction copy is hardcoded to
the **dynamic**-hazard framing:

- consent body: "…Each pump raises the chance of a pop…" (`app/src/lib/i18n.ts:85`)
- instructions: "…Each pump raises the chance it pops…" (`i18n.ts:106`)

Two problems:

1. **Factually wrong for non-dynamic families.** The instrument ships 11 hazard
   families including `constant`/Bernoulli and classic `lejuez` (uniform), where the
   per-pump burst probability does **not** rise with each pump. A constant-hazard
   study tells participants something false.
2. **Structure leak / priming.** Even for the default dynamic study, stating the
   rising-hazard structure up front primes participants and departs from the classic
   BART convention of deliberately vague instructions ("the balloon will pop at some
   point") — relevant to measurement neutrality (D2) and comparability with the BART
   literature.

## Scope

- [ ] Replace the dynamic-specific claim with copy that is correct regardless of the
      configured family — either deliberately classic-BART-vague ("at some point the
      balloon will pop") or family-aware.
- [ ] **Decision to make (flagged in the plan):** a single neutral rewrite (smaller,
      no config surface) **vs** family-aware configurable copy (a new optional
      `study.json` surface). Prefer the smallest reversible slice unless family-aware
      copy is explicitly wanted.
- [ ] Cover both languages (en + tr); keep it consistent between the consent screen
      and the in-task instructions.

## Acceptance

- Instruction + consent copy contains no per-pump rising-hazard claim; it reads
  correctly for a constant/Lejuez study as well as the dynamic default (guarded by a
  string/i18n test).
- Both languages updated; `vitest`, `tsc --noEmit`, `vite build`, `pytest` stay green.

## Comments

Source: 2026-07-04 fresh full-audit, register row F13. Evidence: `i18n.ts:85`, `:106`.
Ties to CONTEXT.md's "Familiarity on the Outside" rule and the dynamic-hazard paradigm
being the *hidden* innovation. Webview-only unless family-aware copy is chosen (then a
config field + contract update).
