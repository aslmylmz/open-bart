"""Hub output writer: mirrored study surfaces + reconstruction provenance (I10).

The last stage of the Hub pipeline (DATA-SPEC §6.4): ``write_rebuild`` takes
the ingestion report (I8) and the rebuilt row streams (I9) and writes the
study-wide pooled surfaces — never per-session files — to a researcher-chosen
destination. Data filenames **mirror the live path exactly**
(``{slug}_results.csv``, ``{slug}_trials.csv``, ``{slug}_data_dictionary.md``)
so an analysis script written against live output runs verbatim against a
rebuild; what distinguishes a reconstruction is location + the provenance
stamp + the presence of ``{slug}_ingestion_report.md``, never a munged data
filename. The CSVs go through the same ``versioned_csv`` writer and the
dictionary through the same renderer the live path uses — byte-identity by
construction (§6.5), with the reconstructed ``{slug}_provenance.json`` the
one surface that *should* differ from live.

Destinations are guarded (§6.4a): sources are read-only, so writing into a
folder being ingested — or into a folder that *contains* one — is refused,
and a non-empty destination is refused unless it is itself a prior Hub
rebuild (it carries the ``reconstructed: true`` marker), in which case a
re-run cleanly replaces it. Config-drift partitions each get a
self-contained subdirectory; the single-partition common case stays flat
(§6.4d). The CLI/UI (I11/I12) are thin adapters over ``write_rebuild`` plus
``render_report`` (the printable report) and ``is_prior_rebuild`` (the
replace-confirmation predicate).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

import scoring
from sidecar.hub import IngestionReport, SessionRecord, _read_json, drift_fields
from sidecar.provenance import render_dictionary
from sidecar.rebuild import RebuildResult
from sidecar.textio import write_utf8
from sidecar.versioned_csv import append_rows


class DestinationRefused(Exception):
    """The destination violates §6.4a — inside a source, containing a source,
    or non-empty without the reconstruction marker. Nothing was written."""


class RebuildReceipt(BaseModel):
    """What ``write_rebuild`` actually put on disk — the surface the CLI
    prints and the UI's file tree confirms."""

    destination: str
    files: list[str] = Field(
        description="written files, relative to the destination, in write order"
    )
    replaced_prior_rebuild: bool = Field(
        description="whether a prior Hub rebuild was cleanly replaced in place"
    )


def _utc_now() -> datetime:
    """The clock the reconstruction provenance is stamped with (§9.5) — the
    same module-level seam ``write_output`` has, so the golden-fixture builder
    can pin it. Production always runs the real UTC clock."""
    return datetime.now(timezone.utc)


def is_prior_rebuild(destination: str | Path) -> bool:
    """Whether the folder carries the reconstruction marker — a study
    provenance record with ``reconstructed: true`` (§6.4e). The marker is
    what makes re-run-replaces-prior-rebuild safe: it is written first, so
    even an interrupted rebuild leaves a folder the next run may replace."""
    dest = Path(destination)
    if not dest.is_dir():
        return False
    return any(
        isinstance(record := _read_json(path), dict)
        and record.get("reconstructed") is True
        for path in dest.glob("*_provenance.json")
    )


def _prepare_destination(dest: Path, sources: list[str]) -> bool:
    """Enforce §6.4a and hand back an empty, existing directory. Returns
    whether a prior rebuild was replaced. Sources are compared resolved, so
    a relative path or symlink cannot smuggle a write into ground truth."""
    resolved = dest.resolve()
    for source in sources:
        root = Path(source).resolve()
        if resolved.is_relative_to(root):
            raise DestinationRefused(
                f"destination {dest} is inside source {source} — sources are "
                f"read-only; the Hub never writes into a folder it is ingesting"
            )
        if root.is_relative_to(resolved):
            raise DestinationRefused(
                f"destination {dest} contains source {source} — a later "
                f"re-run's clean replace would delete it; choose a destination "
                f"wholly separate from every source folder"
            )
    if dest.exists() and not dest.is_dir():
        raise DestinationRefused(f"destination {dest} is not a directory")
    replaced = False
    if dest.is_dir() and any(dest.iterdir()):
        if not is_prior_rebuild(dest):
            raise DestinationRefused(
                f"destination {dest} is not empty and is not a prior Hub "
                f"rebuild — refusing to overwrite; choose a fresh folder"
            )
        for child in dest.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        replaced = True
    dest.mkdir(parents=True, exist_ok=True)
    return replaced


