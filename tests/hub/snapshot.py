"""The committed sample dataset, built from the golden fixture (I16).

DATA-SPEC §9.5 gives the two fixture studies a second job beyond the test
suite: they are the paper's **sample dataset**, committed under `docs/samples/`
(Decision B) so a reviewer can read real output without running anything.
`clean-equivalence/` carries inputs + the *live* study-wide CSVs and backs the
**verifiable** claim (a rebuild reproduces them byte-for-byte — the gate in
``test_hub_equivalence.py``); `hazard-suite/` carries inputs + a reconstructed
`rebuilt/` folder whose ingestion report itemizes every §9.2 hazard, the
**illustrative** artifact.

``regenerate`` is the single code path behind both the regeneration entry
point (``scripts/regenerate_samples.py``) and the drift guard
(``test_samples_snapshot.py``): the guard rebuilds and compares bytes, so the
committed snapshot cannot silently rot, and the fix for a failure is always to
run the one command rather than to hand-edit a sample.

Two things must be pinned beyond what the builder already pins (fixed
synthetic timestamps and machine UUIDs, §9.5), or a snapshot committed from
one machine could never be reproduced on another:

- **the Hub writer's clock**, which stamps the reconstruction provenance and
  dates the ingestion report — the third `_utc_now` seam, alongside the two
  the builder pins for the emission path;
- **`platform.platform()`**, which the provenance record and every session's
  engine stamp carry verbatim. Pinned to an obviously synthetic value: a
  sample dataset must not publish the machine that happened to generate it.

What is deliberately *not* pinned is the version: `scoring.__version__` is
stamped throughout, so a release bump fails the drift guard until the samples
are regenerated. That is the intended behaviour — the snapshot is a claim
about what *this* version emits.

Finally, the samples are built at a **relative** path from the repo root.
Each session's config snapshot records the output directory it was written to,
so reproducibility is per *location*: the guard reproduces the bytes by
building at the same relative path under a temp cwd, and an absolute base
would both break that and leak the generating machine's home directory into a
committed file (the path-leak discipline the screenshots follow). That is why
``regenerate`` takes the directory to work *from* and moves the cwd there
itself — an invariant the callers cannot forget to honour.
"""

from __future__ import annotations

import os
import platform
import shutil
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sidecar import hub_writer
from sidecar.hub import ingest
from sidecar.hub_writer import write_rebuild
from sidecar.rebuild import rebuild

from tests.hub.fixture_builder import (
    CLEAN_STUDY,
    HAZARD_STUDY,
    MACHINES,
    build_clean_equivalence,
    build_hazard_suite,
)

# Relative to the repo root, and part of the bytes — see the module docstring.
SAMPLES = Path("docs") / "samples"

# The two study folders `build_samples` owns. Everything else under
# `docs/samples/` (the README) is hand-written documentation *about* them and
# is neither generated nor drift-guarded.
STUDIES = (CLEAN_STUDY, HAZARD_STUDY)

# Where the hazard suite's reconstruction lands, beside the station folders it
# was assembled from — the committed artifact a reviewer opens.
REBUILT = "rebuilt"

# The machine label the samples publish instead of the one that built them.
PINNED_PLATFORM = "fixture-platform"

# The instant the sample reconstruction claims to have run: a couple of hours
# after the fixture's synthetic sessions, which is when a collection pass
# plausibly happens.
_REBUILD_STAMP = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)


@contextmanager
def _pinned_machine() -> Iterator[None]:
    """Pin the two facts the fixture builder cannot: the Hub writer's clock and
    the platform string. Both call sites (`app` and `provenance`) reach
    `platform.platform` through the stdlib module, so patching it there covers
    the engine stamp and the provenance record alike."""
    original_platform, original_now = platform.platform, hub_writer._utc_now
    platform.platform = lambda *args, **kwargs: PINNED_PLATFORM
    hub_writer._utc_now = lambda: _REBUILD_STAMP
    try:
        yield
    finally:
        platform.platform = original_platform
        hub_writer._utc_now = original_now


def regenerate(root: Path) -> Path:
    """Rebuild both sample studies at ``SAMPLES`` under ``root``, replacing
    whatever was there, and return the directory they landed in.

    ``root`` is the repo root for a real regeneration and a temp directory for
    the drift guard; the cwd moves there for the duration, because the studies
    must be written through the *relative* ``SAMPLES`` path — that string ends
    up inside every session's config snapshot, so it is what makes one build
    reproducible from another place.

    The clean study is committed as the live emission path left it: its
    study-wide CSVs *are* the reference the equivalence gate reproduces, so
    there is nothing to reconstruct. The hazard study is additionally ingested
    and rebuilt into ``hazard-suite/rebuilt/``, since its ingestion report is
    the whole point of committing it.
    """
    previous = Path.cwd()
    os.chdir(root)
    try:
        for study in STUDIES:
            shutil.rmtree(SAMPLES / study, ignore_errors=True)
        SAMPLES.mkdir(parents=True, exist_ok=True)
        with _pinned_machine():
            build_clean_equivalence(SAMPLES)
            hazard = build_hazard_suite(SAMPLES)
            report = ingest(hazard.sources)
            write_rebuild(report, rebuild(report), hazard.root / REBUILT)
        # The per-machine station settings the builder writes to impersonate
        # four machines are harness state, not sample data: they exist only so
        # the sessions can be emitted through the real identity path.
        shutil.rmtree(SAMPLES / MACHINES)
    finally:
        os.chdir(previous)
    return root / SAMPLES
