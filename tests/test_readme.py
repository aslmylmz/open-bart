"""README acceptance guard (issue 31).

The README is the JOSS reviewer's front door: every relative link must
resolve, and the instrument story must be present with no stale claims.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")


def test_all_relative_readme_links_resolve():
    """Every non-http link target in the README exists in the repository."""
    targets = re.findall(r"\[[^\]]*\]\(([^)#]+)(?:#[^)]*)?\)", README)
    relative = [t for t in targets if not t.startswith(("http://", "https://", "mailto:"))]

    missing = [t for t in relative if not (REPO_ROOT / t).exists()]
    assert missing == []
    assert relative, "README should link to repository files"


def test_readme_tells_the_instrument_story_without_stale_claims():
    """The front page describes the standalone configurable instrument: a
    researcher install path, the researcher workflow outputs, and the
    verification command — with no leftovers from the pre-instrument repo."""
    # stale claims
    assert "next.js" not in README.lower()

    # researcher install path
    assert "/releases" in README
    assert "docs/standalone/SMARTSCREEN.md" in README
    assert "docs/standalone/quickstart.md" in README

    # workflow outputs use the canonical vocabulary
    assert "Master CSV" in README

    # the simulation-verified optima claim is reproducible in one command
    assert "python -m scoring.verification" in README
