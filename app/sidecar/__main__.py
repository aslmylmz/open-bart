"""Launch the sidecar on 127.0.0.1 / ephemeral port and announce the port.

Run with ``python -m sidecar`` (with ``app/`` on the path). The Tauri shell
(Phase 2) spawns this, reads ``PORT=<n>`` from stdout, then health-checks
``/healthz``. Binding the socket here (rather than letting uvicorn pick the port)
lets us learn the ephemeral port *before* the server starts, so the port handoff
is race-free.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading

import uvicorn

from sidecar.app import app


def _exit_when_parent_closes_stdin() -> None:
    """Exit if the parent (the Tauri shell) dies. The shell holds our stdin open as a
    liveness pipe; EOF on it means the parent is gone, so we shut down rather than
    orphan. Enabled only via ``BART_SIDECAR_WATCH_PARENT`` so tests and direct runs
    (which supply no liveness pipe) are unaffected. Backstop for hard kills / dev
    Ctrl-C; the shell still kills us directly on a graceful exit.
    """
    stream = sys.stdin
    if stream is None:  # nothing to watch (e.g. detached) — leave the sidecar running
        return
    try:
        stream.read()  # blocks until the parent closes the pipe (EOF)
    except Exception:
        pass
    os._exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="BART offline scoring sidecar")
    parser.add_argument("--host", default="127.0.0.1", help="bind host (localhost only)")
    parser.add_argument("--port", type=int, default=0, help="bind port (0 = ephemeral)")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))
    port = sock.getsockname()[1]
    print(f"PORT={port}", flush=True)

    if os.environ.get("BART_SIDECAR_WATCH_PARENT"):
        threading.Thread(target=_exit_when_parent_closes_stdin, daemon=True).start()

    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
