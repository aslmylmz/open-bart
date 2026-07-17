"""Tests for the offline scoring sidecar (app/sidecar).

The sidecar wraps the installed ``scoring`` package behind a localhost-only
FastAPI app (SPEC §9/§10). These tests exercise it through its public surface:
the HTTP endpoints and the frozen-entry / launcher scripts.
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import scoring
from scoring.bart import score_bart, trial_table
from scoring.config import DEFAULT_TASK_CONFIG, TaskConfig
from scoring.schemas import EventPayload, GameEvent
from sidecar.app import app

APP_DIR = Path(__file__).resolve().parent.parent / "app"

client = TestClient(app)


def _collected_session() -> list[GameEvent]:
    """A varied 3-color session, all balloons collected near their EV-optima.
    Timestamps are ms (performance.now), paced like a real participant so the
    session reads clean under the QC latency rules (issue 40)."""
    plan = {
        "purple": [9, 11, 10, 13, 12, 14, 11, 12, 13, 15],
        "teal": [4, 5, 6, 5, 7, 6, 5, 6, 4, 5],
        "orange": [1, 2, 3, 2, 2, 3, 1, 2, 2, 3],
    }
    events: list[GameEvent] = []
    t = 0.0
    for color, pump_seq in plan.items():
        for pumps in pump_seq:
            for _ in range(pumps):
                t += 300.0
                events.append(
                    GameEvent(timestamp=t, type="pump", payload=EventPayload(color=color))
                )
            t += 300.0
            events.append(
                GameEvent(timestamp=t, type="collect", payload=EventPayload(color=color))
            )
    return events


def _session_payload(events: list[GameEvent], **over) -> dict:
    payload = {
        "session_id": "sess-1",
        "game_type": "BART_RISK",
        "candidate_id": "cand-1",
        "events": [e.model_dump() for e in events],
    }
    payload.update(over)
    return payload


def _frozen_sidecar_bin() -> Path:
    """Locate the PyInstaller-frozen sidecar, or skip.

    The frozen binary (issue 09) is a build artifact, not produced on every test
    run. Point ``BART_SIDECAR_BIN`` at it (CI does this); otherwise we look at the
    default ``dist/bart-sidecar`` and skip when it is absent, so ``pytest -q`` stays
    fast and green without a multi-minute freeze.
    """
    env = os.environ.get("BART_SIDECAR_BIN")
    candidate = Path(env) if env else APP_DIR.parent / "dist" / "bart-sidecar"
    if not candidate.exists():
        win = candidate.with_suffix(".exe")  # Windows artifact carries .exe
        if win.exists():
            candidate = win
    if not candidate.exists() or not os.access(candidate, os.X_OK):
        pytest.skip(f"frozen sidecar not built; set BART_SIDECAR_BIN (looked at {candidate})")
    return candidate


def _run_frozen_sidecar(binary: Path) -> tuple[subprocess.Popen, int | None]:
    """Spawn the frozen sidecar and return (proc, announced port) once it prints PORT=."""
    proc = subprocess.Popen(
        [str(binary)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    port = None
    deadline = time.time() + 60  # a frozen one-file binary unpacks before it serves
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            continue
        m = re.search(r"PORT=(\d+)", line)
        if m:
            port = int(m.group(1))
            break
    # Drain the rest of stdout so a full pipe buffer never blocks the sidecar
    # (the Tauri shell drains it continuously in production, issue 11).
    threading.Thread(
        target=lambda: [None for _ in iter(proc.stdout.readline, "")], daemon=True
    ).start()
    return proc, port


def _frozen_client(timeout: float = 30.0) -> httpx.Client:
    """HTTP client for the frozen sidecar. ``trust_env=False`` bypasses any ambient
    proxy — a localhost sidecar must always be reached directly."""
    return httpx.Client(trust_env=False, timeout=timeout)


def _wait_for_healthz(
    client: httpx.Client, port: int, timeout: float = 30.0
) -> httpx.Response | None:
    """Poll /healthz on the announced port until it answers 200, or time out."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = client.get(f"http://127.0.0.1:{port}/healthz", timeout=1.0)
            if resp.status_code == 200:
                return resp
        except httpx.HTTPError:
            time.sleep(0.2)
    return None


