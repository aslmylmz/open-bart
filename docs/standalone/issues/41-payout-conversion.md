# 41 — Real-world payout conversion

**Feature · depends on: 36**

Status: done

## Context

Behavioral-economics labs pay participants based on performance (client brief
4B). Session earnings are already denominated in configured currency units
(`reward_per_pump`), so this is a **display/payout layer**, not a scoring
change: an optional conversion from task earnings to the amount actually owed
("100 points = $1.50"), shown at debrief and recorded for the payment log.

## Scope

- [ ] The Study Preset gains an optional payout block: conversion rate and a
      currency label/symbol (freeform — "₺", "$", "credits" — no locale
      machinery this cycle). Optional — v1.0.0 presets keep validating; absent
      block means no payout anywhere (today's behavior).
- [ ] The sidecar computes the payout once (earnings × rate, rounded half-up
      to 2 decimals) so the webview and the CSV can never disagree.
- [ ] When configured, the participant debrief card shows the payout owed in
      both languages; the researcher side of the debrief shows it too.
- [ ] The payout lands in the session metrics JSON and as a Master CSV column
      (via the 36 writer). Task-internal earnings columns are unchanged.
- [ ] Data-outputs docs and contract tests cover the column and the rounding
      rule.

## Acceptance

- With a payout block, a finished session shows the converted amount at
  debrief and writes it to the metrics JSON and Master CSV; without one,
  screens and outputs are unchanged from v1.0.0 — covered by tests.
- Rounding is deterministic and documented (one rule, applied in one place).
- `pytest`, `npm test`, `tsc`, `vite build` stay green.

## Comments

**2026-07-03 — implemented (TDD).** `TaskConfig.payout` (optional
`PayoutConversion`: `rate` gt 0, freeform `currency` 1–16 chars; absent = no
payout anywhere; v1.0.0 presets validate unchanged; malformed blocks come back
as structured `/validate-config` errors). One deviation from the scope's
letter, honoring its intent: the computation lives in **`score_bart`**, not
the sidecar — the scope's own reason ("computed once so the webview and the
CSV can never disagree") is satisfied better there, since both `/score` (the
debrief's source) and `/write-output` (the CSV's source) call the engine, the
payout must be on `BARTMetrics` for the metrics JSON anyway, and CLI users get
it too (the QC-flags precedent). Rounding: `Decimal(str(money_collected
rounded 2dp)) × Decimal(str(rate))`, quantized `ROUND_HALF_UP` to 2 dp — the
tracer pins 7.25 × 0.1 = 0.725 → **0.73**, the case banker's rounding gets
wrong. CSV columns (`payout_amount`, `payout_currency`) are present only for
payout studies (the issue-37 condition rule; `_flatten_metrics` drops them
when None); task-internal earnings columns untouched. Debrief shows a payout
line (localized label en "Your payout" / tr "Ödemeniz", amount as
`{amount} {currency}`) only when the engine sent one — the client never
re-derives or re-rounds; the "researcher side" is the metrics JSON + CSV per
issue 28's design. The metrics-schema change broke frozen parity again:
`dist/bart-sidecar` re-frozen and the Tauri bundle copy refreshed. Docs:
payout column table + the rounding rule; the master-CSV contract test now runs
a conditions+payout study (widest schema). Gates: pytest 149 ✅, npm test
96 ✅, tsc ✅, vite build ✅.
