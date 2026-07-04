# 55 — Debrief currency + consent-screen copy

**Bugfix · depends on: —**

Status: ready-for-agent

## Context

Post-audit hardening (Quality Kaizen cycle 01, finding **F7**;
`docs/standalone/QUALITY-KAIZEN.md`). Two low-severity participant-facing
polish items from the audit:

- **Currency:** the debrief hardcodes a `$` prefix on the total-earnings figure
  regardless of the study's language or configured currency; only the optional
  payout line uses the real currency label. A Turkish (₺) study still shows
  earnings as "$X" to the participant.
- **Consent copy:** the in-app consent screen is a single sentence with no
  statement of voluntary participation, withdrawal, confidentiality, or contact.
  It is a task instruction, but its "Before you begin / I agree" framing can read
  as informed consent. It should not impersonate an IRB consent form (labs
  obtain real consent separately).

## Scope

- [ ] The debrief earnings figure uses the study's configured currency label
      (consistent with the payout line), not a hardcoded `$`.
- [ ] The consent-screen copy is relaxed/relabeled so it reads as a task
      instruction, not an IRB consent instrument (both `en` and `tr`).
- [ ] i18n key parity across languages is preserved.

## Acceptance

- A study with a non-`$` currency shows that currency on the debrief earnings.
- The consent screen no longer presents as informed consent; both locales stay
  key-parity-checked.
- `pytest`, `vitest`, `tsc --noEmit`, `vite build` stay green.

## Comments

Source: 2026-07-04 research audit, register row F7 (Low). Copy changes may
warrant a quick researcher review of the exact consent wording.
