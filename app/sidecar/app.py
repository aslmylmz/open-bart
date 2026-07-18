"""The FastAPI app for the offline scoring sidecar.

This module only defines the app and its routes. The launcher in ``__main__``
binds it to ``127.0.0.1`` on an ephemeral port and hands that port to the Tauri
shell (SPEC §9/§10). For Phase 1 the only route is the ``/healthz`` liveness
probe; the scoring/preview/output endpoints land in issue 08.
"""

from __future__ import annotations

import json
import platform
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from scoring import __version__
from scoring.bart import score_bart, trial_table
from scoring.config import DEFAULT_TASK_CONFIG, TaskConfig
from scoring.projection import project_metrics, project_trial
from scoring.schemas import (
    AssessmentResponse,
    EngineStamp,
    SessionEnvelope,
)
from sidecar.models import (
    CheckIdRequest,
    CheckIdResponse,
    CurvePreview,
    PreviewResponse,
    ScoreRequest,
    SetStationRequest,
    StationResponse,
    ValidateConfigResponse,
    WriteOutputRequest,
    WriteOutputResponse,
)
from sidecar.emission import flatten_metrics, identity_row
from sidecar.naming import TIMESTAMP, slug as _slug
from sidecar.provenance import ensure_provenance
from sidecar.station import load_station, store_station_id
from sidecar.versioned_csv import append_row, append_rows

# The station label lands in every output filename, so it obeys the same slug
# discipline check_id enforces on participant IDs, plus a length cap that keeps
# the four-part filename stem well inside filesystem name limits.
_STATION_ID_MAX = 32


def _utc_now() -> datetime:
    """The clock ``write_output`` stamps sessions with (DATA-SPEC §9.5).

    A module-level seam, not a clock abstraction: the golden-fixture builder
    replaces it with fixed synthetic timestamps so the committed samples are
    byte-reproducible through the real emission path. Production always runs
    the real UTC clock.
    """
    return datetime.now(timezone.utc)


def _count_sessions(
    out_dir: Path, config: TaskConfig, candidate_id: str, station_id: str | None
) -> int:
    """How many sessions this station has already recorded for ``candidate_id``.

    Counts the raw event logs — one per session since v1.0.0 — by exact stem
    ``[title](_[station])_[candidate]_[timestamp]_events.jsonl``: with a
    station ID set the stem carries its segment (DATA-SPEC §2.3), so the count
    stays station-scoped — a sneakernet-merged sibling folder's files never
    inflate it. The timestamp is matched strictly (digits + T + Z, no
    underscores) so an ID that merely shares a prefix with another (``P001``
    vs ``P001_2``) is never cross-counted.
    """
    if not out_dir.is_dir():
        return 0
    station_segment = f"_{re.escape(_slug(station_id))}" if station_id else ""
    stem = re.compile(
        rf"^{re.escape(_slug(config.title))}{station_segment}"
        rf"_{re.escape(candidate_id)}_{TIMESTAMP}_events\.jsonl$"
    )
    return sum(1 for p in out_dir.iterdir() if stem.match(p.name))


app = FastAPI(title="BART scoring sidecar", version=__version__)

# The sidecar is strictly loopback (bound to 127.0.0.1, not network-accessible),
# so permissive CORS is safe.  This lets the Vite dev server, Tauri's Windows
# WebView2, and any plain browser reach the sidecar without "Failed to fetch"
# errors from cross-origin preflight rejections (issue 22).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe the shell polls before routing sessions to the sidecar."""
    return {"status": "ok", "version": __version__}


@app.post("/validate-config", response_model=ValidateConfigResponse)
def validate_config(config: dict[str, Any] = Body(...)) -> ValidateConfigResponse:
    """Validate a candidate study config, returning structured errors (SPEC §9).

    Takes a raw object (not a typed ``TaskConfig``) so invalid input yields a 200
    with the messages the UI shows, rather than FastAPI's 422.
    """
    try:
        TaskConfig.model_validate(config)
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        return ValidateConfigResponse(ok=False, errors=errors)
    return ValidateConfigResponse(ok=True, errors=[])


@app.post("/preview", response_model=PreviewResponse)
def preview(config: TaskConfig) -> PreviewResponse:
    """Return each color's hazard/survival/EV vectors + numeric optimum.

    Reads straight from ``TaskConfig.curves``, precomputed on construction, so the
    preview the researcher sees is the exact landscape the task and scorer use.
    """
    return PreviewResponse(
        curves={name: CurvePreview.from_curve(c) for name, c in config.curves.items()}
    )


