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

The directory is **permanently OSF-ready**: everything a methods section or
an [OSF](https://osf.io) upload needs is written there automatically (see the
provenance files below). There is no export step — to publish or archive a
study, compress the output directory as-is and upload it.

## Study-level provenance files

The first session of a study writes three study-level files next to the
session data, namespaced by study title like everything else. They are
maintained automatically on every subsequent session; no one has to remember
to create or update them.

```
[StudyTitle]_study.json
[StudyTitle]_provenance.json
[StudyTitle]_data_dictionary.md
```

```{list-table}
:header-rows: 1
:widths: 28 72

* - File
  - Contents
* - `[StudyTitle]_study.json`
  - A **frozen copy** of the exact study configuration the study started
    under. It is written once and never replaced. If a *changed* config runs
    sessions into the same directory (a mid-study design change), the changed
    config is recorded alongside as a timestamped
    `[StudyTitle]_study_[Timestamp].json` — one copy per distinct config,
    however many sessions run under it — so the original design always stays
    auditable.
* - `[StudyTitle]_provenance.json`
  - The provenance record a methods section needs: `app_version`,
    `engine_version`, `platform`, and the study's RNG `seed`. Refreshed
    automatically when it no longer matches the running app (e.g. a mid-study
    upgrade); left untouched otherwise.
* - `[StudyTitle]_data_dictionary.md`
  - A data dictionary **generated from the scoring models themselves**: every
    column of this study's Master CSV and Trials CSV — including the
    study-specific per-color and conditional columns — plus every field of
    the four per-session files. Because it is generated, a column added in a
    future version appears in the dictionary automatically; it is regenerated
    whenever the schema (or the running config's column set) changes. Do not
    edit it by hand.
```

Like the CSV writers, provenance upkeep never blocks a session: if one of
these files cannot be written (locked, read-only), the session's own data is
saved exactly as always and the problem is reported in the write response's
`warnings`.

## Session files

Each completed session writes four files, namespaced by study title,
candidate ID, and a UTC timestamp so nothing is ever overwritten:

```
[StudyTitle]_[CandidateID]_[Timestamp]_events.jsonl
[StudyTitle]_[CandidateID]_[Timestamp]_metrics.json
[StudyTitle]_[CandidateID]_[Timestamp]_config.json
[StudyTitle]_[CandidateID]_[Timestamp]_session.json
```

