"""The output-filename grammar shared by emission and ingestion.

``write_output`` composes per-session filenames as
``[title](_[station])_[candidate]_[timestamp]_[kind]``, and the session's
``timestamp_utc`` is persisted *only* in that stem (DATA-SPEC §9.3) — so the
Hub must read the same grammar back to recover it. The slug rule and the stem
shape live here, importable by both the FastAPI app and the Hub core without
either importing the other.
"""

from __future__ import annotations

import re

# The strict timestamp token (digits + T + Z, no underscores): the same rule
# ``_count_sessions`` matches on the write side, so an ID that merely shares a
# prefix with another can never smuggle a fake stem boundary.
TIMESTAMP = r"\d{8}T\d+Z"


def slug(text: str) -> str:
    """Filesystem-safe namespace fragment for output filenames (SPEC §13)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "study"


# One per-session output file: ``{stem}_{kind}`` where the stem ends in the
# strict timestamp. The greedy prefix anchors the *last* timestamp-shaped
# token, mirroring the end-anchored match on the write side.
SESSION_FILE = re.compile(
    rf"^(?P<stem>.+_(?P<ts>{TIMESTAMP}))_"
    rf"(?P<kind>events\.jsonl|metrics\.json|config\.json|session\.json)$"
)
