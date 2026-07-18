"""Hub output writer: destination guards, mirrored surfaces, provenance (I10).

The writer's contract (DATA-SPEC §6.4): write only the study-wide pooled
surfaces to a researcher-chosen destination wholly separate from every source,
mirroring the live filenames byte-for-byte so analysis scripts run verbatim
against a rebuild — reconstruction is distinguished by location + provenance
stamp + the presence of an ingestion report, never by munging data filenames.
These tests build station folders through the real emission path (as
``tests/test_hub.py`` does), rebuild them, and assert on the written tree:
the refusal cases, the re-run-replaces-prior-rebuild path, the flat
single-partition layout vs per-partition subdirectories, the reconstruction
provenance block, and the rendered ingestion-report file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scoring import __version__
from scoring.config import DEFAULT_TASK_CONFIG
from sidecar.hub import ingest
from sidecar.hub_writer import DestinationRefused, is_prior_rebuild, write_rebuild
from sidecar.naming import slug
from sidecar.rebuild import rebuild

from tests.test_hub import _edit_json, _the, _use_station, _write

SLUG = slug(DEFAULT_TASK_CONFIG.title)


def _rebuilt(*sources):
    report = ingest(list(sources))
    return report, rebuild(report)


# ── Mirrored filenames + byte-identity with live output (§6.4b/c) ────────────


def test_flat_rebuild_mirrors_live_surfaces_byte_for_byte(tmp_path, monkeypatch):
    """The clean single-partition case stays flat and the three data surfaces
    carry exactly the live names and bytes; the destination adds only the
    provenance record and the ingestion report — never per-session files."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    live = tmp_path / "live"
    cfg = {"standalone": False, "conditions": ["A", "B"]}
    _write(live, cfg, session_id="s-001", candidate_id="P001", condition="A")
    _write(live, cfg, session_id="s-002", candidate_id="P002", condition="B")

    report, result = _rebuilt(live)
    dest = tmp_path / "out"
    receipt = write_rebuild(report, result, dest)

    for name in (
        f"{SLUG}_results.csv",
        f"{SLUG}_trials.csv",
        f"{SLUG}_data_dictionary.md",
    ):
        assert (dest / name).read_bytes() == (live / name).read_bytes()
    assert sorted(p.name for p in dest.iterdir()) == sorted(
        [
            f"{SLUG}_results.csv",
            f"{SLUG}_trials.csv",
            f"{SLUG}_data_dictionary.md",
            f"{SLUG}_provenance.json",
            f"{SLUG}_ingestion_report.md",
        ]
    )
    assert receipt.destination == str(dest)
    assert sorted(receipt.files) == sorted(p.name for p in dest.iterdir())
    assert not receipt.replaced_prior_rebuild


def test_destination_is_created_when_missing(tmp_path, monkeypatch):
    """A fresh nested destination is simply created — no pre-made folder
    required."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    report, result = _rebuilt(tmp_path / "s1")
    dest = tmp_path / "deep" / "nested" / "out"
    write_rebuild(report, result, dest)
    assert (dest / f"{SLUG}_results.csv").exists()


# ── Destination guards (§6.4a) ───────────────────────────────────────────────


def test_refuses_to_write_into_a_folder_being_ingested(tmp_path, monkeypatch):
    """Sources are read-only inputs: the source root itself and anything
    inside it are refused."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    report, result = _rebuilt(tmp_path / "s1")
    with pytest.raises(DestinationRefused, match="ingesting"):
        write_rebuild(report, result, tmp_path / "s1")
    with pytest.raises(DestinationRefused, match="ingesting"):
        write_rebuild(report, result, tmp_path / "s1" / "rebuilt")


