"""The equivalence gate: a Hub rebuild is field-identical to live output (I14).

This module carries the paper's **verifiable claim** (DATA-SPEC §6.5, §9.3) and
nothing else, so it stays citable on its own: for the clean single-station
same-mode case, the study-wide CSVs a Hub reconstruction writes are **byte-
identical** to the ones the live emission path appended session by session.
Both sides are produced here, now, by the *current* code — the reference is
never a committed CSV ([T05] §5f) — over the golden fixture's
``clean-equivalence`` study (I13), the only mode that live-appends at all.

Byte-equality is the gate; the per-cell diff below exists only to make a
failure readable. Two surfaces are deliberately exempt: ``provenance.json``
*should* differ (it is the §11 "tell" that a folder was reconstructed), and the
data dictionary is checked **structurally** rather than byte-wise, since it is
a generated document rather than data.

The gate also validates a round-trip nothing else covers: ``timestamp_utc`` is
persisted *only* in each session's filename stem (§9.3), so a rebuild that
failed to recover it from the filename could not reproduce the first column.

``tests/test_hub_writer.py`` asserts the same byte-identity as one property of
the writer among many; this module is deliberately the *isolated* statement of
it over the golden fixture, so the claim can be cited without pointing a
reviewer at a file about something else ([I14] "keep this module separate").

If this module ever fails, the fix is to converge the Hub onto the **shared**
emission code (``sidecar.emission``), never to special-case the assertion.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from sidecar.hub import IngestionReport, ingest
from sidecar.hub_writer import write_rebuild
from sidecar.rebuild import RebuildResult, rebuild

from tests.hub.fixture_builder import build_clean_equivalence

# The one §6.6 verify code that is *not* a mismatch — it notes a cross-version
# agreement. Everything else the pass emits is matched by prefix rather than by
# name, so renaming or adding a mismatch code can never quietly empty the
# filter and let the gate pass on a divergence it stopped recognizing.
VERIFY_AGREEMENT_CODE = "verify_version_note"


@dataclass(frozen=True)
class Gate:
    """The two sides of the comparison: the folder the live path wrote and the
    folder the Hub reconstructed from that same folder's per-session files."""

    live: Path
    rebuilt: Path
    slug: str
    report: IngestionReport
    result: RebuildResult

    def pair(self, surface: str) -> tuple[Path, Path]:
        """The live and rebuilt copies of one study-wide surface."""
        name = f"{self.slug}_{surface}"
        return self.live / name, self.rebuilt / name


@pytest.fixture
def gate(tmp_path: Path) -> Gate:
    """Build the clean study, then reconstruct it from its own per-session
    files. The rebuild reads the *same* folder the live output sits in and
    writes to a separate destination — the Hub never writes into a source."""
    fixture = build_clean_equivalence(tmp_path / "live")
    report = ingest(fixture.sources)
    result = rebuild(report)
    destination = tmp_path / "rebuilt"
    write_rebuild(report, result, destination)
    return Gate(
        live=fixture.root,
        rebuilt=destination,
        slug=fixture.slug,
        report=report,
        result=result,
    )


# ── Reading a failure ────────────────────────────────────────────────────────


def _rows(raw: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(raw.decode("utf-8"), newline="")))


def _cell_diff(live: bytes, rebuilt: bytes) -> str:
    """A parsed, per-cell account of how two CSVs differ — the debugging aid
    §9.3 asks for. Only ever rendered on failure: the *gate* is the raw byte
    comparison above it, so a diff that finds nothing to say (a difference in
    line endings, quoting, or trailing bytes) still fails the test loudly."""
    left, right = _rows(live), _rows(rebuilt)
    lines: list[str] = []
    if left and right and left[0] != right[0]:
        lines.append(f"header: live={left[0]} rebuilt={right[0]}")
    if len(left) != len(right):
        lines.append(f"row count: live={len(left)} rebuilt={len(right)}")
    header = left[0] if left else []
    for index, (a, b) in enumerate(zip(left[1:], right[1:]), start=1):
        for column, (cell_a, cell_b) in enumerate(zip(a, b)):
            if cell_a != cell_b:
                name = header[column] if column < len(header) else f"col {column}"
                lines.append(f"row {index} {name}: live={cell_a!r} rebuilt={cell_b!r}")
    return "\n".join(lines) or (
        "no cell differs — the bytes do (line endings, quoting, or trailing "
        "bytes), which is exactly what a parsed comparison would have missed"
    )


