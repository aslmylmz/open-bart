"""Tests for the header-versioned CSV append writer (issue 36).

The Master CSV (and the trials CSV, issue 39) is one file per study, appended
across sessions *and app versions*. These tests pin the writer's contract:
plain append on a matching header, auto-migrate with a backup on an older
header, and a sibling file — never a lost session — when the file is locked
or comes from a newer app.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

from sidecar.versioned_csv import append_row


def _read(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """The file's header and rows, as researchers' tools would load them."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def test_creates_file_with_header_on_first_append(tmp_path):
    """First session of a study: the file is created with a header row and the
    session row, in the row's column order."""
    path = tmp_path / "Study_results.csv"

    result = append_row(path, {"candidate_id": "cand-1", "total_pumps": 42})

    assert result.path == path
    assert result.warning is None
    header, rows = _read(path)
    assert header == ["candidate_id", "total_pumps"]
    assert rows == [{"candidate_id": "cand-1", "total_pumps": "42"}]


def test_matching_header_appends_in_place(tmp_path):
    """Same app version, session after session: rows accumulate under the one
    header with no backups or sibling files appearing."""
    path = tmp_path / "Study_results.csv"
    append_row(path, {"candidate_id": "cand-1", "total_pumps": 42})

    result = append_row(path, {"candidate_id": "cand-2", "total_pumps": 7})

    assert result.path == path
    assert result.warning is None
    header, rows = _read(path)
    assert header == ["candidate_id", "total_pumps"]
    assert [r["candidate_id"] for r in rows] == ["cand-1", "cand-2"]
    assert list(tmp_path.iterdir()) == [path]  # nothing else was created


def test_older_header_migrates_with_backup(tmp_path):
    """A lab upgrades the app mid-study: the file on disk has last version's
    header. The writer backs the file up, rewrites it under the current header
    — old rows keep their values by column *name*, with honest blanks in the
    new columns — and appends the new session's row."""
    path = tmp_path / "Study_results.csv"
    append_row(path, {"candidate_id": "cand-1", "total_pumps": 42})

    result = append_row(
        path, {"candidate_id": "cand-2", "total_pumps": 7, "condition": "control"}
    )

    assert result.path == path
    header, rows = _read(path)
    assert header == ["candidate_id", "total_pumps", "condition"]
    assert rows == [
        {"candidate_id": "cand-1", "total_pumps": "42", "condition": ""},
        {"candidate_id": "cand-2", "total_pumps": "7", "condition": "control"},
    ]

    backups = [p for p in tmp_path.iterdir() if p != path]
    assert len(backups) == 1
    assert backups[0].name.startswith("Study_results") and "backup" in backups[0].name
    assert _read(backups[0]) == (
        ["candidate_id", "total_pumps"],
        [{"candidate_id": "cand-1", "total_pumps": "42"}],
    )

    # The researcher is told why a backup file appeared next to their sheet.
    assert result.warning is not None
    assert backups[0].name in result.warning


def test_unknown_columns_fall_back_to_sibling_file(tmp_path):
    """The file has columns this app version doesn't know (written by a *newer*
    app). Migration is add-columns-only — rewriting could drop data — so the
    session row goes to a timestamped sibling file and the original stays
    byte-for-byte untouched."""
    path = tmp_path / "Study_results.csv"
    append_row(
        path, {"candidate_id": "cand-1", "total_pumps": 42, "condition": "control"}
    )
    original = path.read_bytes()

    result = append_row(path, {"candidate_id": "cand-2", "total_pumps": 7})

    assert path.read_bytes() == original
    assert result.path != path
    assert result.path.parent == tmp_path
    assert result.warning is not None
    assert result.path.name in result.warning
    header, rows = _read(result.path)
    assert header == ["candidate_id", "total_pumps"]
    assert rows == [{"candidate_id": "cand-2", "total_pumps": "7"}]


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not make a file unwritable on Windows"
)
def test_unwritable_file_falls_back_to_sibling(tmp_path):
    """The file cannot be appended to (e.g. open in Excel on Windows): the
    session row goes to a timestamped sibling file with a readable warning —
    never an exception, never a lost session."""
    path = tmp_path / "Study_results.csv"
    append_row(path, {"candidate_id": "cand-1", "total_pumps": 42})
    path.chmod(0o444)
    try:
        result = append_row(path, {"candidate_id": "cand-2", "total_pumps": 7})
    finally:
        path.chmod(0o644)

    assert result.path != path
    assert result.warning is not None
    assert result.path.name in result.warning
    assert _read(result.path) == (
        ["candidate_id", "total_pumps"],
        [{"candidate_id": "cand-2", "total_pumps": "7"}],
    )
    # The locked file itself was left alone.
    assert _read(path)[1] == [{"candidate_id": "cand-1", "total_pumps": "42"}]


def test_unparseable_file_falls_back_to_sibling(tmp_path):
    """The file on disk can't be merged into — e.g. Excel re-saved it in a
    non-UTF-8 encoding, or a crash left a truncated row. The session row still
    lands in a sibling file with a warning; the damaged file is left alone."""
    path = tmp_path / "Study_results.csv"
    original = "candidate_id\ncand-1,stray-extra-cell\n".encode("utf-16")
    path.write_bytes(original)

    result = append_row(path, {"candidate_id": "cand-2", "total_pumps": 7})

    assert path.read_bytes() == original
    assert result.path != path
    assert result.warning is not None
    assert result.path.name in result.warning
    assert _read(result.path) == (
        ["candidate_id", "total_pumps"],
        [{"candidate_id": "cand-2", "total_pumps": "7"}],
    )
