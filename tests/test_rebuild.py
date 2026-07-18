"""Hub rebuild core: re-score, project, order, verify (I9).

The rebuild is a pure re-derivation from ground truth that shares the live
path's own emission code (DATA-SPEC §6): every session is re-scored from
``events.jsonl`` + ``config.json`` with the one current engine, projected to a
single rebuild mode, and emitted through the same flattener/row-builders the
live writer uses — so the clean single-station case is byte-identical to live
output *by construction*, and stored ``metrics.json`` is demoted to the §6.6
verify/QC comparison. These tests build folders through the real emission path
(as ``tests/test_hub.py`` does), plant one hazard at a time, and assert on the
rebuilt row streams plus the verify findings slotted into the same report.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scoring import __version__
from scoring.config import DEFAULT_TASK_CONFIG
from sidecar.hub import ingest
from sidecar.naming import slug
from sidecar.rebuild import rebuild
from sidecar.versioned_csv import append_rows

from tests.test_hub import (
    _copy_session,
    _edit_json,
    _findings,
    _the,
    _use_station,
    _write,
)


def _rebuilt_ids(result) -> list[str]:
    return [r["session_id"] for p in result.partitions for r in p.results_rows]


def _verify_findings(report) -> list:
    return [f for f in report.findings if f.code.startswith("verify_")]


# ── The equivalence claim: shared emission code, byte-identical output ───────


@pytest.mark.parametrize("label", [None, "S1"])
def test_clean_single_station_rebuild_is_byte_identical_to_live(
    tmp_path, monkeypatch, label
):
    """The §6.5 gate in miniature (the full fixture is I14): three clean
    ``standalone=False`` sessions produce live CSVs; the rebuild's row streams,
    written through the same ``versioned_csv`` writer, reproduce both files
    byte-for-byte — column order, float formatting, row order, the condition
    column, and (with a labeled station) no extra station columns."""
    _use_station(monkeypatch, tmp_path, "a", label)
    live = tmp_path / "live"
    cfg = {"standalone": False, "conditions": ["A", "B"]}
    _write(live, cfg, session_id="s-001", candidate_id="P001", condition="A")
    _write(live, cfg, session_id="s-002", candidate_id="P002", condition="B")
    _write(live, cfg, session_id="s-003", candidate_id="P003", condition="A")

    report = ingest([live])
    result = rebuild(report)

    assert _verify_findings(report) == []
    study_slug = slug(DEFAULT_TASK_CONFIG.title)
    out = tmp_path / "out"
    out.mkdir()
    [partition] = result.partitions
    append_rows(out / f"{study_slug}_results.csv", partition.results_rows)
    append_rows(out / f"{study_slug}_trials.csv", partition.trials_rows)
    for name in (f"{study_slug}_results.csv", f"{study_slug}_trials.csv"):
        assert (out / name).read_bytes() == (live / name).read_bytes()


def test_rebuild_writes_the_rescore_never_the_stored_metrics(
    tmp_path, monkeypatch
):
    """Stored ``metrics.json`` is demoted to verify/QC (§6.1): a tampered
    stored value never reaches the rebuilt rows — the re-score does."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _edit_json(out["metrics"], total_pumps=9999)

    result = rebuild(ingest([tmp_path / "s1"]))
    [row] = result.partitions[0].results_rows
    assert row["total_pumps"] != 9999


# ── Duality at rebuild: projection axis, not partition (§6.3) ────────────────


def test_default_rebuild_mode_is_the_studys_configured_mode(
    tmp_path, monkeypatch
):
    """No override → the study's own configured mode (frozen ``study.json``),
    so the reconstructed master matches the live one — a classic study
    rebuilds classic: canon columns only, no per-color block, no trial
    latency column."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(
        tmp_path / "s1",
        {"metrics_mode": "classic"},
        session_id="s-001",
        candidate_id="P001",
    )

    report = ingest([tmp_path / "s1"])
    assert report.configured_mode == "classic"
    result = rebuild(report)
    assert result.mode == "classic"
    assert result.mode_source == "configured"
    [row] = result.partitions[0].results_rows
    assert "average_pumps_adjusted" in row
    assert "purple_average_pumps" not in row
    assert all(
        "mean_latency_between_pumps" not in t
        for t in result.partitions[0].trials_rows
    )


def test_override_projects_a_classic_collected_study_to_advanced(
    tmp_path, monkeypatch
):
    """The one thing the Hub can do the live path cannot (§6.3): events carry
    the complete session, so an explicit override rebuilds the full Advanced
    set from a Classic-collected study."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(
        tmp_path / "s1",
        {"metrics_mode": "classic"},
        session_id="s-001",
        candidate_id="P001",
    )

    result = rebuild(ingest([tmp_path / "s1"]), mode="advanced")
    assert result.mode == "advanced"
    assert result.mode_source == "override"
    [row] = result.partitions[0].results_rows
    assert "purple_average_pumps" in row
    assert all(
        "mean_latency_between_pumps" in t
        for t in result.partitions[0].trials_rows
    )