def test_healthz_reports_ok_and_version():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "version": scoring.__version__}


def test_hello_score_entry_runs_standalone():
    """The frozen-sidecar smoke entry scores a session and prints its marker."""
    result = subprocess.run(
        [sys.executable, str(APP_DIR / "sidecar" / "hello_score.py")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "HELLO_SCORE_OK" in result.stdout
    assert "optimum=11" in result.stdout  # default purple EV-optimum


def test_launcher_binds_ephemeral_localhost_port():
    """`python -m sidecar` binds an ephemeral 127.0.0.1 port, prints it, serves."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "sidecar", "--port", "0"],
        cwd=str(APP_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        port = None
        deadline = time.time() + 30
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                continue
            m = re.search(r"PORT=(\d+)", line)
            if m:
                port = int(m.group(1))
                break
        assert port and port > 0, "launcher did not announce an ephemeral port"

        # Poll /healthz until the server is accepting connections.
        ok = False
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/healthz", timeout=1.0)
                if resp.status_code == 200:
                    ok = True
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        assert ok, "sidecar did not answer /healthz on the announced port"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_frozen_sidecar_announces_port_and_serves_healthz():
    """The PyInstaller-frozen `bart-sidecar` boots, announces its ephemeral port,
    and answers /healthz — the SPEC §9/§18 freeze contract for the full sidecar."""
    binary = _frozen_sidecar_bin()
    proc, port = _run_frozen_sidecar(binary)
    try:
        assert port and port > 0, "frozen sidecar did not announce an ephemeral port"
        with _frozen_client() as client:
            resp = _wait_for_healthz(client, port)
            assert resp is not None, "frozen sidecar did not answer /healthz on its port"
            assert resp.json() == {"status": "ok", "version": scoring.__version__}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_frozen_sidecar_score_matches_direct_scoring():
    """POST /score on the frozen `bart-sidecar` equals score_bart() directly — the
    frozen engine produces byte-identical metrics (issue 08 parity, now frozen)."""
    binary = _frozen_sidecar_bin()
    events = _collected_session()
    proc, port = _run_frozen_sidecar(binary)
    try:
        assert port and port > 0, "frozen sidecar did not announce an ephemeral port"
        with _frozen_client() as client:
            assert _wait_for_healthz(client, port) is not None, "frozen sidecar never became ready"
            resp = client.post(
                f"http://127.0.0.1:{port}/score",
                json={"session": _session_payload(events)},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["raw_metrics"] == score_bart(events).model_dump(mode="json")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_sidecar_exits_when_parent_closes_stdin():
    """With the watchdog enabled, the sidecar exits on its own when its parent (the
    Tauri shell) dies — detected as EOF on the stdin pipe the shell holds open. This
    is the no-orphan backstop for hard kills / dev Ctrl-C (issue 11); it stays off
    unless BART_SIDECAR_WATCH_PARENT is set, so ordinary runs are unaffected."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "sidecar", "--port", "0"],
        cwd=str(APP_DIR),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "BART_SIDECAR_WATCH_PARENT": "1"},
    )
    try:
        port = None
        deadline = time.time() + 30
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            if re.search(r"PORT=(\d+)", line):
                port = True
                break
        assert port, "sidecar did not start"
        proc.stdin.close()  # parent "dies" → EOF on the sidecar's stdin
        assert proc.wait(timeout=10) is not None  # exits itself, no kill needed
    finally:
        if proc.poll() is None:
            proc.kill()


def test_score_matches_direct_scoring():
    """POST /score returns the same metrics as calling score_bart directly
    (SPEC §17 acceptance), wrapped in an AssessmentResponse."""
    events = _collected_session()
    resp = client.post("/score", json={"session": _session_payload(events)})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_id"] == "sess-1"
    assert body["candidate_id"] == "cand-1"
    assert body["game_type"] == "BART_RISK"
    assert body["normalized_scores"] == []
    assert body["raw_metrics"] == score_bart(events).model_dump(mode="json")


