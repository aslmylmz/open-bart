"""TaskConfig and ColorProfile: the configurable definition of one BART study.

A ``TaskConfig`` is the single source of truth. Each ``ColorProfile`` pairs a
hazard family with a pump cap and turns it into a ``BalloonCurve`` on demand;
``TaskConfig`` supplies the shared ``reward_per_pump`` and exposes per-color
optima used by both the task and the scoring engine.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, PrivateAttr, field_validator

from scoring.config.curve import BalloonCurve, balloon_curve
from scoring.config.hazards import HazardSpec, DynamicHazard


class ColorProfile(BaseModel):
    """One balloon color: a hazard family bounded by a per-color pump cap."""

    name: str
    label: str
    display_hex: str
    max_pumps: int = Field(gt=0, description="N: hard cap on pumps for this color")
    trials: int = Field(gt=0, description="number of balloons of this color")
    hazard: HazardSpec

    def curve(self, reward_per_pump: float) -> BalloonCurve:
        """Precompute this color's survival/EV curve and numeric optimum."""
        return balloon_curve(self.hazard.hazard_vector(self.max_pumps), reward_per_pump)


class TaskConfig(BaseModel):
    """A complete, self-describing BART study: the one source of truth.

    On construction it precomputes each color's ``BalloonCurve`` from the shared
    ``reward_per_pump``, so task bursting and scoring read the same vectors.
    """

    schema_version: str = "1.0"
    title: str
    language: Literal["tr", "en"] = "en"
    reward_per_pump: float = Field(gt=0, description="currency units per banked pump")
    seed: Optional[int] = Field(default=None, description="RNG seed for reproducible bursts")
    output_dir: str = Field(default=".", description="local folder for session data")
    colors: list[ColorProfile] = Field(min_length=1)
    conditions: list[str] = Field(
        default_factory=list,
        description=(
            "allowed condition names for between-subject designs; empty means "
            "this study has no conditions (issue 37)"
        ),
    )

    _curves: dict[str, BalloonCurve] = PrivateAttr(default_factory=dict)

    @field_validator("conditions")
    @classmethod
    def conditions_must_be_usable_names(cls, v: list[str]) -> list[str]:
        """Condition names feed a dropdown and a CSV column: surrounding
        whitespace is stripped; blank, duplicate, or unreasonably long names
        are configuration errors the researcher must fix in Study Setup."""
        names = [name.strip() for name in v]
        if any(not name for name in names):
            raise ValueError("condition names must not be blank")
        if len(set(names)) != len(names):
            raise ValueError("condition names must not repeat")
        if any(len(name) > 64 for name in names):
            raise ValueError("condition names must be 64 characters or fewer")
        return names

    def model_post_init(self, __context: object) -> None:
        self._curves = {c.name: c.curve(self.reward_per_pump) for c in self.colors}

    @property
    def curves(self) -> dict[str, BalloonCurve]:
        """Per-color precomputed survival/EV curves, keyed by color name."""
        return self._curves

    def curve_for(self, name: str) -> BalloonCurve:
        return self._curves[name]

    @property
    def optima(self) -> dict[str, int]:
        """Per-color EV-optimal stop, keyed by color name."""
        return {name: curve.optimum for name, curve in self._curves.items()}


# The validated default study: the original 128/32/8 dynamic hazard, $0.25/pump.
DEFAULT_TASK_CONFIG = TaskConfig(
    title="Dynamic Hazard Rate BART (default dynamic study)",
    language="en",
    reward_per_pump=0.25,
    colors=[
        ColorProfile(
            name="purple",
            label="Purple",
            display_hex="#7c3aed",
            max_pumps=128,
            trials=10,
            hazard=DynamicHazard(),
        ),
        ColorProfile(
            name="teal",
            label="Teal",
            display_hex="#14b8a6",
            max_pumps=32,
            trials=10,
            hazard=DynamicHazard(),
        ),
        ColorProfile(
            name="orange",
            label="Orange",
            display_hex="#f97316",
            max_pumps=8,
            trials=10,
            hazard=DynamicHazard(),
        ),
    ],
)