def test_mid_study_mode_switch_unifies_to_one_column_set(tmp_path, monkeypatch):
    """metrics_mode is re-projected across *all* sessions to the one rebuild
    mode (§6.3): a classic session among advanced ones lands in the same
    partition with the identical column set — a mode switch unifies at
    rebuild, unlike the live writer's new-lineage stance (§4.6)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(
        tmp_path / "s1",
        {"metrics_mode": "classic"},
        session_id="s-002",
        candidate_id="P002",
    )

    report = ingest([tmp_path / "s1"])
    result = rebuild(report)
    assert result.mode == "advanced"  # the frozen design record's mode
    [rows] = [p.results_rows for p in result.partitions]
    assert len(rows) == 2
    assert list(rows[0]) == list(rows[1])
    assert "purple_average_pumps" in rows[1]


# ── Verify-grading matrix (§6.6) — keyed on engine.engine_version ────────────


def test_verify_clean_session_reports_nothing(tmp_path, monkeypatch):
    """Metrics match under the same engine: clean, no verify line at all."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    report = ingest([tmp_path / "s1"])
    rebuild(report)
    assert _verify_findings(report) == []


def test_same_engine_mismatch_is_loud_corruption(tmp_path, monkeypatch):
    """Identical engine on identical events must reproduce: a same-version
    mismatch is corruption/tamper — Attention, loud — and still non-blocking
    (the session rebuilds from the re-score)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _edit_json(out["metrics"], total_pumps=9999)

    report = ingest([tmp_path / "s1"])
    result = rebuild(report)
    line = _the(report, "verify_corruption")
    assert line.group == "attention"
    assert line.loud
    assert "same engine" in line.message
    assert "corruption" in line.message
    assert _rebuilt_ids(result) == ["s-001"]


def test_cross_engine_mismatch_is_an_informational_note(tmp_path, monkeypatch):
    """A stored value from an older engine that differs from the re-score is
    benign engine drift — expected, an informational note, never flagged."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _edit_json(
        out["session"],
        engine={
            "app_version": "0.9.0",
            "engine_version": "0.9.0",
            "platform": "test",
        },
    )
    _edit_json(out["metrics"], total_pumps=9999)

    report = ingest([tmp_path / "s1"])
    rebuild(report)
    line = _the(report, "verify_engine_drift")
    assert line.group == "info"
    assert not line.loud
    assert "0.9.0" in line.message
    assert _findings(report, "verify_corruption") == []


def test_prestamp_mismatch_is_ungraded_attention(tmp_path, monkeypatch):
    """No engine stamp (pre-stamp data) + differing metrics cannot be graded
    benign-vs-corruption: Attention, not loud, still rebuilt."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _edit_json(out["session"], engine=None)
    _edit_json(out["metrics"], total_pumps=9999)

    report = ingest([tmp_path / "s1"])
    result = rebuild(report)
    line = _the(report, "verify_ungraded")
    assert line.group == "attention"
    assert not line.loud
    assert "no engine stamp" in line.message
    assert _rebuilt_ids(result) == ["s-001"]


def test_prestamp_match_is_clean(tmp_path, monkeypatch):
    """No stamp but the metrics reproduce: clean, nothing to grade."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _edit_json(out["session"], engine=None)

    report = ingest([tmp_path / "s1"])
    rebuild(report)
    assert _verify_findings(report) == []


