"""The "never silent" demonstration: every planted hazard is itemized (I15).

Where the equivalence gate (``test_hub_equivalence.py``) states what the Hub
gets *right* on clean data, this module states what it never lets pass
quietly. It runs the Hub over the golden fixture's ``hazard-suite`` (I13) —
one study, four stations, every row of DATA-SPEC §9.2 planted on its own
session — and asserts that each defect surfaces as **exactly one** report
line, in the severity group §5 assigns it.

One hazard per session is what makes that assertion meaningful: a dropped flag
cannot be masked by another session's line, and a line that fires twice is as
much a defect as one that never fires. The ``HAZARDS`` table below is
therefore closed — its codes are asserted to be *all* the codes the report
carries, so a new finding the Hub learns to emit fails this module until it is
written down here.

Assertions are on the **structured** finding (``code`` + ``group`` + ``loud``)
as [I15] asks, with message fragments used only where a code covers two
distinct rows (the two ID collisions, the two config drifts) and one final
test spot-checking that the rendered report really files each line under its
group's heading.

Three claims here are about the Hub's *boundaries* rather than any single row:
the missing-file trichotomy (metrics gone is clean, events or identity gone is
held), the §10 refusal to parse a foreign ``bart_export.csv``, and the clean
baseline session that must attract no line at all.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

import pytest

from sidecar.hub import Group, HubFinding, IngestionReport, ingest
from sidecar.hub_writer import render_report
from sidecar.rebuild import RebuildResult, rebuild

from tests.hub.fixture_builder import Fixture, build_hazard_suite

# The three group headings ``render_report`` files findings under (§7.3), and
# the marker it puts on the loud data-integrity tier.
HEADINGS: dict[Group, str] = {
    "held": "## Held — excluded until resolved",
    "attention": "## Attention — pooled, but itemized",
    "info": "## Clean / informational",
}
LOUD_MARKER = "⚠ "

# The stray ``bart_export.csv`` is the one hazard with no §9.2 row number — it
# is a study-level skip rather than a defect planted on a session.
FOREIGN_FILE_ROW = "—"


@dataclass(frozen=True)
class Hazard:
    """One row of the §9.2 table as this module asserts it: what the Hub must
    say about it, and how to tell that line apart from its siblings.

    ``session`` names the fixture session the hazard was planted on, and is set
    only where attribution is the *discriminator* — two rows sharing a code.
    ``says`` are fragments the message must contain: enough to prove the right
    line was found, never so much that rewording the prose breaks the suite.
    """

    row: str
    what: str
    code: str
    group: Group
    loud: bool = False
    session: str | None = None
    says: tuple[str, ...] = ()


# §9.2 in one place. ``test_samples_snapshot.py`` (I16) imports this table to
# assert the *committed* sample report itemizes the same rows, so it is the
# suite's shared census rather than this module's private list — a row edited
# here changes what both modules claim.
HAZARDS = (
    Hazard(
        row="2",
        what="identical duplicate collapses",
        code="identical_duplicates_collapsed",
        group="info",
        says=("collapsed 1 identical duplicate file-set(s)",),
    ),
    Hazard(
        row="3",
        what="divergent duplicate is held",
        code="divergent_duplicate",
        group="held",
        says=("held: divergent duplicate",),
    ),
    Hazard(
        row="4",
        what="ID collision sharing a fixed seed is loud",
        code="id_collision",
        group="attention",
        loud=True,
        session="collide-seed-a",
        says=("ID collision", "NOT independent", "participant_key added"),
    ),
    Hazard(
        row="5",
        what="ID collision without a seed",
        code="id_collision",
        group="attention",
        session="collide-free-a",
        says=("ID collision", "participant_key added"),
    ),
    Hazard(
        row="6",
        what="two machines share a station label",
        code="duplicate_station_label",
        group="attention",
        says=("duplicate station label",),
    ),
    Hazard(
        row="7",
        what="currency drift pools with a flag",
        code="config_drift_notable",
        group="attention",
        says=("config drift: currency", "sessions pooled"),
    ),
    Hazard(
        # Rows 4 and 5 need one colliding pair on a fixed seed and one on none,
        # so the suite necessarily also drifts on `seed` — and that drift is
        # itself a finding. Derived, not planted, but the table must still
        # account for it or the closure assertion below would fail.
        row="4+5 (derived)",
        what="seed drift the two collisions imply",
        code="config_drift_notable",
        group="attention",
        says=("config drift: seed", "sessions pooled"),
    ),
    Hazard(
        row="9",
        what="older schema pools on current defaults",
        code="older_schema",
        group="attention",
        says=("older schema 1.0 pooled",),
    ),
    Hazard(
        row="10",
        what="same-engine metrics mismatch is corruption",
        code="verify_corruption",
        group="attention",
        loud=True,
        says=("possible corruption",),
    ),
    Hazard(
        row="11",
        what="older-engine metrics mismatch is benign drift",
        code="verify_engine_drift",
        group="info",
        says=("benign engine drift",),
    ),
    Hazard(
        row="12",
        what="pre-stamp metrics mismatch cannot be graded",
        code="verify_ungraded",
        group="attention",
        says=("no engine stamp (pre-stamp data)",),
    ),
    Hazard(
        row="13",
        what="language drift forces its own partition",
        code="config_drift_partition",
        group="attention",
        says=("config drift: language → partition",),
    ),
    Hazard(
        row="14",
        what="future schema is held for a Hub upgrade",
        code="future_schema",
        group="held",
        says=("held: future schema 2.0", "upgrade the Hub"),
    ),
    Hazard(
        row="15",
        what="ground truth gone: cannot re-score",
        code="missing_events",
        group="held",
        says=("held: no events, cannot re-score",),
    ),
    Hazard(
        row="16",
        what="stored metrics gone: re-scored, nothing to verify",
        code="missing_metrics",
        group="info",
        says=("stored metrics absent; re-scored, no verify",),
    ),
    Hazard(
        row="17",
        what="identity gone: the filename is not enough",
        code="missing_session",
        group="held",
        says=("held: session envelope missing",),
    ),
    Hazard(
        row="18",
        what="a config that cannot be read at all",
        code="unreadable_json",
        group="held",
        says=("held: unreadable JSON",),
    ),
    Hazard(
        row=FOREIGN_FILE_ROW,
        what="the foreign export is skipped, not parsed",
        code="foreign_files",
        group="info",
        says=("skipped 1 unrecognized file(s)",),
    ),
)

HAZARD_BY_ROW = {hazard.row: hazard for hazard in HAZARDS}

# Applied to both parametrized tests below, so the two can never drift onto
# different subsets of the table.
over_hazards = pytest.mark.parametrize(
    "hazard", HAZARDS, ids=[f"row-{h.row}-{h.code}" for h in HAZARDS]
)


@dataclass(frozen=True)
class Suite:
    """The built hazard study, ingested and rebuilt once."""

    fixture: Fixture
    report: IngestionReport
    result: RebuildResult

    def session_id(self, name: str) -> str:
        """The UUID of the session a hazard was planted on."""
        return self.fixture.sessions[name]

    def find(self, hazard: Hazard) -> HubFinding:
        """The one report line this hazard must have produced. Failing to
        resolve to exactly one is itself the finding: zero means the Hub went
        silent, more than one means a defect was double-counted."""
        matches = [
            finding
            for finding in self.report.findings
            if finding.code == hazard.code
            and all(fragment in finding.message for fragment in hazard.says)
            and (
                hazard.session is None
                or self.session_id(hazard.session) in finding.session_ids
            )
        ]
        assert len(matches) == 1, (
            f"row {hazard.row} ({hazard.what}) matched {len(matches)} report "
            f"lines, expected 1:\n"
            + "\n".join(f"  {m.group}/{m.code}: {m.message}" for m in matches)
        )
        return matches[0]

    @property
    def rebuilt_ids(self) -> set[str]:
        """Every session that actually produced rows — the operative meaning of
        "held": a held session is one whose id never appears here."""
        return {
            session_id
            for partition in self.result.partitions
            for session_id in partition.session_ids
        }

    @property
    def results_rows(self) -> list[dict[str, Any]]:
        """The reconstructed master-CSV rows across all partitions."""
        return [
            row
            for partition in self.result.partitions
            for row in partition.results_rows
        ]

    def partition_of(self, name: str) -> int:
        """Which partition a planted session landed in — 0 is the main set."""
        session_id = self.session_id(name)
        return next(
            index
            for index, partition in enumerate(self.result.partitions)
            if session_id in partition.session_ids
        )


@pytest.fixture(scope="module")
def suite(tmp_path_factory: pytest.TempPathFactory) -> Suite:
    """Built, ingested and rebuilt once for the whole module: twenty sessions
    through the live emission path is the expensive part, and every test here
    only reads the result. Both stages run because the §6.6 verify rows (10–12)
    are appended by the rebuild, not the ingest."""
    fixture = build_hazard_suite(tmp_path_factory.mktemp("hazards"))
    report = ingest(fixture.sources)
    result = rebuild(report)
    return Suite(fixture=fixture, report=report, result=result)


@pytest.fixture(scope="module")
def rendered(suite: Suite) -> str:
    """The report as a researcher reads it, rendered once for the whole
    module."""
    return render_report(suite.report, suite.result)


# ── One planted defect → exactly one report line (§9.2) ──────────────────────


def test_the_hazard_table_accounts_for_every_report_line(suite: Suite):
    """The closure that makes the per-row tests below a *census* rather than a
    sample: the codes the Hub emitted are exactly the codes this module's table
    claims, with the same multiplicities. A hazard that stopped firing, fired
    twice, or a new line nobody wrote down all land here.

    ``test_fixture_builder.py`` asserts the same multiset against a literal
    dict, which is the *fixture's* guarantee that it planted §9.2. This one is
    tied to ``HAZARDS`` instead, so it fails the moment the Hub grows a line
    this module has not decided a group and a message for — a claim about this
    file staying complete, not about the fixture."""
    assert Counter(f.code for f in suite.report.findings) == Counter(
        hazard.code for hazard in HAZARDS
    )


@over_hazards
def test_each_planted_hazard_is_itemized_in_its_severity_group(
    suite: Suite, hazard: Hazard
):
    """Every row of §9.2, asserted on the structured finding: the Hub found it,
    said it once, and filed it where the severity rules put it — held blocks
    the session, attention pools it with a flag, info is clean/informational.
    ``loud`` is asserted too: the data-integrity tier is what a researcher must
    not scroll past."""
    finding = suite.find(hazard)

    assert finding.group == hazard.group
    assert finding.loud is hazard.loud


def test_the_clean_baseline_session_attracts_no_line(suite: Suite):
    """Row 1 is the control: an untouched session in a folder full of planted
    defects. It must rebuild and be named by nothing — otherwise the suite's
    lines could be coming from the fixture's mere shape rather than from the
    hazards planted in it."""
    clean = suite.session_id("clean-1")

    assert clean in suite.rebuilt_ids
    assert [f.code for f in suite.report.findings if clean in f.session_ids] == []


# ── "Held" as behaviour, not just as a label (§5, §5.6) ──────────────────────


def test_missing_metrics_is_clean_but_missing_events_or_identity_is_held(
    suite: Suite,
):
    """The trichotomy: three deletions grade differently because they cost
    different things. ``metrics.json`` is a *derived* artifact — its loss costs
    only the verify comparison, so the session re-scores and pools.
    ``events.jsonl`` is ground truth and ``session.json`` is identity; without
    either there is nothing to faithfully reconstruct, so the session is held
    rather than guessed at."""
    assert suite.session_id("missing-metrics") in suite.rebuilt_ids
    assert suite.session_id("missing-events") not in suite.rebuilt_ids
    assert suite.session_id("missing-session") not in suite.rebuilt_ids

    assert suite.find(HAZARD_BY_ROW["16"]).group == "info"
    assert suite.find(HAZARD_BY_ROW["15"]).group == "held"
    assert suite.find(HAZARD_BY_ROW["17"]).group == "held"


@pytest.mark.parametrize("name", ["dup-divergent", "future-schema", "truncated-json"])
def test_a_held_session_never_reaches_the_rebuild(suite: Suite, name: str):
    """§5 defines held as *"excluded until resolved"*, so the group label is
    only half the claim — the other half is that the data really stayed out.
    Without this, a regression that printed the hold and then pooled the
    session anyway would satisfy every group assertion above. The two
    deletions are covered by the trichotomy test; these are the remaining
    holds — the divergent duplicate the Hub must never pick a winner for, the
    future schema it cannot read, and the config it cannot parse."""
    assert suite.session_id(name) not in suite.rebuilt_ids


# ── The §10 boundary: foreign data is skipped, never parsed ──────────────────


def test_the_foreign_export_is_counted_and_left_alone(suite: Suite):
    """§10's boundary, stated as behaviour: a loose ``bart_export.csv`` sitting
    among the sessions is reported as *skipped* — not read, not scored, not
    guessed at. The proof is threefold: the Hub said it skipped one file, the
    subject it contains never reaches a rebuilt row, and the file is still
    exactly where and what it was, since sources are read-only."""
    export = suite.fixture.root / "lab-03" / "bart_export.csv"

    assert suite.find(HAZARD_BY_ROW[FOREIGN_FILE_ROW]).group == "info"
    assert "1001" not in {row["candidate_id"] for row in suite.results_rows}
    assert export.read_text(encoding="utf-8").startswith("subjID,trial,pumps,exploded")


# ── Which drifts split the study and which do not (§5.4) ─────────────────────


def test_a_classic_mode_session_unifies_at_rebuild(suite: Suite):
    """Row 8 is the hazard that *isn't* one. A station configured for Classic
    output collected the same events as everyone else; ``metrics_mode`` is a
    projection over one scored result, not a different task. So it earns no
    report line and — the load-bearing claim — it does not split the study: the
    session pools into the **main** partition and is re-projected to the
    study's own mode, emerging with the clean baseline's columns. A Hub that
    treated the mode as pooling-breaking would strand it in a partition of its
    own, and only the partition assertion would notice."""
    rows = {row["session_id"]: row for row in suite.results_rows}
    classic = suite.session_id("mode-classic")

    assert [f.code for f in suite.report.findings if classic in f.session_ids] == []
    assert suite.partition_of("mode-classic") == 0
    assert suite.result.mode == "advanced"
    assert rows[classic].keys() == rows[suite.session_id("clean-1")].keys()


def test_the_language_drift_gets_a_partition_of_its_own(suite: Suite):
    """Row 13's second half. ``language`` changes the task a participant
    actually faced, so §5.4 makes it pooling-breaking: the report line is only
    half the response, and the other half is that the session is separated —
    it lands in its own partition, which §7.4 writes to its own subdirectory,
    rather than being pooled into a dataset it is not comparable with."""
    assert suite.partition_of("drift-lang") != 0
    assert suite.partition_of("clean-1") == 0
    assert suite.report.partitions[suite.partition_of("drift-lang")].breaking[
        "language"
    ] == "tr"


# ── The rendered report actually files them (§7.3) ───────────────────────────


def _section(rendered: str, heading: str) -> str:
    """One severity section of the rendered report, from its heading to the
    next one — so a line asserted "under Held" is really under Held, not merely
    somewhere in the document."""
    assert heading in rendered, f"the rendered report has no {heading!r} section"
    return rendered.split(heading, 1)[1].split("\n## ", 1)[0]


@over_hazards
def test_the_rendered_report_files_each_line_under_its_heading(
    suite: Suite, rendered: str, hazard: Hazard
):
    """The spot-check [I15] asks for, on the artifact a researcher actually
    reads: the structured findings above are only "never silent" if the
    rendered report shows them, under the right heading, with the loud tier
    marked. Asserted as the whole bullet — a lost ``⚠`` fails as surely as a
    lost line — but built from ``finding.message`` rather than from a literal,
    so the wording stays the Hub's to change."""
    finding = suite.find(hazard)
    bullet = (
        f"- {LOUD_MARKER if hazard.loud else ''}"
        f"**`{finding.code}`** {finding.message}"
    )

    assert bullet in _section(rendered, HEADINGS[hazard.group])
