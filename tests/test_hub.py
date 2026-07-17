"""Hub ingestion: read assembled station folders, decide, itemize (I8).

The Hub's governing rule is that it never acts silently (DATA-SPEC §5): every
session is included cleanly, or flagged / held / partitioned / skipped, and
every departure is named in the itemized ingestion report. These tests build
station folders through the real emission path (``/write-output``, exactly as
stations produce them in the field), plant one hazard at a time by file
surgery, and assert on the structured report — the same surface the fixture
suite (I15) and the CLI/UI (I11/I12) consume.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from scoring.config import DEFAULT_TASK_CONFIG
from sidecar.hub import NoStudyError, ingest

from tests.test_sidecar import _collected_session, _session_payload, client


def _use_station(monkeypatch, tmp_path: Path, key: str, label: str | None) -> str:
    """Impersonate one machine: its own settings file (→ its own machine UUID),
    optionally labeled. Returns the machine UUID for assertions."""
    monkeypatch.setenv("BART_STATION_FILE", str(tmp_path / f"machine-{key}.json"))
    if label is not None:
        out = client.post("/station", json={"station_id": label}).json()
        assert out["ok"], out
    return client.get("/station").json()["machine_uuid"]


def _write(out_dir: Path, cfg_extra: dict | None = None, **payload_over) -> dict:
    """POST one collected session to /write-output (standalone, so folders look
    like real multi-station output); returns the response body."""
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(out_dir)
    cfg["standalone"] = True
    cfg.update(cfg_extra or {})
    resp = client.post(
        "/write-output",
        json={
            "session": _session_payload(_collected_session(), **payload_over),
            "config": cfg,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _copy_session(out: dict, dest: Path) -> None:
    """Byte-copy one session's four files into another folder (sneakernet)."""
    dest.mkdir(parents=True, exist_ok=True)
    for kind in ("events", "metrics", "config", "session"):
        shutil.copy(out[kind], dest)


def _edit_json(path: str, **fields) -> None:
    """Rewrite one JSON file with some fields changed (hazard planting)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data.update(fields)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _findings(report, code: str) -> list:
    return [f for f in report.findings if f.code == code]


def _the(report, code: str):
    """The single finding with this code — 1:1 hazard→line is the contract."""
    found = _findings(report, code)
    assert len(found) == 1, f"expected exactly one {code!r}, got {found}"
    return found[0]


def _pooled_ids(report) -> list[str]:
    return [s.session_id for p in report.partitions for s in p.sessions]


# ── Clean ingest ─────────────────────────────────────────────────────────────


def test_clean_multi_station_ingest_pools_everything_silently(
    tmp_path, monkeypatch
):
    """Two labeled stations, distinct participants: every session pools into
    one partition, sorted (station, timestamp, session_id), with no held or
    attention findings — a clean run reports nothing but the clean sessions.
    The folders' differing output_dir is benign drift, ignored (§5.4)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(tmp_path / "s2", session_id="s-003", candidate_id="P003")

    report = ingest([tmp_path / "s1", tmp_path / "s2"])

    assert report.title == DEFAULT_TASK_CONFIG.title
    assert [f for f in report.findings if f.group in ("held", "attention")] == []
    assert len(report.partitions) == 1
    assert _pooled_ids(report) == ["s-001", "s-002", "s-003"]
    assert report.will_rebuild == 3


def test_clean_sessions_carry_identity_the_rebuild_needs(tmp_path, monkeypatch):
    """Each pooled session record carries what I9/I10 consume: the four file
    paths, the envelope + parsed config, the stem-recovered timestamp, the
    events hash, and an unambiguous participant_key (station::candidate)."""
    uuid_a = _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    [record] = ingest([tmp_path / "s1"]).partitions[0].sessions
    assert record.session_id == "s-001"
    assert record.candidate_id == "P001"
    assert record.station_id == "S1"
    assert record.machine_uuid == uuid_a
    assert record.participant_key == "S1::P001"
    assert record.events_path == out["events"]
    assert record.metrics_path == out["metrics"]
    assert record.timestamp_utc == Path(out["events"]).name.removesuffix(
        "_events.jsonl"
    ).rsplit("_", 1)[1]
    assert record.envelope.session_id == "s-001"
    assert record.config.title == DEFAULT_TASK_CONFIG.title
    assert len(record.events_sha256) == 64


