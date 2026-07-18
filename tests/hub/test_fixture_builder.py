"""The golden-fixture builder's own guarantees (I13).

The builder is the single source of truth for the two validation suites that
follow — the clean byte-equality gate (I14) and the hazard report-line
assertions (I15) — so its own contract is asserted here: it is deterministic,
it produces well-formed sessions through the *real* emission path, and the
hazard suite carries exactly the planted defects of DATA-SPEC §9.2 and no
others. Per-line message assertions belong to I15; this module asserts the
census, not the wording.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from sidecar.hub import ingest
from sidecar.rebuild import rebuild

from tests.hub.fixture_builder import (
    build_clean_equivalence,
    build_hazard_suite,
)


def _tree(root: Path) -> dict[str, bytes]:
    """Every file under ``root`` keyed by its relative path — the surface the
    determinism guarantee is about."""
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _codes(report) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in report.findings:
        counts[finding.code] = counts.get(finding.code, 0) + 1
    return counts


# ── Determinism (§9.5) ───────────────────────────────────────────────────────


@pytest.mark.parametrize("build", [build_clean_equivalence, build_hazard_suite])
def test_studies_are_byte_reproducible(tmp_path, build):
    """Fixed synthetic timestamps and machine UUIDs instead of ``datetime.now``
    / ``uuid4``: building the same fixture twice in the same place yields
    byte-identical trees — the precondition for a committed snapshot guarded
    by a drift test (I16). Same place, because each session's config snapshot
    records the output directory it was written to."""
    base = tmp_path / "base"
    first = _tree(build(base).root)
    shutil.rmtree(base)

    assert _tree(build(base).root) == first


# ── clean-equivalence: the live-output reference (§9.1) ──────────────────────


def test_clean_study_is_real_live_output_of_three_sessions(tmp_path):
    """One station, ``standalone=False`` — the only mode with a live-append
    reference — so the folder carries the two study-wide CSVs the equivalence
    gate (I14) compares a rebuild against, beside three clean sessions."""
    fixture = build_clean_equivalence(tmp_path)

    names = sorted(p.name for p in fixture.root.iterdir())
    assert f"{fixture.slug}_results.csv" in names
    assert f"{fixture.slug}_trials.csv" in names
    assert f"{fixture.slug}_data_dictionary.md" in names
    assert len(fixture.sessions) == 3
    for kind in ("events.jsonl", "metrics.json", "config.json", "session.json"):
        assert sum(name.endswith(kind) for name in names) == 3


def test_clean_study_ingests_with_nothing_to_report(tmp_path):
    """No hazards means no report lines at all: the clean study must not
    pollute the gate with findings of its own."""
    fixture = build_clean_equivalence(tmp_path)

    report = ingest(fixture.sources)

    assert report.findings == []
    assert report.will_rebuild == 3
    assert len(report.partitions) == 1


# ── hazard-suite: one hazard per session (§9.2) ──────────────────────────────


def test_hazard_suite_plants_exactly_the_expected_hazards(tmp_path):
    """The §9.2 census: every planted defect yields its own report line, and
    nothing else does. ``config_drift_notable`` appears twice — currency (row
    7) and the seed variation rows 4 and 5 jointly imply — and ``id_collision``
    twice (rows 4 and 5); the verify rows only land once the rebuild has
    re-scored, so both stages run here."""
    fixture = build_hazard_suite(tmp_path)

    report = ingest(fixture.sources)
    rebuild(report)

    assert _codes(report) == {
        # held
        "divergent_duplicate": 1,
        "future_schema": 1,
        "missing_events": 1,
        "missing_session": 1,
        "unreadable_json": 1,
        # attention
        "config_drift_notable": 2,
        "config_drift_partition": 1,
        "duplicate_station_label": 1,
        "id_collision": 2,
        "older_schema": 1,
        "verify_corruption": 1,
        "verify_ungraded": 1,
        # info
        "foreign_files": 1,
        "identical_duplicates_collapsed": 1,
        "missing_metrics": 1,
        "verify_engine_drift": 1,
    }
    # One hazard per session means every line is attributable to the session it
    # was planted on — the property that stops a dropped flag being masked.
    for code, name in (
        ("verify_corruption", "verify-corrupt"),
        ("verify_engine_drift", "verify-drift"),
        ("verify_ungraded", "verify-ungraded"),
        ("missing_events", "missing-events"),
        ("missing_metrics", "missing-metrics"),
        ("divergent_duplicate", "dup-divergent"),
    ):
        [finding] = [f for f in report.findings if f.code == code]
        assert finding.session_ids == [fixture.sessions[name]], code


def test_hazard_suite_splits_into_one_main_and_one_drift_partition(tmp_path):
    """The language drift (row 13) is the only pooling-breaking one, so the
    suite rebuilds as MAIN + exactly one DRIFT partition (§9.1)."""
    fixture = build_hazard_suite(tmp_path)

    report = ingest(fixture.sources)

    assert [len(p.sessions) for p in report.partitions] == [14, 1]
    assert report.partitions[1].breaking["language"] == "tr"


def test_malformed_inputs_are_written_directly_not_emitted(tmp_path):
    """Well-formed sessions go through ``write_output``; a defect that the
    emission path cannot produce is planted on the files themselves — a
    truncated config is truncated bytes, a removed file is simply absent."""
    fixture = build_hazard_suite(tmp_path)

    truncated = fixture.file("truncated-json", "config.json")
    assert truncated.read_text(encoding="utf-8") == '{"incomplete":'
    assert not fixture.file("missing-events", "events.jsonl").exists()
    assert not fixture.file("missing-metrics", "metrics.json").exists()
    assert not fixture.file("missing-session", "session.json").exists()
