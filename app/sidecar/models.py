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


class WriteOutputRequest(BaseModel):
    """A session to persist, with the study config it was run under (SPEC §13)."""

    session: GameSession
    config: TaskConfig


class WriteOutputResponse(BaseModel):
    """Absolute paths of the files written for one session."""

    events: str
    metrics: str
    config: str