def test_score_uses_supplied_config(tmp_path):
    """POST /score with a non-default config scores against THAT config's optima,
    not the default study — i.e. per-study scoring is wired through to score_bart."""
    events = _collected_session()
    cfg_dict = DEFAULT_TASK_CONFIG.model_dump()
    cfg_dict["colors"][0]["max_pumps"] = 64  # purple optimum shifts off the default 11
    custom = TaskConfig.model_validate(cfg_dict)

    resp = client.post(
        "/score", json={"session": _session_payload(events), "config": cfg_dict}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["raw_metrics"] == score_bart(events, custom).model_dump(mode="json")
    assert body["raw_metrics"] != score_bart(events).model_dump(mode="json")


def test_preview_returns_curves_matching_config():
    """POST /preview echoes the per-color hazard/survival/EV vectors and numeric
    optimum straight from TaskConfig.curves (SPEC §7.3)."""
    resp = client.post("/preview", json=DEFAULT_TASK_CONFIG.model_dump())
    assert resp.status_code == 200, resp.text
    curves = resp.json()["curves"]
    assert {c: curves[c]["optimum"] for c in curves} == {
        "purple": 11,
        "teal": 5,
        "orange": 2,
    }
    pc = DEFAULT_TASK_CONFIG.curves["purple"]
    assert curves["purple"]["hazard"] == list(pc.hazard)
    assert curves["purple"]["survival"] == pytest.approx(list(pc.survival))
    assert curves["purple"]["ev"] == pytest.approx(list(pc.ev))
    assert curves["purple"]["optimal_ev"] == pytest.approx(pc.optimal_ev)


def test_write_output_defaults_to_the_study_config(tmp_path, monkeypatch):
    """POST /write-output with no config persists using DEFAULT_TASK_CONFIG, so the
    Run flow (issue 11) can write a session without modeling a TaskConfig in the
    client. DEFAULT_TASK_CONFIG.output_dir == "." resolves under the spawn cwd."""
    monkeypatch.chdir(tmp_path)
    events = _collected_session()
    resp = client.post("/write-output", json={"session": _session_payload(events)})
    assert resp.status_code == 200, resp.text
    paths = resp.json()
    for key in ("events", "metrics", "config"):
        assert Path(paths[key]).exists()
    metrics = json.loads(Path(paths["metrics"]).read_text(encoding="utf-8"))
    assert metrics == score_bart(events).model_dump(mode="json")


def test_validate_config_accepts_default_and_rejects_bad():
    """POST /validate-config returns ok for a valid study and structured errors
    for an invalid one (without raising a 422)."""
    good = client.post("/validate-config", json=DEFAULT_TASK_CONFIG.model_dump())
    assert good.status_code == 200, good.text
    assert good.json() == {"ok": True, "errors": []}

    bad_cfg = DEFAULT_TASK_CONFIG.model_dump()
    bad_cfg["reward_per_pump"] = 0  # must be > 0
    bad = client.post("/validate-config", json=bad_cfg)
    assert bad.status_code == 200, bad.text
    body = bad.json()
    assert body["ok"] is False
    assert any("reward_per_pump" in e for e in body["errors"])


@pytest.mark.parametrize(
    "conditions",
    [
        ["control", ""],  # blank entry
        ["control", "   "],  # whitespace-only entry
        ["control", "control"],  # duplicate
        ["control", "x" * 65],  # unreasonably long name
    ],
)
def test_validate_config_rejects_bad_conditions(conditions):
    """Invalid `conditions` lists come back as readable structured errors naming
    the field — Study Setup shows them like every other config error (issue 37).
    The sidecar stays the sole validation authority."""
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["conditions"] = conditions
    resp = client.post("/validate-config", json=cfg)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert any("conditions" in e for e in body["errors"])


@pytest.mark.parametrize(
    "payout",
    [
        {"rate": 0, "currency": "$"},  # rate must be positive
        {"rate": -1.5, "currency": "$"},
        {"rate": 0.1, "currency": ""},  # label must not be blank
        {"rate": 0.1},  # label is required when the block exists
    ],
)
def test_validate_config_rejects_bad_payout_blocks(payout):
    """A malformed payout block comes back as readable structured errors naming
    the field (issue 41); a v1.0.0 preset without the block stays valid."""
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["payout"] = payout
    resp = client.post("/validate-config", json=cfg)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert any("payout" in e for e in body["errors"])

    cfg.pop("payout")
    assert client.post("/validate-config", json=cfg).json()["ok"] is True


@pytest.mark.parametrize("passcode", ["", "   ", "x" * 65])
def test_validate_config_rejects_unusable_exit_passcodes(passcode):
    """A blank or absurdly long exit passcode (issue 44) is a config error the
    researcher must fix in Study Setup; a valid one is accepted, and a preset
    without the field stays valid (v1.0.0 behavior)."""
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["exit_passcode"] = passcode
    body = client.post("/validate-config", json=cfg).json()
    assert body["ok"] is False
    assert any("exit_passcode" in e for e in body["errors"])

    cfg["exit_passcode"] = "1234"
    assert client.post("/validate-config", json=cfg).json()["ok"] is True

    cfg.pop("exit_passcode")
    assert client.post("/validate-config", json=cfg).json()["ok"] is True


def test_check_id_fresh_id_has_no_sessions(tmp_path):
    """POST /check-id with an ID the study has never seen reports zero existing
    sessions — the ID screen can start the run with no friction (issue 38)."""
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    resp = client.post("/check-id", json={"candidate_id": "P001", "config": cfg})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "ok": True,
        "sessions": 0,
        "error": None,
        "standalone": False,
        "station_id": None,
    }


