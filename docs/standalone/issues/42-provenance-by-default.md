# 42 — Provenance by default: OSF-ready output directory

**Feature · depends on: none**

Status: done

## Context

Client brief 2C asks for a "one-click OSF Publication Zip". The grill
reframed it: a manual export button is a failure mode (nobody clicks it), and
the OS already makes zips. Instead, **the output directory itself is
permanently OSF-ready** — every ingredient a methods section or an OSF upload
needs is written there automatically, so "export" is right-click → Compress.

## Scope

- [ ] On the first session of a study, the sidecar writes into the output
      directory: a frozen copy of the exact `study.json` used, a provenance
      file (app version, engine version, platform, seed), and a data
      dictionary describing every column of the Master CSV and trials CSV
      plus every field of the session files.
- [ ] The data dictionary is **generated from the scoring models/schema**,
      not hand-written — a new column added in code appears in the dictionary
      without anyone remembering to document it twice.
- [ ] If the app version differs from the recorded provenance (mid-study
      upgrade), the provenance and dictionary are refreshed; the frozen
      `study.json` copy is never silently replaced — a changed config gets
      written alongside, versioned, so the original design stays auditable.
- [ ] Practice sessions (43) neither create nor refresh provenance files —
      test runs must leave the official output directory untouched.
- [ ] The data-outputs docs describe the provenance files and point OSF
      uploaders at the output directory.

## Acceptance

- After one session, the output directory contains the frozen preset, the
  provenance file, and a generated dictionary that names every column the
  study's CSVs actually have — verified by tests that diff dictionary
  contents against a written CSV header.
- Running a second session does not rewrite unchanged provenance; an app
  version change refreshes provenance + dictionary without touching the
  original frozen preset.
- `pytest`, `npm test`, `tsc`, `vite build` stay green.

## Comments

**2026-07-03 — implemented (TDD).** New `app/sidecar/provenance.py`:
`ensure_provenance(out_dir, config, slug)` runs on every `/write-output`,
placed inside the single study-wide decision block in `write_output` so
practice mode (43) will gate it together with the two CSVs. Three files,
namespaced like everything else: `[title]_study.json` (frozen once, **never**
replaced — a changed config is recorded alongside as timestamped
`[title]_study_[ts].json`, once per distinct config, compared parsed so
reformatting isn't a "change"; the timestamp is matched strictly per the
`_count_sessions` rule so a candidate literally named `study` can't shadow a
copy), `[title]_provenance.json` (`app_version` + `engine_version` — both
read from `scoring.__version__` at call time since app and engine ship in
lockstep via the issue-35 handshake, recorded separately so a future split
stays representable — plus `platform.platform()` and the config seed), and
`[title]_data_dictionary.md`. The dictionary is generated from the pydantic
models' own `Field` descriptions: Master CSV section mirrors
`_flatten_metrics` (identity + `BARTMetrics` scalars + per-color
`{color}_{field}` blocks; `condition`/`payout_*` follow the
present-only-when-configured rule), Trials CSV section mirrors
identity + `TrialRecord`, and per-session file sections render
`GameEvent`/`EventPayload`/`BARTMetrics` extras/`ColorMetrics`/`GameSession`
envelope/`TaskConfig`/`ColorProfile` tables. Tests diff the dictionary tables
against **real written CSV headers** (widest schema and default study), so a
column added in code can never go undocumented — the same guard style as
`test_docs`. Refresh rule is write-if-changed (content comparison): a second
session touches nothing (pinned via `st_mtime_ns`), a version bump refreshes
provenance + dictionary but never the frozen preset. Failures follow the
issue-36 contract: any `OSError` becomes a readable warning in
`WriteOutputResponse.warnings`, the session's own files and CSV rows are
never blocked (test chmods the provenance file read-only). Schema changes are
**descriptions only** (`TrialRecord.balloon_color/pumps/outcome`, undescribed
`TaskConfig`/`ColorProfile` fields) — no serialized shape change, so the
frozen-sidecar parity test stays green with no re-freeze. No client change
(response model untouched; no participant-facing strings, so no i18n). Docs:
new "Study-level provenance files" section in `data_outputs.md` with the
right-click → Compress OSF pointer, guarded by
`test_provenance_files_are_documented`. Gates: pytest 159 ✅ (149 → +9
provenance +1 docs), npm test 96 ✅, tsc ✅, vite build ✅.
