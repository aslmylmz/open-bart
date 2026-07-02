"""The FastAPI app for the offline scoring sidecar.

This module only defines the app and its routes. The launcher in ``__main__``
binds it to ``127.0.0.1`` on an ephemeral port and hands that port to the Tauri
shell (SPEC §9/§10). For Phase 1 the only route is the ``/healthz`` liveness
probe; the scoring/preview/output endpoints land in issue 08.
"""

from __future__ import annotations

import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from scoring import __version__
from scoring.bart import score_bart
from scoring.config import DEFAULT_TASK_CONFIG, TaskConfig
from scoring.schemas import AssessmentResponse, BARTMetrics
from sidecar.models import (
    CurvePreview,
    PreviewResponse,
    ScoreRequest,
    ValidateConfigResponse,
    WriteOutputRequest,
    WriteOutputResponse,
)


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
    for color in row.pop("color_metrics", []):
        name = color.pop("color")
        for field, value in color.items():
            row[f"{name}_{field}"] = value
    return row


def _append_master_csv(out_dir: Path, config: TaskConfig, row: dict[str, Any]) -> Path:
    """Append one session row to the study's master CSV (CONTEXT.md), creating
    the file with a header row when absent. Appends follow the existing header,
    so the sheet stays rectangular even if columns evolve across versions."""
    path = out_dir / f"{_slug(config.title)}_results.csv"
    if path.exists():
        with path.open("r", newline="", encoding="utf-8") as fh:
            fieldnames = next(csv.reader(fh), None) or list(row)
    else:
        fieldnames = list(row)
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, restval="", extrasaction="ignore")
        if fh.tell() == 0:
            writer.writeheader()
        writer.writerow(row)
    return path

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


@app.post("/write-output", response_model=WriteOutputResponse)
def write_output(req: WriteOutputRequest) -> WriteOutputResponse:
    """Persist one session under the config's output_dir (SPEC §13).

    Writes three files namespaced by study title + candidate + timestamp: the raw
    event log (JSONL), the scored metrics (JSON), and a snapshot of the full
    ``TaskConfig`` so each dataset is self-documenting and reproducible. Also
    appends one flat row to the study's master CSV (issue 28).
    """
    config = req.config or DEFAULT_TASK_CONFIG
    out_dir = Path(config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stem = f"{_slug(config.title)}_{_slug(req.session.candidate_id)}_{ts}"

    events_path = out_dir / f"{stem}_events.jsonl"
    metrics_path = out_dir / f"{stem}_metrics.json"
    config_path = out_dir / f"{stem}_config.json"

    with events_path.open("w", encoding="utf-8") as fh:
        for event in req.session.events:
            fh.write(event.model_dump_json() + "\n")

    metrics = score_bart(req.session.events, config)
    metrics_path.write_text(metrics.model_dump_json(indent=2), encoding="utf-8")
    config_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")

    master_csv = _append_master_csv(
        out_dir,
        config,
        {
            "timestamp_utc": ts,
            "session_id": req.session.session_id,
            "candidate_id": req.session.candidate_id,
            **_flatten_metrics(metrics),
        },
    )

    return WriteOutputResponse(
        events=str(events_path),
        metrics=str(metrics_path),
        config=str(config_path),
        master_csv=str(master_csv),
    )