def rebuilt_sessions_by_source(
    report: IngestionReport, result: RebuildResult
) -> dict[str, list[SessionRecord]]:
    """Each source root mapped to the rebuilt session records attributed to it:
    a session counts for a source when the pooled copy's ``events`` file lives
    under that root (collapsed duplicates count once). The single attribution
    rule behind both the provenance source-manifest below and the Sources-band
    counts (I12's ``_source_views``), so the two can never disagree about which
    folder contributed what. Sources are compared resolved; a session under a
    nested source root counts for each root it lies within, as the manifest has
    always done."""
    records = {
        record.session_id: record
        for partition in report.partitions
        for record in partition.sessions
    }
    rebuilt = [
        records[sid]
        for partition in result.partitions
        for sid in partition.session_ids
    ]
    return {
        source: [
            record
            for record in rebuilt
            if Path(record.events_path).resolve().is_relative_to(Path(source).resolve())
        ]
        for source in report.sources
    }


def _source_manifest(
    report: IngestionReport, result: RebuildResult
) -> list[dict[str, Any]]:
    """Per-source session counts for the provenance block and the report."""
    return [
        {"folder": source, "sessions": len(records)}
        for source, records in rebuilt_sessions_by_source(report, result).items()
    ]


def _provenance(report: IngestionReport, result: RebuildResult) -> dict[str, Any]:
    """The §6.4e reconstruction block — the §11 "tell" that this folder is a
    rebuild, and the one output that *should* differ from live (§6.5)."""
    return {
        "reconstructed": True,
        "hub_version": scoring.__version__,
        "engine_version": result.engine_version,
        "rebuild_mode": result.mode,
        "rebuild_mode_source": result.mode_source,
        "rebuild_timestamp_utc": _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_manifest": _source_manifest(report, result),
        "ingestion_report": f"{report.slug}_ingestion_report.md",
    }


def render_report(report: IngestionReport, result: RebuildResult) -> str:
    """The itemized ingestion report as markdown — the "never silent"
    artifact (§7.3): headline counts, per-source attribution, then every
    finding by severity group, with the loud data-integrity tier marked.
    Empty Held/Attention groups still appear, as an explicit "None." — the
    evidence the Hub looked. Rendered once here for the report file, the CLI
    printout, and the committed paper sample alike."""
    rebuilt = sum(len(partition.session_ids) for partition in result.partitions)
    mode_origin = (
        "the study's configured mode"
        if result.mode_source == "configured"
        else "explicit rebuild-time override"
    )
    lines = [
        f"# Ingestion Report — {report.title}",
        "",
        f"Reconstructed by the Data Hub (version {scoring.__version__}) on "
        f"{_utc_now().strftime('%Y-%m-%d %H:%M UTC')}. The Hub never acts "
        f"silently: every session was included cleanly, or its departure is "
        f"itemized below.",
        "",
        f"Rebuild mode: `{result.mode}` ({mode_origin}).",
        "",
        f"**{rebuilt} session(s) rebuilt · {len(report.held)} held · "
        f"{len(report.attention)} attention · "
        f"{len(report.partitions)} partition(s)**",
        "",
        "## Sources",
        "",
        "Sources are read-only; the Hub never writes into them.",
        "",
    ]
    lines += [
        f"- `{entry['folder']}` — {entry['sessions']} session(s) rebuilt"
        for entry in _source_manifest(report, result)
    ]
    groups = [
        (
            "## Held — excluded until resolved",
            "Holds affect only the listed sessions; the rebuild proceeded "
            "on the rest.",
            report.held,
        ),
        ("## Attention — pooled, but itemized", None, report.attention),
        ("## Clean / informational", None, report.info),
    ]
    for heading, note, findings in groups:
        lines += ["", heading, ""]
        if note is not None:
            lines += [note, ""]
        if not findings:
            lines.append("None.")
        lines += [
            f"- {'⚠ ' if finding.loud else ''}**`{finding.code}`** "
            f"{finding.message}"
            for finding in findings
        ]
    if len(report.partitions) > 1:
        lines += [
            "",
            "## Partitions",
            "",
            "Config drift split the sessions into separately comparable "
            "sets; each subdirectory is self-contained.",
            "",
        ]
        main = report.partitions[0]
        for index, (built, source) in enumerate(
            zip(result.partitions, report.partitions), start=1
        ):
            drift = ", ".join(drift_fields(source, main))
            note = "the main set" if index == 1 else f"differs in: {drift}"
            lines.append(
                f"- `partition-{index}/` — {len(built.session_ids)} "
                f"session(s) — {note}"
            )
    lines.append("")
    return "\n".join(lines)


