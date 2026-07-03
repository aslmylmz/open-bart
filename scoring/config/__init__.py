"""Domain models for BART configuration.

The `TaskConfig` is the single source of truth for a session, capturing everything
needed to administer and score the task: color profiles, reward, and the specific
hazard models.

These classes use `pydantic` to provide strict runtime validation. They are
designed to be loaded from `study.json` presets.
"""

from scoring.config.curve import BalloonCurve, balloon_curve
from scoring.config.hazards import (
    ConstantHazard,
    ExponentialHazard,
    DynamicHazard,
    GompertzHazard,
    HazardSpec,
    LogisticHazard,
    LognormalHazard,
    RayleighHazard,
    StepHazard,
    TabularHazard,
    LejuezHazard,
    WeibullHazard,
)
from scoring.config.task_config import (
    DEFAULT_TASK_CONFIG,
    ColorProfile,
    PayoutConversion,
    QCThresholds,
    TaskConfig,
)

__all__ = [
    # Main domain entities
    "TaskConfig",
    "ColorProfile",
    "PayoutConversion",
    "QCThresholds",
    "DEFAULT_TASK_CONFIG",
    # Specific hazard families
    "ConstantHazard",
    "ExponentialHazard",
    "DynamicHazard",
    "GompertzHazard",
    "LogisticHazard",
    "LognormalHazard",
    "RayleighHazard",
    "StepHazard",
    "TabularHazard",
    "LejuezHazard",
    "WeibullHazard",
    # Precomputed math
    "BalloonCurve",
    "balloon_curve",
    # Discriminated union type
    "HazardSpec",
]
