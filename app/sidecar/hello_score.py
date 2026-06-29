"""Minimal frozen-sidecar smoke entry: proves the scoring engine runs frozen.

This is the artifact PyInstaller freezes *first* (SPEC §9/§18), to retire the
"numpy bundles and runs on Windows" risk before the full sidecar is built. It
imports the installed ``scoring`` package, scores a tiny session, and prints a
deterministic line the Windows CI asserts on. Run directly: ``python hello_score.py``.
"""

from __future__ import annotations

from scoring import __version__
from scoring.bart import score_bart
from scoring.config import DEFAULT_TASK_CONFIG
from scoring.schemas import EventPayload, GameEvent


def _smoke_session() -> list[GameEvent]:
    """A small 3-color session, every balloon collected near its EV-optimum.

    Multi-color so scoring exercises the numpy regression/correlation paths (the
    parts most worth de-risking under PyInstaller), not a degenerate single
    balloon.
    """
    optima = DEFAULT_TASK_CONFIG.optima
    events: list[GameEvent] = []
    t = 0.0
    for color in ("purple", "teal", "orange"):
        for _ in range(3):  # three collected balloons per color
            for _ in range(optima[color]):
                t += 1.0
                events.append(
                    GameEvent(timestamp=t, type="pump", payload=EventPayload(color=color))
                )
            t += 1.0
            events.append(
                GameEvent(timestamp=t, type="collect", payload=EventPayload(color=color))
            )
    return events


def main() -> int:
    optimum = DEFAULT_TASK_CONFIG.optima["purple"]
    metrics = score_bart(_smoke_session())
    print(
        f"HELLO_SCORE_OK version={__version__} optimum={optimum} "
        f"balloons={metrics.total_balloons}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
