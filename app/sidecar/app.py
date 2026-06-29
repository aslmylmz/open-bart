"""The FastAPI app for the offline scoring sidecar.

This module only defines the app and its routes. The launcher in ``__main__``
binds it to ``127.0.0.1`` on an ephemeral port and hands that port to the Tauri
shell (SPEC §9/§10). For Phase 1 the only route is the ``/healthz`` liveness
probe; the scoring/preview/output endpoints land in issue 08.
"""

from __future__ import annotations

from fastapi import FastAPI

from scoring import __version__

app = FastAPI(title="BART scoring sidecar", version=__version__)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe the shell polls before routing sessions to the sidecar."""
    return {"status": "ok", "version": __version__}
