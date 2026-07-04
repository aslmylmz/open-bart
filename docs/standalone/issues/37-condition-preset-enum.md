# 37 — Condition as a preset-driven enum

**Feature · depends on: 36**

Status: done

## Context

Sessions are identified by `candidate_id` alone; between-subject designs have
no first-class home for the assignment, so labs encode it in the ID ("004-E")
or join it from Qualtrics later. Client brief 3A asks to "force entry of
Subject ID and Condition" — but not every study *has* conditions, and a
free-text field invites the exact RA typos ("exp", "Exp ", "experimental")
the guardrail is meant to prevent.

Grill decision: **preset-driven enum**. The Study Preset optionally declares
the allowed condition names; when it does, the ID screen shows a required
dropdown — no typing, no typos. When it doesn't, no condition UI appears and
the output schema is unchanged in spirit (the column is present but empty
only for studies that configure conditions — see Scope).

## Scope

- [ ] The Study Preset gains an optional `conditions` list (e.g.
      `["control", "experimental"]`). Absent/empty means "this study has no
      conditions". Field is optional — every v1.0.0 `study.json` must keep
      validating unchanged.
- [ ] The sidecar remains the sole validation authority: non-empty entries,
      no duplicates, sane length — with structured errors surfaced in Study
      Setup like every other config error.
- [ ] Study Setup lets the researcher define the condition names; the saved
      `study.json` round-trips them.
- [ ] When `conditions` is non-empty, the ID screen shows a required dropdown
      (localized label); a session cannot start without a selection. When
      empty, no condition UI renders.
- [ ] The selected condition lands in the session files and as a Master CSV
      column (via the 36 writer, so pre-upgrade studies migrate cleanly).
- [ ] Data-outputs docs and the contract tests cover the new column.

## Acceptance

- A preset with conditions forces a dropdown choice; the chosen value appears
  in the session files and the Master CSV row — covered end-to-end by tests.
- A preset without conditions shows no condition UI and still validates,
  loads, and runs (backward compatibility with v1.0.0 presets).
- Invalid `conditions` configs produce readable structured errors in Study
  Setup, not a crash.
- `pytest`, `npm test`, `tsc`, `vite build` stay green.

## Comments

**2026-07-03 — implemented (TDD).** `TaskConfig.conditions` (optional, default
`[]`; validator strips whitespace and rejects blank/duplicate/>64-char names —
structured errors via `/validate-config`). `GameSession.condition` carries the
assignment; the Master CSV gains a `condition` column **only for studies that
declare conditions** (v1.0.0 sheets untouched; adding conditions mid-study
migrates via the issue-36 writer — end-to-end test). One scope decision made
during implementation: "lands in the session files" is honored by a new fourth
per-session file, `*_session.json` (the session envelope: id, game_type,
candidate, condition) — before it, session identity lived only in filenames, so
ADR 0001's "master CSV is rebuildable from individual files" claim didn't hold;
the ADR is amended and 38's acknowledgment can be recorded there. UI: Study
Setup gains a comma-separated Conditions field (blur-commit, round-trips
`study.json`); the ID screen shows a required localized dropdown (en/tr) —
Continue stays disabled until ID + condition are set; no conditions → no
condition UI. Tests: config tracer + 4 validation params + 3 sidecar
(CSV/envelope/mid-study) + RunFlow dropdown ×3 + full participant-flow
integration + BartGame payload + session/api/studyForm units; docs contract
test now runs a conditioned study. Gates: pytest 123 ✅, npm test 86 ✅, tsc ✅,
vite build ✅.
