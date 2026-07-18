"""Hub rebuild core: re-score, project, order, verify (I9).

The rebuild is a **pure re-derivation from ground truth that shares the live
path's own emission code** (DATA-SPEC §6). ``rebuild`` takes an ingestion
report (I8) and re-scores every pooled session from ``events.jsonl`` +
``config.json`` with the sidecar's single current engine — one path for
same-mode and cross-mode rebuilds alike — then emits row streams through the
same ``sidecar.emission`` row builders / ``trial_table`` / projection code
``write_output`` uses, so the clean single-station case is byte-identical to
live output *by construction* (§6.5). If the equivalence gate ever fails, the
fix is to converge on the shared code, never to grow a parallel builder here.

Stored ``metrics.json`` is demoted to the §6.6 verify/QC comparison: the Hub
grades each divergence on the session's engine stamp (same-version mismatch =
corruption, loud; cross-version = benign drift, informational; no stamp =
ungraded) and always writes the re-score. Verify findings — and the rare
session whose events cannot be re-scored — are appended to the report's own
findings list, keeping one itemized report for the writer/CLI/UI (I10–I12) to
render. Output *writing* (destination, filenames, partition subdirectories,
reconstruction provenance) is I10's; this module only produces the rows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from scoring import __version__
from scoring.bart import score_bart, trial_table
from scoring.projection import MetricsMode, project_metrics, project_trial
from scoring.schemas import BARTMetrics, GameEvent
from sidecar.emission import flatten_metrics, identity_row
from sidecar.hub import HubFinding, IngestionReport, SessionRecord, _read_json


class PartitionRebuild(BaseModel):
    """One partition's reconstructed row streams, aligned 1:1 (same index,
    same fingerprint) with ``IngestionReport.partitions``. Rows are plain
    mappings ready for ``versioned_csv.append_rows`` — the writer (I10)
    points them at the destination files."""

    fingerprint: str = Field(description="the source partition's fingerprint")
    session_ids: list[str] = Field(
        description=(
            "sessions that actually produced rows — admitted sessions minus "
            "any held at rebuild as unscorable"
        )
    )
    results_rows: list[dict[str, Any]] = Field(
        description="master-CSV rows, one per session, in §5.5 sort order"
    )
    trials_rows: list[dict[str, Any]] = Field(
        description="trials-CSV rows, one per balloon, grouped by session"
    )


class RebuildResult(BaseModel):
    """The rebuild's deliverable: every partition's row streams plus the
    facts the reconstruction provenance block records (§6.4e)."""

    mode: MetricsMode = Field(
        description="the one metrics mode every session was projected to"
    )
    mode_source: Literal["configured", "override"] = Field(
        description=(
            "how the mode was chosen: the study's own configured mode "
            "(default) or an explicit rebuild-time override (§6.3)"
        )
    )
    engine_version: str = Field(
        description=(
            "the single engine that re-scored every row — what the "
            "reconstruction provenance truthfully stamps (§6.1)"
        )
    )
    partitions: list[PartitionRebuild]


def _read_events(path: str) -> list[GameEvent]:
    """The persisted ground truth, parsed back to the exact event list the
    live path scored — one JSON event per line."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [
        GameEvent.model_validate(json.loads(line)) for line in lines if line.strip()
    ]


def _multi_station(report: IngestionReport) -> bool:
    """Whether the pooled sessions span more than one station *label*. Only
    then do the ``station_id``/``participant_key`` columns join the rows
    (§11). One label means the columns could not attribute anything: a
    single-station study must stay byte-identical to live (§6.5) even when a
    sneakernet copy lost its provenance record, and a duplicate-label pair is
    already itemized at ingest with its participant_key ambiguity named."""
    labels = {
        record.station_id or ""
        for partition in report.partitions
        for record in partition.sessions
    }
    return len(labels) > 1


def _identity(record: SessionRecord, multi_station: bool) -> dict[str, Any]:
    """This session's identity columns, from the same builder the live writer
    emits through (§6.5) — the station columns join only when the rebuild
    actually spans stations."""
    station = (
        {"station_id": record.station_id, "participant_key": record.participant_key}
        if multi_station
        else {}
    )
    return identity_row(
        timestamp_utc=record.timestamp_utc,
        session_id=record.session_id,
        candidate_id=record.candidate_id,
        condition=record.envelope.condition,
        conditions_declared=bool(record.config.conditions),
        **station,
    )