def test_refuses_a_destination_containing_a_source(tmp_path, monkeypatch):
    """A destination that *contains* a source is just as unsafe: a later
    re-run's clean replace would delete the ground truth inside it."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "data" / "s1", session_id="s-001", candidate_id="P001")

    report, result = _rebuilt(tmp_path / "data" / "s1")
    with pytest.raises(DestinationRefused, match="separate"):
        write_rebuild(report, result, tmp_path / "data")


def test_refuses_a_non_empty_non_rebuild_destination(tmp_path, monkeypatch):
    """Anything already in a folder without the reconstruction marker is not
    the Hub's to overwrite — refused, and the folder is left untouched."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    report, result = _rebuilt(tmp_path / "s1")
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "notes.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(DestinationRefused, match="prior Hub rebuild"):
        write_rebuild(report, result, dest)
    assert (dest / "notes.txt").read_text(encoding="utf-8") == "mine"
    assert not (dest / f"{SLUG}_results.csv").exists()


def test_rerun_replaces_a_prior_rebuild_in_place(tmp_path, monkeypatch):
    """The reconstruction marker is what makes a re-run safe: the prior
    rebuild's files — including ones the new run would not write, like a
    stale partition subdirectory — are cleanly replaced, never merged."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    report, result = _rebuilt(tmp_path / "s1")
    dest = tmp_path / "out"
    assert not is_prior_rebuild(dest)
    write_rebuild(report, result, dest)
    assert is_prior_rebuild(dest)

    stale = dest / "partition-2"
    stale.mkdir()
    (stale / f"{SLUG}_results.csv").write_text("stale", encoding="utf-8")
    receipt = write_rebuild(report, result, dest)
    assert receipt.replaced_prior_rebuild
    assert not stale.exists()
    assert (dest / f"{SLUG}_results.csv").exists()


# ── Reconstruction provenance (§6.4e) ────────────────────────────────────────


def test_provenance_carries_the_reconstruction_block(tmp_path, monkeypatch):
    """The rebuilt ``{slug}_provenance.json`` is the §11 "tell": marker,
    Hub + engine versions, the explicit rebuild mode, a timestamp, the
    source manifest with per-folder session counts, and the report
    reference."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(tmp_path / "s2", session_id="s-003", candidate_id="P003")

    report, result = _rebuilt(tmp_path / "s1", tmp_path / "s2")
    dest = tmp_path / "out"
    write_rebuild(report, result, dest)

    record = json.loads(
        (dest / f"{SLUG}_provenance.json").read_text(encoding="utf-8")
    )
    assert record["reconstructed"] is True
    assert record["hub_version"] == __version__
    assert record["engine_version"] == __version__
    assert record["rebuild_mode"] == "advanced"
    assert record["rebuild_mode_source"] == "configured"
    assert record["rebuild_timestamp_utc"]
    assert record["source_manifest"] == [
        {"folder": str(tmp_path / "s1"), "sessions": 2},
        {"folder": str(tmp_path / "s2"), "sessions": 1},
    ]
    assert record["ingestion_report"] == f"{SLUG}_ingestion_report.md"