def test_cross_session_order_is_station_timestamp_session_id(
    tmp_path, monkeypatch
):
    """Cross-session row order asserts no cross-station chronology (§5.5):
    stations sort by label even against wall-clock write order."""
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(tmp_path / "s2", session_id="s-101", candidate_id="P201")
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-102", candidate_id="P101")
    _write(tmp_path / "s1", session_id="s-103", candidate_id="P102")

    report = ingest([tmp_path / "s1", tmp_path / "s2"])
    assert _pooled_ids(report) == ["s-102", "s-103", "s-101"]


# ── Abort: the one dataset-level failure ─────────────────────────────────────


def test_no_identifiable_study_aborts(tmp_path):
    """Abort only when no study is identifiable at all (§5.6): an empty
    target, a nonexistent one, or folders with no parseable study config."""
    with pytest.raises(NoStudyError):
        ingest([tmp_path])
    with pytest.raises(NoStudyError):
        ingest([tmp_path / "nope"])
    (tmp_path / "bart_export.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(NoStudyError):
        ingest([tmp_path])


def test_study_identified_from_session_config_when_no_frozen_study(
    tmp_path, monkeypatch
):
    """A folder holding only per-session files (no study-level files at all)
    still identifies the study through a session's own config snapshot."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _copy_session(out, tmp_path / "bare")

    report = ingest([tmp_path / "bare"])
    assert report.title == DEFAULT_TASK_CONFIG.title
    assert report.will_rebuild == 1


# ── Dedupe: three-way on (session_id, events hash) ───────────────────────────


def test_identical_duplicate_collapses_with_one_summary_line(
    tmp_path, monkeypatch
):
    """Same UUID + same events hash = the same physical session copied into
    two folders: collapse to one, one summary line (§5.2)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _copy_session(out, tmp_path / "usb-copy")

    report = ingest([tmp_path / "s1", tmp_path / "usb-copy"])
    assert _pooled_ids(report) == ["s-001"]
    line = _the(report, "identical_duplicates_collapsed")
    assert line.group == "info"
    assert "collapsed 1 identical duplicate" in line.message


def test_divergent_duplicate_is_held_never_auto_picked(tmp_path, monkeypatch):
    """Same UUID, different events hash: the Hub must not guess which copy is
    authoritative — both are excluded until resolved (§5.2)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _copy_session(out, tmp_path / "twin")
    copied_events = tmp_path / "twin" / Path(out["events"]).name
    copied_events.write_text(
        copied_events.read_text(encoding="utf-8")
        + '{"timestamp": 999999.0, "type": "pump", "payload": {}}\n',
        encoding="utf-8",
    )

    report = ingest([tmp_path / "s1", tmp_path / "twin"])
    line = _the(report, "divergent_duplicate")
    assert line.group == "held"
    assert "divergent duplicate" in line.message
    assert "s-001" in line.message and "resolve before assembly" in line.message
    # Held blocks only the affected session; the good one still pools.
    assert _pooled_ids(report) == ["s-002"]


def test_rerun_same_candidate_same_station_keeps_both(tmp_path, monkeypatch):
    """Different UUID, same (candidate, station) is a genuine re-run —
    test-retest is real data: keep both, non-blocking note (§5.2)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P001")

    report = ingest([tmp_path / "s1"])
    assert _pooled_ids(report) == ["s-001", "s-002"]
    line = _the(report, "rerun")
    assert line.group == "info"
    assert "P001" in line.message and "2 sessions" in line.message


# ── ID collisions across stations ────────────────────────────────────────────


def test_id_collision_without_seed_is_a_hygiene_note(tmp_path, monkeypatch):
    """A candidate spanning two stations with no seed: non-destructive and
    non-blocking — both sessions pool, participant_key disambiguates, and the
    report carries an ID-hygiene line only (§5.3)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(tmp_path / "s2", session_id="s-002", candidate_id="P001")

    report = ingest([tmp_path / "s1", tmp_path / "s2"])
    assert _pooled_ids(report) == ["s-001", "s-002"]
    keys = {s.participant_key for p in report.partitions for s in p.sessions}
    assert keys == {"S1::P001", "S2::P001"}
    line = _the(report, "id_collision")
    assert line.group == "attention"
    assert not line.loud
    assert "P001" in line.message and "participant_key" in line.message


def test_id_collision_with_equal_seed_is_loud_not_independent(
    tmp_path, monkeypatch
):
    """The same candidate on two stations under the same fixed seed replayed
    identical balloon sequences — a loud data-integrity warning, still
    non-blocking (§5.3)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", {"seed": 42}, session_id="s-001", candidate_id="P001")
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(tmp_path / "s2", {"seed": 42}, session_id="s-002", candidate_id="P001")

    report = ingest([tmp_path / "s1", tmp_path / "s2"])
    line = _the(report, "id_collision")
    assert line.group == "attention"
    assert line.loud
    assert "NOT independent" in line.message
    assert _pooled_ids(report) == ["s-001", "s-002"]


def test_id_collision_with_differing_seeds_stays_quiet(tmp_path, monkeypatch):
    """Differing (or null) seeds mean the sessions are independent runs — the
    collision is ID messiness, not a data-integrity problem (§5.3)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", {"seed": 42}, session_id="s-001", candidate_id="P001")
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(tmp_path / "s2", {"seed": 7}, session_id="s-002", candidate_id="P001")

    line = _the(ingest([tmp_path / "s1", tmp_path / "s2"]), "id_collision")
    assert not line.loud
    assert "NOT independent" not in line.message


def test_generated_id_collision_gets_its_own_louder_line(tmp_path, monkeypatch):
    """Two auto-generated IDs colliding is near-impossible by chance (9-digit
    space) — a distinct, louder, still non-blocking line that compounds with
    the ordinary collision line (§5.3, [T10])."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    a = _write(tmp_path / "s1", session_id="s-001", candidate_id="384715926")
    _use_station(monkeypatch, tmp_path, "b", "S2")
    b = _write(tmp_path / "s2", session_id="s-002", candidate_id="384715926")
    _edit_json(a["session"], id_source="generated")
    _edit_json(b["session"], id_source="generated")

    report = ingest([tmp_path / "s1", tmp_path / "s2"])
    loud = _the(report, "generated_id_collision")
    assert loud.group == "attention"
    assert loud.loud
    assert "auto-generated" in loud.message
    assert "Investigate before pooling" in loud.message
    assert _the(report, "id_collision")  # the ordinary line still compounds
    assert _pooled_ids(report) == ["s-001", "s-002"]


def test_generated_vs_manual_collision_is_the_ordinary_line(
    tmp_path, monkeypatch
):
    """A generated-vs-manual collision is a manual-ID hygiene issue — only the
    ordinary collision line fires (§5.3)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    a = _write(tmp_path / "s1", session_id="s-001", candidate_id="384715926")
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(tmp_path / "s2", session_id="s-002", candidate_id="384715926")
    _edit_json(a["session"], id_source="generated")

    report = ingest([tmp_path / "s1", tmp_path / "s2"])
    assert _findings(report, "generated_id_collision") == []
    assert _the(report, "id_collision")


def test_id_collision_across_two_machines_sharing_a_label_still_fires(
    tmp_path, monkeypatch
):
    """A station is keyed on label + machine UUID (§5.3): the same candidate
    on two machines both labeled S1 is a collision (not a re-run), even
    though no label difference shows it."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "one", session_id="s-001", candidate_id="P001")
    _use_station(monkeypatch, tmp_path, "b", "S1")
    _write(tmp_path / "two", session_id="s-002", candidate_id="P001")

    report = ingest([tmp_path / "one", tmp_path / "two"])
    line = _the(report, "id_collision")
    assert "2 machines all labeled 'S1'" in line.message
    assert _findings(report, "rerun") == []
    assert _the(report, "duplicate_station_label")


def test_duplicate_station_label_is_flagged(tmp_path, monkeypatch):
    """Two machines both labeled S1 (different machine UUIDs in their folders'
    provenance records) — the duplicate-station-label hazard (§5.3)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "one", session_id="s-001", candidate_id="P001")
    _use_station(monkeypatch, tmp_path, "b", "S1")
    _write(tmp_path / "two", session_id="s-002", candidate_id="P002")

    report = ingest([tmp_path / "one", tmp_path / "two"])
    line = _the(report, "duplicate_station_label")
    assert line.group == "attention"
    assert "S1" in line.message and "2 different machines" in line.message


# ── Config drift: three tiers ────────────────────────────────────────────────


def test_notable_drift_flags_but_still_pools(tmp_path, monkeypatch):
    """currency is notable drift: reported, but the sessions stay in one
    partition (§5.4)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(tmp_path / "s2", {"currency": "₺"}, session_id="s-002", candidate_id="P002")

    report = ingest([tmp_path / "s1", tmp_path / "s2"])
    assert len(report.partitions) == 1
    assert report.will_rebuild == 2
    line = _the(report, "config_drift_notable")
    assert line.group == "attention"
    assert "currency" in line.message and "pooled" in line.message


def test_pooling_breaking_drift_partitions_by_fingerprint(tmp_path, monkeypatch):
    """reward_per_pump changes the task: the Hub splits output by
    config-fingerprint — one comparable set per configuration — rather than
    refusing or silently pooling (§5.4). The larger set is the main one."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(
        tmp_path / "s2",
        {"reward_per_pump": 0.5},
        session_id="s-003",
        candidate_id="P003",
    )

    report = ingest([tmp_path / "s1", tmp_path / "s2"])
    assert len(report.partitions) == 2
    assert [s.session_id for s in report.partitions[0].sessions] == ["s-001", "s-002"]
    assert [s.session_id for s in report.partitions[1].sessions] == ["s-003"]
    assert report.will_rebuild == 3
    line = _the(report, "config_drift_partition")
    assert line.group == "attention"
    assert "reward_per_pump" in line.message and "partition" in line.message


def test_language_drift_is_pooling_breaking(tmp_path, monkeypatch):
    """Instruction language is a real manipulation: language=tr among en
    forces a partition boundary (§5.4)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(
        tmp_path / "s1", {"language": "tr"}, session_id="s-002", candidate_id="P002"
    )

    report = ingest([tmp_path / "s1"])
    assert len(report.partitions) == 2
    assert "language" in _the(report, "config_drift_partition").message


def test_metrics_mode_difference_neither_drifts_nor_partitions(
    tmp_path, monkeypatch
):
    """metrics_mode is a projection axis, not a partition axis (§6.3): a
    classic-mode session among advanced ones unifies at rebuild — no drift
    line, one partition."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(
        tmp_path / "s1",
        {"metrics_mode": "classic"},
        session_id="s-002",
        candidate_id="P002",
    )

    report = ingest([tmp_path / "s1"])
    assert len(report.partitions) == 1
    assert _findings(report, "config_drift_partition") == []
    assert _findings(report, "config_drift_notable") == []


def test_frozen_config_disagreeing_with_every_session_is_flagged(
    tmp_path, monkeypatch
):
    """The folders' frozen design records join the drift comparison (§5.4):
    a frozen study config that matches no ingested session — here because the
    sessions it recorded were culled and later ones ran a changed design —
    is named, not silently ignored."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    original = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(
        tmp_path / "s1",
        {"reward_per_pump": 0.5},
        session_id="s-002",
        candidate_id="P002",
    )
    for kind in ("events", "metrics", "config", "session"):
        Path(original[kind]).unlink()

    report = ingest([tmp_path / "s1"])
    assert _pooled_ids(report) == ["s-002"]
    line = _the(report, "frozen_config_drift")
    assert line.group == "attention"
    assert "matches no ingested session" in line.message