def _verify(
    record: SessionRecord, metrics: BARTMetrics, findings: list[HubFinding]
) -> None:
    """The §6.6 verify-grading matrix: compare the re-score to the stored
    ``metrics.json`` — in the session's own recorded mode, since that is what
    was projected to disk at write time — and grade any divergence on the
    envelope's engine stamp. Always non-blocking: the rebuild writes the
    re-score regardless; the stamp only upgrades ungraded → graded."""
    if record.metrics_path is None:
        return  # absent/unreadable was already noted at ingest (§5.6)
    stored = _read_json(Path(record.metrics_path))
    if stored is None:
        findings.append(
            HubFinding(
                code="missing_metrics",
                group="info",
                message=(
                    f"stored metrics unreadable; re-scored, no verify — "
                    f"{record.label}"
                ),
                session_ids=[record.session_id],
                paths=[record.metrics_path],
            )
        )
        return
    expected = project_metrics(
        metrics.model_dump(mode="json"), record.config.metrics_mode
    )
    stamp = record.envelope.engine
    if stored == expected:
        if stamp is not None and stamp.engine_version != __version__:
            findings.append(
                HubFinding(
                    code="verify_version_note",
                    group="info",
                    message=(
                        f"stored metrics reproduce across engine versions "
                        f"({stamp.engine_version} → {__version__}) — "
                        f"{record.label}"
                    ),
                    session_ids=[record.session_id],
                )
            )
        return
    if stamp is None:
        findings.append(
            HubFinding(
                code="verify_ungraded",
                group="attention",
                message=(
                    f"stored metrics differ from re-score with no engine "
                    f"stamp (pre-stamp data) — cannot grade drift vs "
                    f"corruption; re-scored values used — {record.label}"
                ),
                session_ids=[record.session_id],
                paths=[record.metrics_path],
            )
        )
    elif stamp.engine_version == __version__:
        findings.append(
            HubFinding(
                code="verify_corruption",
                group="attention",
                loud=True,
                message=(
                    f"stored metrics differ from re-score under the same "
                    f"engine {__version__} — identical engine on identical "
                    f"events must reproduce; possible corruption or "
                    f"tampering — {record.label}"
                ),
                session_ids=[record.session_id],
                paths=[record.metrics_path],
            )
        )
    else:
        findings.append(
            HubFinding(
                code="verify_engine_drift",
                group="info",
                message=(
                    f"stored metrics differ from re-score — benign engine "
                    f"drift ({stamp.engine_version} → {__version__}); "
                    f"re-scored values used — {record.label}"
                ),
                session_ids=[record.session_id],
            )
        )


def rebuild(
    report: IngestionReport, mode: MetricsMode | None = None
) -> RebuildResult:
    """Reconstruct every partition's row streams from ground truth (§6).

    ``mode=None`` (the default) projects to the study's own configured mode,
    so the reconstructed master matches the live one — exactly what the
    equivalence gate compares. An explicit ``mode`` is the §6.3 override:
    every session is re-projected to it, so a Classic-collected study yields
    the full Advanced set. Verify findings and unscorable-events holds are
    appended to ``report.findings`` (one itemized report; call once per
    report). Sessions the ingest already held or refused never appear here.
    """
    chosen: MetricsMode = mode if mode is not None else report.configured_mode
    multi_station = _multi_station(report)
    partitions: list[PartitionRebuild] = []
    for partition in report.partitions:
        results_rows: list[dict[str, Any]] = []
        trials_rows: list[dict[str, Any]] = []
        session_ids: list[str] = []
        for record in partition.sessions:
            try:
                events = _read_events(record.events_path)
                metrics = score_bart(events, record.config)
                trials = trial_table(events, record.config)
            except (OSError, ValueError):
                # Hashable at ingest but not parseable/scoreable now: the
                # same loss as missing ground truth — held per session.
                report.findings.append(
                    HubFinding(
                        code="unscorable_events",
                        group="held",
                        message=(
                            f"held: events cannot be re-scored — "
                            f"{record.label}"
                        ),
                        session_ids=[record.session_id],
                        paths=[record.events_path],
                    )
                )
                continue
            _verify(record, metrics, report.findings)
            identity = _identity(record, multi_station)
            results_rows.append(
                {**identity, **project_metrics(flatten_metrics(metrics), chosen)}
            )
            trials_rows.extend(
                {**identity, **project_trial(trial.model_dump(mode="json"), chosen)}
                for trial in trials
            )
            session_ids.append(record.session_id)
        partitions.append(
            PartitionRebuild(
                fingerprint=partition.fingerprint,
                session_ids=session_ids,
                results_rows=results_rows,
                trials_rows=trials_rows,
            )
        )
    return RebuildResult(
        mode=chosen,
        mode_source="configured" if mode is None else "override",
        engine_version=__version__,
        partitions=partitions,
    )