@app.post("/score", response_model=AssessmentResponse)
def score(req: ScoreRequest) -> AssessmentResponse:
    """Score a session against its study config and return the client's shape.

    ``score_bart`` returns a flat ``BARTMetrics``; the client expects an
    ``AssessmentResponse``. Offline there are no population norms, so
    ``normalized_scores`` is empty and ``profile_traits`` is left to the metrics'
    own ``behavioral_profile``. ``config`` is optional → ``DEFAULT_TASK_CONFIG``,
    so the engine's per-color optima and reward follow the study that was run.
    """
    config = req.config or DEFAULT_TASK_CONFIG
    metrics = score_bart(req.session.events, config)
    return AssessmentResponse(
        session_id=req.session.session_id,
        game_type=req.session.game_type,
        candidate_id=req.session.candidate_id,
        raw_metrics=metrics,
        normalized_scores=[],
        profile_traits={},
    )


@app.get("/station", response_model=StationResponse)
def get_station() -> StationResponse:
    """This machine's station identity (DATA-SPEC §2.3): the per-machine app
    setting the study-setup surface re-displays each session, plus the
    per-install UUID minted on first run."""
    identity = load_station()
    return StationResponse(
        station_id=identity.station_id, machine_uuid=identity.machine_uuid
    )


def _station_id_problem(station_id: str) -> str | None:
    """Why this station label cannot be used, or ``None`` when it can. The
    label lands in filenames, so it obeys the same slug discipline ``check_id``
    enforces on participant IDs (DATA-SPEC §2.3)."""
    if _slug(station_id) != station_id:
        return (
            f"Station ID '{station_id}' cannot be used in file names. Use "
            f"only letters, numbers, dots, underscores, and dashes."
        )
    if len(station_id) > _STATION_ID_MAX:
        return f"Station ID must be at most {_STATION_ID_MAX} characters."
    return None


@app.post("/station", response_model=StationResponse)
def set_station(req: SetStationRequest) -> StationResponse:
    """Persist a new station label for this machine — entered once at machine
    setup, never retyped per participant. A whitespace-only label clears the
    setting; an unusable label is rejected without touching the stored one."""
    station_id = req.station_id.strip() or None
    error = _station_id_problem(station_id) if station_id is not None else None
    if error is None:
        try:
            identity = store_station_id(station_id)
            return StationResponse(
                station_id=identity.station_id, machine_uuid=identity.machine_uuid
            )
        except OSError as exc:
            reason = getattr(exc, "strerror", None) or str(exc) or type(exc).__name__
            error = f"Could not save the station ID ({reason})."
    identity = load_station()
    return StationResponse(
        ok=False,
        station_id=identity.station_id,
        machine_uuid=identity.machine_uuid,
        error=error,
    )


@app.post("/check-id", response_model=CheckIdResponse)
def check_id(req: CheckIdRequest) -> CheckIdResponse:
    """Vet a participant ID before the session starts (issue 38).

    The sidecar owns all file I/O (CONTEXT.md), so the duplicate check lives
    here: the study's output directory is scanned for session files already
    recorded under this ID, and the count feeds the ID screen's warn-confirm.
    """
    config = req.config or DEFAULT_TASK_CONFIG
    station = load_station()
    # Every verdict states the deployment mode affirmatively (DATA-SPEC §2.6):
    # the ID screen words the duplicate warning from these flags — the count
    # below is station-scoped and local-only; cross-station duplicates are the
    # Hub's to flag at assembly.
    mode = {"standalone": config.standalone, "station_id": station.station_id}
    # The blank-station poka-yoke (DATA-SPEC §2.3): a standalone session with
    # no station ID would be unattributable at the Hub, so it never starts.
    # Machine setup, not the participant ID, is what needs fixing here.
    if config.standalone and not station.station_id:
        return CheckIdResponse(
            ok=False,
            sessions=0,
            error=(
                "This study runs in Standalone Mode, but this machine has no "
                "station ID set. Set the station ID on the study-setup screen "
                "before running sessions."
            ),
            **mode,
        )
    candidate_id = req.candidate_id
    if not candidate_id.strip():
        return CheckIdResponse(
            ok=False, sessions=0, error="Participant ID must not be empty.", **mode
        )
    # The filename slug rules are the single source of truth: an ID the output
    # files would silently rewrite (004/E → 004-E) is rejected up front, so the
    # ID in the data always matches the ID in the filenames.
    if _slug(candidate_id) != candidate_id:
        return CheckIdResponse(
            ok=False,
            sessions=0,
            error=(
                f"Participant ID '{candidate_id}' cannot be used in file names. "
                f"Use only letters, numbers, dots, underscores, and dashes."
            ),
            **mode,
        )
    return CheckIdResponse(
        ok=True,
        sessions=_count_sessions(
            Path(config.output_dir), config, candidate_id, station.station_id
        ),
        error=None,
        **mode,
    )


