"""Data Hub view model: the JSON projection the tab renders (I12).

The Data Hub UI tab (DATA-SPEC §7.1–7.4) is a thin surface over the same
ingest → rebuild → write core as the CLI (I11); ``sidecar/hub_view.py`` is the
adapter that flattens the core's two dataclasses into the single view the tab
consumes, and ``perform_rebuild`` is the guarded write the Rebuild control fires.
These tests build station folders through the real emission path (as
``tests/test_hub.py`` does), then assert the projection matches the core: the
headline counts, per-source attribution, findings-by-group, the previewed file
tree (pinned to what ``write_rebuild`` actually lands), and the ``status`` each
rebuild outcome maps to.
"""

from __future__ import annotations

import json
from pathlib import Path

from scoring.config import DEFAULT_TASK_CONFIG
from sidecar.hub import ingest
from sidecar.hub_view import build_hub_view, perform_rebuild
from sidecar.hub_writer import planned_files, write_rebuild
from sidecar.naming import slug
from sidecar.rebuild import rebuild

from tests.test_hub import _copy_session, _edit_json, _use_station, _write
from tests.test_sidecar import client

SLUG = slug(DEFAULT_TASK_CONFIG.title)


# ── build_hub_view: the clean projection (§7.2–7.4) ──────────────────────────


def test_view_projects_a_clean_multi_station_ingest(tmp_path, monkeypatch):
    """Two labeled stations, distinct participants: the view is ``ok``, counts
    every rebuilt session, splits into one partition, and names the study —
    the same facts the report carries, flattened for the tab."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(tmp_path / "s2", session_id="s-003", candidate_id="P003")

    view = build_hub_view([str(tmp_path / "s1"), str(tmp_path / "s2")])

    assert view.ok
    assert view.error is None
    assert view.title == DEFAULT_TASK_CONFIG.title
    assert view.slug == SLUG
    assert view.will_rebuild == 3
    assert view.held == 0
    assert view.attention == 0
    assert view.partitions == 1


def test_view_attributes_stations_and_sessions_per_source(tmp_path, monkeypatch):
    """Each Sources-band row counts the distinct stations and rebuilt sessions
    attributed to that root — the copy that was actually pooled (§7.2)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    _use_station(monkeypatch, tmp_path, "b", "S2")
    _write(tmp_path / "s2", session_id="s-003", candidate_id="P003")

    view = build_hub_view([str(tmp_path / "s1"), str(tmp_path / "s2")])

    by_folder = {src.folder: src for src in view.sources}
    assert by_folder[str(tmp_path / "s1")].stations == 1
    assert by_folder[str(tmp_path / "s1")].sessions == 2
    assert by_folder[str(tmp_path / "s2")].stations == 1
    assert by_folder[str(tmp_path / "s2")].sessions == 1


def test_view_collapsed_duplicate_counts_its_source_once(tmp_path, monkeypatch):
    """A session copied into a second source folder collapses to one rebuilt
    row, attributed to the folder holding the pooled copy — the duplicate
    source contributes zero sessions, matching I10's per-source manifest."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _copy_session(out, tmp_path / "backup")

    view = build_hub_view([str(tmp_path / "s1"), str(tmp_path / "backup")])

    by_folder = {src.folder: src.sessions for src in view.sources}
    assert view.will_rebuild == 1
    assert sum(by_folder.values()) == 1


def test_view_groups_findings_with_loud_and_session_counts(tmp_path, monkeypatch):
    """A held session (missing events) surfaces as a ``held`` finding view with
    its session count; the groups map 1:1 to the report's own groups so the
    tab's accordions mirror I8 exactly."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    out = _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    Path(out["events"]).unlink()  # ground truth gone → held

    view = build_hub_view([str(tmp_path / "s1")])

    held = [f for f in view.findings if f.group == "held"]
    assert view.held == len(held) == 1
    assert held[0].code == "missing_events"
    assert held[0].sessions == 1
    assert view.will_rebuild == 1  # the sound session still rebuilds


def test_view_file_tree_matches_what_the_writer_lands(tmp_path, monkeypatch):
    """The Output band's preview is exactly the writer's own file list, with
    the provenance record flagged as the reconstruction marker (§7.4)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    view = build_hub_view([str(tmp_path / "s1")])
    report = ingest([str(tmp_path / "s1")])
    result = rebuild(report)

    assert [f.path for f in view.files] == planned_files(report, result)
    marked = [f.path for f in view.files if f.reconstructed]
    assert marked == [f"{SLUG}_provenance.json"]


def test_view_multi_partition_previews_subdirectories(tmp_path, monkeypatch):
    """Config drift splits the rebuild into ``partition-N/`` subdirectories;
    the previewed tree carries them, so the tab shows the real split (§7.4)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    drift = _write(tmp_path / "s1", session_id="s-003", candidate_id="P003")
    _edit_json(drift["config"], reward_per_pump=99.0)  # pooling-breaking

    view = build_hub_view([str(tmp_path / "s1")])

    assert view.partitions == 2
    assert any(f.path.startswith("partition-1/") for f in view.files)
    assert any(f.path.startswith("partition-2/") for f in view.files)