def test_check_id_reports_how_many_sessions_an_id_already_has(tmp_path):
    """After two recorded sessions for P001, /check-id reports 2 for P001 —
    the warn-confirm's count. An ID that merely shares a prefix (P001_2) keeps
    its own tally: its sessions are not attributed to P001 (issue 38)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    for candidate in ("P001", "P001", "P001_2"):
        resp = client.post(
            "/write-output",
            json={"session": _session_payload(events, candidate_id=candidate), "config": cfg},
        )
        assert resp.status_code == 200, resp.text

    check = client.post("/check-id", json={"candidate_id": "P001", "config": cfg})
    assert check.status_code == 200, check.text
    assert check.json()["sessions"] == 2

    cousin = client.post("/check-id", json={"candidate_id": "P001_2", "config": cfg})
    assert cousin.json()["sessions"] == 1


@pytest.mark.parametrize("bad_id", ["", "   ", "004/E", "P?01", "a b"])
def test_check_id_rejects_unusable_ids_with_a_readable_message(tmp_path, bad_id):
    """Empty/whitespace and filesystem-hostile IDs come back ok=False with a
    readable message; the existing filename slug rules stay the single source
    of truth for what is allowed (issue 38)."""
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    resp = client.post("/check-id", json={"candidate_id": bad_id, "config": cfg})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is False
    assert body["sessions"] == 0
    assert body["error"]  # a human-readable reason, not a bare flag


def test_write_output_persists_session_files(tmp_path):
    """POST /write-output writes the raw events, scored metrics, and a config
    snapshot under the config's output_dir, and returns their paths (SPEC §13)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)
    resp = client.post(
        "/write-output",
        json={"session": _session_payload(events), "config": cfg},
    )
    assert resp.status_code == 200, resp.text
    paths = resp.json()

    for key in ("events", "metrics", "config"):
        p = Path(paths[key])
        assert p.exists()
        assert tmp_path in p.parents  # written under the configured output_dir

    # Raw events: one JSONL line per event.
    lines = Path(paths["events"]).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(events)

    # Metrics JSON matches the engine's direct output.
    metrics = json.loads(Path(paths["metrics"]).read_text(encoding="utf-8"))
    assert metrics == score_bart(events).model_dump(mode="json")

    # Config snapshot is the self-documenting study record.
    snapshot = json.loads(Path(paths["config"]).read_text(encoding="utf-8"))
    assert snapshot["title"] == DEFAULT_TASK_CONFIG.title