@app.post("/write-output", response_model=WriteOutputResponse)
def write_output(req: WriteOutputRequest) -> WriteOutputResponse:
    """Persist one session under the config's output_dir (SPEC §13).

    Writes three files namespaced by study title + candidate + timestamp: the raw
    event log (JSONL), the scored metrics (JSON), and a snapshot of the full
    ``TaskConfig`` so each dataset is self-documenting and reproducible. Also
    appends one flat row to the study's master CSV (issue 28) through the
    header-versioned writer (issue 36), which migrates or falls back to a
    sibling file — surfaced in ``warnings`` — rather than misalign columns.
    """
    config = req.config or DEFAULT_TASK_CONFIG
    out_dir = Path(config.output_dir)
    # Practice sessions (issue 43) run the identical pipeline into a practice/
    # subfolder: inspectable but never mingled with official data.
    if req.session.practice:
        out_dir = out_dir / "practice"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = _utc_now().strftime("%Y%m%dT%H%M%S%fZ")
    # With a station ID set, the stem gains a station segment (DATA-SPEC §2.3)
    # so sneakernet-merged station folders can never collide on filename,
    # independent of clock skew. Unset — single-station mode — the stem stays
    # byte-identical to v1.0.0.
    station = load_station()
    station_segment = f"_{_slug(station.station_id)}" if station.station_id else ""
    stem = (
        f"{_slug(config.title)}{station_segment}"
        f"_{_slug(req.session.candidate_id)}_{ts}"
    )

    events_path = out_dir / f"{stem}_events.jsonl"
    metrics_path = out_dir / f"{stem}_metrics.json"
    config_path = out_dir / f"{stem}_config.json"
    session_path = out_dir / f"{stem}_session.json"

    with events_path.open("w", encoding="utf-8") as fh:
        for event in req.session.events:
            fh.write(event.model_dump_json() + "\n")

    # The engine always computes the full BARTMetrics; the study's metrics
    # mode is a projection applied here, at the single emission point, so it
    # reaches metrics.json and both CSVs uniformly and never forks the engine
    # (DATA-SPEC §4.1). The raw event log above stays the complete session
    # either way.
    metrics = score_bart(req.session.events, config)
    metrics_path.write_text(
        json.dumps(
            project_metrics(metrics.model_dump(mode="json"), config.metrics_mode),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    config_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")

    # The session envelope (DATA-SPEC §3): identity + design assignment +
    # per-session provenance in a per-session file, so the master CSV stays
    # rebuildable from the individual files (ADR 0001) and the condition
    # survives outside the spreadsheet (issue 37). The raw telemetry stays in
    # the .jsonl. The engine stamp is server-authored — the sidecar records
    # what actually ran, so nothing a client sends can forge it.
    envelope = SessionEnvelope(
        session_id=req.session.session_id,
        game_type=req.session.game_type,
        candidate_id=req.session.candidate_id,
        condition=req.session.condition,
        duplicate_acknowledged=req.session.duplicate_acknowledged,
        practice=req.session.practice,
        station_id=station.station_id,
        engine=EngineStamp(
            app_version=__version__,
            engine_version=__version__,
            platform=platform.platform(),
        ),
    )
    session_path.write_text(envelope.model_dump_json(indent=2), encoding="utf-8")

    # The study-wide files — provenance (issue 42), master CSV, trials CSV —
    # are written together here: one decision point, and practice sessions
    # (issue 43) skip all of it — a test run must leave the official study
    # files untouched. The condition column exists only for studies that
    # declare conditions, so condition-less studies keep their v1.0.0 sheets
    # untouched (issue 37). The response always states the deployment mode
    # affirmatively (DATA-SPEC §2.4): the return surface derives Standalone
    # Mode + station from this payload, never from a missing file.
    receipt = {
        "events": str(events_path),
        "metrics": str(metrics_path),
        "config": str(config_path),
        "session": str(session_path),
        "standalone": config.standalone,
        "station_id": station.station_id,
    }
    if req.session.practice:
        return WriteOutputResponse(**receipt)
    provenance_warnings = ensure_provenance(
        out_dir, config, _slug(config.title), station
    )
    # Standalone Mode disables exactly one thing (DATA-SPEC §2.2): the two
    # study-wide CSV appends that fragment across machines. The per-session
    # files above and the provenance files just written stay per-station; the
    # Hub reassembles the master/trials CSVs from them at collection time.
    if config.standalone:
        return WriteOutputResponse(**receipt, warnings=provenance_warnings)
    identity = identity_row(
        timestamp_utc=ts,
        session_id=req.session.session_id,
        candidate_id=req.session.candidate_id,
        condition=req.session.condition,
        conditions_declared=bool(config.conditions),
    )
    master_csv = append_row(
        out_dir / f"{_slug(config.title)}_results.csv",
        {**identity, **project_metrics(flatten_metrics(metrics), config.metrics_mode)},
    )
    trials_csv = append_rows(
        out_dir / f"{_slug(config.title)}_trials.csv",
        [
            {**identity, **project_trial(trial.model_dump(mode="json"), config.metrics_mode)}
            for trial in trial_table(req.session.events, config)
        ],
    )

    return WriteOutputResponse(
        **receipt,
        master_csv=str(master_csv.path),
        trials_csv=str(trials_csv.path),
        warnings=provenance_warnings
        + [r.warning for r in (master_csv, trials_csv) if r.warning],
    )
