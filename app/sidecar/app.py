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
from pydantic import ValidationError

from scoring import __version__
from scoring.bart import score_bart
from scoring.config import DEFAULT_TASK_CONFIG, TaskConfig
from scoring.schemas import AssessmentResponse, GameSession
from sidecar.models import (
    CurvePreview,
    PreviewResponse,
    ValidateConfigResponse,
    WriteOutputRequest,
    WriteOutputResponse,
)


def _slug(text: str) -> str:
    """Filesystem-safe namespace fragment for output filenames (SPEC §13)."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "study"

app = FastAPI(title="BART scoring sidecar", version=__version__)


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
def score(session: GameSession) -> AssessmentResponse:
    """Score a session and return it in the shape the client consumes.

    ``score_bart`` returns a flat ``BARTMetrics``; the client expects an
    ``AssessmentResponse``. Offline there are no population norms, so
    ``normalized_scores`` is empty and ``profile_traits`` is left to the metrics'
    own ``behavioral_profile``. Phase 1 scores against the default study; a
    config-driven path lands with Study Setup.
    """
    metrics = score_bart(session.events)
    return AssessmentResponse(
        session_id=session.session_id,
        game_type=session.game_type,
        candidate_id=session.candidate_id,
        raw_metrics=metrics,
        normalized_scores=[],
        profile_traits={},
    )


@app.post("/write-output", response_model=WriteOutputResponse)
def write_output(req: WriteOutputRequest) -> WriteOutputResponse:
    """Persist one session under the config's output_dir (SPEC §13).

    Writes three files namespaced by study title + candidate + timestamp: the raw
    event log (JSONL), the scored metrics (JSON), and a snapshot of the full
    ``TaskConfig`` so each dataset is self-documenting and reproducible.
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

    metrics = score_bart(req.session.events)
    metrics_path.write_text(metrics.model_dump_json(indent=2), encoding="utf-8")
    config_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")

    return WriteOutputResponse(
        events=str(events_path),
        metrics=str(metrics_path),
        config=str(config_path),
    )
