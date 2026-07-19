# Multi-station studies

Running one participant at a time on one machine needs nothing on this page —
the app already maintains a single Master CSV as you go, and you are done.

This page is for the other case: **several machines collecting the same study
at once**. Then the shared spreadsheet is exactly what breaks. Each machine
maintains its own copy, and at the end of collection you are left holding a
folder of near-identical CSVs to concatenate by hand, with no reliable way to
tell whether two of them were even running the same design.

Standalone Mode plus the Data Hub replaces that with: stations write only their
own session files, you collect the folders, and the Hub rebuilds the study-wide
outputs in one pass — telling you, itemized, everything it found along the way.

:::{note}
The instrument never uses the network. Stations cannot see each other, and
nothing is uploaded. "Collection" here means USB stick, network share, or
whatever institutional sync your lab already uses.
:::

## 1. Turn on Standalone Mode in the study

In Study Setup, set **Standalone Mode** on before distributing the study.
It rides in the `study.json` you hand to every machine, so all stations agree
by construction.

This is deliberately a property of the *study*, not a per-machine preference.
If it were a machine setting, one station left un-toggled would go on quietly
writing its own partial Master CSV — and you would not find out until analysis.

It changes exactly one thing: stations no longer append to the study-wide
`_results.csv` and `_trials.csv`. Every station still writes the four
per-session files and all three provenance files, so each station folder stays
independently complete and OSF-ready.

## 2. Label each machine, once

On each machine, open Study Setup. The identity bar shows a
**Standalone Mode · Station: …** badge; click it to set that machine's label
(`S1`, `lab-A-03` — anything short and filename-safe).

This is a per-machine app setting, not part of the study, and it is entered
once at setup — never per participant. The badge re-displays it every session
so a mislabelled machine is visible before you run anyone.

**A station with no label cannot run sessions in Standalone Mode.** That is
deliberate: an unlabelled station's data is unattributable after the fact, and
that is not recoverable, so the app blocks it at the point where it is still
trivial to fix.

The label is stamped into the filename, into every `session.json`, and into
`provenance.json`. A random per-install UUID is stored beside it — which is how
the Hub can tell two machines that were *both* labelled `S1` apart from one
machine's legitimate data. Offline, no machine can know another's label, so
duplicate labels cannot be prevented at entry; they can only be detected at
assembly, and this is what makes that possible.

:::{admonition} Fixed seeds across stations
:class: warning

The balloon sequence is reproducible from `(seed, participant ID)`. So if two
participants on two different stations are given the *same* ID under a fixed
seed, they see **identical** balloon sequences — their sessions are not
independent observations. Study Setup warns about this inline whenever
Standalone Mode and a fixed seed are on together. Keep participant IDs globally
unique across stations, or leave the seed unset. The Hub flags it loudly if it
happens anyway.

If you have no external ID scheme to keep unique, the study option below does
it for you and the warning downgrades to a note.
:::

### Optional: let the app generate participant IDs

Keeping IDs unique across machines that cannot see each other is exactly the
kind of thing people get wrong at 9am with a queue of participants. Setting
`"auto_participant_id": true` in the study preset puts a **Generate** button
on the participant-ID screen; it fills the field with a random nine-digit
number, and the space is wide enough (~0.055% collision at a pooled N of 1000)
that a duplicate is an anomaly rather than an expectation.

