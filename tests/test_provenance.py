"""Provenance-by-default: the OSF-ready output directory (issue 42).

Every study's output directory permanently carries a frozen copy of the exact
study config, a provenance record (app/engine versions, platform, seed), and a
data dictionary generated from the scoring models. These tests exercise the
behavior through the public /write-output endpoint, the same way sessions
create the files in the field.
"""

from __future__ import annotations

import csv
import json
import platform
import re
import sys
from pathlib import Path

import pytest

import scoring
from scoring.config import DEFAULT_TASK_CONFIG

from tests.test_sidecar import _collected_session, _session_payload, client

WIDEST = {
    "conditions": ["control", "experimental"],
    "payout": {"rate": 0.1, "currency": "$"},
}


def _write_session(tmp_path, cfg_extra: dict | None = None, **payload_over) -> dict:
    """POST one collected session to /write-output; returns the response body."""
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)
    cfg.update(cfg_extra or {})
    resp = client.post(
        "/write-output",
        json={
            "session": _session_payload(_collected_session(), **payload_over),
            "config": cfg,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _study_slug(out: dict) -> str:
    """The study's filename namespace, recovered from the master CSV path."""
    return Path(out["master_csv"]).name.removesuffix("_results.csv")


def _csv_header(path: str) -> list[str]:
    with open(path, newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh))


def _dictionary_rows(tmp_path, out: dict, heading: str) -> list[tuple[str, str]]:
    """A dictionary section's table rows — (backticked column name,
    description) — in document order."""
    text = (tmp_path / f"{_study_slug(out)}_data_dictionary.md").read_text("utf-8")
    section = text.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"^\| `([^`]+)` \| (.*) \|$", section, flags=re.M)


def test_first_session_makes_the_output_directory_osf_ready(tmp_path):
    """The first session writes the three study-level files alongside the
    session files: a frozen copy of the exact study config used, a provenance
    record naming the app version, engine version, platform, and seed, and a
    generated data dictionary — so 'export for OSF' is right-click → Compress,
    with nothing to remember."""
    out = _write_session(tmp_path)
    slug = _study_slug(out)

    frozen = json.loads((tmp_path / f"{slug}_study.json").read_text("utf-8"))
    expected = DEFAULT_TASK_CONFIG.model_dump(mode="json")
    expected["output_dir"] = str(tmp_path)
    assert frozen == expected

    prov = json.loads((tmp_path / f"{slug}_provenance.json").read_text("utf-8"))
    assert prov == {
        "app_version": scoring.__version__,
        "engine_version": scoring.__version__,
        "platform": platform.platform(),
        "seed": None,
    }

    dictionary = (tmp_path / f"{slug}_data_dictionary.md").read_text("utf-8")
    assert "Data Dictionary" in dictionary
    assert scoring.__version__ in dictionary


def test_dictionary_names_every_master_csv_column(tmp_path):
    """The dictionary's Master CSV section lists exactly the columns the
    study's real master CSV has — same names, same order — for the widest
    schema (conditions + payout declared). Generated from the scoring models,
    so a column added in code can never be missing here."""
    out = _write_session(tmp_path, WIDEST, condition="control")

    rows = _dictionary_rows(tmp_path, out, "Master CSV columns")
    assert [name for name, _ in rows] == _csv_header(out["master_csv"])
    # Every column carries a non-empty description — a dictionary of bare
    # names would satisfy the header diff but document nothing.
    assert all(desc.strip() for _, desc in rows)


def test_dictionary_names_every_trials_csv_column(tmp_path):
    """The dictionary's Trials CSV section lists exactly the columns of the
    study's real long-format trials CSV (issue 39), with a description for
    each — condition included for conditioned studies."""
    out = _write_session(tmp_path, WIDEST, condition="control")

    rows = _dictionary_rows(tmp_path, out, "Trials CSV columns")
    assert [name for name, _ in rows] == _csv_header(out["trials_csv"])
    assert all(desc.strip() for _, desc in rows)


def test_dictionary_mirrors_the_conditional_column_rule(tmp_path):
    """A study with no conditions and no payout gets a dictionary without the
    `condition` / `payout_*` columns — the dictionary documents the columns
    this study's CSV actually has (issues 37/41), not the widest schema."""
    out = _write_session(tmp_path)

    documented = [n for n, _ in _dictionary_rows(tmp_path, out, "Master CSV columns")]
    assert documented == _csv_header(out["master_csv"])
    assert "condition" not in documented
    assert "payout_amount" not in documented


