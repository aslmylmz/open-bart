"""Header-versioned append for study-wide CSV files (issue 36).

The Master CSV — and, from issue 39, the trials CSV — is a single file per
study that the sidecar appends to across sessions *and app versions*. A lab
that upgrades the app mid-study must never end up with silently misaligned
columns: this writer compares the file's header to the row being written and
migrates (with a backup), or falls back to a sibling file, instead of ever
appending a row that does not line up with the header on disk.
"""

from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class AppendResult:
    """Where the session row landed, plus a readable warning when the write
    did not go to ``path`` as-is (migration, sibling fallback)."""

    path: Path
    warning: str | None = None


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _read_header(path: Path) -> list[str] | None:
    """The file's header row, or ``None`` when the file doesn't exist yet."""
    if not path.exists():
        return None
    with path.open("r", newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh), None)


def _append(path: Path, fieldnames: list[str], rows: list[Mapping[str, Any]]) -> None:
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if fh.tell() == 0:
            writer.writeheader()
        writer.writerows(rows)


def _migrate(path: Path, backup: Path, fieldnames: list[str]) -> None:
    """Rewrite ``path`` under the current header, add-columns-only: existing
    rows keep their values by column name and get blanks in new columns. Reads
    from the already-written ``backup`` so a crash mid-rewrite loses nothing."""
    with backup.open("r", newline="", encoding="utf-8") as src:
        rows = list(csv.DictReader(src))
    with path.open("w", newline="", encoding="utf-8") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(rows)


def _write_sibling(
    path: Path, fieldnames: list[str], rows: list[Mapping[str, Any]]
) -> Path:
    """Write the rows to a timestamped sibling file so the session is never
    lost when the main file cannot be appended to."""
    sibling = path.with_name(f"{path.stem}_unmerged_{_timestamp()}{path.suffix}")
    _append(sibling, fieldnames, rows)
    return sibling


def append_row(path: Path, row: Mapping[str, Any]) -> AppendResult:
    """Append one row to the CSV at ``path`` — see ``append_rows``."""
    return append_rows(path, [row])


def append_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> AppendResult:
    """Append ``rows`` (sharing one key set) to the CSV at ``path``, creating
    it with a header row when absent. The first row's key order is the
    canonical column order.

    When the file's header is *older* (a subset of the rows' columns), the file
    is backed up alongside and auto-migrated to the current header first. When
    it has columns this app doesn't know (a *newer* app wrote it), the rows go
    to a timestamped sibling file instead — migration is add-columns-only. A
    locked, unwritable, or unparseable file (e.g. open in Excel on Windows, or
    re-saved in a non-UTF-8 encoding) likewise falls back to a sibling file:
    the session is never lost and never raises.
    """
    rows = list(rows)
    if not rows:
        return AppendResult(path=path)
    fieldnames = list(rows[0])
    try:
        return _append_or_migrate(path, fieldnames, rows)
    except (OSError, ValueError, csv.Error) as exc:
        reason = getattr(exc, "strerror", None) or str(exc) or type(exc).__name__
        sibling = _write_sibling(path, fieldnames, rows)
        return AppendResult(
            path=sibling,
            warning=(
                f"Could not update {path.name} ({reason}) — the file may be open "
                f"in another program (e.g. Excel) or damaged. The session's rows "
                f"were saved to {sibling.name}; merge them into the main file by "
                f"hand."
            ),
        )


def _append_or_migrate(
    path: Path, fieldnames: list[str], rows: list[Mapping[str, Any]]
) -> AppendResult:
    existing = _read_header(path)
    if existing is not None and existing != fieldnames:
        unknown = [column for column in existing if column not in set(fieldnames)]
        if unknown:
            sibling = _write_sibling(path, fieldnames, rows)
            return AppendResult(
                path=sibling,
                warning=(
                    f"{path.name} has columns this app version does not know "
                    f"({', '.join(unknown)}) — it was likely written by a newer "
                    f"version. The session's rows were saved to {sibling.name}; "
                    f"merge them into the main file by hand."
                ),
            )
        backup = path.with_name(f"{path.stem}_backup_{_timestamp()}{path.suffix}")
        shutil.copy2(path, backup)
        _migrate(path, backup, fieldnames)
        _append(path, fieldnames, rows)
        return AppendResult(
            path=path,
            warning=(
                f"Column schema changed: {path.name} was migrated to the current "
                f"columns (older rows keep blanks in new columns); the original "
                f"file was backed up as {backup.name}."
            ),
        )
    _append(path, fieldnames, rows)
    return AppendResult(path=path)
