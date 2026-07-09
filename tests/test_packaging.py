"""Packaging behavior: the scoring package is installable and self-identifying.

These are deliberately interface-level: they assert what an installed package
exposes (a version string, matching distribution metadata), not how it is built.
"""

from __future__ import annotations

import re

import pytest


def test_scoring_exposes_version():
    """The package self-identifies via ``scoring.__version__`` (PEP 440-ish)."""
    import scoring

    assert isinstance(scoring.__version__, str)
    assert re.match(r"^\d+\.\d+\.\d+", scoring.__version__)


def test_installed_metadata_matches_version():
    """When pip-installed, distribution metadata agrees with the in-code version.

    Skipped in a bare source checkout (the conftest path hack), so the suite
    passes whether or not the package is installed.
    """
    from importlib.metadata import PackageNotFoundError, version

    import scoring

    try:
        dist_version = version("open-bart")
    except PackageNotFoundError:
        pytest.skip("scoring not pip-installed (running from a source checkout)")

    assert dist_version == scoring.__version__
