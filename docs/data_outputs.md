# Data Outputs Reference

Everything a session writes to disk, and every column of the Master CSV and
the Trials CSV.
Metric *definitions* live in the [Metrics Reference](metrics_reference.md);
this page documents the files and column names as they appear in your output
directory.

## The output directory

All files are written to the study's configured **output directory**
(`TaskConfig.output_dir`, set in Study Setup). If the path cannot be created
or a relative path cannot be resolved, the app falls back to the OS-native
application data directory.

## Session files

Each completed session writes four files, namespaced by study title,
candidate ID, and a UTC timestamp so nothing is ever overwritten:

```
[StudyTitle]_[CandidateID]_[Timestamp]_events.jsonl
[StudyTitle]_[CandidateID]_[Timestamp]_metrics.json
[StudyTitle]_[CandidateID]_[Timestamp]_config.json
[StudyTitle]_[CandidateID]_[Timestamp]_session.json
```

```{list-table}
:header-rows: 1
:widths: 24 76

* - File
  - Contents
* - `*_events.jsonl`
  - Raw pump-level telemetry: one JSON object per `GameEvent` (timestamp,
    type, payload), exactly as recorded by the task.
* - `*_metrics.json`
  - The full scored output — the complete `BARTMetrics` object, including the
    nested `behavioral_profile` narrative and per-color breakdowns.
* - `*_config.json`
  - A snapshot of the exact `TaskConfig` that produced the session, making
    every dataset self-documenting and reproducible.
* - `*_session.json`
  - The session envelope: `session_id`, `game_type`, `candidate_id`, the
    assigned `condition` (`null` for studies without conditions), and
    `duplicate_acknowledged` — `true` when the ID screen warned that this
    participant ID already had recorded sessions and the researcher chose to
    continue, so accidental ID reuse stays visible in the data. Keeps the
    session's identity in the data itself — not just in filenames — so the
    Master CSV can always be rebuilt from the per-session files.
```

## The Master CSV

Alongside the per-session files, the sidecar appends **one flat row per
session** to a single shared spreadsheet in the output directory:

```
[StudyTitle]_results.csv
```

- The file is created **with a header row** on the first write.
- Per-color metrics are flattened to `{color}_{field}` columns so they load
  as plain variables in SPSS or R.
- The nested `behavioral_profile` narrative is **deliberately excluded** —
  it is not meaningful as spreadsheet cells; read it from `*_metrics.json`.

### Upgrading mid-study: migration and backups

Software updates can add columns to the Master CSV. The writer compares the
file's header to the current column schema on every append, so one file per
study stays the rule even across app versions — columns are never silently
misaligned:

- **Header matches** — the row is appended, exactly as before.
- **Older header** (the file predates newly added columns) — the file is
  first copied to a timestamped backup
  (`[StudyTitle]_results_backup_[Timestamp].csv`), then rewritten under the
  current header: pre-upgrade rows keep their values by column *name* and get
  **honest blanks** in the new columns. The new session row is appended and
  the migration is reported in the write response's `warnings`.
- **Unknown columns** (the file was written by a *newer* app version) — the
  file is left untouched; the session row is written to a timestamped sibling
  file (`[StudyTitle]_results_unmerged_[Timestamp].csv`) with a warning, for
  you to merge by hand.
- **Locked, unwritable, or damaged file** (e.g. open in Excel, or re-saved
  in a non-UTF-8 encoding) — same sibling-file fallback: the session is
  never lost and never aborts the run.

### Identity columns

| Column | Meaning |
|--------|---------|
| `timestamp_utc` | Session write time (UTC, filename-safe format) |
| `session_id` | The client-generated session identifier |
| `candidate_id` | The participant ID entered at the start of the run |
| `condition` | The condition assigned at the ID screen — **present only for studies whose preset declares `conditions`**; studies without conditions keep their original column set. Sessions written before conditions were added to a running study carry an honest blank (see the migration rules above). |

### Session-integrity columns

| Column | Meaning |
|--------|---------|
| `session_valid` | Overall validation verdict for the session |
| `session_warnings` | Validation warnings (JSON-encoded list in one cell) |
| `total_balloons` | Balloons played |
| `total_pumps` | Total pumps across the session |
| `total_explosions` | Balloons lost to bursts |
| `total_collections` | Balloons banked |

### Risk-taking and calibration columns

