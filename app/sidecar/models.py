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
    ``error``) and how many sessions this station already has for it — the ID
    screen's warn-confirm input (issue 38). ``standalone``/``station_id``
    (DATA-SPEC §2.6) let the ID screen word the duplicate warning honestly:
    the count is station-scoped and local-only — cross-station duplicates are
    the Hub's to flag at assembly."""

    ok: bool
    sessions: int
    error: str | None = None
    standalone: bool = False
    station_id: str | None = None


class SetStationRequest(BaseModel):
    """A new station label for this machine (DATA-SPEC §2.3). Whitespace-only
    clears the setting — the machine UUID always stays."""

    station_id: str


class StationResponse(BaseModel):
    """This machine's station identity, plus the ok/error verdict when a new
    label was submitted (a rejected label never replaces the stored one).
    ``machine_uuid`` is the random per-install UUID minted on first run — the
    Hub's duplicate-station-label detector."""

    ok: bool = True
    station_id: str | None = None
    machine_uuid: str
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
    main file was locked or unmergeable (issue 36), explained in ``warnings``.
    Practice sessions (issue 43) and Standalone Mode (DATA-SPEC §2.2) append
    to no study-wide CSVs, so their ``master_csv``/``trials_csv`` are ``None``.
    ``standalone``/``station_id`` state the deployment mode affirmatively
    (§2.4): the return surface derives everything from this payload, never
    from a file's absence."""

    events: str
    metrics: str
    config: str
    session: str
    master_csv: str | None = None
    trials_csv: str | None = None
    warnings: list[str] = Field(default_factory=list)
    standalone: bool = False
    station_id: str | None = None