def test_write_output_appends_master_csv(tmp_path):
    """Every /write-output appends one row per session to the study's master CSV
    (``[StudyTitle]_results.csv``), creating it with a header on first
    write — researchers get an SPSS/R-ready sheet with no manual merging (issue 28)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    for candidate in ("cand-1", "cand-2"):
        resp = client.post(
            "/write-output",
            json={
                "session": _session_payload(events, candidate_id=candidate),
                "config": cfg,
            },
        )
        assert resp.status_code == 200, resp.text

    csv_path = Path(resp.json()["master_csv"])
    assert csv_path.parent == tmp_path
    assert csv_path.name.endswith("_results.csv")

    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    # One row per completed session, identified by candidate + session.
    assert [r["candidate_id"] for r in rows] == ["cand-1", "cand-2"]
    assert rows[0]["session_id"] == "sess-1"
    assert rows[0]["timestamp_utc"]

    # A study with no declared conditions keeps its v1.0.0 sheet: no
    # condition column appears (issue 37).
    assert "condition" not in rows[0]

    # Scalar metrics match the engine's scoring of the same session.
    metrics = score_bart(events, DEFAULT_TASK_CONFIG)
    assert float(rows[0]["average_pumps_adjusted"]) == pytest.approx(
        metrics.average_pumps_adjusted
    )
    assert int(rows[0]["total_balloons"]) == metrics.total_balloons

    # Per-color metrics are flattened into scalar columns (SPSS/R-friendly).
    purple = next(cm for cm in metrics.color_metrics if cm.color == "purple")
    assert float(rows[0]["purple_average_pumps"]) == pytest.approx(purple.average_pumps)
    assert rows[0]["purple_risk_profile"] == purple.risk_profile


def test_master_csv_omits_non_scalar_metric_columns(tmp_path):
    """The flat master CSV carries only scalar cells: the dict/list metric fields
    (`ev_optimal_stops`, `session_warnings`) are kept in the per-session metrics
    JSON and never stringified into the sheet as Python-repr blobs (issue 53)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    resp = client.post(
        "/write-output", json={"session": _session_payload(events), "config": cfg}
    )
    assert resp.status_code == 200, resp.text

    with Path(resp.json()["master_csv"]).open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))

    assert "ev_optimal_stops" not in header
    assert "session_warnings" not in header

    # The data isn't lost — it stays in the per-session metrics JSON.
    metrics = json.loads(Path(resp.json()["metrics"]).read_text(encoding="utf-8"))
    assert "ev_optimal_stops" in metrics
    assert "session_warnings" in metrics


def test_master_csv_has_no_dict_or_list_cells(tmp_path):
    """Durable contract: no master-CSV cell is a stringified dict/list, so the
    sheet loads cleanly in R/SPSS. Guards against any future non-scalar metric
    field leaking into the flat sheet (issue 53)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    resp = client.post(
        "/write-output", json={"session": _session_payload(events), "config": cfg}
    )
    assert resp.status_code == 200, resp.text

    with Path(resp.json()["master_csv"]).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    for key, value in rows[0].items():
        assert not value.startswith(("{", "[")), f"non-scalar cell in {key!r}: {value!r}"


def test_write_output_records_condition_in_master_csv(tmp_path):
    """For a study that declares conditions, the session's assigned condition
    lands as a `condition` column next to the identity columns (issue 37)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)
    cfg["conditions"] = ["control", "experimental"]

    resp = client.post(
        "/write-output",
        json={
            "session": _session_payload(events, condition="experimental"),
            "config": cfg,
        },
    )
    assert resp.status_code == 200, resp.text

    with Path(resp.json()["master_csv"]).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    assert header[:4] == ["timestamp_utc", "session_id", "candidate_id", "condition"]
    assert rows[0]["condition"] == "experimental"


