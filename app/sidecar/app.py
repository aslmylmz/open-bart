"""The FastAPI app for the offline scoring sidecar.

This module only defines the app and its routes. The launcher in ``__main__``
binds it to ``127.0.0.1`` on an ephemeral port and hands that port to the Tauri
shell (SPEC §9/§10). For Phase 1 the only route is the ``/healthz`` liveness
probe; the scoring/preview/output endpoints land in issue 08.
"""

from __future__ import annotations

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
from scoring.schemas import AssessmentResponse, BARTMetrics
from sidecar.models import (
    CheckIdRequest,
    CheckIdResponse,
    CurvePreview,
    PreviewResponse,
    ScoreRequest,
    ValidateConfigResponse,
    WriteOutputRequest,
    WriteOutputResponse,
)
from sidecar.provenance import ensure_provenance
from sidecar.versioned_csv import append_row, append_rows


def _slug(text: str) -> str:
    """Filesystem-safe namespace fragment for output filenames (SPEC §13)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "study"


def _flatten_metrics(metrics: BARTMetrics) -> dict[str, Any]:
    """One flat, scalar-only mapping of a session's metrics for the master CSV.

    Per-color metrics become ``{color}_{field}`` columns so they load as plain
    variables in SPSS/R; the nested narrative ``behavioral_profile`` stays
    JSON-only (not meaningful as spreadsheet cells).
    """
    row = metrics.model_dump(mode="json")
    row.pop("behavioral_profile", None)
    # Payout columns exist only for studies that declare a payout block —
    # the same present-only-when-configured rule as `condition` (issues 37/41).
    if row.get("payout_amount") is None:
        row.pop("payout_amount", None)
        row.pop("payout_currency", None)
    for color in row.pop("color_metrics", []):
        name = color.pop("color")
        for field, value in color.items():
            row[f"{name}_{field}"] = value
    return row


def _count_sessions(out_dir: Path, config: TaskConfig, candidate_id: str) -> int:
    """How many sessions this study has already recorded for ``candidate_id``.

    Counts the raw event logs — one per session since v1.0.0 — by exact stem
    ``[title]_[candidate]_[timestamp]_events.jsonl``. The timestamp is matched
    strictly (digits + T + Z, no underscores) so an ID that merely shares a
    prefix with another (``P001`` vs ``P001_2``) is never cross-counted.
    """
    if not out_dir.is_dir():
        return 0
    stem = re.compile(
        rf"^{re.escape(_slug(config.title))}_{re.escape(candidate_id)}"
        rf"_\d{{8}}T\d+Z_events\.jsonl$"
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


@app.post("/check-id", response_model=CheckIdResponse)
def check_id(req: CheckIdRequest) -> CheckIdResponse:
    """Vet a participant ID before the session starts (issue 38).

    The sidecar owns all file I/O (CONTEXT.md), so the duplicate check lives
    here: the study's output directory is scanned for session files already
    recorded under this ID, and the count feeds the ID screen's warn-confirm.
    """
    config = req.config or DEFAULT_TASK_CONFIG
    candidate_id = req.candidate_id
    if not candidate_id.strip():
        return CheckIdResponse(
            ok=False, sessions=0, error="Participant ID must not be empty."
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
        )
    return CheckIdResponse(
        ok=True,
        sessions=_count_sessions(Path(config.output_dir), config, candidate_id),
        error=None,
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
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stem = f"{_slug(config.title)}_{_slug(req.session.candidate_id)}_{ts}"

    events_path = out_dir / f"{stem}_events.jsonl"
    metrics_path = out_dir / f"{stem}_metrics.json"
    config_path = out_dir / f"{stem}_config.json"
    session_path = out_dir / f"{stem}_session.json"

    with events_path.open("w", encoding="utf-8") as fh:
        for event in req.session.events:
            fh.write(event.model_dump_json() + "\n")

    metrics = score_bart(req.session.events, config)
    metrics_path.write_text(metrics.model_dump_json(indent=2), encoding="utf-8")
    config_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")

    # The session envelope: identity + design assignment in a per-session file,
    # so the master CSV stays rebuildable from the individual files (ADR 0001)
    # and the condition survives outside the spreadsheet (issue 37). The raw
    # telemetry stays in the .jsonl.
    session_path.write_text(
        req.session.model_dump_json(exclude={"events"}, indent=2), encoding="utf-8"
    )

    # The study-wide files — provenance (issue 42), master CSV, trials CSV —
    # are written together here: one decision point, so a future practice mode
    # (issue 43) can skip them all in one place. The condition column exists
    # only for studies that declare conditions, so condition-less studies keep
    # their v1.0.0 sheets untouched (issue 37).
    provenance_warnings = ensure_provenance(out_dir, config, _slug(config.title))
    identity = {
        "timestamp_utc": ts,
        "session_id": req.session.session_id,
        "candidate_id": req.session.candidate_id,
        **({"condition": req.session.condition or ""} if config.conditions else {}),
    }
    master_csv = append_row(
        out_dir / f"{_slug(config.title)}_results.csv",
        {**identity, **_flatten_metrics(metrics)},
    )
    trials_csv = append_rows(
        out_dir / f"{_slug(config.title)}_trials.csv",
        [
            {**identity, **trial.model_dump(mode="json")}
            for trial in trial_table(req.session.events, config)
        ],
    )

    return WriteOutputResponse(
        events=str(events_path),
        metrics=str(metrics_path),
        config=str(config_path),
        session=str(session_path),
        master_csv=str(master_csv.path),
        trials_csv=str(trials_csv.path),
        warnings=provenance_warnings
        + [r.warning for r in (master_csv, trials_csv) if r.warning],
    )
