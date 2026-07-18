"""Hub CLI: the scriptable strip over the shared Hub core (I11).

The CLI's whole contract (DATA-SPEC §7.5) is adapter-thin: `openbart hub
<sources…> --out <dir>` wraps the same ingest → rebuild → write core the UI
tab uses, prints the same rendered ingestion report the destination file
carries, and maps the outcome to exit codes — 0 clean, 2 held sessions
present, 3 no study identifiable, 4 destination refused. These tests build
station folders through the real emission path (as ``tests/test_hub.py``
does), invoke ``cli.main`` in-process, and assert on exit code, stdout/stderr,
and what did — or pointedly did not — land on disk.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scoring.config import DEFAULT_TASK_CONFIG
from sidecar import hub_writer
from sidecar.cli import main
from sidecar.naming import slug

from tests.test_hub import _use_station, _write

SLUG = slug(DEFAULT_TASK_CONFIG.title)


def _pin_clock(monkeypatch) -> None:
    """Pin the writer's provenance/report clock so the printed report and the
    written file can be compared byte-for-byte across a minute boundary."""
    fixed = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(hub_writer, "_utc_now", lambda: fixed)


def _station_folder(tmp_path, monkeypatch, n_sessions: int = 2) -> Path:
    _use_station(monkeypatch, tmp_path, "a", "S1")
    src = tmp_path / "s1"
    for i in range(1, n_sessions + 1):
        _write(src, session_id=f"s-{i:03d}", candidate_id=f"P{i:03d}")
    return src


# ── Exit 0: clean rebuild ────────────────────────────────────────────────────


def test_clean_run_writes_rebuild_and_exits_0(tmp_path, monkeypatch, capsys):
    """The happy path: sources in, reconstructed surfaces out, exit 0 — and
    stdout carries the same rendered report the destination file does, plus a
    receipt of every file written."""
    _pin_clock(monkeypatch)
    src = _station_folder(tmp_path, monkeypatch)
    dest = tmp_path / "out"

    code = main(["hub", str(src), "--out", str(dest)])

    assert code == 0
    for name in (
        f"{SLUG}_results.csv",
        f"{SLUG}_trials.csv",
        f"{SLUG}_data_dictionary.md",
        f"{SLUG}_provenance.json",
        f"{SLUG}_ingestion_report.md",
    ):
        assert (dest / name).is_file(), name
    out = capsys.readouterr().out
    report_file = (dest / f"{SLUG}_ingestion_report.md").read_text(
        encoding="utf-8"
    )
    assert out.startswith(report_file)
    assert f"Wrote 5 file(s) to {dest}" in out
    assert f"{SLUG}_results.csv" in out


def test_default_mode_is_configured_and_flag_is_override(tmp_path, monkeypatch):
    """--mode omitted → the study's configured mode ('configured'); an
    explicit --mode is recorded as a rebuild-time override (§6.3), the one
    thing the Hub can do the live path cannot."""
    src = _station_folder(tmp_path, monkeypatch, n_sessions=1)

    assert main(["hub", str(src), "--out", str(tmp_path / "o1")]) == 0
    prov = json.loads(
        (tmp_path / "o1" / f"{SLUG}_provenance.json").read_text(encoding="utf-8")
    )
    assert prov["rebuild_mode"] == DEFAULT_TASK_CONFIG.metrics_mode
    assert prov["rebuild_mode_source"] == "configured"

    assert main(
        ["hub", str(src), "--out", str(tmp_path / "o2"), "--mode", "classic"]
    ) == 0
    prov = json.loads(
        (tmp_path / "o2" / f"{SLUG}_provenance.json").read_text(encoding="utf-8")
    )
    assert prov["rebuild_mode"] == "classic"
    assert prov["rebuild_mode_source"] == "override"


# ── Exit 2: held sessions present ────────────────────────────────────────────


def test_held_sessions_exit_2_but_the_rebuild_still_proceeds(
    tmp_path, monkeypatch, capsys
):
    """Held blocks only the affected sessions, never the run (§7.3): the rest
    is written, the held line is printed, and exit 2 says 'look at the
    report' — in --dry-run exactly as in a real run."""
    _use_station(monkeypatch, tmp_path, "a", "S1")
    src = tmp_path / "s1"
    _write(src, session_id="s-001", candidate_id="P001")
    broken = _write(src, session_id="s-002", candidate_id="P002")
    Path(broken["events"]).unlink()
    dest = tmp_path / "out"

    code = main(["hub", str(src), "--out", str(dest)])

    assert code == 2
    out = capsys.readouterr().out
    assert "held: no events" in out
    assert "1 session(s) rebuilt · 1 held" in out
    assert (dest / f"{SLUG}_results.csv").is_file()

    assert main(["hub", str(src), "--dry-run"]) == 2


