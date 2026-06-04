"""
BART Event Validators

BART-specific event validation logic for the scoring engine.

Usage:
    from scoring.schemas.game_events import validate_bart_events
"""

from __future__ import annotations

from scoring.schemas import (
    AssessmentResponse,
    BARTMetrics,
    ColorMetrics,
    EventPayload,
    GameEvent,
    GameSession,
    GameType,
    NormalizedScore,
)

__all__ = [
    "AssessmentResponse",
    "BARTMetrics",
    "ColorMetrics",
    "EventPayload",
    "GameEvent",
    "GameSession",
    "GameType",
    "NormalizedScore",
    "validate_bart_events",
]


# ── BART Event Type Registry ────────────────────────────────────────────────

BART_VALID_EVENT_TYPES = frozenset({"pump", "collect", "explode"})


def validate_bart_events(events: list[GameEvent]) -> list[GameEvent]:
    """
    BART-specific event validation.

    Rules:
    1. Only 'pump', 'collect', and 'explode' event types are allowed.
    2. Every balloon must end with exactly one terminal event
       ('collect' or 'explode') — never both, never neither.
    3. Each balloon must have at least one 'pump' before a terminal event.
    """
    for i, event in enumerate(events):
        if event.type not in BART_VALID_EVENT_TYPES:
            raise ValueError(
                f"Invalid BART event type '{event.type}' at index {i}. "
                f"Allowed: {sorted(BART_VALID_EVENT_TYPES)}"
            )

    current_balloon_pumps = 0
    balloon_index = 1

    for i, event in enumerate(events):
        if event.type == "pump":
            current_balloon_pumps += 1
        elif event.type in ("collect", "explode"):
            if current_balloon_pumps == 0:
                raise ValueError(
                    f"Balloon {balloon_index} has a terminal event "
                    f"('{event.type}') at index {i} with zero pumps."
                )
            current_balloon_pumps = 0
            balloon_index += 1

    return events
