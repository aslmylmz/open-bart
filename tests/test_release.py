"""Release-consistency guards (issue 34).

A release touches seven manifests; JOSS reviews one exact tagged version.
``scoring.__version__`` is the source of truth — every other manifest must
agree with it, and the citation metadata must describe the instrument.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import scoring

REPO = Path(__file__).resolve().parent.parent


def _manifest_versions() -> dict[str, str]:
    versions: dict[str, str] = {}

    conf = (REPO / "docs" / "conf.py").read_text(encoding="utf-8")
    versions["docs/conf.py"] = re.search(r'release = "([^"]+)"', conf).group(1)

    tauri = json.loads((REPO / "app" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    versions["tauri.conf.json"] = tauri["version"]

    cargo = (REPO / "app" / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8")
    versions["Cargo.toml"] = re.search(r'^version = "([^"]+)"', cargo, flags=re.M).group(1)

    lock = (REPO / "app" / "src-tauri" / "Cargo.lock").read_text(encoding="utf-8")
    versions["Cargo.lock"] = re.search(
        r'name = "bart-instrument"\nversion = "([^"]+)"', lock
    ).group(1)

    pkg = json.loads((REPO / "app" / "package.json").read_text(encoding="utf-8"))
    versions["package.json"] = pkg["version"]

    pkg_lock = json.loads((REPO / "app" / "package-lock.json").read_text(encoding="utf-8"))
    versions["package-lock.json (root)"] = pkg_lock["version"]
    versions["package-lock.json (pkg)"] = pkg_lock["packages"][""]["version"]

    cff = (REPO / "CITATION.cff").read_text(encoding="utf-8")
    versions["CITATION.cff"] = re.search(r'^version: "([^"]+)"', cff, flags=re.M).group(1)

    index = (REPO / "docs" / "index.md").read_text(encoding="utf-8")
    versions["docs/index.md citation"] = re.search(r"Version (\d+\.\d+\.\d+)", index).group(1)

    return versions


def test_every_manifest_agrees_on_one_version():
    """scoring.__version__ is the release version; no manifest may lag."""
    mismatched = {
        name: found
        for name, found in _manifest_versions().items()
        if found != scoring.__version__
    }
    assert mismatched == {}, f"expected everything at {scoring.__version__}"


def test_citation_metadata_describes_the_instrument():
    """The Zenodo record is built from CITATION.cff: it must describe the
    configurable offline instrument, not the pre-instrument repo."""
    cff = (REPO / "CITATION.cff").read_text(encoding="utf-8")

    assert "React game" not in cff  # the old abstract's framing
    assert "offline" in cff.lower()
    assert "hazard famil" in cff.lower()
    assert re.search(r'^date-released: "\d{4}-\d{2}-\d{2}"', cff, flags=re.M)