def test_dictionary_describes_every_field_of_the_session_files(tmp_path):
    """Beyond the CSVs, the dictionary documents the per-session files: every
    field of the raw event objects, the scored metrics, the session envelope,
    and the study config snapshot — all generated from the models."""
    from scoring.config import ColorProfile, TaskConfig
    from scoring.schemas import BARTMetrics, GameEvent, GameSession

    out = _write_session(tmp_path)
    text = (tmp_path / f"{_study_slug(out)}_data_dictionary.md").read_text("utf-8")
    assert "## Per-session files" in text

    # Metric scalars are documented once, in the Master CSV table (the metrics
    # section builds on it), so fields are looked up document-wide.
    for model, skip in (
        (GameEvent, set()),
        (BARTMetrics, set()),
        (GameSession, {"events"}),  # the envelope excludes the event log
        (TaskConfig, set()),
        (ColorProfile, set()),
    ):
        missing = [
            name
            for name in model.model_fields
            if name not in skip and f"`{name}`" not in text
        ]
        assert missing == [], f"{model.__name__}: {missing}"


def _provenance_files(tmp_path, out: dict) -> list[Path]:
    slug = _study_slug(out)
    return [
        tmp_path / f"{slug}_study.json",
        tmp_path / f"{slug}_provenance.json",
        tmp_path / f"{slug}_data_dictionary.md",
    ]


def test_second_session_leaves_unchanged_provenance_untouched(tmp_path):
    """Sessions never churn the provenance files: when nothing changed, a
    later session rewrites none of them (timestamps stay put) and no versioned
    study copies appear."""
    out = _write_session(tmp_path)
    files = _provenance_files(tmp_path, out)
    before = [f.stat().st_mtime_ns for f in files]

    _write_session(tmp_path, candidate_id="cand-2")

    assert [f.stat().st_mtime_ns for f in files] == before
    assert not list(tmp_path.glob(f"{_study_slug(out)}_study_*.json"))


def test_app_upgrade_refreshes_provenance_and_dictionary_not_the_frozen_preset(
    tmp_path, monkeypatch
):
    """A mid-study upgrade (recorded version ≠ running version) refreshes the
    provenance record and regenerates the dictionary, but the frozen study
    config is never replaced — the original design stays auditable."""
    out = _write_session(tmp_path)
    frozen, prov, dictionary = _provenance_files(tmp_path, out)
    frozen_before = frozen.read_bytes()

    monkeypatch.setattr(scoring, "__version__", "9.9.9")
    _write_session(tmp_path, candidate_id="cand-2")

    refreshed = json.loads(prov.read_text("utf-8"))
    assert refreshed["app_version"] == "9.9.9"
    assert refreshed["engine_version"] == "9.9.9"
    assert "9.9.9" in dictionary.read_text("utf-8")
    assert frozen.read_bytes() == frozen_before
    assert not list(tmp_path.glob(f"{_study_slug(out)}_study_*.json"))


def test_changed_config_is_versioned_alongside_the_frozen_preset(tmp_path):
    """Running sessions under a changed config never touches the frozen
    original: the changed config is written alongside as a timestamped
    versioned copy — exactly one per distinct config, however many sessions
    run under it — and the dictionary refreshes to the new column set."""
    out = _write_session(tmp_path)
    frozen, _, dictionary = _provenance_files(tmp_path, out)
    frozen_before = frozen.read_bytes()

    changed = {"conditions": ["control", "experimental"]}
    _write_session(tmp_path, changed, candidate_id="cand-2", condition="control")
    _write_session(tmp_path, changed, candidate_id="cand-3", condition="control")

    assert frozen.read_bytes() == frozen_before
    copies = [
        p
        for p in tmp_path.glob(f"{_study_slug(out)}_study_*.json")
        if re.fullmatch(rf"{_study_slug(out)}_study_\d{{8}}T\d+Z\.json", p.name)
    ]
    assert len(copies) == 1
    versioned = json.loads(copies[0].read_text("utf-8"))
    assert versioned["conditions"] == ["control", "experimental"]
    # The dictionary tracks the running config: the condition column is now in.
    assert "| `condition` |" in dictionary.read_text("utf-8")


@pytest.mark.skipif(sys.platform == "win32", reason="chmod is advisory on Windows")
def test_unwritable_provenance_file_warns_but_never_blocks_the_session(
    tmp_path, monkeypatch
):
    """A provenance file that cannot be rewritten (locked, read-only) comes
    back as a readable warning — the session's own files and CSV rows are
    written exactly as always (the issue-36 never-lose-a-session rule)."""
    out = _write_session(tmp_path)
    _, prov, _ = _provenance_files(tmp_path, out)
    prov.chmod(0o444)
    monkeypatch.setattr(scoring, "__version__", "9.9.9")  # forces a rewrite

    out = _write_session(tmp_path, candidate_id="cand-2")

    assert any(prov.name in w for w in out["warnings"])
    assert Path(out["metrics"]).exists()
    with open(out["master_csv"], newline="", encoding="utf-8") as fh:
        assert [r["candidate_id"] for r in csv.DictReader(fh)] == ["cand-1", "cand-2"]
    prov.chmod(0o644)
