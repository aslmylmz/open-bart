"""Test Run / practice mode: sessions that cannot contaminate the dataset
(issue 43).

The contamination accident runs both directions — a test session landing in
the real data, or a real participant unknowingly run in practice (data
silently lost). These tests pin the sidecar half of the guarantee through the
public /write-output endpoint: practice sessions run the real pipeline into a
``practice/`` subfolder, stamped, and never touch the official study files.
"""

from __future__ import annotations

import json
from pathlib import Path

from scoring.bart import score_bart
from scoring.config import DEFAULT_TASK_CONFIG

from tests.test_sidecar import _collected_session, _session_payload, client


def _write_session(tmp_path, practice: bool = False, **payload_over) -> dict:
    """POST one collected session to /write-output; returns the response body."""
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)
    session = _session_payload(_collected_session(), **payload_over)
    if practice:
        session["practice"] = True
    resp = client.post("/write-output", json={"session": session, "config": cfg})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_practice_session_lands_stamped_in_the_practice_subfolder(tmp_path):
    """A practice session exercises the real pipeline end-to-end — the same
    four files, really scored — but under ``practice/``, stamped in the
    session envelope, and with no study-wide CSV rows anywhere."""
    events = _collected_session()
    out = _write_session(tmp_path, practice=True, candidate_id="TEST")

    for key in ("events", "metrics", "config", "session"):
        path = Path(out[key])
        assert path.exists()
        assert path.parent == tmp_path / "practice"

    # The stamp: the envelope says so in the data itself, not just the path.
    envelope = json.loads(Path(out["session"]).read_text("utf-8"))
    assert envelope["practice"] is True

    # Real pipeline: the metrics are the engine's own scoring of the session.
    metrics = json.loads(Path(out["metrics"]).read_text("utf-8"))
    assert metrics == score_bart(events, DEFAULT_TASK_CONFIG).model_dump(mode="json")

    # No study-wide files were written for it.
    assert out["master_csv"] is None
    assert out["trials_csv"] is None
    assert out["warnings"] == []


def test_practice_run_leaves_the_official_study_files_byte_identical(tmp_path):
    """The dataset-contamination guarantee, official direction: after a real
    session has established the CSVs and provenance files, a practice run
    changes not a single byte of them — the master CSV, trials CSV, and
    provenance files are exactly as before."""
    _write_session(tmp_path, candidate_id="P001")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    assert before  # session files + CSVs + provenance are there

    _write_session(tmp_path, practice=True, candidate_id="TEST")

    after = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    assert after == before


def test_practice_first_run_creates_no_study_wide_files(tmp_path):
    """Practice on a fresh study neither creates the CSVs nor the provenance
    files: the official output directory stays empty except the practice/
    subfolder with the session's own four files."""
    _write_session(tmp_path, practice=True, candidate_id="TEST")

    assert [p.name for p in tmp_path.iterdir()] == ["practice"]
    suffixes = sorted(
        p.name.rsplit("_", 1)[-1] for p in (tmp_path / "practice").iterdir()
    )
    assert suffixes == ["config.json", "events.jsonl", "metrics.json", "session.json"]