def planned_files(report: IngestionReport, result: RebuildResult) -> list[str]:
    """The destination-relative files ``write_rebuild`` will produce, in write
    order — computed *without* writing, so the UI's Output band (I12) can
    preview the exact tree a rebuild lands (§7.4). It mirrors ``write_rebuild``
    file-for-file (provenance first, each partition's surfaces — flat for the
    single-partition common case, ``partition-N/`` subdirectories otherwise,
    a CSV only when that partition produced rows — then the shared ingestion
    report); ``test_planned_files_matches_write_rebuild`` pins the two together
    so the preview can never promise a file the writer does not deliver."""
    files = [f"{report.slug}_provenance.json"]
    multi = len(result.partitions) > 1
    for index, built in enumerate(result.partitions, start=1):
        prefix = f"partition-{index}/" if multi else ""
        if built.results_rows:
            files.append(f"{prefix}{report.slug}_results.csv")
        if built.trials_rows:
            files.append(f"{prefix}{report.slug}_trials.csv")
        files.append(f"{prefix}{report.slug}_data_dictionary.md")
    files.append(f"{report.slug}_ingestion_report.md")
    return files


def write_rebuild(
    report: IngestionReport, result: RebuildResult, destination: str | Path
) -> RebuildReceipt:
    """Write the reconstructed study-wide surfaces to ``destination`` (§6.4).

    Guards the destination (raising ``DestinationRefused``; a prior Hub
    rebuild is cleanly replaced), then writes: the reconstruction provenance
    (first, so an interrupted run already carries the replace-safe marker),
    each partition's mirrored data surfaces — flat for the single-partition
    common case, one self-contained ``partition-N/`` subdirectory each
    otherwise — and the shared top-level ingestion-report file. The data
    dictionary is rendered per partition from that partition's own config,
    projected to the mode the rows were actually rebuilt in.
    """
    dest = Path(destination)
    replaced = _prepare_destination(dest, report.sources)
    files: list[str] = []
    write_utf8(
        dest / f"{report.slug}_provenance.json",
        json.dumps(_provenance(report, result), indent=2),
    )
    files.append(f"{report.slug}_provenance.json")
    multi = len(result.partitions) > 1
    for index, (built, source) in enumerate(
        zip(result.partitions, report.partitions), start=1
    ):
        folder = dest / f"partition-{index}" if multi else dest
        folder.mkdir(exist_ok=True)
        prefix = f"{folder.name}/" if multi else ""
        for name, rows in (
            (f"{report.slug}_results.csv", built.results_rows),
            (f"{report.slug}_trials.csv", built.trials_rows),
        ):
            if rows:
                append_rows(folder / name, rows)
                files.append(prefix + name)
        config = source.sessions[0].config.model_copy(
            update={"metrics_mode": result.mode}
        )
        write_utf8(
            folder / f"{report.slug}_data_dictionary.md",
            render_dictionary(config, report.slug),
        )
        files.append(f"{prefix}{report.slug}_data_dictionary.md")
    write_utf8(
        dest / f"{report.slug}_ingestion_report.md", render_report(report, result)
    )
    files.append(f"{report.slug}_ingestion_report.md")
    return RebuildReceipt(
        destination=str(dest), files=files, replaced_prior_rebuild=replaced
    )
