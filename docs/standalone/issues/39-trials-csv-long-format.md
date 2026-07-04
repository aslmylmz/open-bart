# 39 — Study-wide trials CSV (long-format trial-level export)

**Feature · depends on: 36**

Status: done

## Context

The Master CSV is session-level (wide): one row per participant run. Raw
per-pump detail lives in each session's events `.jsonl`. What's missing is the
shape mixed-model analyses in R/SPSS actually consume: **one row per trial
(balloon), long format, across all participants**. Per-session trial files
would recreate the manual concatenation chore the Master CSV was invented to
eliminate (client brief 2A), so the grill decision is a second study-wide
append file mirroring the Master CSV pattern.

## Scope

- [ ] At session completion the sidecar appends one row per trial to
      `[slug(StudyTitle)]_trials.csv` in the output directory, using the 36
      header-versioned writer (header on create, auto-migrate, locked-file
      fallback).
- [ ] Rows carry identity + design + behavior: participant, condition (when
      configured), session id/timestamp, trial index, balloon color, hazard
      family, pumps, outcome (collected/exploded), trial earnings, and a
      per-trial response-latency summary. Column names follow the canonical
      BART nomenclature (CONTEXT.md) so the file is readable without a
      codebook.
- [ ] Trial rows are computed in the scoring engine from the event log (not
      re-derived in the sidecar), so CLI users of `scoring` get the same
      trial table.
- [ ] Practice sessions (43) must never append here — same rule as the Master
      CSV; encode the rule where both files' appends are decided.
- [ ] Data-outputs docs get a column table for the new file; contract tests
      guard it.

## Acceptance

- Completing two sessions of the default 30-trial study yields a trials CSV
  with 60 data rows and one header, appended in session order — covered by
  tests.
- Long-format invariant holds: every trial of every session appears exactly
  once; collected and exploded trials are both present and distinguishable.
- The file plays by the 36 rules (migration, backup, locked-file sibling).
- `pytest`, `npm test`, `tsc`, `vite build` stay green.

## Comments

**2026-07-03 — implemented (TDD).** Engine: new public
`scoring.bart.trial_table(events, config) -> list[TrialRecord]` (model in
`scoring.schemas`) — one record per balloon with trial index, balloon_color,
hazard_family (from the config's color profile), pumps, outcome
(collected/exploded), trial_earnings, and mean_latency_between_pumps (per-trial
mean inter-pump gap in ms; honestly empty under two pumps). A trailing balloon
with no terminal event (aborted session) is omitted. Sidecar: `/write-output`
appends the rows to `[slug]_trials.csv` through the 36 writer — `versioned_csv`
gained `append_rows` (batch, one header check; `append_row` is now the
single-row case; the 36 contract tests survived the refactor untouched). The
identity columns (timestamp_utc, session_id, candidate_id, condition-if-
declared) are built once and shared by both study-wide appends, which now live
at a single decision point in `write_output` — the place practice mode (43)
will gate. Response gains `trials_csv`; warnings merge from both appends. Note:
adding conditions mid-study now migrates *both* study-wide files (two backups)
— the 37 test was tightened to `*_results_backup_*`. Docs: "The Trials CSV"
column table + a second docs contract test that diffs the written header
against the page. Gates: pytest 137 ✅, npm test 92 ✅ (client untouched),
tsc ✅, vite build ✅.