def test_title_mismatch_is_a_prominent_warning(tmp_path, monkeypatch):
    """Two titles in one ingest asks 'are these even the same study?' — a
    loud top-level warning, while sessions still pool by fingerprint (§5.4)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(
        tmp_path / "s1",
        {"title": "A Different Study"},
        session_id="s-002",
        candidate_id="P002",
    )

    line = _the(ingest([tmp_path / "s1"]), "title_mismatch")
    assert line.group == "attention"
    assert line.loud
    assert "A Different Study" in line.message


# ── Schema versions ──────────────────────────────────────────────────────────


def test_older_schema_pools_with_a_note(tmp_path, monkeypatch):
    """schema_version below the Hub's max loads through current models with
    defaults filling — pooled, noted per session (§6.2)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    old = _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _edit_json(old["config"], schema_version="1.0")

    report = ingest([tmp_path / "s1"])
    assert _pooled_ids(report) == ["s-001", "s-002"]
    line = _the(report, "older_schema")
    assert line.group == "attention"
    assert "1.0" in line.message and "pooled" in line.message


def test_future_schema_is_held_with_upgrade_advice(tmp_path, monkeypatch):
    """schema_version above the Hub's max cannot be trusted to mean what the
    current models say: refuse that session with 'upgrade the Hub', never
    abort the rest (§6.2)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    future = _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _edit_json(future["config"], schema_version="2.0")

    report = ingest([tmp_path / "s1"])
    assert _pooled_ids(report) == ["s-001"]
    line = _the(report, "future_schema")
    assert line.group == "held"
    assert "2.0" in line.message and "upgrade" in line.message.lower()


# ── Input tolerance: graded by what is actually lost ─────────────────────────


def test_missing_metrics_keeps_the_session_with_a_note(tmp_path, monkeypatch):
    """Ground truth present → fully re-scorable; only the verify comparison
    can't run (§5.6)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    Path(out["metrics"]).unlink()

    report = ingest([tmp_path / "s1"])
    [record] = report.partitions[0].sessions
    assert record.metrics_path is None
    line = _the(report, "missing_metrics")
    assert line.group == "info"
    assert "re-scored, no verify" in line.message


