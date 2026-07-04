"""Metric documentation status (issue 54 / kaizen F6).

The scoring schema must tell researchers which fields are analysis-ready
primitives and which are exploratory, unnormed composites, so a narrative
heuristic is never mistaken for a validated dependent variable. Field
descriptions are public — they flow into the generated data dictionary and the
API schema — so asserting on them tests researcher-facing behavior.
"""

from __future__ import annotations

from scoring.schemas import BARTMetrics


def _desc(field: str) -> str:
    return (BARTMetrics.model_fields[field].description or "").lower()


def test_adaptive_strategy_score_is_flagged_exploratory():
    """The composite is an arbitrary fixed-weight index, not a normed scale."""
    assert "exploratory" in _desc("adaptive_strategy_score")


def test_behavioral_profile_risk_style_is_flagged_exploratory():
    """The risk_style narrative is a hand-tuned heuristic, not a classifier."""
    assert "exploratory" in _desc("behavioral_profile")


def test_deprecated_metric_is_not_silently_exported():
    """color_discrimination_index stays exported for back-compat but must always
    carry an explicit deprecation marker, so it is never silently presented as a
    live metric (issue 54)."""
    assert "deprecated" in _desc("color_discrimination_index")