# ── The gate (§6.5, §9.3) ────────────────────────────────────────────────────


@pytest.mark.parametrize("surface", ["results.csv", "trials.csv"])
def test_rebuilt_csv_is_byte_identical_to_live(gate: Gate, surface: str):
    """The headline claim. Column order, float formatting, quoting and row
    order all hold by construction — both sides go through the same flattener,
    identity builder and CSV writer — so anything that drifts them apart shows
    up here as unequal bytes."""
    live, rebuilt = gate.pair(surface)
    live_bytes, rebuilt_bytes = live.read_bytes(), rebuilt.read_bytes()

    assert rebuilt_bytes == live_bytes, _cell_diff(live_bytes, rebuilt_bytes)


def test_rebuild_reports_zero_verify_mismatches(gate: Gate):
    """§6.5's second surface: ``metrics.json`` equivalence is not a file
    comparison but the §6.6 verify pass finding nothing — every session's
    stored metrics reproduce exactly under the running engine.

    Zero mismatches only means something if the pass had something to compare:
    it returns early for a session whose stored metrics are absent, so the
    sessions are also asserted to carry theirs. Otherwise an ingest regression
    that dropped the metrics paths would satisfy this test by finding nothing.
    """
    mismatches = [
        finding
        for finding in gate.report.findings
        if finding.code.startswith("verify_")
        and finding.code != VERIFY_AGREEMENT_CODE
    ]
    records = [
        record
        for partition in gate.report.partitions
        for record in partition.sessions
    ]

    assert mismatches == []
    assert gate.report.will_rebuild == 3
    assert [record.metrics_path for record in records].count(None) == 0


def test_rebuild_is_the_single_station_projection(gate: Gate):
    """One station means the ``station_id``/``participant_key`` columns stay
    out of the *rebuilt* rows (§11) and those rows are projected to the study's
    own configured mode — the two conditions under which "field-identical" is
    even claimed. Asserted on the rebuild, since live output could not carry
    the station columns however the Hub behaved."""
    _, rebuilt = gate.pair("results.csv")
    header = _rows(rebuilt.read_bytes())[0]

    assert "station_id" not in header
    assert "participant_key" not in header
    assert gate.result.mode_source == "configured"
    assert gate.result.mode == gate.report.configured_mode


# ── The two exempt surfaces ──────────────────────────────────────────────────


def _structure(text: str) -> list[str]:
    """A generated markdown document reduced to its shape: its headings and the
    row labels of its tables (the documented column names), in order. Enough to
    catch a section or column that a rebuild failed to document, without
    pinning prose the renderer is free to reword."""
    structure: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            structure.append(line.strip())
        elif line.startswith("| ") and not re.fullmatch(r"\|[\s|:-]+", line):
            structure.append(line.split("|")[1].strip())
    return structure


def test_data_dictionary_matches_structurally(gate: Gate):
    """Checked structurally, not byte-wise, as §6.5 asks: the dictionary is a
    generated *document*, and the fidelity claim is about data. The rebuild
    happens to render it through the same renderer and so lands the same bytes
    today — pinned as such by ``test_hub_writer.py`` — but this module states
    only the weaker claim it needs, which no rewording of the prose can break.
    """
    live, rebuilt = gate.pair("data_dictionary.md")

    assert _structure(rebuilt.read_text(encoding="utf-8")) == _structure(
        live.read_text(encoding="utf-8")
    )


def test_provenance_is_excluded_because_a_rebuild_must_declare_itself(gate: Gate):
    """The one output that *should* differ. No comparison is made here — a
    provenance difference must never fail this module — only the reason the
    exclusion is legitimate: the rebuilt record carries the §6.4e
    reconstruction marker, so a reader can always tell the two folders apart.
    A rebuild that passed itself off as live output would be the real
    failure."""
    live, rebuilt = gate.pair("provenance.json")

    assert json.loads(rebuilt.read_text(encoding="utf-8"))["reconstructed"] is True
    assert "reconstructed" not in json.loads(live.read_text(encoding="utf-8"))
