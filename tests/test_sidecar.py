"""Tests for the offline scoring sidecar (app/sidecar).

The sidecar wraps the installed ``scoring`` package behind a localhost-only
FastAPI app (SPEC §9/§10). These tests exercise it through its public surface:
the HTTP endpoints and the frozen-entry / launcher scripts.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

import scoring
from sidecar.app import app

APP_DIR = Path(__file__).resolve().parent.parent / "app"

client = TestClient(app)


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
