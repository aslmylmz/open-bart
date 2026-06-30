"""Tests for the offline scoring sidecar (app/sidecar).

The sidecar wraps the installed ``scoring`` package behind a localhost-only
FastAPI app (SPEC §9/§10). These tests exercise it through its public surface:
the HTTP endpoints and the frozen-entry / launcher scripts.
"""

from __future__ import annotations

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
from scoring.bart import score_bart
from scoring.config import DEFAULT_TASK_CONFIG
from scoring.schemas import EventPayload, GameEvent
from sidecar.app import app

APP_DIR = Path(__file__).resolve().parent.parent / "app"

client = TestClient(app)


def _collected_session() -> list[GameEvent]:
    """A varied 3-color session, all balloons collected near their EV-optima."""
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
                t += 1.0
                events.append(
                    GameEvent(timestamp=t, type="pump", payload=EventPayload(color=color))
                )
            t += 1.0
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
                f"http://127.0.0.1:{port}/score", json=_session_payload(events)
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
    resp = client.post("/score", json=_session_payload(events))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["session_id"] == "sess-1"
    assert body["candidate_id"] == "cand-1"
    assert body["game_type"] == "BART_RISK"
    assert body["normalized_scores"] == []
    assert body["raw_metrics"] == score_bart(events).model_dump(mode="json")


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