# ── Exit 3: no study identifiable ────────────────────────────────────────────


def test_no_identifiable_study_exits_3_and_writes_nothing(
    tmp_path, monkeypatch, capsys
):
    """The one true abort (§5.6): nothing in any source names a study, so
    there is nothing to rebuild — exit 3, error on stderr, no destination."""
    src = tmp_path / "not-a-study"
    src.mkdir()
    (src / "notes.txt").write_text("holiday photos", encoding="utf-8")
    dest = tmp_path / "out"

    code = main(["hub", str(src), "--out", str(dest)])

    assert code == 3
    assert "no study identifiable" in capsys.readouterr().err
    assert not dest.exists()


# ── Exit 4: destination refused ──────────────────────────────────────────────


def test_destination_inside_a_source_is_refused_with_4(
    tmp_path, monkeypatch, capsys
):
    """Sources are read-only (§6.4a): pointing --out into a source is refused
    by the writer's own guard — exit 4 and the source is untouched."""
    src = _station_folder(tmp_path, monkeypatch, n_sessions=1)
    before = sorted(p.name for p in src.iterdir())

    code = main(["hub", str(src), "--out", str(src / "out")])

    assert code == 4
    assert "refused" in capsys.readouterr().err
    assert sorted(p.name for p in src.iterdir()) == before


def test_non_empty_non_rebuild_destination_is_refused_with_4(
    tmp_path, monkeypatch, capsys
):
    """A non-empty folder without the reconstruction marker is never
    overwritten (§6.4a) — even --force does not reach it; exit 4."""
    src = _station_folder(tmp_path, monkeypatch, n_sessions=1)
    dest = tmp_path / "thesis"
    dest.mkdir()
    (dest / "draft.docx").write_text("precious", encoding="utf-8")

    code = main(["hub", str(src), "--out", str(dest)])

    assert code == 4
    assert "refused" in capsys.readouterr().err
    assert (dest / "draft.docx").read_text(encoding="utf-8") == "precious"


def test_replacing_a_prior_rebuild_requires_force(tmp_path, monkeypatch, capsys):
    """A prior rebuild is only replaced on explicit --force — the CLI's stand-in
    for the UI's replace confirmation, gated on the reconstruction marker."""
    src = _station_folder(tmp_path, monkeypatch, n_sessions=1)
    dest = tmp_path / "out"
    assert main(["hub", str(src), "--out", str(dest)]) == 0
    capsys.readouterr()

    code = main(["hub", str(src), "--out", str(dest)])
    assert code == 4
    assert "--force" in capsys.readouterr().err

    code = main(["hub", str(src), "--out", str(dest), "--force"])
    assert code == 0
    assert "replaced the prior rebuild" in capsys.readouterr().out


# ── --dry-run: report only, write nothing ────────────────────────────────────


def test_dry_run_prints_the_report_and_writes_nothing(
    tmp_path, monkeypatch, capsys
):
    """--dry-run is the report-only path: full ingestion + rebuild printout,
    zero filesystem effect — the destination is never even created."""
    src = _station_folder(tmp_path, monkeypatch)
    dest = tmp_path / "out"

    code = main(["hub", str(src), "--out", str(dest), "--dry-run"])

    assert code == 0
    out = capsys.readouterr().out
    assert "# Ingestion Report" in out
    assert "2 session(s) rebuilt" in out
    assert "Dry run — nothing written." in out
    assert not dest.exists()


def test_dry_run_needs_no_out_but_a_real_run_does(tmp_path, monkeypatch, capsys):
    """--out is only meaningful when something will be written, so --dry-run
    runs without one; a real run without --out is a usage error — exit 64
    (EX_USAGE), never argparse's stock 2, which §7.5 reserves for 'held'."""
    src = _station_folder(tmp_path, monkeypatch, n_sessions=1)

    assert main(["hub", str(src), "--dry-run"]) == 0

    with pytest.raises(SystemExit) as excinfo:
        main(["hub", str(src)])
    assert excinfo.value.code == 64
    assert "--out" in capsys.readouterr().err


# ── One binary, both faces: `python -m sidecar hub …` dispatches here ────────


def test_module_entry_point_dispatches_hub_to_the_cli(
    tmp_path, monkeypatch, capsys
):
    """``python -m sidecar hub …`` (and thus the frozen sidecar binary's
    ``hub`` subcommand) routes to the CLI and exits with its code."""
    src = _station_folder(tmp_path, monkeypatch, n_sessions=1)
    from sidecar import __main__ as entry

    monkeypatch.setattr(
        sys, "argv", ["sidecar", "hub", str(src), "--dry-run"]
    )
    with pytest.raises(SystemExit) as excinfo:
        entry.main()

    assert excinfo.value.code == 0
    assert "# Ingestion Report" in capsys.readouterr().out
