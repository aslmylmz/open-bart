"""The Advanced → Classic metrics projection (DATA-SPEC §4.3).

Classic mode is a projection, not an engine split: ``score_bart`` always
computes the full ``BARTMetrics``, and this module is the single statement of
what the classic surface keeps — a drop-columns transform whose output is a
strict, same-named **subset** of the advanced output. The same keep-set reaches
every persisted surface (master CSV, trials CSV, ``metrics.json``, and the
generated data dictionary), so the replication claim rests on this short spec
rather than a parallel engine.

Repo field names are kept; the literature name/definition of each canon metric
travels in ``CLASSIC_CANON`` and is rendered into the data dictionary — never
as a column rename. Classic is session-level only: the per-color
``{color}_*`` blocks drop out because their keys are not in the keep-set, so a
single-color study in Classic is a verbatim 2003 replication and a multi-color
study reports the pooled canon five.

The transforms are pure (mode + mapping in, mapping out) and independent of
the emission path; ``write_output`` applies them at its single decision point.
Presence rules are inherited from the input mapping: the master-CSV flattener
already keeps ``session_warnings`` JSON-only and drops the ``payout_*`` pair
for payout-less studies, while ``metrics.json`` carries both (payout as null,
exactly as Advanced does) — the projection only ever removes non-classic keys.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping

from scoring.schemas import BARTMetrics

MetricsMode = Literal["classic", "advanced"]

# The five exact-match canon metrics ([T01]; Lejuez et al. 2002/2003), mapped
# to the literature name/definition the data dictionary renders per column.
# Note the deliberate choices: total_explosions is the *count* (not a rate),
# and average_pumps_adjusted reproduces the canonical estimator as published —
# known-biased under censoring (Pleskac et al., 2008), kept for comparability.
CLASSIC_CANON: dict[str, str] = {
    "average_pumps_adjusted": (
        "Classic canon: the adjusted average number of pumps (Lejuez et al., "
        "2002) — mean pumps on unexploded balloons, the primary BART score. "
        "Deliberately the canonical estimator, biased under censoring "
        "(Pleskac et al., 2008)."
    ),
    "total_explosions": (
        "Classic canon: the number of balloon explosions (Lejuez et al., "
        "2002) — reported as a count, not a rate."
    ),
    "total_pumps": (
        "Classic canon: the total pump count across the session "
        "(Lejuez et al., 2003)."
    ),
    "avg_pumps_all_balloons": (
        "Classic canon: the unadjusted average number of pumps across all "
        "balloons, exploded included (Lejuez et al., 2002)."
    ),
    "money_collected": (
        "Classic canon: total money earned from collected balloons "
        "(Lejuez et al., 2002)."
    ),
}

# The integrity/QC tier Classic keeps (§4.3): a Classic dataset must still
# tell an analyst which sessions to trust — projecting metrics.json down to
# the five canon metrics alone would erase session_valid/qc_flagged from
# every derived surface. The qc_* family is derived from the model so a new
# flag can never silently fall out of Classic.
_QC_FAMILY = frozenset(n for n in BARTMetrics.model_fields if n.startswith("qc_"))
CLASSIC_INTEGRITY: frozenset[str] = _QC_FAMILY | {
    "total_balloons",
    "session_valid",
    "session_warnings",
    "payout_amount",
    "payout_currency",
}

# The complete Classic session-level keep-set, applied uniformly to the
# flattened master-CSV row and the metrics.json mapping.
CLASSIC_FIELDS: frozenset[str] = frozenset(CLASSIC_CANON) | CLASSIC_INTEGRITY

# Classic trial rows are TrialRecord minus this — the one field the canon
# audit named non-canonical. Everything else (hazard_family, balloon_color,
# pumps, outcome, trial_earnings) is a design/behavior fact and stays.
CLASSIC_TRIALS_DROPPED: frozenset[str] = frozenset({"mean_latency_between_pumps"})


def project_metrics(mapping: Mapping[str, Any], mode: MetricsMode) -> dict[str, Any]:
    """Project one session's session-level mapping down to ``mode``.

    Serves both session-level surfaces — the full ``metrics.json`` dump and
    the flattened master-CSV row — with one rule: classic keeps a key iff it
    is in ``CLASSIC_FIELDS``. Key order (hence CSV column order) is inherited
    from the input, so Classic is a same-order subset of Advanced by
    construction; the ``{color}_*`` blocks drop out with everything else.
    """
    if mode != "classic":
        return dict(mapping)
    return {k: v for k, v in mapping.items() if k in CLASSIC_FIELDS}


def project_trial(mapping: Mapping[str, Any], mode: MetricsMode) -> dict[str, Any]:
    """Project one trials-CSV row (a ``TrialRecord`` mapping) down to ``mode``."""
    if mode != "classic":
        return dict(mapping)
    return {k: v for k, v in mapping.items() if k not in CLASSIC_TRIALS_DROPPED}
