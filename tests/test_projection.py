"""The Classic metrics projection (DATA-SPEC §4.3/§4.4, impl issue I2).

Classic mode is a projection, not an engine split: ``score_bart`` always
computes the full ``BARTMetrics``; ``scoring.projection`` is the single place
that says which session-level fields and trial columns the classic surface
keeps. These tests pin the two halves of the contract:

- the adjusted-score fix — ``average_pumps_adjusted`` emits *missing* when
  zero balloons were collected, in **both** modes, instead of silently
  falling back to the all-balloon mean;
- the projection — Classic output is a strict, same-named **subset** of
  Advanced (same names, same values, fewer columns) on every surface.
"""

from __future__ import annotations

import json

from scoring.bart import score_bart, trial_table
from scoring.projection import CLASSIC_CANON, CLASSIC_FIELDS, project_metrics, project_trial
from scoring.schemas import BARTMetrics, TrialRecord

from tests.test_scoring import build_events, rich_session

# The classic session-level surface, spelled out (DATA-SPEC §4.3): the five
# exact-match canon metrics plus the integrity/QC tier. The tests hardcode
# this — asserting against the module's own constant would prove nothing.
CANON_FIVE = {
    "average_pumps_adjusted",
    "total_explosions",
    "total_pumps",
    "avg_pumps_all_balloons",
    "money_collected",
}
INTEGRITY_TIER = {
    "total_balloons",
    "session_valid",
    "session_warnings",
    "qc_fast_response_trials",
    "qc_zero_pump_streak",
    "qc_flagged",
    "qc_fast_response_ms",
    "qc_zero_pump_streak_threshold",
    "payout_amount",
    "payout_currency",
}


def all_explode_session():
    """A pathological session: every balloon explodes, none collected."""
    balloons = []
    for color in ("purple", "teal", "orange"):
        balloons.extend([(color, 3, False)] * 10)
    return build_events(balloons)


# ── The adjusted-score fix (§4.4) ────────────────────────────────────────────


def test_zero_collected_session_emits_missing_adjusted_score():
    """When zero balloons were collected there is no adjusted score: the field
    is None (null in JSON, empty CSV cell) — not a silent fallback to the
    all-balloon mean, which is a different estimator."""
    metrics = score_bart(all_explode_session())
    assert metrics.average_pumps_adjusted is None
    assert metrics.avg_pumps_all_balloons == 3.0  # the honest column still exists
    assert json.loads(metrics.model_dump_json())["average_pumps_adjusted"] is None


def test_collected_session_keeps_the_adjusted_score():
    """The fix touches only the zero-collected edge: any session with at least
    one collected balloon scores exactly as before."""
    balloons = [("purple", 11, True)] * 10 + [("teal", 5, True)] * 10 + [
        ("orange", 2, False)
    ] * 10
    metrics = score_bart(build_events(balloons))
    assert metrics.average_pumps_adjusted == 8.0  # (10*11 + 10*5) / 20


# ── The Classic projection: session-level surfaces (§4.3) ────────────────────


def test_classic_metrics_json_is_a_strict_same_named_subset():
    """Classic metrics.json keeps a subset of Advanced's keys — same names,
    same values, same relative order — and nothing else."""
    dump = score_bart(rich_session()).model_dump(mode="json")
    classic = project_metrics(dump, "classic")

    assert set(classic) < set(dump)
    assert list(classic) == [k for k in dump if k in classic]  # order inherited
    assert all(classic[k] == dump[k] for k in classic)  # shared fields identical


def test_classic_metrics_json_keeps_exactly_canon_plus_integrity():
    """The keep-set is the five canon metrics plus the integrity/QC tier —
    per-color blocks and every advanced behavioral/derived metric are gone."""
    dump = score_bart(rich_session()).model_dump(mode="json")
    classic = project_metrics(dump, "classic")

    assert set(classic) == CANON_FIVE | INTEGRITY_TIER
    assert "color_metrics" not in classic
    assert "learning_rate" not in classic
    assert "explosion_rate" not in classic  # the count is canon, the rate is not


def test_advanced_projection_is_the_identity():
    """Advanced mode passes everything through untouched — the v1.0.0 surface."""
    dump = score_bart(rich_session()).model_dump(mode="json")
    assert project_metrics(dump, "advanced") == dump


def test_classic_master_row_drops_the_color_blocks():
    """The flattened master-CSV row projects by the same rule: the per-color
    ``{color}_*`` columns vanish because they are not in the keep-set."""
    from sidecar.emission import flatten_metrics

    row = flatten_metrics(score_bart(rich_session()))
    classic = project_metrics(row, "classic")

    assert set(classic) == (CANON_FIVE | INTEGRITY_TIER) - {
        "session_warnings",  # JSON-only: the flattener already keeps it out
        "payout_amount",  # conditional columns: the default study has no payout
        "payout_currency",
    }
    assert not any(k.startswith(("purple_", "teal_", "orange_")) for k in classic)


def test_classic_fields_constant_matches_the_spec():
    """The module's exported keep-set is exactly the spec's — the dictionary
    generator builds the researcher-facing docs from it."""
    assert CLASSIC_FIELDS == frozenset(CANON_FIVE | INTEGRITY_TIER)
    assert set(CLASSIC_CANON) == CANON_FIVE
    # Every classic field must exist on BARTMetrics, or the "same-named
    # subset" claim is broken at the source.
    assert CLASSIC_FIELDS <= set(BARTMetrics.model_fields)


# ── The Classic projection: trials CSV (§4.3) ────────────────────────────────


def test_classic_trial_rows_drop_only_the_latency_column():
    """Classic trial rows are ``TrialRecord`` minus ``mean_latency_between_pumps``
    — the one field the canon audit named non-canonical. Design/behavior facts
    (hazard family, color, pumps, outcome, earnings) all stay."""
    rows = [t.model_dump(mode="json") for t in trial_table(rich_session())]
    for row in rows:
        classic = project_trial(row, "classic")
        assert set(classic) == set(TrialRecord.model_fields) - {
            "mean_latency_between_pumps"
        }
        assert all(classic[k] == row[k] for k in classic)
        assert project_trial(row, "advanced") == row