| Column | Meaning |
|--------|---------|
| `average_pumps_adjusted` | Mean pumps on collected balloons (RNG-truncation safe) |
| `avg_pumps_all_balloons` | Mean pumps across all balloons |
| `rng_normalized_pumps` | Mean pumps as a ratio of the EV-optimal stop |
| `ev_ratio_score` | EV(participant)/EV(optimal) × 100, EV-weighted across colors |
| `risk_calibration_score` | Calibration score (explosion penalty reported separately) |
| `explosion_penalty` | Excess explosion rate vs expected at optimal play |
| `explosion_rate` | Observed explosion rate |
| `ev_efficiency_uniformity` | 1 − CV of per-color EV efficiencies (empty when fewer than two risk contexts) |
| `ev_optimal_stops` | Per-color EV-optimal stops (JSON-encoded mapping in one cell) |
| `risk_adjustment_score` | Alignment with the per-color optimal stops |
| `risk_sensitivity` | Pump differentiation across hazard levels |
| `color_discrimination_index` | Purple-vs-orange pump differentiation |
| `patience_index` | Distance above/below optimal stopping |
| `patience_index_normalized` | Normalized patience index |
| `impulsivity_index` | Latency-based impulsivity (fast pumping) |
| `mean_latency_between_pumps` | Mean inter-pump latency (ms) |

### Learning and adaptation columns

| Column | Meaning |
|--------|---------|
| `learning_rate` | Session-long learning estimator |
| `half_split_learning_rate` | First-half vs second-half improvement |
| `tercile_learning_rate` | First-third vs last-third improvement |
| `color_discrimination_trajectory` | Change in color differentiation across the session |
| `post_explosion_sensitivity` | Pump change after a same-color explosion |

### Consistency and composite columns

| Column | Meaning |
|--------|---------|
| `response_consistency` | Overall response consistency |
| `within_balloon_consistency` | Pump-timing consistency within balloons |
| `between_balloon_consistency` | Pump-count consistency between balloons |
| `flat_strategy_detected` | Undifferentiated pumping across colors (boolean) |
| `adaptive_strategy_score` | Composite: calibration, learning, uniformity, earnings |
| `money_collected` | Session earnings in the study's currency |
| `money_efficiency` | Earnings relative to simulated optimal play |

### Per-color columns — `{color}_{field}`

One set per configured color, in the study's color order (for the default
study: `purple_…`, `teal_…`, `orange_…`):

| Field (as `{color}_{field}`) | Meaning |
|------------------------------|---------|
| `{color}_average_pumps` | Mean pumps on this color (all balloons) |
| `{color}_behavioral_avg_pumps` | Mean pumps on collected balloons of this color |
| `{color}_total_balloons` | Balloons of this color played |
| `{color}_collected_count` | Balloons of this color banked |
| `{color}_explosion_rate` | Explosion rate on this color |
| `{color}_excess_explosion_rate` | Explosion surplus vs optimal play on this color |
| `{color}_ev_efficiency` | EV efficiency on this color |
| `{color}_ev_optimal_stop` | The color's numeric EV-optimal stop |
| `{color}_risk_profile` | The color's risk tier label |
| `{color}_used_fallback` | Whether all-balloon data substituted for collected-only |

In addition, the default study's colors carry three legacy convenience
columns mirrored from the top-level metrics: `purple_avg_pumps`,
`teal_avg_pumps`, and `orange_avg_pumps` (i.e. `{color}_avg_pumps`; present
for the default color names only).

### What is *not* in the CSV

`behavioral_profile` — the narrative risk-style classification with its
description and dominant traits — is only in `*_metrics.json`. Join the CSV
to the JSON files on `candidate_id` + `timestamp_utc` if you need it in a
dataframe.

## The Trials CSV

Alongside the session-level Master CSV, the sidecar appends **one row per
trial (balloon)** to a second study-wide spreadsheet — the long-format table
mixed-model analyses in R or SPSS consume directly, with no manual
concatenation of per-session files:

```
[StudyTitle]_trials.csv
```

Rows are appended in session order at each session's completion, and the file
follows the same [migration and backup rules](#upgrading-mid-study-migration-and-backups)
as the Master CSV (header on create, timestamped backup + auto-migrate on a
schema change, timestamped `*_unmerged_*` sibling when the file is locked).
The trial rows are computed by the scoring engine (`scoring.bart.trial_table`),
so CLI users of the `scoring` package get exactly the same table.

| Column | Meaning |
|--------|---------|
| `timestamp_utc` | Session write time (UTC) — same value as the session's Master CSV row |
| `session_id` | The client-generated session identifier |
| `candidate_id` | The participant ID entered at the start of the run |
| `condition` | The session's assigned condition — present only for studies whose preset declares `conditions`, exactly as in the Master CSV |
| `trial` | 1-based trial index within the session |
| `balloon_color` | The balloon's color name |
| `hazard_family` | The hazard family this balloon's color ran under (from the study config) |
| `pumps` | Pumps on this balloon |
| `outcome` | `collected` (banked) or `exploded` (popped) |
| `trial_earnings` | Pumps × reward when collected; 0 when popped |
| `mean_latency_between_pumps` | Mean gap between this trial's successive pumps (ms); empty when the trial has fewer than two pumps |
