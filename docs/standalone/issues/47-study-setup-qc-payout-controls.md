# 47 — Study Setup: form controls for QC thresholds and payout conversion

**Feature · depends on: 46**

Status: ready-for-agent

## Context

`TaskConfig` supports two researcher-facing configuration blocks that Study
Setup cannot currently edit: `QCThresholds` (issue 40 — `fast_response_ms`,
`zero_pump_streak`) and `PayoutConversion` (issue 41 — `rate`, `currency`).
Until issue 46 brings the TS type into parity they are invisible to the webview;
once visible, Study Setup should expose them so a researcher can configure them
without hand-editing `study.json`. QC thresholds carry the data-quality flag
cutoffs in the Study Preset (flags annotate, never exclude); payout converts
task earnings to the real amount owed. Both stay optional — absent means the
literature-informed QC defaults / no payout, the v1.0.0 behavior.

## Scope

- [ ] Study Setup gains inputs to edit `QCThresholds` (`fast_response_ms`,
      `zero_pump_streak`) and `PayoutConversion` (`rate`, `currency`), wired
      through the existing immutable form-model helpers (`setStudyField` and
      friends, returning a new `TaskConfig`). Payout is optional — a clear
      "no payout" state that serializes to an absent block.
- [ ] The controls follow Researcher View conventions (Apple-HIG-inspired,
      single scrollable card, dark posture — ADR 0003); Study Setup labels are
      English-only by convention. Any new participant-facing string gets en+tr
      parity.
- [ ] Validation stays with the Sidecar: invalid values surface through
      `/validate-config` (the sole validation authority) into the existing error
      list — no re-encoded pydantic rules in the webview.

## Acceptance

- A researcher can set QC thresholds and a payout conversion entirely from Study
  Setup, save the Preset, reload it, and see the values round-trip.
- An out-of-range value (e.g. non-positive `rate`) is rejected via
  `/validate-config` and shown in the error list; a study with no payout saves
  with no payout block and behaves as v1.0.0.
- The parity guard from issue 46 stays green (this issue adds UI only; the fields
  already exist in the TS type).
- `pytest`, `npm test`, `tsc`, and `vite build` green.

## Comments

**2026-07-04 — implemented (TDD on the pure form-model helpers; webview-only).**
Followed the established `setStudyField` / `parseExitPasscode` pattern: three new
immutable helpers in `app/src/setup/studyForm.ts`, each returning a fresh
`TaskConfig`, unit-tested red→green in `studyForm.test.ts` (that is where this
repo's form-model test discipline lives; `StudySetup.tsx` stays a thin, untested
shell). Helpers: `setQcField` (materializes the `qc` block from `DEFAULT_QC` —
`{100, 5}`, mirroring the pydantic `QCThresholds` defaults — on first edit, so an
untouched study keeps `qc` absent = engine defaults); `setPayoutEnabled` (enable
seeds `DEFAULT_PAYOUT` `{rate: 1, currency: "$"}` and keeps any existing block on
re-enable; disable sets `payout: null` — the no-payout state, following the
`exit_passcode` null precedent); `setPayoutField` (patches rate/currency). A
`parseStudy` regression test locks the save/reload round-trip for both blocks.
Shell wiring: a new "Data Quality & Payout" section (Researcher-View card, dark
posture, English-only labels — ADR 0003) between Study Info and Color Profiles;
QC inputs show the effective defaults even when `qc` is absent, and a checkbox
gates the rate/currency inputs (hidden = no payout). No pydantic change → no
contract regen; the issue-46 parity guard stays green. No participant-facing
strings added — payout *display* (Debrief + `payoutLabel` en/tr) was already done
in issue 41; sidecar `/validate-config` already rejects bad qc/payout blocks
(`test_validate_config_rejects_bad_payout_blocks`), so no re-encoded rules in the
webview. **Verified:** drove the real `<StudySetup>` through React DOM with a
throwaway `*.test.tsx` harness (deleted after) — confirmed QC defaults render,
editing materializes the block, the payout toggle shows/hides the rate/currency
controls, currency edits round-trip, and disabling returns `payout: null`. Gates:
pytest **161** ✅ (+0), vitest **128** ✅ (+10), tsc ✅, vite build ✅.