def test_write_output_persists_session_envelope(tmp_path):
    """Each session also writes a `*_session.json` envelope — the session's
    identity (id, candidate, condition) in a per-session file, so the master
    CSV stays rebuildable from the individual files (ADR 0001) and the
    assigned condition survives outside the spreadsheet (issue 37)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)
    cfg["conditions"] = ["control", "experimental"]

    resp = client.post(
        "/write-output",
        json={"session": _session_payload(events, condition="control"), "config": cfg},
    )
    assert resp.status_code == 200, resp.text
    paths = resp.json()

    envelope_path = Path(paths["session"])
    assert envelope_path.parent == tmp_path
    assert envelope_path.name.endswith("_session.json")

    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    assert envelope["session_id"] == "sess-1"
    assert envelope["candidate_id"] == "cand-1"
    assert envelope["condition"] == "control"
    assert "events" not in envelope  # raw telemetry stays in the .jsonl


def test_adding_conditions_mid_study_migrates_master_csv(tmp_path):
    """A lab adds conditions to a running study: the pre-upgrade master CSV has
    no `condition` column. The next session migrates the sheet via the
    header-versioned writer (issue 36) — old rows get an honest blank, the new
    row carries its assignment, and a backup appears (issue 37)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    first = client.post(
        "/write-output", json={"session": _session_payload(events), "config": cfg}
    )
    assert first.status_code == 200, first.text

    cfg["conditions"] = ["control", "experimental"]
    second = client.post(
        "/write-output",
        json={
            "session": _session_payload(
                events, candidate_id="cand-2", condition="control"
            ),
            "config": cfg,
        },
    )
    assert second.status_code == 200, second.text

    with Path(second.json()["master_csv"]).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["condition"] for r in rows] == ["", "control"]
    assert [r["candidate_id"] for r in rows] == ["cand-1", "cand-2"]
    # One backup for the master CSV (the trials CSV migrates separately, with
    # its own backup — issue 39).
    assert len(list(tmp_path.glob("*_results_backup_*.csv"))) == 1


def test_duplicate_acknowledgment_is_recorded_in_the_session_envelope(tmp_path):
    """When the RA continues past the duplicate-ID warning, the acknowledgment
    rides the session and is stamped into `*_session.json` — the accident stays
    visible in the data (issue 38). Sessions without a warning record False."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    plain = client.post(
        "/write-output", json={"session": _session_payload(events), "config": cfg}
    )
    assert plain.status_code == 200, plain.text
    envelope = json.loads(Path(plain.json()["session"]).read_text(encoding="utf-8"))
    assert envelope["duplicate_acknowledged"] is False

    acknowledged = client.post(
        "/write-output",
        json={
            "session": _session_payload(events, duplicate_acknowledged=True),
            "config": cfg,
        },
    )
    assert acknowledged.status_code == 200, acknowledged.text
    envelope = json.loads(
        Path(acknowledged.json()["session"]).read_text(encoding="utf-8")
    )
    assert envelope["duplicate_acknowledged"] is True


def test_write_output_appends_trials_csv_long_format(tmp_path):
    """Every /write-output appends one row per trial to the study-wide
    `[StudyTitle]_trials.csv` — the long-format table mixed-model analyses
    consume (issue 39). Two 30-trial sessions → 60 data rows under one header,
    in session order; identity columns tie each row to its session, and a
    study without conditions gets no condition column (same rule as the
    Master CSV)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    for candidate in ("cand-1", "cand-2"):
        resp = client.post(
            "/write-output",
            json={
                "session": _session_payload(events, candidate_id=candidate),
                "config": cfg,
            },
        )
        assert resp.status_code == 200, resp.text

    trials_path = Path(resp.json()["trials_csv"])
    assert trials_path.parent == tmp_path
    assert trials_path.name.endswith("_trials.csv")

    with trials_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 60  # 30 trials × 2 sessions, one header
    assert [r["candidate_id"] for r in rows] == ["cand-1"] * 30 + ["cand-2"] * 30
    assert [int(r["trial"]) for r in rows] == list(range(1, 31)) * 2
    assert rows[0]["session_id"] == "sess-1"
    assert rows[0]["timestamp_utc"]
    assert "condition" not in rows[0]

    # Behavior columns match the engine's own trial table (same source).
    engine_trials = trial_table(events, DEFAULT_TASK_CONFIG)
    assert rows[0]["balloon_color"] == engine_trials[0].balloon_color
    assert rows[0]["hazard_family"] == "dynamic"
    assert int(rows[0]["pumps"]) == engine_trials[0].pumps
    assert {r["outcome"] for r in rows} == {"collected"}  # all-collected session
    assert float(rows[0]["trial_earnings"]) == pytest.approx(
        engine_trials[0].trial_earnings
    )


