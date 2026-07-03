# Atomic dual-format persistence with master CSV aggregation

The sidecar's `/write-output` endpoint writes three artifacts atomically from a single `{ session, config }` POST on session completion:

1. **`[CandidateID]_[Timestamp]_events.jsonl`** — raw GameEvent telemetry (one JSON object per line), the lossless archival record.
2. **`[CandidateID]_[Timestamp]_metrics.json`** — the full scored BARTMetrics output for this session.
3. **Append one row to `[StudyTitle]_results.csv`** — the master spreadsheet. If the file does not exist, write the header row first; then append. This is the only aggregated output; it exists so researchers can open a single file in Excel/SPSS at the end of a study without running merge scripts.

Individual session files are uniquely named (candidate ID + ISO timestamp) to guarantee no overwrites even if the same participant runs twice.

## Output directory resolution

The output path comes from `TaskConfig.output_dir`. On locked-down lab machines where the configured path is unwritable (common on clinical Windows installs and university-managed macOS), the sidecar falls back to the OS-native application data directory:

- macOS: `~/Library/Application Support/com.metu.bart/sessions`
- Windows: `%LOCALAPPDATA%\com.metu.bart\sessions`

This was wired in Issue 11. The fallback is silent (logged, not surfaced to the participant) to avoid disrupting a session in progress.

## Why individual files + master CSV (not just one or the other)

- Individual files prevent a corrupt or locked master CSV from losing session data — the per-session files are always the source of truth.
- The master CSV prevents the common researcher complaint of "I have 200 JSON files and no idea how to merge them." It is a convenience layer, rebuildable from the individual files.
- A single atomic `/write-output` call (rather than separate persist + aggregate endpoints) guarantees both succeed or the sidecar reports a single coherent error.

## Amendment (2026-07-02, issues 16/28/37)

The artifact set has grown since this decision was recorded; the atomicity and
rebuildability rules are unchanged:

- Filenames gained a `[StudyTitle]_` prefix, and a third per-session file was
  added alongside events + metrics: **`*_config.json`**, the exact `TaskConfig`
  snapshot that produced the session (issue 16).
- **`*_session.json`** (issue 37) — the session envelope: `session_id`,
  `game_type`, `candidate_id`, and the assigned `condition`. Before this file,
  session identity lived only in filenames and the master CSV row, so the
  "rebuildable from the individual files" claim above did not actually hold for
  identity columns. It now does; issue 38's duplicate-ID acknowledgment gets
  recorded here too.
