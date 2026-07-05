"""Contract guard: the hand-written TypeScript mirrors in ``app/src/lib`` must
not silently drift from the pydantic models that own the study/session shapes.

The webview re-declares ``TaskConfig`` / ``ColorProfile`` / the hazard families /
``GameSession`` by hand — a typing convenience; the sidecar stays the sole
validation authority. Those hand-written shapes have drifted before:
``TaskConfig`` grew ``qc`` and ``payout`` on the Python side and the TS type
never followed, so Study Setup silently could not configure them.

This test derives each guarded model's field inventory from its JSON schema and
asserts it equals the committed contract file that the TS side checks itself
against (``app/src/lib/contract.generated.json``). When a guarded model changes,
this test fails; regenerate with:

    python tests/test_ts_contract.py

Scope is the round-trip **input** contracts only — shapes where a missing TS
field is a real defect (an unconfigurable setting, or a payload the sidecar
rejects). Read-only projections (``Debrief``'s ``AssessmentResult`` and the
``api.ts`` response DTOs) are deliberate subsets and are intentionally NOT
guarded here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Make ``import scoring`` resolve when this file is run directly as a script to
# regenerate the contract (``python tests/test_ts_contract.py``), not only under
# pytest where conftest.py puts the repo root on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.config import (  # noqa: E402
    ColorProfile,
    ConstantHazard,
    DynamicHazard,
    ExponentialHazard,
    GompertzHazard,
    LejuezHazard,
    LogisticHazard,
    LognormalHazard,
    PayoutConversion,
    QCThresholds,
    RayleighHazard,
    StepHazard,
    TabularHazard,
    TaskConfig,
    WeibullHazard,
)
from scoring.schemas import GameSession  # noqa: E402

CONTRACT_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "src" / "lib" / "contract.generated.json"
)

# The 11 hazard families, keyed in the contract by their `family` discriminator.
_HAZARD_FAMILIES = [
    ConstantHazard,
    DynamicHazard,
    ExponentialHazard,
    GompertzHazard,
    LejuezHazard,
    LogisticHazard,
    LognormalHazard,
    RayleighHazard,
    StepHazard,
    TabularHazard,
    WeibullHazard,
]

_REGEN = "regenerate: python tests/test_ts_contract.py"


def _fields(model: Any) -> list[str]:
    """The serialized field names of a pydantic model — its JSON object keys."""
    return sorted(model.model_json_schema()["properties"])


def build_contract() -> dict[str, Any]:
    """The field inventory the TS mirrors must match, keyed by pydantic model."""
    hazards = {
        fam.model_fields["family"].default: _fields(fam) for fam in _HAZARD_FAMILIES
    }
    return {
        "TaskConfig": _fields(TaskConfig),
        "ColorProfile": _fields(ColorProfile),
        "QCThresholds": _fields(QCThresholds),
        "PayoutConversion": _fields(PayoutConversion),
        "GameSession": _fields(GameSession),
        "HazardSpec": hazards,
    }


def test_ts_contract_is_in_sync() -> None:
    """The committed TS contract file matches the current pydantic models."""
    assert CONTRACT_PATH.exists(), f"{CONTRACT_PATH.name} missing — {_REGEN}"
    actual = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert actual == build_contract(), (
        f"{CONTRACT_PATH.name} is stale vs the pydantic models — {_REGEN}"
    )


def _write_contract() -> None:
    CONTRACT_PATH.write_text(
        json.dumps(build_contract(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    _write_contract()
    print(f"wrote {CONTRACT_PATH}")