def test_trials_csv_carries_condition_for_conditioned_studies(tmp_path):
    """A study with declared conditions stamps the session's assignment on
    every trial row — the design column between-subject models group by
    (issues 37 + 39)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)
    cfg["conditions"] = ["control", "experimental"]

    resp = client.post(
        "/write-output",
        json={
            "session": _session_payload(events, condition="experimental"),
            "config": cfg,
        },
    )
    assert resp.status_code == 200, resp.text

    with Path(resp.json()["trials_csv"]).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    assert header[:4] == ["timestamp_utc", "session_id", "candidate_id", "condition"]
    assert {r["condition"] for r in rows} == {"experimental"}


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not make a file unwritable on Windows"
)
def test_locked_trials_csv_never_loses_the_session_rows(tmp_path):
    """The trials CSV plays by the issue-36 rules: locked (e.g. open in Excel)
    → the session's 30 trial rows land in a timestamped sibling file with a
    readable warning, and the master CSV append is unaffected (issue 39)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    first = client.post(
        "/write-output", json={"session": _session_payload(events), "config": cfg}
    )
    assert first.status_code == 200, first.text
    trials_path = Path(first.json()["trials_csv"])

    trials_path.chmod(0o444)
    try:
        second = client.post(
            "/write-output",
            json={
                "session": _session_payload(events, candidate_id="cand-2"),
                "config": cfg,
            },
        )
    finally:
        trials_path.chmod(0o644)

    assert second.status_code == 200, second.text
    body = second.json()
    sibling = Path(body["trials_csv"])
    assert sibling != trials_path
    assert "_unmerged_" in sibling.name
    assert body["warnings"] and sibling.name in body["warnings"][0]
    # The master CSV kept both sessions; the sibling holds all 30 trial rows.
    assert Path(body["master_csv"]) == Path(first.json()["master_csv"])
    with sibling.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 30
    assert {r["candidate_id"] for r in rows} == {"cand-2"}


def test_flagged_session_lands_in_master_csv_with_qc_columns(tmp_path):
    """QC flags annotate, never exclude (issue 40): a session that trips the
    fast-response rule still writes all four session files and its Master CSV
    row — with the flag, the counts, and the thresholds it was judged against
    visible in the columns."""
    events = _collected_session()
    # Append one hurried trial: pumps 50 ms apart (default threshold: 100 ms).
    t = events[-1].timestamp
    hurried = [
        GameEvent(timestamp=t + 50.0 * (i + 1), type="pump", payload=EventPayload(color="teal"))
        for i in range(3)
    ]
    hurried.append(
        GameEvent(timestamp=t + 400.0, type="collect", payload=EventPayload(color="teal"))
    )
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    resp = client.post(
        "/write-output",
        json={"session": _session_payload(events + hurried), "config": cfg},
    )
    assert resp.status_code == 200, resp.text
    paths = resp.json()
    for key in ("events", "metrics", "config", "session"):
        assert Path(paths[key]).exists()

    with Path(paths["master_csv"]).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1  # flagged, not excluded
    assert rows[0]["qc_flagged"] == "True"
    assert int(rows[0]["qc_fast_response_trials"]) == 1
    assert float(rows[0]["qc_fast_response_ms"]) == 100.0
    assert int(rows[0]["qc_zero_pump_streak_threshold"]) == 5

    metrics = json.loads(Path(paths["metrics"]).read_text(encoding="utf-8"))
    assert metrics["qc_flagged"] is True