def test_view_mode_override_reprojects(tmp_path, monkeypatch):
    """An explicit mode is the §6.3 override: the view reports the overridden
    mode and marks its source, matching what a rebuild in that mode produces."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    view = build_hub_view([str(tmp_path / "s1")], mode="classic")

    assert view.mode == "classic"
    assert view.mode_source == "override"
    assert view.configured_mode == DEFAULT_TASK_CONFIG.metrics_mode


def test_view_no_study_is_not_ok(tmp_path):
    """An empty folder identifies no study — the one dataset-level abort comes
    back as ``ok=False`` with the message, never an exception (§5.6, §7.3)."""
    (tmp_path / "empty").mkdir()

    view = build_hub_view([str(tmp_path / "empty")])

    assert not view.ok
    assert view.error and "no study identifiable" in view.error


# ── perform_rebuild: the guarded write behind the Rebuild control (§7.4) ─────────


def test_perform_rebuild_writes_and_reports_the_receipt(tmp_path, monkeypatch):
    """The happy path writes the mirrored surfaces and returns ``written`` with
    the files, destination, and rebuilt/held counts the UI confirms."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    dest = tmp_path / "out"

    resp = perform_rebuild([str(tmp_path / "s1")], str(dest))

    assert resp.ok and resp.status == "written"
    assert resp.destination == str(dest)
    assert f"{SLUG}_results.csv" in resp.files
    assert resp.rebuilt == 1
    assert resp.held == 0
    assert (dest / f"{SLUG}_results.csv").exists()


def test_perform_rebuild_refuses_writing_into_a_source(tmp_path, monkeypatch):
    """A destination inside a source is refused, nothing is written, and the
    reason is carried back for the band to show (§6.4a)."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    resp = perform_rebuild([str(tmp_path / "s1")], str(tmp_path / "s1" / "rebuilt"))

    assert not resp.ok and resp.status == "refused"
    assert resp.message and "read-only" in resp.message
    assert not (tmp_path / "s1" / "rebuilt").exists()


def test_perform_rebuild_asks_to_confirm_replacing_a_prior_rebuild(tmp_path, monkeypatch):
    """A prior Hub rebuild in the destination comes back ``needs_force`` without
    touching it — the UI's confirm-replace input; ``force`` then replaces it."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    dest = tmp_path / "out"
    perform_rebuild([str(tmp_path / "s1")], str(dest))  # a first, real rebuild

    blocked = perform_rebuild([str(tmp_path / "s1")], str(dest))
    assert not blocked.ok and blocked.status == "needs_force"

    forced = perform_rebuild([str(tmp_path / "s1")], str(dest), force=True)
    assert forced.ok and forced.status == "written"
    assert forced.replaced_prior_rebuild


def test_perform_rebuild_reports_no_study(tmp_path):
    """No identifiable study → ``no_study`` (nothing to rebuild), the CLI's
    exit-3 case surfaced for the UI."""
    (tmp_path / "empty").mkdir()

    resp = perform_rebuild([str(tmp_path / "empty")], str(tmp_path / "out"))

    assert not resp.ok and resp.status == "no_study"
    assert not (tmp_path / "out").exists()


# ── planned_files drift guard: the preview cannot outrun the writer ───────────


def test_planned_files_matches_write_rebuild(tmp_path, monkeypatch):
    """``planned_files`` is the Output band's preview source; it must name
    exactly what ``write_rebuild`` lands — file-for-file, in write order — or
    the tab would promise a tree the writer does not deliver."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    _write(tmp_path / "s1", session_id="s-002", candidate_id="P002")
    drift = _write(tmp_path / "s1", session_id="s-003", candidate_id="P003")
    _edit_json(drift["config"], reward_per_pump=99.0)

    report = ingest([str(tmp_path / "s1")])
    result = rebuild(report)
    receipt = write_rebuild(report, result, tmp_path / "out")

    assert planned_files(report, result) == receipt.files


# ── HTTP wiring: the /hub/* routes the webview actually calls (§7) ────────────


def test_endpoint_hub_ingest_returns_the_view(tmp_path, monkeypatch):
    """POST /hub/ingest parses the request and serializes the view — the exact
    round trip the tab's `ingestSources` client makes."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")

    resp = client.post(
        "/hub/ingest", json={"sources": [str(tmp_path / "s1")], "mode": None}
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] and body["will_rebuild"] == 1
    assert body["files"][0] == {"path": f"{SLUG}_provenance.json", "reconstructed": True}


def test_endpoint_hub_rebuild_writes_the_surfaces(tmp_path, monkeypatch):
    """POST /hub/rebuild performs the guarded write and returns the receipt —
    the round trip the tab's Rebuild control makes."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    _write(tmp_path / "s1", session_id="s-001", candidate_id="P001")
    dest = tmp_path / "out"

    resp = client.post(
        "/hub/rebuild",
        json={"sources": [str(tmp_path / "s1")], "out": str(dest), "force": False},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] and body["status"] == "written"
    assert (dest / f"{SLUG}_results.csv").exists()