Once a machine has been given a [station label](#standalone-mode-and-the-data-hub)
it is inserted after the title
(`[StudyTitle]_[Station]_[CandidateID]_[Timestamp]_…`), so two machines can
never produce the same filename however their clocks are set. The segment
follows the label, not the mode: a machine with no label set — the
single-machine default — writes the filenames shown above, unchanged.

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
    assigned `condition` (`null` for studies without conditions),
    `duplicate_acknowledged` — `true` when the ID screen warned that this
    participant ID already had recorded sessions and the researcher chose to
    continue, so accidental ID reuse stays visible in the data — `practice`,
    `true` for [Test Run sessions](#test-run-practice-sessions), the
    `station_id` that recorded it, the
    [`id_source`](#auto-generated-participant-ids) of the participant ID, and
    the [`engine` stamp](#the-engine-stamp). Keeps the session's identity in the
    data itself — not just in filenames — so the Master CSV can always be
    rebuilt from the per-session files.
```

### The engine stamp

Every `*_session.json` carries a nested `engine` block recording what actually
ran the session:

```json
"engine": {
  "app_version": "1.1.0",
  "engine_version": "1.1.0",
  "platform": "macOS-15.5-arm64-arm-64bit"
}
```

It is written by the sidecar at write time — never supplied by the task — so
it states the truth about the run rather than a client's claim. The study-level
`_provenance.json` records the same three facts, but it is refreshed in place
on an upgrade, which means it can only ever describe the *last* app that
touched the study. The per-session copy is what lets a mid-study upgrade, or a
study collected across machines running different versions, still be
attributed session by session. It is also why the field cannot be added
retroactively: engine version is a write-time fact, so sessions recorded before
this stamp existed are permanently unversioned (they read as `null`, and the
[Data Hub](#standalone-mode-and-the-data-hub) grades them as *ungraded* rather
than guessing).

### Auto-generated participant IDs

Set `"auto_participant_id": true` in the study preset and the participant-ID
screen gains a **Generate** button, which fills the field with a random
nine-digit number (`482719300`). It is off by default, and independent of
[Standalone Mode](#standalone-mode-and-the-data-hub) — a multi-station study
that hands out its own roster IDs should leave it off.

The point is collision resistance across machines that cannot see each other.
Nine digits puts the chance that two participants in a pooled sample of 1000
share an ID at about 0.055%, so a collision the [Data Hub](#standalone-mode-and-the-data-hub)
reports is a real anomaly — duplicated data or a broken generator — rather
than routine ID messiness. It also settles the fixed-seed hazard: two
participants with the same ID on different machines would replay the same
balloon sequence, and globally unique IDs make that impossible. The Study
Setup screen's seed warning says so, downgrading to an informational note when
the option is on.

The format is deliberately plain. A bare integer is shape-identical to the
`subjID` convention that hBayesDM, PEBL, and Inquisit already expect, so a
generated ID needs no translation on the way into an analysis pipeline; the
first digit is never zero, because Excel and SPSS strip leading zeros on
import and break the join against your own records.

Nothing about it is mandatory. The field stays editable — regenerate by
tapping again, or clear it and type your own — because `candidate_id` is your
external join key to consent, payment, and screening records, and a forced
random number would destroy that. Each session records which path the ID
actually came from:

```json
"id_source": "generated"
```

`"generated"` or `"manual"`, and `null` for studies that never offered the
button (where every ID is hand-typed anyway) or for data recorded before the
option existed. This is what lets the Hub tell a near-impossible collision
between two *generated* IDs from an ordinary hand-typed duplicate.

## Test Run (practice) sessions

Use the **Test run** button in the Researcher View to click through a study —
new preset, new lab machine, RA training — without touching the dataset.
A Test Run is the real pipeline end-to-end (gameplay, scoring, file writing),
so a passing test run is evidence the real thing works. It differs from an
official run in exactly three ways:

- **Destination.** Its four session files land in a `practice/` subfolder of
  the output directory — inspectable, but never mingled with official data.
  The Master CSV, the trials CSV, and the provenance files are **never**
  created, appended to, or refreshed by a practice session.
- **Stamps.** The participant ID is pre-filled with `TEST` (practice is
  exempt from the ID guardrails), and the session envelope carries
  `"practice": true`, so a stray file is identifiable by content, not just by
  location.
- **Banner.** Every screen of the session — consent, ID, gameplay, debrief —
  wears a high-contrast "TEST RUN — data not recorded" banner, so a real
  participant can never be run in practice mode unnoticed.

When publishing or archiving an output directory, the `practice/` subfolder
can simply be deleted (or left in — it is clearly separated and stamped).

## The Master CSV

Alongside the per-session files, the sidecar appends **one flat row per
session** to a single shared spreadsheet in the output directory:

```
[StudyTitle]_results.csv
```

- The file is created **with a header row** on the first write.
- Per-color metrics are flattened to `{color}_{field}` columns so they load
  as plain variables in SPSS or R.
- Non-scalar fields are **deliberately excluded** so every cell is scalar and
  loads cleanly in SPSS/R: the nested `behavioral_profile` narrative, the
  `session_warnings` list, and the `ev_optimal_stops` mapping. Read them from
  `*_metrics.json`. (The per-color EV-optimal stops are also available as the
  scalar `{color}_ev_optimal_stop` columns.)

In a [multi-station study](#standalone-mode-and-the-data-hub) this file is not
written as sessions run — one per machine would fragment the dataset. The
per-session files are still written exactly as above, and the Data Hub builds
this file under this same name once the folders are collected, so analysis
scripts run against it unchanged. A multi-station rebuild adds two identity
columns the live path has no use for: a leading `station_id`, and
`participant_key` (`S1::P001`) — an unambiguous key for the case where the same
participant ID was issued on more than one station.

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
| `session_valid` | Overall validation verdict for the session (the `session_warnings` list itself is JSON-only — see `*_metrics.json`) |
| `total_balloons` | Balloons played |
| `total_pumps` | Total pumps across the session |
| `total_explosions` | Balloons lost to bursts |
| `total_collections` | Balloons banked |

### Risk-taking and calibration columns

| Column | Meaning |
|--------|---------|
| `average_pumps_adjusted` | Mean pumps on collected balloons (RNG-truncation safe); empty when zero balloons were collected |
| `avg_pumps_all_balloons` | Mean pumps across all balloons |
| `rng_normalized_pumps` | Mean pumps as a ratio of the EV-optimal stop |
| `ev_ratio_score` | EV(participant)/EV(optimal) × 100, EV-weighted across colors |
| `risk_calibration_score` | Calibration score (explosion penalty reported separately) |
| `explosion_penalty` | Excess explosion rate vs expected at optimal play |
| `explosion_rate` | Observed explosion rate |
| `ev_efficiency_uniformity` | 1 − CV of per-color EV efficiencies (empty when fewer than two risk contexts) |
| `risk_adjustment_score` | Alignment with the per-color optimal stops |
| `risk_sensitivity` | Pump differentiation across hazard levels |
| `color_discrimination_index` | Safest-vs-riskiest color pump differentiation |
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

### Payout columns

For studies whose preset declares a `payout` block (issue 41) — a conversion
rate and a freeform currency label ("₺", "$", "credits") — the amount
actually owed is recorded next to the task-internal earnings. Like
`condition`, these columns are **present only for studies that configure a
payout**; other studies' column sets are unchanged.

The rounding rule, applied once in the scoring engine (so the debrief screen
and the CSV can never disagree): `payout_amount = money_collected ×
payout.rate`, rounded **half-up** to 2 decimals (0.725 → 0.73 — not banker's
rounding).

| Column | Meaning |
|--------|---------|
| `payout_amount` | The converted amount owed to the participant |
| `payout_currency` | The preset's freeform currency label, verbatim |

### Data-quality (QC) columns

Automatic data-quality flags (also in `*_metrics.json`). **Flags annotate,
never exclude**: no session is ever dropped, reordered, or withheld because a
rule tripped — exclusion is the analyst's preregistered decision. Thresholds
are configurable in the Study Preset's optional `qc` block and travel in
`study.json`; when the block is absent, the literature-informed defaults
below apply. The thresholds each session was actually judged against are
recorded in its own row, so a flag's criteria can be stated post hoc.

| Column | Rule | Default |
|--------|------|---------|
| `qc_fast_response_trials` | Number of trials containing at least one inter-pump gap faster than the fast-response threshold | threshold: 100 ms (`qc.fast_response_ms`) |
| `qc_zero_pump_streak` | Longest run of consecutive trials with zero pumps | threshold: 5 trials (`qc.zero_pump_streak`) |
| `qc_flagged` | `True` when any rule tripped: a fast-response trial exists, or the zero-pump streak reached the threshold | — |
| `qc_fast_response_ms` | The fast-response threshold (ms) this session was judged against | 100 |
| `qc_zero_pump_streak_threshold` | The streak length this session was judged against | 5 |

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

In addition, `orange_avg_pumps` is a single top-level column: the mean collected
pumps on the study's **highest-risk** color (the color with the lowest EV-optimal
stop). It keeps its historical name from the default study — for a renamed study
it still holds the riskiest color's average, not a color literally named orange.
Per-color averages for every color are the `{color}_average_pumps` and
`{color}_behavioral_avg_pumps` columns above; there is no separate low- or
mid-risk top-level average column.

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

## Metrics mode: Classic and Advanced

Everything documented above is the **Advanced** surface — the default, and the
full set of metrics the engine derives. A study can instead be configured
(`metrics_mode: "classic"` in Study Setup) to report the **Classic** surface:
the canonical Lejuez BART scores and nothing else.

Classic is a **projection, not a second scoring engine**. The engine always
computes the full metric set; the mode decides which of those columns are
written. So a Classic column is never a differently-computed column — it is the
same value under the same name, and the Classic column set is a strict subset
of the Advanced one. Nothing is lost that cannot be recovered: `*_events.jsonl`
remains complete raw telemetry, so a Classic study can be re-scored into the
full Advanced set at any time (the [Data Hub](#standalone-mode-and-the-data-hub)
does exactly this with a one-flag override).

**The five canon metrics.** These are the published BART scores, kept under
this project's field names, with the literature name and definition of each
carried in the generated data dictionary:

| Column | Canonical meaning |
|--------|-------------------|
| `average_pumps_adjusted` | The adjusted average pumps (Lejuez et al., 2002) — the primary BART score, computed over unexploded balloons |
| `total_explosions` | Number of explosions — the **count**, not a rate |
| `total_pumps` | Total pumps across the session (Lejuez et al., 2003) |
| `avg_pumps_all_balloons` | Unadjusted average pumps across all balloons, exploded included |
| `money_collected` | Total earnings from collected balloons |

```{admonition} The adjusted score reproduces a known bias, deliberately
:class: note

`average_pumps_adjusted` is the canonical estimator **as published**, which is
biased under right-censoring (Pleskac et al., 2008). Classic mode exists for
comparability with the published literature, so it reproduces the canonical
score rather than improving it. The Advanced surface carries the
censoring-corrected measures alongside.
```

**Plus an integrity tier.** Classic also keeps `session_valid`,
`session_warnings`, `total_balloons`, the `qc_*` family, and the `payout_*`
pair when a payout is configured. A five-column Classic file would strip an
analyst's only signal of which sessions to trust; the canon defines which
*metrics* are reported, not whether the dataset says it is sound.

**Dropped in Classic:** every derived behavioral metric (calibration, learning,
consistency, composites) and all per-color `{color}_*` blocks — Classic is
session-level only, matching the single-balloon 2003 replication format. From
the Trials CSV it drops `mean_latency_between_pumps`; the rest of the trial row
is design and behavior, not a metric, and is kept.

The mode reaches every derived surface uniformly — Master CSV, Trials CSV,
`*_metrics.json`, and the data dictionary — and is recorded in the frozen
`study.json`, each session's `config.json`, `_provenance.json`, and the data
dictionary header. There is no per-row mode column: the mode is constant within
a file.

Changing mode mid-study **starts a new output lineage** rather than rewriting
history. Classic → Advanced widens the file under the ordinary
[migration rules](#upgrading-mid-study-migration-and-backups) (backup, then
honest blanks in the new columns); Advanced → Classic cannot narrow a file
in place, so the session lands in a timestamped sibling with a warning. A Hub
rebuild is not subject to this — it re-projects every session into one chosen
mode.

## Standalone Mode and the Data Hub

A lab running one participant at a time on one machine needs nothing here.
**Standalone Mode** is for running many machines at once, where the shared
Master CSV is the thing that breaks: each station would maintain its own,
leaving the researcher to concatenate files that may not even be comparable.

Setting `standalone: true` in the study preset changes **exactly one thing
about what is written**: stations stop appending to the study-wide
`_results.csv` and `_trials.csv`. Everything else lands exactly as documented
on this page — the four per-session files *and* all three provenance files, on
every station. Each station folder stays independently complete and OSF-ready.

The station's own label is a separate per-machine setting (`S1`, `lab-A-03`).
It is stamped into three places: the filename stem, each `session.json`, and
`provenance.json` — which also gains a random per-install UUID, so that two
machines accidentally given the same label can still be told apart.

Collection is by hand — USB, network share, institutional sync; the app never
uses the network. You then point the **Data Hub** at the assembled folders and
it rebuilds `_results.csv`, `_trials.csv`, and the data dictionary under their
usual names, re-scoring every session from its raw events, alongside an
itemized report of everything it found.

For the workflow itself — turning the mode on, labelling machines, reading the
ingestion report, the CLI, and what the Hub flags — see
[Multi-station studies](standalone/multi_station.md). This page stays the
reference for the resulting files and columns.

## A worked sample dataset

[`docs/samples/`](https://github.com/aslmylmz/open-bart/tree/main/docs/samples)
holds two small studies produced by the instrument itself and committed to the
repository, so you can read real output — and a real Hub reconstruction —
without installing anything:

- **`clean-equivalence/`** — what a study directory looks like: three sessions,
  every file described on this page, no defects.
- **`hazard-suite/`** — four station folders as they arrive from the field,
  with one problem planted per session — including one station left running the
  task in a different language, which is why the rebuild splits into two
  partitions — and the `rebuilt/` output the Hub made of them, with its
  itemized ingestion report.

They are generated, never hand-edited, and a test regenerates and byte-compares
them on every run — so what is committed is always what today's code emits.
The sessions are synthetic fixtures, not participant data.
