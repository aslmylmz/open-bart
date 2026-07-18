"""
Regenerate the committed sample dataset (`docs/samples/`)
========================================================

The one command behind DATA-SPEC §9.5's committed snapshot: it rebuilds both
golden-fixture studies from the *live* emission path and the Hub, exactly as
`tests/hub/test_samples_snapshot.py` does when it checks them for drift. If
that test fails, run this and commit the result — never hand-edit a sample.

Regeneration is expected after a release version bump (the samples stamp
`scoring.__version__` throughout) or any deliberate change to what the
instrument emits. A diff that is *not* one of those is the drift guard doing
its job.

Usage:
    python scripts/regenerate_samples.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# The repo root puts `import scoring` (and `tests`) on the path; `app/` puts
# the sidecar package on it — the same two entries conftest.py adds, since
# this script runs outside pytest.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from tests.hub.snapshot import STUDIES, regenerate  # noqa: E402


def main() -> None:
    # Always from the repo root: the samples record the directory they were
    # written to, so running this from anywhere else would bake a different
    # config snapshot into every session.
    samples = regenerate(ROOT)
    for study in STUDIES:
        files = sum(1 for path in (samples / study).rglob("*") if path.is_file())
        print(f"{(samples / study).relative_to(ROOT)}: {files} file(s)")


if __name__ == "__main__":
    main()
