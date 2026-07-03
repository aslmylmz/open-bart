"""Docs-as-contract guards (issue 32).

The Sphinx site is part of the instrument's public interface: the hazard-family
reference must cover every family the config accepts, and the data-outputs page
must document every column the sidecar actually writes to the Master CSV.
"""

from __future__ import annotations

import subprocess
import sys
import typing
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parent.parent / "docs"


def _docs_deps_available() -> bool:
    try:
        import furo  # noqa: F401
        import myst_parser  # noqa: F401
        import sphinx  # noqa: F401
        import sphinx_copybutton  # noqa: F401
    except ImportError:
        return False
    return True


def _curated_families() -> set[str]:
    """Family tags derived from the HazardSpec union itself, so adding a
    twelfth family fails this guard until it is documented."""
    from scoring.config.hazards import HazardSpec

    union = typing.get_args(HazardSpec)[0]
    return {cls.model_fields["family"].default for cls in typing.get_args(union)}


def test_every_hazard_family_has_a_reference_section():
    page = (DOCS / "hazard_families.md").read_text(encoding="utf-8")
    headings = [line for line in page.splitlines() if line.startswith("#")]

    undocumented = {
        family
        for family in _curated_families()
        if not any(family in h.lower() for h in headings)
    }
    assert undocumented == set()


def test_every_master_csv_column_is_documented(tmp_path):
    """Write a real session through the public /write-output endpoint and check
    that every column of the resulting Master CSV appears in the data-outputs
    page — per-color columns via their `{color}_field` pattern. The study
    declares conditions so the widest schema (incl. `condition`, issue 37) is
    the one held to the documentation contract."""
    import csv

    from scoring.config import DEFAULT_TASK_CONFIG
    from tests.test_sidecar import _collected_session, _session_payload, client

    page = (DOCS / "data_outputs.md").read_text(encoding="utf-8")

    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)
    cfg["conditions"] = ["control", "experimental"]
    resp = client.post(
        "/write-output",
        json={
            "session": _session_payload(_collected_session(), condition="control"),
            "config": cfg,
        },
    )
    assert resp.status_code == 200, resp.text
    with open(resp.json()["master_csv"], newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert header, "master CSV should have a header row"

    colors = [c.name for c in DEFAULT_TASK_CONFIG.colors]
    undocumented = []
    for column in header:
        color = next((c for c in colors if column.startswith(c + "_")), None)
        needle = f"{{color}}_{column[len(color) + 1:]}" if color else column
        if needle not in page:
            undocumented.append(column)
    assert undocumented == []


@pytest.mark.skipif(not _docs_deps_available(), reason="docs extras not installed")
def test_sphinx_build_is_warning_free(tmp_path):
    """The published site builds with zero warnings (the Phase 4 standard):
    -W turns any warning — stale refs, orphaned pages — into a failure."""
    proc = subprocess.run(
        [
            sys.executable, "-m", "sphinx",
            "-b", "html", "-W", "--keep-going",
            str(DOCS), str(tmp_path / "html"),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
