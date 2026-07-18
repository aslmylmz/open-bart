"""The CSV row shapes shared by the live writer and the Hub rebuild.

The equivalence claim (DATA-SPEC §6.5) is that a Hub rebuild of clean
single-station data is byte-identical to live output *by construction*:
column order, float formatting, and presence rules are identical because both
paths run the same code — this module — never two builders kept in sync by
hand. ``write_output`` composes each row as identity + flattened metrics (or
identity + trial record); the rebuild (I9) composes the same rows from the
persisted per-session files.
"""

from __future__ import annotations

from typing import Any

from scoring.schemas import BARTMetrics


def flatten_metrics(metrics: BARTMetrics) -> dict[str, Any]:
    """One flat, scalar-only mapping of a session's metrics for the master CSV.

    Per-color metrics become ``{color}_{field}`` columns so they load as plain
    variables in SPSS/R; the nested narrative ``behavioral_profile`` stays
    JSON-only (not meaningful as spreadsheet cells).
    """
    row = metrics.model_dump(mode="json")
    row.pop("behavioral_profile", None)
    # Non-scalar fields stay JSON-only (issue 53): in a flat sheet they land as
    # Python-repr dict/list blobs (invalid JSON, embedded commas) and are
    # redundant with the scalar {color}_ev_optimal_stop / _efficiency columns.
    row.pop("ev_optimal_stops", None)
    row.pop("session_warnings", None)
    # Payout columns exist only for studies that declare a payout block —
    # the same present-only-when-configured rule as `condition` (issues 37/41).
    if row.get("payout_amount") is None:
        row.pop("payout_amount", None)
        row.pop("payout_currency", None)
    for color in row.pop("color_metrics", []):
        name = color.pop("color")
        for field, value in color.items():
            row[f"{name}_{field}"] = value
    return row


def identity_row(
    *,
    timestamp_utc: str,
    session_id: str,
    candidate_id: str,
    condition: str | None = None,
    conditions_declared: bool = False,
    station_id: str | None = None,
    participant_key: str | None = None,
) -> dict[str, Any]:
    """The identity columns every study-wide CSV row starts with.

    The ``condition`` column exists only for studies that declare conditions
    (issue 37), so condition-less studies keep their v1.0.0 sheets untouched.
    The station columns (DATA-SPEC §11) exist only on a multi-station Hub
    rebuild — pass ``participant_key`` to add the sort-leading ``station_id``
    and the unambiguous ``participant_key``; live emission never does, and a
    single-station rebuild must not either (the §6.5 byte-equality gate).
    """
    row: dict[str, Any] = {}
    if participant_key is not None:
        row["station_id"] = station_id or ""
    row["timestamp_utc"] = timestamp_utc
    row["session_id"] = session_id
    row["candidate_id"] = candidate_id
    if participant_key is not None:
        row["participant_key"] = participant_key
    if conditions_declared:
        row["condition"] = condition or ""
    return row
