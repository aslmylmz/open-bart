"""Station identity: per-machine app setting + per-install UUID (DATA-SPEC §2.3).

Every station gets a globally-attributable identity — a researcher-entered
station label persisted as a per-machine app setting (outside ``study.json``)
plus a random per-install machine UUID — so sneakernet-merged folders never
collide and duplicate station labels stay Hub-detectable. These tests exercise
the setting through the sidecar's public HTTP surface (``/station``) and the
three enforcement/stamp sites: ``check_id``'s blank poka-yoke, the output
filename stem, and the study's provenance record.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scoring.config import DEFAULT_TASK_CONFIG

from tests.test_provenance import _write_session
from tests.test_sidecar import client


def _standalone_check(candidate_id: str = "P001") -> dict:
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["standalone"] = True
    resp = client.post(
        "/check-id", json={"candidate_id": candidate_id, "config": cfg}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_station_starts_unset_with_a_persistent_machine_uuid():
    """A fresh install has no station label but does have a machine UUID,
    generated on first run and stable across calls (the duplicate detector
    is worthless if it changes between sessions)."""
    first = client.get("/station").json()
    assert first["station_id"] is None
    assert first["machine_uuid"]
    assert client.get("/station").json()["machine_uuid"] == first["machine_uuid"]


def test_two_installs_get_distinct_machine_uuids(tmp_path, monkeypatch):
    """Two machines labeled identically must still be distinguishable at the
    Hub: each install generates its own UUID."""
    monkeypatch.setenv("BART_STATION_FILE", str(tmp_path / "machine-a.json"))
    uuid_a = client.get("/station").json()["machine_uuid"]
    monkeypatch.setenv("BART_STATION_FILE", str(tmp_path / "machine-b.json"))
    uuid_b = client.get("/station").json()["machine_uuid"]
    assert uuid_a != uuid_b


def test_set_station_id_round_trips_and_persists():
    out = client.post("/station", json={"station_id": "S1"}).json()
    assert out["ok"] is True
    assert out["station_id"] == "S1"
    again = client.get("/station").json()
    assert again["station_id"] == "S1"
    assert again["machine_uuid"] == out["machine_uuid"]


def test_set_station_id_empty_clears_the_setting():
    client.post("/station", json={"station_id": "S1"})
    out = client.post("/station", json={"station_id": "  "}).json()
    assert out["ok"] is True
    assert out["station_id"] is None
    assert client.get("/station").json()["station_id"] is None


@pytest.mark.parametrize("bad_id", ["S 1", "lab/3", "S1!", "x" * 33])
def test_set_station_id_rejects_unusable_labels(bad_id):
    """The station label lands in every output filename, so it obeys the same
    slug discipline ``check_id`` enforces on participant IDs — plus a length
    cap — and a rejected label never replaces the stored one."""
    client.post("/station", json={"station_id": "S1"})
    out = client.post("/station", json={"station_id": bad_id}).json()
    assert out["ok"] is False
    assert out["error"]
    assert client.get("/station").json()["station_id"] == "S1"


def test_check_id_blocks_standalone_sessions_without_a_station_id():
    """The blank poka-yoke: standalone on + no station ID set ⇒ sessions are
    blocked at the ID screen with a message naming the fix."""
    out = _standalone_check()
    assert out["ok"] is False
    assert "station" in out["error"].lower()


def test_check_id_allows_standalone_sessions_once_a_station_id_is_set():
    client.post("/station", json={"station_id": "S1"})
    assert _standalone_check()["ok"] is True


def test_check_id_without_standalone_never_requires_a_station():
    resp = client.post("/check-id", json={"candidate_id": "P001"})
    assert resp.json()["ok"] is True


def test_write_output_stamps_the_station_into_the_filename_stem(tmp_path):
    """With a station set the stem is {title}_{station}_{candidate}_{timestamp},
    so merged station folders can never collide on filename — independent of
    clock skew."""
    client.post("/station", json={"station_id": "S1"})
    out = _write_session(tmp_path)
    events = Path(out["events"]).name
    assert re.fullmatch(
        r"Dynamic-Hazard-Rate-BART-default-dynamic-study_S1_cand-1"
        r"_\d{8}T\d+Z_events\.jsonl",
        events,
    ), events


def test_write_output_without_a_station_keeps_todays_filenames(tmp_path):
    """Single-station mode leaves the station unset, and filenames stay
    byte-identical to the v1.0.0 stem — no empty segment, no placeholder."""
    out = _write_session(tmp_path)
    events = Path(out["events"]).name
    assert re.fullmatch(
        r"Dynamic-Hazard-Rate-BART-default-dynamic-study_cand-1"
        r"_\d{8}T\d+Z_events\.jsonl",
        events,
    ), events


def test_provenance_carries_station_and_machine_uuid_when_set(tmp_path):
    client.post("/station", json={"station_id": "S1"})
    _write_session(tmp_path)
    prov = json.loads(
        next(tmp_path.glob("*_provenance.json")).read_text("utf-8")
    )
    assert prov["station_id"] == "S1"
    assert prov["machine_uuid"] == client.get("/station").json()["machine_uuid"]


def test_provenance_is_unchanged_when_no_station_is_set(tmp_path):
    """The single-station provenance record keeps exactly its v1.1.0 keys —
    outputs stay byte-identical when the station setting is unset."""
    _write_session(tmp_path)
    prov = json.loads(
        next(tmp_path.glob("*_provenance.json")).read_text("utf-8")
    )
    assert set(prov) == {
        "app_version",
        "engine_version",
        "metrics_mode",
        "platform",
        "seed",
    }


def test_standalone_write_skips_the_study_wide_csvs(tmp_path):
    """Standalone Mode disables exactly one thing (DATA-SPEC §2.2): the two
    study-wide CSV appends that fragment across machines. The four per-session
    files — the Hub's ground truth — and all three provenance files are still
    written per-station, unchanged."""
    client.post("/station", json={"station_id": "S1"})
    out = _write_session(tmp_path, {"standalone": True})
    assert out["master_csv"] is None
    assert out["trials_csv"] is None
    assert not list(tmp_path.glob("*_results.csv"))
    assert not list(tmp_path.glob("*_trials.csv"))
    for key in ("events", "metrics", "config", "session"):
        assert Path(out[key]).is_file()
    assert list(tmp_path.glob("*_study.json"))
    assert list(tmp_path.glob("*_provenance.json"))
    assert list(tmp_path.glob("*_data_dictionary.md"))


def test_write_output_states_mode_and_station_affirmatively(tmp_path):
    """Both UI surfaces derive Standalone Mode + station purely from the
    /write-output payload (DATA-SPEC §2.4) — never from a missing file."""
    client.post("/station", json={"station_id": "S1"})
    out = _write_session(tmp_path, {"standalone": True})
    assert out["standalone"] is True
    assert out["station_id"] == "S1"


def test_write_output_defaults_keep_the_single_station_path(tmp_path):
    """Default config: live-append stays the canonical path and the payload
    says so affirmatively (standalone False, no station)."""
    out = _write_session(tmp_path)
    assert out["standalone"] is False
    assert out["station_id"] is None
    assert out["master_csv"] is not None


def test_check_id_counts_sessions_recorded_under_the_station_stem(tmp_path):
    """With a station set, filename stems carry the station segment (I4) —
    the local count must keep catching within-station re-runs (§2.6), and the
    strict stem match must keep an ID that merely shares a prefix with another
    (P001 vs P001_2) from being cross-counted."""
    client.post("/station", json={"station_id": "S1"})
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)
    for _ in range(2):
        _write_session(tmp_path, candidate_id="P001")
    _write_session(tmp_path, candidate_id="P001_2")
    check = client.post("/check-id", json={"candidate_id": "P001", "config": cfg})
    assert check.json()["sessions"] == 2
    cousin = client.post("/check-id", json={"candidate_id": "P001_2", "config": cfg})
    assert cousin.json()["sessions"] == 1


def test_check_id_reports_mode_and_station(tmp_path):
    """CheckIdResponse carries the standalone/station flags (§2.6) so the ID
    screen can word the duplicate warning honestly — station-scoped, local-only
    — without inferring the mode from anything else."""
    client.post("/station", json={"station_id": "S1"})
    out = _standalone_check()
    assert out["standalone"] is True
    assert out["station_id"] == "S1"
    plain = client.post("/check-id", json={"candidate_id": "P001"}).json()
    assert plain["standalone"] is False