def test_missing_events_is_held(tmp_path, monkeypatch):
    """No events.jsonl means no ground truth: unrebuildable, held (§5.6)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    Path(out["events"]).unlink()

    report = ingest([tmp_path / "s1"])
    assert _pooled_ids(report) == ["s-002"]
    line = _the(report, "missing_events")
    assert line.group == "held"
    assert "no events" in line.message and "cannot re-score" in line.message


def test_unreadable_events_holds_only_that_session(tmp_path, monkeypatch):
    """Ground truth present but inaccessible is the same loss as missing
    events — held per session, and one bad file never aborts the ingest."""
    if os.geteuid() == 0:
        pytest.skip("permission bits don't bind as root")
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    Path(out["events"]).chmod(0o000)
    try:
        report = ingest([tmp_path / "s1"])
    finally:
        Path(out["events"]).chmod(0o644)

    assert _pooled_ids(report) == ["s-002"]
    line = _the(report, "unreadable_events")
    assert line.group == "held"
    assert "cannot re-score" in line.message


def test_missing_session_envelope_is_held(tmp_path, monkeypatch):
    """No session.json means identity is compromised — the filename yields
    station/candidate/timestamp but not session_id/condition (§5.6)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    Path(out["session"]).unlink()

    report = ingest([tmp_path / "s1"])
    assert _pooled_ids(report) == ["s-002"]
    line = _the(report, "missing_session")
    assert line.group == "held"
    assert "session envelope missing" in line.message


