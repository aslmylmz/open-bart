"""Projection wiring + the injectable clock in the live emission path
(DATA-SPEC §4.1/§9.5, impl issue I6).

``score_bart`` always computes the full ``BARTMetrics``; ``write_output``
applies the Classic projection at its single emission point, so
``metrics_mode`` reaches the master CSV, the trials CSV, and ``metrics.json``
uniformly — a drop-columns transform, never an engine fork. (The data
dictionary, the fourth surface, is generated mode-aware by the provenance
module and pinned in ``test_provenance``.)

The clock seam is what makes deterministic golden fixtures possible: the
fixture builder (DATA-SPEC §9.5) injects fixed synthetic timestamps into the
*real* emission path, so committed samples stay byte-reproducible while
production keeps the real UTC clock.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import sidecar.app as sidecar_app
from scoring.bart import score_bart
from scoring.config import DEFAULT_TASK_CONFIG

from tests.test_projection import CANON_FIVE, INTEGRITY_TIER
from tests.test_provenance import WIDEST, _csv_header, _dictionary_rows, _write_session
from tests.test_sidecar import _collected_session


def _master_rows(out: dict) -> list[dict]:
    with open(out["master_csv"], newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ── Projection wiring: one keep-set on every surface (§4.1) ──────────────────


def test_classic_metrics_json_is_projected_to_the_keep_set(tmp_path):
    """A classic study's ``metrics.json`` carries exactly the canon five plus
    the integrity/QC tier — the advanced behavioral/derived metrics and the
    per-color blocks never reach disk (the raw event log stays the complete
    ground truth)."""
    out = _write_session(
        tmp_path, {**WIDEST, "metrics_mode": "classic"}, condition="control"
    )
    data = json.loads(Path(out["metrics"]).read_text("utf-8"))
    assert set(data) == CANON_FIVE | INTEGRITY_TIER


def test_classic_csv_headers_match_the_dictionary(tmp_path):
    """In classic mode the real CSVs and the generated data dictionary agree
    column for column: identity prepended mode-independently, then the
    projected keep-set in Advanced's order — and the trials sheet loses
    exactly ``mean_latency_between_pumps``."""
    out = _write_session(
        tmp_path, {**WIDEST, "metrics_mode": "classic"}, condition="control"
    )

    master = _csv_header(out["master_csv"])
    assert master == [n for n, _ in _dictionary_rows(tmp_path, out, "Master CSV columns")]
    assert master[:4] == ["timestamp_utc", "session_id", "candidate_id", "condition"]
    assert not any(k.startswith(("purple_", "teal_", "orange_")) for k in master)

    trials = _csv_header(out["trials_csv"])
    assert trials == [n for n, _ in _dictionary_rows(tmp_path, out, "Trials CSV columns")]
    assert "mean_latency_between_pumps" not in trials


def test_classic_values_are_advanceds_on_every_shared_field(tmp_path):
    """No engine fork: the same session written in both modes yields a classic
    ``metrics.json`` that is exactly the advanced one minus the dropped keys —
    same names, same values, from the same ``write_output`` call."""
    advanced = _write_session(tmp_path / "adv", {"output_dir": str(tmp_path / "adv")})
    classic = _write_session(
        tmp_path / "cls",
        {"output_dir": str(tmp_path / "cls"), "metrics_mode": "classic"},
    )

    adv = json.loads(Path(advanced["metrics"]).read_text("utf-8"))
    cls = json.loads(Path(classic["metrics"]).read_text("utf-8"))
    assert cls == {k: adv[k] for k in cls}
    assert set(cls) < set(adv)


def test_advanced_emission_keeps_the_full_surface(tmp_path):
    """Default (advanced) mode still emits the complete v1.0.0 surface: the
    full ``metrics.json`` — per-color blocks and narrative included — and the
    per-color columns and pump-latency column in the CSVs."""
    out = _write_session(tmp_path)

    data = json.loads(Path(out["metrics"]).read_text("utf-8"))
    assert "color_metrics" in data
    assert "behavioral_profile" in data
    assert any(k.startswith("orange_") for k in _csv_header(out["master_csv"]))
    assert "mean_latency_between_pumps" in _csv_header(out["trials_csv"])


def test_advanced_metrics_json_bytes_are_unchanged(tmp_path):
    """The uniform emission path is byte-preserving where it must be: in
    advanced mode the projected dump serializes to exactly the bytes the
    pre-projection ``model_dump_json`` wrote, so default-mode studies keep
    byte-for-byte current output (DATA-SPEC §4.6)."""
    out = _write_session(tmp_path)
    written = Path(out["metrics"]).read_text("utf-8")
    metrics = score_bart(_collected_session(), DEFAULT_TASK_CONFIG)
    assert written == metrics.model_dump_json(indent=2)


# ── The clock seam (§9.5) ────────────────────────────────────────────────────


def test_an_injected_clock_makes_timestamps_deterministic(tmp_path, monkeypatch):
    """Injecting a fixed clock at the seam yields the same ``timestamp_utc``
    in the filename stem and in the CSV rows — the property the committed
    golden samples rest on."""
    fixed = datetime(2020, 1, 2, 3, 4, 5, 678900, tzinfo=timezone.utc)
    monkeypatch.setattr(sidecar_app, "_utc_now", lambda: fixed)

    out = _write_session(tmp_path)

    stamp = "20200102T030405678900Z"
    assert Path(out["events"]).name.endswith(f"_{stamp}_events.jsonl")
    assert [r["timestamp_utc"] for r in _master_rows(out)] == [stamp]


def test_the_default_clock_is_the_real_utc_clock(tmp_path):
    """Production behavior is unchanged: with nothing injected, the stamped
    timestamp is the real UTC write time."""
    before = datetime.now(timezone.utc)
    out = _write_session(tmp_path)
    after = datetime.now(timezone.utc)

    stamp = re.search(r"_(\d{8}T\d+Z)_events\.jsonl$", Path(out["events"]).name).group(1)
    written = datetime.strptime(stamp, "%Y%m%dT%H%M%S%fZ").replace(tzinfo=timezone.utc)
    assert before <= written <= after