def test_cross_engine_match_is_a_version_note(tmp_path, monkeypatch):
    """Metrics reproduce across engine versions: clean, with the §6.6 version
    note only."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _edit_json(
        out["session"],
        engine={
            "app_version": "0.9.0",
            "engine_version": "0.9.0",
            "platform": "test",
        },
    )

    report = ingest([tmp_path / "s1"])
    rebuild(report)
    line = _the(report, "verify_version_note")
    assert line.group == "info"
    assert "0.9.0" in line.message and __version__ in line.message


def test_verify_compares_in_the_sessions_own_recorded_mode(
    tmp_path, monkeypatch
):
    """The stored ``metrics.json`` was projected by the session's own mode at
    write time, so the verify comparison stays in that mode even when the
    rebuild is overridden to another — no false mismatch."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(
        tmp_path / "s1",
        {"metrics_mode": "classic"},
        session_id="s-001",
        candidate_id="P001",
    )

    report = ingest([tmp_path / "s1"])
    rebuild(report, mode="advanced")
    assert _verify_findings(report) == []


# ── Rebuild-time tolerance & refusal ─────────────────────────────────────────


def test_refused_future_schema_session_never_reaches_the_rebuild(
    tmp_path, monkeypatch
):
    """A future-schema session is refused at ingest (§6.2); the rebuild
    proceeds on the rest — refuse-with-report, never abort."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    future = _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _edit_json(future["config"], schema_version="2.0")

    report = ingest([tmp_path / "s1"])
    result = rebuild(report)
    assert _the(report, "future_schema").group == "held"
    assert _rebuilt_ids(result) == ["s-001"]


def test_unscorable_events_hold_only_that_session_at_rebuild(
    tmp_path, monkeypatch
):
    """Events that hash fine at ingest but cannot be parsed/scored at rebuild
    are held per session — one bad file never sinks the rest."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    Path(out["events"]).write_text("not an event log\n", encoding="utf-8")

    report = ingest([tmp_path / "s1"])
    result = rebuild(report)
    line = _the(report, "unscorable_events")
    assert line.group == "held"
    assert "cannot be re-scored" in line.message
    assert _rebuilt_ids(result) == ["s-002"]
    assert result.partitions[0].session_ids == ["s-002"]


# ── Ordering + multi-station columns ─────────────────────────────────────────


def test_multi_station_rows_carry_station_and_participant_key(
    tmp_path, monkeypatch
):
    """When the pooled data spans stations, the sort-leading ``station_id``
    and the unambiguous ``participant_key`` join every row (§11) — ordered
    (station, timestamp, session_id) across stations."""
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(tmp_path / "s2", session_id="s-002", candidate_id="P002")
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    result = rebuild(ingest([tmp_path / "s1", tmp_path / "s2"]))
    rows = result.partitions[0].results_rows
    assert _rebuilt_ids(result) == ["s-001", "s-002"]
    assert list(rows[0])[:4] == [
        "station_id",
        "timestamp_utc",
        "session_id",
        "candidate_id",
    ]
    assert rows[0]["station_id"] == "S1"
    assert rows[0]["participant_key"] == "S1::P001"
    assert rows[1]["participant_key"] == "S2::P002"
    assert result.partitions[0].trials_rows[0]["station_id"] == "S1"


def test_one_label_with_a_provenance_less_copy_keeps_live_columns(
    tmp_path, monkeypatch
):
    """The station columns key on the *label*, not machine attribution: a
    sneakernet copy that lost its folder's provenance record (machine UUID
    unknown) must not make a single-station study sprout station columns and
    break the §6.5 byte-equality stance."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    out = _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _copy_session(out, tmp_path / "bare")

    result = rebuild(ingest([tmp_path / "bare", tmp_path / "s1"]))
    assert _rebuilt_ids(result) == ["s-001", "s-002"]
    assert all(
        "station_id" not in row and "participant_key" not in row
        for row in result.partitions[0].results_rows
    )


def test_disagreeing_modes_without_a_design_record_default_to_advanced(
    tmp_path, monkeypatch
):
    """Bare per-session folders (no frozen ``study.json``) with a mid-study
    mode switch: no winner is inferred from cross-machine clocks (§5.5) — the
    default is the lossless advanced superset, override always available."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    first = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    second = _write(
        tmp_path / "s1",
        {"metrics_mode": "classic"},
        session_id="s-002",
        candidate_id="P002",
    )
    _copy_session(first, tmp_path / "bare")
    _copy_session(second, tmp_path / "bare")

    report = ingest([tmp_path / "bare"])
    assert report.configured_mode == "advanced"


def test_rebuild_result_carries_the_engine_for_provenance(tmp_path, monkeypatch):
    """The output writer (I10) stamps reconstruction provenance with the one
    engine that produced every row — the Hub's own."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    result = rebuild(ingest([tmp_path / "s1"]))
    assert result.engine_version == __version__
