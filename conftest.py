"""Make the repo root and ``app/`` importable under pytest.

The repo root puts ``import scoring`` on the path; ``app/`` puts the sidecar
package (``import sidecar``) on the path without it being a pip-installed package.
"""

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "app"))


@pytest.fixture(autouse=True)
def _isolated_station_settings(tmp_path_factory, monkeypatch):
    """Point the sidecar's per-machine station settings at a per-test temp file
    so tests never read or write this machine's real station identity — and a
    station ID set on a developer machine can never leak into test filenames."""
    station_home = tmp_path_factory.mktemp("station-home")
    monkeypatch.setenv("BART_STATION_FILE", str(station_home / "station.json"))