def test_payout_lands_in_master_csv_and_metrics_only_when_configured(tmp_path):
    """A payout study writes the owed amount + currency to the metrics JSON and
    as Master CSV columns; a study without a payout block keeps its column set
    unchanged — the same present-only-when-configured rule as `condition`
    (issues 37/41). Task-internal earnings columns are untouched either way."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    plain = client.post(
        "/write-output", json={"session": _session_payload(events), "config": cfg}
    )
    assert plain.status_code == 200, plain.text
    with Path(plain.json()["master_csv"]).open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))
    assert "payout_amount" not in row and "payout_currency" not in row
    assert row["money_collected"]  # task-internal earnings unchanged

    paid_cfg = {**cfg, "title": "Paid study", "payout": {"rate": 0.1, "currency": "₺"}}
    paid = client.post(
        "/write-output", json={"session": _session_payload(events), "config": paid_cfg}
    )
    assert paid.status_code == 200, paid.text
    metrics = json.loads(Path(paid.json()["metrics"]).read_text(encoding="utf-8"))
    with Path(paid.json()["master_csv"]).open(newline="", encoding="utf-8") as fh:
        paid_row = next(csv.DictReader(fh))
    assert float(paid_row["payout_amount"]) == metrics["payout_amount"]
    assert paid_row["payout_currency"] == "₺"
    assert metrics["payout_amount"] == pytest.approx(
        round(float(paid_row["money_collected"]) * 0.1, 2)
    )


def test_write_output_migrates_master_csv_with_older_header(tmp_path):
    """A lab upgrades the app mid-study: the master CSV on disk has last
    version's (narrower) header. /write-output backs the file up, migrates it
    to the current header — pre-upgrade rows keep their values with blanks in
    new columns — appends the session, and surfaces a warning (issue 36)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    first = client.post(
        "/write-output", json={"session": _session_payload(events), "config": cfg}
    )
    assert first.status_code == 200, first.text
    csv_path = Path(first.json()["master_csv"])

    # Rewrite the file as an older app version would have left it: same rows,
    # one column short of the current schema.
    with csv_path.open(newline="", encoding="utf-8") as fh:
        old_rows = list(csv.DictReader(fh))
    dropped = list(old_rows[0])[-1]
    kept = [c for c in old_rows[0] if c != dropped]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=kept, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(old_rows)

    second = client.post(
        "/write-output",
        json={"session": _session_payload(events, candidate_id="cand-2"), "config": cfg},
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert Path(body["master_csv"]) == csv_path
    assert body["warnings"], "the migration should be surfaced to the researcher"

    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["candidate_id"] for r in rows] == ["cand-1", "cand-2"]
    assert rows[0][dropped] == ""  # honest blank in the pre-upgrade row
    assert rows[1][dropped] != ""

    backups = list(tmp_path.glob("*_backup_*.csv"))
    assert len(backups) == 1


@pytest.mark.skipif(
    sys.platform == "win32", reason="chmod does not make a file unwritable on Windows"
)
def test_write_output_locked_master_csv_never_loses_the_session(tmp_path):
    """The master CSV is locked (e.g. open in Excel): the session row lands in
    a timestamped sibling file, the response's master_csv points at it, and a
    readable warning explains what happened — no exception (issue 36)."""
    events = _collected_session()
    cfg = DEFAULT_TASK_CONFIG.model_dump()
    cfg["output_dir"] = str(tmp_path)

    first = client.post(
        "/write-output", json={"session": _session_payload(events), "config": cfg}
    )
    assert first.status_code == 200, first.text
    csv_path = Path(first.json()["master_csv"])

    csv_path.chmod(0o444)
    try:
        second = client.post(
            "/write-output",
            json={
                "session": _session_payload(events, candidate_id="cand-2"),
                "config": cfg,
            },
        )
    finally:
        csv_path.chmod(0o644)

    assert second.status_code == 200, second.text
    body = second.json()
    sibling = Path(body["master_csv"])
    assert sibling != csv_path
    assert body["warnings"] and sibling.name in body["warnings"][0]

    with sibling.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["candidate_id"] for r in rows] == ["cand-2"]


def test_cors_preflight_returns_allow_origin():
    """An OPTIONS preflight to any endpoint returns Access-Control-Allow-Origin,
    so cross-origin fetches from the webview / dev browser succeed (issue 22)."""
    resp = client.options(
        "/preview",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200, resp.text
    assert "access-control-allow-origin" in resp.headers


def test_cors_header_on_post_response():
    """A regular POST from a cross-origin browser carries the allow-origin header
    on the response, so the browser hands the body to fetch() (issue 22)."""
    resp = client.post(
        "/preview",
        json=DEFAULT_TASK_CONFIG.model_dump(),
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 200
    assert "access-control-allow-origin" in resp.headers