It is off by default and independent of Standalone Mode — plenty of
multi-station studies hand out meaningful central IDs from a roster and should
leave it alone. When it is on, the field stays editable: regenerate by tapping
again, or clear it and type your own, because the participant ID is your join
key to consent and payment records and the app should never take it away from
you. Each session records which path its ID came from (`id_source`), which is
what lets the Hub distinguish a near-impossible collision between two
generated IDs — reported in its own louder line — from ordinary hand-typed ID
reuse. See [Auto-generated participant IDs](../data_outputs.md#auto-generated-participant-ids)
for the format and the reasoning.

## 3. Run participants as usual

Nothing about the participant-facing flow changes. The only visible difference
is on the researcher's return screen at the end of a session: where the Master
CSV row would normally confirm a write, it states

> Master CSV — **Not written on this station (Standalone Mode; assembled at
> the Hub)**

rather than a silent dash. The per-session and provenance files are confirmed
as always. A mode this consequential should never have to be inferred from
something's absence.

## 4. Collect the station folders

When collection is done, copy each station's output directory somewhere the
Hub machine can read — one folder per station:

```
studies/stress-2026/
  lab-01/
  lab-02/
  lab-03/
```

The folder names are yours; the Hub reads each station's identity from the
files inside, not from what you called the directory. Copy rather than move if
you like — an identical copy of a session appearing in two folders is
recognised and collapsed, not double-counted.

## 5. Rebuild in the Data Hub

Open the **Data Hub** tab — a peer of Study Setup, not something launched from
inside a study.

**Sources.** Add the station folders (drop them in, or use the folder picker).
Each row shows the station and how many sessions it holds. Sources are strictly
read-only; the Hub never writes into a folder it is reading.

**Ingestion report.** As soon as sources are added, the report appears — and
it stays visible. It is never a modal, never a gate, and never something you
click past. It is the Hub's primary deliverable, in three groups:

- **Held** — excluded until you resolve them. The rest of the rebuild proceeds
  regardless; a hold affects only the sessions listed.
- **Attention** — pooled into the output, but itemized so you know they are
  there.
- **Clean / informational** — everything that went in without incident, plus
  notes like collapsed duplicate copies.

**Output.** Choose a destination folder — a fresh one, separate from every
source. Optionally override the metrics mode (see below). The file tree
previews exactly what will be written. Then **Rebuild**.

The Hub refuses to write into a source folder, and refuses to overwrite a
non-empty folder that is not itself a previous rebuild. Re-running into a
previous rebuild replaces it cleanly.

## What the Hub writes

Data filenames **mirror the live path exactly** — `{Study}_results.csv`,
`{Study}_trials.csv`, `{Study}_data_dictionary.md` — so an analysis script
written against a single-station study runs against a rebuild verbatim. A
reconstruction is identified by its location, its provenance stamp, and the
presence of an ingestion report, never by a mangled filename.

```
rebuilt/
  {Study}_ingestion_report.md     the itemized report
  {Study}_provenance.json         with reconstructed: true, sources, rebuild mode
  {Study}_results.csv             one row per session
  {Study}_trials.csv              one row per balloon
  {Study}_data_dictionary.md
```

The Hub writes only the pooled study-wide surfaces. It never modifies, mirrors,
or rewrites your per-session files — those stay in the read-only sources as the
archival record.

If config drift forced a partition (below), each partition gets its own
self-contained subdirectory (`partition-1/`, `partition-2/`) under a shared
ingestion report. The ordinary single-partition case stays flat.

## What it re-scores, and why

Every session is **re-scored from its raw `events.jsonl`**, with the Hub's own
engine. The stored `metrics.json` is not the data source — it is a check.

The reason is version skew. Study-level provenance records the last app that
touched a folder, so in a study collected across machines that upgraded at
different times, no station folder can tell you which engine actually scored
which session. Re-scoring dissolves the problem: the pooled dataset is uniform,
and its provenance truthfully names the single engine that produced it.

The Hub then compares each re-score against the stored metrics and reports what
it finds, graded by the [per-session engine stamp](../data_outputs.md#the-engine-stamp):

| What it sees | How it is reported |
|---|---|
| Same engine version, different metrics | **Attention (loud)** — an identical engine on identical events must reproduce; this suggests corruption or tampering |
| Different engine version, different metrics | Informational — benign version drift, expected |
| No engine stamp, different metrics | **Attention** — pre-stamp data, so benign drift and corruption cannot be told apart |
| Metrics match | Clean |

This never blocks anything and never changes what is written — the re-scored
value is always what lands. It only decides how loudly the difference is
reported.

## What it flags

The governing rule is that **the Hub never acts silently**. Every session is
either included cleanly or its departure is named. In brief:

| Situation | What happens |
|---|---|
| The same session copied into two folders | Collapsed to one; noted as a count |
| The same session ID with **different** contents in two folders | **Held.** The Hub will not guess which copy is authoritative |
| Two machines sharing a station label | **Attention** — their data cannot be told apart by label |
| The same participant ID on more than one station | Pooled, never rewritten; an unambiguous `participant_key` (`S1::P001`) column is added. **Loud** if both ran the same fixed seed — those sessions are not independent |
| Two **auto-generated** participant IDs colliding across stations | Pooled like any collision, but reported on its own **loud** line — near-impossible by chance, so it points at duplicated data or a broken generator |
| A station running a *different task design* (hazard curves, reward, conditions, payout, language) | **Partitioned** into a separate output set — pooling incomparable tasks is the one thing worse than stopping |
| A station differing only in seed, currency, or schema version | Flagged, still pooled |
| Only `output_dir` differs | Ignored |
| An older study schema | Pooled — current defaults fill the gaps |
| A *newer* study schema than this Hub | **Held** — upgrade the Hub and re-run |
| `metrics.json` missing, events present | Kept and re-scored; only the verify check is skipped |
| `events.jsonl` or `session.json` missing | **Held** — unrebuildable, or identity compromised |
| Unreadable or truncated JSON | **Held**, that session only — one bad file never sinks two hundred good ones |
| Unrelated files in the folder | Ignored, with a one-line count |

The Hub aborts for exactly one reason: it cannot establish what study it is
looking at at all. Everything else is a report line.

Participant IDs are **never rewritten**, station labels are never invented, and
no session is ever dropped to make the output tidier.

## Classic and Advanced at rebuild

By default the Hub rebuilds in the study's own configured metrics mode, which
is what makes a rebuild comparable to live output.

You can override it. Because the Hub re-scores from raw events, it can do
something the live path cannot: produce the **full Advanced metric set from a
study that was collected in Classic**. The reconstructed provenance records
which mode was used, so the output is self-describing either way.

Unlike a real design difference, a mid-study mode change does not partition at
rebuild. Mode only decides which columns project out — it says nothing about
what the participant actually experienced — so the Hub re-projects every
session into the one chosen mode and they unify.

## From the command line

The same core, without the UI:

```bash
openbart hub <source>... --out <dir> [--mode classic|advanced] [--force] [--dry-run]
```

`--dry-run` runs ingestion and prints the report without writing anything.
`--force` replaces a previous rebuild in place. The report printed is the same
one the destination file carries.

Exit codes, for scripting:

| Code | Meaning |
|---|---|
| `0` | Clean rebuild |
| `2` | Held sessions present; the rebuild proceeded on the rest |
| `3` | No study identifiable in any source; nothing rebuilt |
| `4` | Destination refused — inside a source, containing a source, non-empty, or a prior rebuild without `--force` |
| `64` | Usage error |

In a clone, run it as `python -m sidecar hub …`; the frozen sidecar binary
exposes the same `hub` subcommand.

## See a worked example

[`docs/samples/`](https://github.com/aslmylmz/open-bart/tree/main/docs/samples)
contains a four-station study with one problem planted in each session —
a sneakernet duplicate, two machines sharing a label, an ID reused across
stations, a station left on a different currency, a station running the task in
a different language, stored scores that disagree with the events, files that
never made it back — together with the `rebuilt/` output the Hub made of it,
where the language difference is what splits the data into two partitions.
Reading
[its ingestion report](https://github.com/aslmylmz/open-bart/blob/main/docs/samples/hazard-suite/rebuilt/hazard-suite_ingestion_report.md)
is the fastest way to see what the Hub tells you when data is imperfect.

For the files and columns themselves, see the
[Data Outputs Reference](../data_outputs.md).
