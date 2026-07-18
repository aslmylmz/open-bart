"""Data Hub view model: one JSON projection of the Hub core for the UI (I12).

The researcher-facing Data Hub tab (DATA-SPEC §7.1–7.4) drives the *same*
ingest → rebuild → write core as the CLI (I11) — no Hub decisions live in the
webview. This module is the thin adapter between them:

- ``build_hub_view`` runs ``ingest`` then ``rebuild`` (write nothing) and
  flattens their two dataclasses into the single ``HubView`` the tab renders —
  the headline counts (§7.3), per-source station/session attribution (§7.2),
  every finding by severity group, and the exact file tree ``write_rebuild``
  (I10) would land (§7.4). ``NoStudyError`` — the one dataset-level abort —
  comes back as ``ok=False`` with its message, never a 500.
- ``plan_rebuild`` performs the guarded write the single accent "Rebuild"
  control triggers, mapping the core's outcomes (``NoStudyError``,
  ``DestinationRefused``, a prior-rebuild that needs confirmation) to the
  ``status`` the tab shows.

Every number the tab displays is computed here, over the real core, so the tab
and the CLI can never disagree about what a rebuild does — the whole point of
Variant B being a surface, not a second implementation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from scoring.projection import MetricsMode
from sidecar.hub import Group, IngestionReport, NoStudyError, ingest
from sidecar.hub_writer import (
    DestinationRefused,
    RebuildResult,
    is_prior_rebuild,
    planned_files,
    rebuilt_sessions_by_source,
    write_rebuild,
)
from sidecar.rebuild import rebuild


class HubIngestRequest(BaseModel):
    """The Sources band's request: the read-only folders to ingest and the
    optional metrics-mode override (§7.4). ``mode=None`` rebuilds in the
    study's configured mode — the default the override toggle starts on."""

    sources: list[str]
    mode: MetricsMode | None = None


class HubRebuildRequest(BaseModel):
    """The Rebuild control's request: the same sources + mode, plus the chosen
    destination and whether the researcher has confirmed replacing a prior
    rebuild (``force`` — the UI's stand-in for the CLI's ``--force``)."""

    sources: list[str]
    out: str
    mode: MetricsMode | None = None
    force: bool = False


class HubSourceView(BaseModel):
    """One Sources-band row (§7.2): a source folder and how much of the pooled
    dataset was attributed to it — distinct stations and rebuilt sessions."""

    folder: str
    stations: int
    sessions: int


class HubFindingView(BaseModel):
    """One report line for the Ingestion-report band (§7.3), flattened from a
    ``HubFinding``: the UI groups by ``group`` and marks ``loud`` lines. The
    session UUIDs collapse to a count — the band shows how many sessions a line
    is about, not the raw IDs."""

    code: str
    group: Group
    message: str
    loud: bool
    sessions: int = Field(description="how many sessions this line is about")


class HubPlannedFile(BaseModel):
    """One row of the Output band's "will write" file-tree preview (§7.4): a
    destination-relative path and whether it is the reconstruction-marker
    provenance record (the one file the prototype flags ``reconstructed:true``)."""

    path: str
    reconstructed: bool = False


class HubView(BaseModel):
    """The whole Data Hub tab state derived from one ingest + rebuild (§7).

    ``ok=False`` carries the ``NoStudyError`` message and leaves the rest at
    empty defaults — the one dataset-level abort the band surfaces without ever
    gating on it. Everything else is a clean projection of the core."""

    ok: bool = True
    error: str | None = None
    title: str = ""
    slug: str = ""
    sources: list[HubSourceView] = Field(default_factory=list)
    configured_mode: MetricsMode = "advanced"
    mode: MetricsMode = "advanced"
    mode_source: Literal["configured", "override"] = "configured"
    will_rebuild: int = 0
    held: int = 0
    attention: int = 0
    partitions: int = 0
    findings: list[HubFindingView] = Field(default_factory=list)
    files: list[HubPlannedFile] = Field(default_factory=list)


