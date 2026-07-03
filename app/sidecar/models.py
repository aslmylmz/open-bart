"""Request/response shapes specific to the sidecar's HTTP surface.

These wrap the ``scoring`` package's own models (``TaskConfig``, ``GameSession``,
``BARTMetrics``) for the endpoints that need a different shape than the engine
returns: config validation, the live curve preview, and writing session files.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from scoring.config import BalloonCurve, TaskConfig
from scoring.schemas import GameSession


class ValidateConfigResponse(BaseModel):
    """Result of validating a candidate ``study.json`` (SPEC §9)."""

    ok: bool
    errors: list[str] = Field(default_factory=list)


class CurvePreview(BaseModel):
    """One color's precomputed survival/EV curve for the Study-Setup preview."""

    hazard: list[float]
    survival: list[float]
    ev: list[float]
    optimum: int
    optimal_ev: float

    @classmethod
    def from_curve(cls, curve: BalloonCurve) -> "CurvePreview":
        return cls(
            hazard=list(curve.hazard),
            survival=list(curve.survival),
            ev=list(curve.ev),
            optimum=curve.optimum,
            optimal_ev=curve.optimal_ev,
        )


class PreviewResponse(BaseModel):
    """Per-color curves + optima for a whole ``TaskConfig`` (SPEC §7.3)."""

    curves: dict[str, CurvePreview]


class ScoreRequest(BaseModel):
    """A session to score, optionally with the study config it ran under. When
    ``config`` is omitted the sidecar scores against the default study, mirroring
    ``WriteOutputRequest`` and the original bare-session contract."""

    session: GameSession
    config: TaskConfig | None = None


class CheckIdRequest(BaseModel):
    """A candidate participant ID to vet before a session starts (issue 38).
    ``config`` names the study whose output directory is scanned; omitted →
    the default study, mirroring ``/score`` and ``/write-output``."""

    candidate_id: str
    config: TaskConfig | None = None


class CheckIdResponse(BaseModel):
    """Verdict on a participant ID: whether it can be used at all (``ok`` /
    ``error``) and how many sessions the study already has for it — the ID
    screen's warn-confirm input (issue 38)."""

    ok: bool
    sessions: int
    error: str | None = None


class WriteOutputRequest(BaseModel):
    """A session to persist, optionally with the study config it ran under (SPEC
    §13). When ``config`` is omitted the sidecar falls back to the default study,
    mirroring how ``/score`` defaults (a per-study path lands with Study Setup)."""

    session: GameSession
    config: TaskConfig | None = None


class WriteOutputResponse(BaseModel):
    """Absolute paths of the files written for one session, plus the study's
    master CSV the session row landed in — a timestamped sibling file when the
    main file was locked or unmergeable (issue 36), explained in ``warnings``."""

    events: str
    metrics: str
    config: str
    session: str
    master_csv: str
    trials_csv: str
    warnings: list[str] = Field(default_factory=list)