def test_truncated_config_holds_only_that_session(tmp_path, monkeypatch):
    """One bad file must never sink the rest: a truncated config.json holds
    that session with an unreadable-JSON line; its neighbors pool (§5.6)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    bad = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    Path(bad["config"]).write_text('{"incomplete":', encoding="utf-8")

    report = ingest([tmp_path / "s1"])
    assert _pooled_ids(report) == ["s-002"]
    line = _the(report, "unreadable_json")
    assert line.group == "held"
    assert "unreadable JSON" in line.message


def test_foreign_files_are_ignored_with_one_summary_line(tmp_path, monkeypatch):
    """The Hub globs its own patterns and resists parsing anything else — at
    most one summary line for however many strays (§5.6)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    (tmp_path / "s1" / "bart_export.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "s1" / ".DS_Store").write_bytes(b"\x00\x01")
    (tmp_path / "s1" / "notes.txt").write_text("misc", encoding="utf-8")

    report = ingest([tmp_path / "s1"])
    assert report.will_rebuild == 1
    line = _the(report, "foreign_files")
    assert line.group == "info"
    assert "skipped 3 unrecognized file(s)" in line.message


def test_own_study_level_files_are_not_foreign(tmp_path, monkeypatch):
    """The study's own frozen config, provenance record, and data dictionary
    are recognized — a clean folder produces no foreign-file line."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    assert _findings(ingest([tmp_path / "s1"]), "foreign_files") == []


def test_practice_sessions_are_never_assembled(tmp_path, monkeypatch):
    """Test Run sessions live under practice/ and must never mingle with
    official data (issue 43): the Hub skips them, with a line."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-901", candidate_id="P001", practice=True)

    report = ingest([tmp_path / "s1"])
    assert _pooled_ids(report) == ["s-001"]
    line = _the(report, "practice_excluded")
    assert line.group == "info"
