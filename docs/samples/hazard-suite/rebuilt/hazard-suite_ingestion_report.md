# Ingestion Report — hazard-suite

Reconstructed by the Data Hub (version 1.2.1) on 2026-03-02 12:00 UTC. The Hub never acts silently: every session was included cleanly, or its departure is itemized below.

Rebuild mode: `advanced` (the study's configured mode).

**15 session(s) rebuilt · 5 held · 9 attention · 2 partition(s)**

## Sources

Sources are read-only; the Hub never writes into them.

- `docs/samples/hazard-suite/lab-01` — 5 session(s) rebuilt
- `docs/samples/hazard-suite/lab-01-second` — 1 session(s) rebuilt
- `docs/samples/hazard-suite/lab-02` — 5 session(s) rebuilt
- `docs/samples/hazard-suite/lab-03` — 4 session(s) rebuilt

## Held — excluded until resolved

Holds affect only the listed sessions; the rebuild proceeded on the rest.

- **`missing_events`** held: no events, cannot re-score — lab-01 · P-missing-events · 20260302T090700000000Z
- **`missing_session`** held: session envelope missing — the filename yields only station/candidate/timestamp, not session_id or condition: hazard-suite_lab-03_P-missing-session_20260302T092000000000Z
- **`divergent_duplicate`** held: divergent duplicate — session sess-dup-divergent differs across folders (docs/samples/hazard-suite/lab-01, docs/samples/hazard-suite/lab-01-second); resolve before assembly
- **`unreadable_json`** held: unreadable JSON — hazard-suite_lab-01_P-truncated-json_20260302T090800000000Z_config.json
- **`future_schema`** held: future schema 2.0 — this Hub supports ≤ 1.1; upgrade the Hub and re-run (lab-02 · P-future-schema · 20260302T091400000000Z)

## Attention — pooled, but itemized

- **`older_schema`** older schema 1.0 pooled — current-model defaults fill the missing fields (lab-03 · P-schema-old · 20260302T091600000000Z)
- **`duplicate_station_label`** duplicate station label: 'lab-01' is used by 2 different machines — their data cannot be told apart by label; participant_key stays ambiguous until stations are re-labeled
- **`id_collision`** ID collision: 'P-COLLIDE-FREE' appears on stations lab-01, lab-03 (participant_key added)
- ⚠ **`id_collision`** ID collision: 'P-COLLIDE-SEED' ran on stations lab-01, lab-02 with the same fixed seed → identical balloon sequences; these sessions are NOT independent (participant_key added)
- **`config_drift_partition`** config drift: language → partition (1 session(s) split from the main set)
- **`config_drift_notable`** config drift: seed (777 vs None) — sessions pooled
- **`config_drift_notable`** config drift: currency ('$' vs 'TRY') — sessions pooled
- ⚠ **`verify_corruption`** stored metrics differ from re-score under the same engine 1.2.1 — identical engine on identical events must reproduce; possible corruption or tampering — lab-01 · P-verify-corrupt · 20260302T090600000000Z
- **`verify_ungraded`** stored metrics differ from re-score with no engine stamp (pre-stamp data) — cannot grade drift vs corruption; re-scored values used — lab-03 · P-verify-ungraded · 20260302T091800000000Z

## Clean / informational

- **`identical_duplicates_collapsed`** collapsed 1 identical duplicate file-set(s) (1 extra file copies)
- **`missing_metrics`** stored metrics absent; re-scored, no verify — lab-02 · P-missing-metrics · 20260302T091500000000Z
- **`foreign_files`** skipped 1 unrecognized file(s)
- **`verify_engine_drift`** stored metrics differ from re-score — benign engine drift (1.0.0 → 1.2.1); re-scored values used — lab-02 · P-verify-drift · 20260302T091300000000Z

## Partitions

Config drift split the sessions into separately comparable sets; each subdirectory is self-contained.

- `partition-1/` — 14 session(s) — the main set
- `partition-2/` — 1 session(s) — differs in: language