def test_provenance_records_an_explicit_mode_override(tmp_path, monkeypatch):
    """A Classic-collected study rebuilt in Advanced is self-describing
    (§6.3): the provenance states the override and the dictionary documents
    the mode the surfaces were actually projected to."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(
        tmp_path / "s1",
        {"metrics_mode": "classic"},
        session_id="s-001",
        candidate_id="P001",
    )

    report = ingest([tmp_path / "s1"])
    result = rebuild(report, mode="advanced")
    dest = tmp_path / "out"
    write_rebuild(report, result, dest)

    record = json.loads(
        (dest / f"{SLUG}_provenance.json").read_text(encoding="utf-8")
    )
    assert record["rebuild_mode"] == "advanced"
    assert record["rebuild_mode_source"] == "override"
    dictionary = (dest / f"{SLUG}_data_dictionary.md").read_text(encoding="utf-8")
    assert "Metrics mode: `advanced`" in dictionary


# ── Partitions (§6.4d) ───────────────────────────────────────────────────────


def test_config_drift_partitions_get_self_contained_subdirs(
    tmp_path, monkeypatch
):
    """Multi-partition output: one subdirectory per partition, each carrying
    its own three mirrored data surfaces, plus the shared top-level report
    and provenance — and no top-level data files."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _write(
        tmp_path / "s1",
        {"reward_per_pump": 0.10},
        session_id="s-003",
        candidate_id="P003",
    )

    report, result = _rebuilt(tmp_path / "s1")
    dest = tmp_path / "out"
    receipt = write_rebuild(report, result, dest)

    for folder, rows in (("partition-1", 2), ("partition-2", 1)):
        for name in (
            f"{SLUG}_results.csv",
            f"{SLUG}_trials.csv",
            f"{SLUG}_data_dictionary.md",
        ):
            assert (dest / folder / name).exists()
        results = (dest / folder / f"{SLUG}_results.csv").read_text(
            encoding="utf-8"
        )
        assert len(results.splitlines()) == rows + 1  # header + one per session
    assert not (dest / f"{SLUG}_results.csv").exists()
    assert (dest / f"{SLUG}_ingestion_report.md").exists()
    assert (dest / f"{SLUG}_provenance.json").exists()
    assert f"partition-1/{SLUG}_results.csv" in receipt.files


# ── The ingestion-report file (§7.3 rendered to disk) ────────────────────────


def test_ingestion_report_itemizes_every_group(tmp_path, monkeypatch):
    """The written report is the "never silent" artifact: headline counts,
    then every held / attention / informational finding itemized — including
    the verify findings the rebuild slotted into the same report."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    tampered = _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _edit_json(tampered["metrics"], total_pumps=9999)
    held = _write(tmp_path / "s1", session_id="s-003", candidate_id="P003")
    Path(held["events"]).unlink()

    report, result = _rebuilt(tmp_path / "s1")
    dest = tmp_path / "out"
    write_rebuild(report, result, dest)

    text = (dest / f"{SLUG}_ingestion_report.md").read_text(encoding="utf-8")
    assert f"# Ingestion Report — {report.title}" in text
    assert "2 session(s) rebuilt · 1 held · 1 attention · 1 partition(s)" in text
    assert "Rebuild mode: `advanced`" in text
    assert str(tmp_path / "s1") in text
    assert "## Held — excluded until resolved" in text
    assert _the(report, "missing_events").message in text
    assert "## Attention — pooled, but itemized" in text
    assert _the(report, "verify_corruption").message in text
    assert "⚠" in text  # the loud data-integrity tier is marked


def test_ingestion_report_says_none_for_empty_groups(tmp_path, monkeypatch):
    """A clean run still shows the Held and Attention sections — an explicit
    "None." is the evidence the Hub looked."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    report, result = _rebuilt(tmp_path / "s1")
    dest = tmp_path / "out"
    write_rebuild(report, result, dest)

    text = (dest / f"{SLUG}_ingestion_report.md").read_text(encoding="utf-8")
    assert text.count("None.") >= 2


def test_ingestion_report_names_partition_subdirs_and_drift(
    tmp_path, monkeypatch
):
    """With partitions, the report maps each subdirectory to its session
    count and the fields that split it from the main set."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(
        tmp_path / "s1",
        {"reward_per_pump": 0.10, "language": "tr"},
        session_id="s-002",
        candidate_id="P002",
    )

    report, result = _rebuilt(tmp_path / "s1")
    dest = tmp_path / "out"
    write_rebuild(report, result, dest)

    text = (dest / f"{SLUG}_ingestion_report.md").read_text(encoding="utf-8")
    assert "## Partitions" in text
    assert "`partition-1/` — 1 session(s) — the main set" in text
    assert "`partition-2/` — 1 session(s) — differs in: " in text
    assert "reward_per_pump" in text
    assert "language" in text
