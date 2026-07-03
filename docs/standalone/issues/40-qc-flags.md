# 40 — Data-quality flags: engine-computed, preset thresholds

**Feature · depends on: 36**

Status: ready-for-agent

## Context

Client brief 2B: flag "bad" participant data automatically so analysts don't
publish garbage. The grill pinned three principles: flags **annotate, never
exclude** (exclusion is the analyst's preregistered decision — an instrument
that silently drops data is a methodological liability); thresholds are
**configurable in the Study Preset** so labs can align flags with their
preregistration and carry them portably in `study.json`; and the computation
lives in the **scoring engine**, so CLI users get identical flags.

## Scope

- [ ] The Study Preset gains an optional QC block with literature-informed
      defaults: fast-response threshold (default 100 ms) and zero-pump streak
      length (default 5 consecutive trials). Optional — v1.0.0 presets keep
      validating; defaults apply when absent.
- [ ] The scoring engine computes per-session QC metrics from the event log:
      count of trials containing sub-threshold response latencies, longest
      zero-/minimal-engagement streak, and an overall `qc_flagged` boolean
      (any rule tripped).
- [ ] Flags land as Master CSV columns (via the 36 writer) and in the scored
      metrics JSON. Nothing is ever excluded, reordered, or withheld because
      of a flag.
- [ ] The thresholds actually used are recorded with the results (a lab must
      be able to state, post hoc, which criteria produced a flag).
- [ ] Data-outputs docs document each flag, its rule, its default, and the
      annotate-only stance; contract tests guard the columns.

## Acceptance

- A synthetic session with a 50 ms inter-pump latency and one with five
  zero-pump trials each trip exactly their rule; a clean session trips
  nothing — engine-level tests, plus an end-to-end test seeing the columns in
  the Master CSV row.
- Custom thresholds in the preset change the outcomes; absent block = default
  behavior.
- No code path drops or excludes a session based on a flag.
- `pytest`, `npm test`, `tsc`, `vite build` stay green.

## Comments

**2026-07-03 — implemented (TDD).** `TaskConfig.qc` (optional `QCThresholds`
block: `fast_response_ms` default 100, `zero_pump_streak` default 5; both
`gt=0`-validated; v1.0.0 presets validate unchanged and get the defaults).
The engine computes flags in `score_bart` from the **raw** balloons —
auto-repeat trials included, since the flags describe data quality:
`qc_fast_response_trials` (trials containing any sub-threshold inter-pump
gap), `qc_zero_pump_streak` (longest zero-pump run), `qc_flagged` (any rule
tripped), plus the two thresholds actually used
(`qc_fast_response_ms`, `qc_zero_pump_streak_threshold`) recorded per row for
post-hoc statements. All five land in the metrics JSON and Master CSV
automatically; annotate-never-exclude is pinned by an end-to-end test showing
a flagged session still writes all four session files and its CSV row. Both
boundary cases tested (streak of 4 vs 5; 50 ms vs 300 ms pacing; custom 400 ms
threshold flips a clean session). Two side effects worth knowing: (1) the
`_collected_session` test fixture paced pumps 1 *ms* apart — a latent bug
exposed by QC; it now paces 300 ms like a real participant. (2) The new
metrics fields broke `/score` parity with the stale local frozen binary, so
`dist/bart-sidecar` was re-frozen from current code (PyInstaller 6.18.0) and
the gitignored Tauri bundle copy refreshed (issue-35 lesson: the version
handshake can't catch same-version staleness). No TS/UI changes — `study.json`
round-trips preserve the `qc` block. Docs: QC column table with rules,
defaults, and the annotate-only stance; the master-CSV contract test guards
the columns. Gates: pytest 142 ✅, npm test 92 ✅, tsc ✅, vite build ✅.