class HubRebuildResponse(BaseModel):
    """The Rebuild control's outcome (§7.4). ``status`` drives the UI:

    - ``written`` — the reconstructed surfaces landed (``files`` under
      ``destination``); ``replaced_prior_rebuild`` says a prior one was
      overwritten in place.
    - ``needs_force`` — the destination is a prior Hub rebuild; the UI arms a
      confirm-replace and re-requests with ``force=true``.
    - ``refused`` — the destination violates the §6.4a guards (inside a source,
      containing one, or a non-empty non-rebuild folder); nothing was written.
    - ``no_study`` — no study identifiable in any source; nothing to rebuild.
    """

    ok: bool
    status: Literal["written", "needs_force", "refused", "no_study"]
    message: str | None = None
    destination: str | None = None
    files: list[str] = Field(default_factory=list)
    replaced_prior_rebuild: bool = False
    held: int = 0
    rebuilt: int = 0


def _source_views(
    report: IngestionReport, result: RebuildResult
) -> list[HubSourceView]:
    """Per-source attribution for the Sources band (§7.2): the rebuilt sessions
    and distinct station labels under each source root, over the one shared
    attribution rule the provenance manifest uses (I10) — so the tab's counts
    can never disagree with the reconstruction record."""
    return [
        HubSourceView(
            folder=source,
            stations=len({record.station_id or "" for record in records}),
            sessions=len(records),
        )
        for source, records in rebuilt_sessions_by_source(report, result).items()
    ]


def _finding_views(report: IngestionReport) -> list[HubFindingView]:
    return [
        HubFindingView(
            code=finding.code,
            group=finding.group,
            message=finding.message,
            loud=finding.loud,
            sessions=len(finding.session_ids),
        )
        for finding in report.findings
    ]


def _file_views(report: IngestionReport, result: RebuildResult) -> list[HubPlannedFile]:
    provenance = f"{report.slug}_provenance.json"
    return [
        HubPlannedFile(path=name, reconstructed=name == provenance)
        for name in planned_files(report, result)
    ]


def build_hub_view(
    sources: list[str], mode: MetricsMode | None = None
) -> HubView:
    """Ingest ``sources`` and rebuild in ``mode`` (write nothing), returning
    the flattened tab state (§7.1–7.4). ``NoStudyError`` becomes ``ok=False``
    with its message; every lesser defect is already a finding in the report."""
    try:
        report = ingest(sources)
    except NoStudyError as exc:
        return HubView(ok=False, error=str(exc))
    # rebuild appends verify/unscorable findings to report.findings, so the
    # view is read only after it runs — the same order the CLI/writer use.
    result = rebuild(report, mode)
    return HubView(
        ok=True,
        title=report.title,
        slug=report.slug,
        sources=_source_views(report, result),
        configured_mode=report.configured_mode,
        mode=result.mode,
        mode_source=result.mode_source,
        will_rebuild=sum(len(p.session_ids) for p in result.partitions),
        held=len(report.held),
        attention=len(report.attention),
        partitions=len(report.partitions),
        findings=_finding_views(report),
        files=_file_views(report, result),
    )


def perform_rebuild(
    sources: list[str],
    out: str,
    mode: MetricsMode | None = None,
    force: bool = False,
) -> HubRebuildResponse:
    """Perform the guarded write the Rebuild control triggers (§7.4), mapping
    the core's outcomes to a ``status`` the UI acts on. The prior-rebuild
    confirmation is checked first (before any ingest) so an accidental
    overwrite is caught even when the sources changed since the preview."""
    if not force and is_prior_rebuild(out):
        return HubRebuildResponse(
            ok=False,
            status="needs_force",
            message=(
                f"{out} already holds a Hub rebuild — rebuilding will replace "
                f"those files in place."
            ),
            destination=out,
        )
    try:
        report = ingest(sources)
    except NoStudyError as exc:
        return HubRebuildResponse(ok=False, status="no_study", message=str(exc))
    result = rebuild(report, mode)
    try:
        receipt = write_rebuild(report, result, out)
    except DestinationRefused as exc:
        return HubRebuildResponse(
            ok=False, status="refused", message=str(exc), destination=out
        )
    return HubRebuildResponse(
        ok=True,
        status="written",
        destination=receipt.destination,
        files=receipt.files,
        replaced_prior_rebuild=receipt.replaced_prior_rebuild,
        held=len(report.held),
        rebuilt=sum(len(p.session_ids) for p in result.partitions),
    )
