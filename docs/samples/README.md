# Sample dataset

Two small studies produced by the instrument itself, committed so you can read
real output — and a real Data Hub reconstruction — without installing or
running anything.

**These are not participant data.** Every session here was generated
synthetically by a deterministic builder; the participant IDs, timestamps,
machine identifiers and platform string are all fixtures.

## `clean-equivalence/` — what a study directory looks like

One station, three clean sessions, no defects: the four per-session files
(`_events.jsonl`, `_metrics.json`, `_config.json`, `_session.json`) beside the
study-wide surfaces the app maintains as it runs — the master `_results.csv`,
the per-balloon `_trials.csv`, the generated `_data_dictionary.md`, and the
`_provenance.json` / `_study.json` records that make the folder self-describing.

This folder is the reference behind the Hub's fidelity claim: reconstructing
these CSVs from the per-session files alone reproduces them **byte for byte**.
The test that proves it is `tests/hub/test_hub_equivalence.py`, and it produces
both sides from the current code rather than trusting the copy committed here.

## `hazard-suite/` — what the Hub says when data is imperfect

Four station folders (`lab-01/`, `lab-01-second/`, `lab-02/`, `lab-03/`) as
they would arrive from the field after a multi-station study, with one problem
planted per session: a sneakernet duplicate, two machines sharing a label, a
participant ID reused across stations, a station left on a different currency,
stored scores that disagree with the events, files that never made it back.

`rebuilt/` is what the Hub made of them. Open
[`rebuilt/hazard-suite_ingestion_report.md`](hazard-suite/rebuilt/hazard-suite_ingestion_report.md):
every planted problem is itemized under a severity heading — held, attention,
or clean — because the Hub never drops a session silently. The pooled data
lands in `rebuilt/partition-1/`, with the one session whose task language
differed separated into `partition-2/` rather than pooled into a dataset it is
not comparable with.

## Regenerating

Both studies are generated, never hand-edited:

```
python scripts/regenerate_samples.py
```

`tests/hub/test_samples_snapshot.py` rebuilds them and compares every byte, so
what is committed here is always what today's code emits. If that test fails,
run the command above and read the diff — it is telling you the instrument's
output changed.
