"""Deterministic text output: UTF-8, LF, on every platform.

Every file this instrument writes is research data — archived, committed to a
repository, checksummed, diffed against a rebuild. Python's text mode does not
serve that: it translates ``\\n`` to the *host's* line ending, so the same
session recorded on Windows and on macOS produces different bytes for
identical data. That silently costs three things:

- **The byte-identity claim** (DATA-SPEC §6.5/§9.5). A rebuild is supposed to
  reproduce live output byte-for-byte, and the committed `docs/samples/`
  snapshot is supposed to equal a fresh build. Both held on POSIX and only
  accidentally on Windows — the drift guard passed there solely because Git's
  ``core.autocrlf=true`` smudge happened to reintroduce the same CRLFs the
  writer had produced. A contributor with ``autocrlf=false`` saw it fail.
- **Mixed-platform studies.** A study collected on Windows and macOS stations
  is the case the multi-station architecture exists to serve; its per-session
  files should not differ by host.
- **Diffs.** A file that changes line endings shows as wholly rewritten.

So writing goes through here, and the line ending is a property of the format
rather than of the machine. CSVs are the deliberate exception and do not use
this module: ``csv.writer`` terminates rows with a literal CRLF per RFC 4180,
which is part of the format and already platform-independent.
"""

from __future__ import annotations

from pathlib import Path
from typing import IO


def write_utf8(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` as UTF-8 with LF endings, replacing it."""
    path.write_text(text, encoding="utf-8", newline="\n")


def open_utf8(path: Path, mode: str = "w") -> IO[str]:
    """Open ``path`` for UTF-8 LF text output — the streaming counterpart, for
    the event log, which is appended line by line rather than composed whole."""
    return path.open(mode, encoding="utf-8", newline="\n")
