# 06 — Sidecar skeleton: FastAPI `/healthz` + launcher + hello-score

**Phase 1 · SPEC §9, §10 · depends on: 05**

## Context

Stand up the FastAPI app shell that wraps the installed `scoring` package. Keep it
minimal: just `/healthz`, a launcher that binds `127.0.0.1` on an **ephemeral** port
and prints the chosen port (the Rust layer will read it in Phase 2), and a tiny
**hello-score** entrypoint used to de-risk PyInstaller in issue 07. No real scoring
endpoints yet — those land in issue 08, after the freeze is proven.

The sidecar lives under `app/sidecar/` and is **not** pip-installed (pyproject ships
only `scoring*`); PyInstaller freezes it from source and it imports the installed
`scoring` package at runtime — no code duplication.

## Scope

- [ ] [pyproject.toml](../../../pyproject.toml): add optional extras
  `sidecar = ["fastapi", "uvicorn"]` and `build = ["pyinstaller"]`.
- [ ] `app/sidecar/__init__.py`, `app/sidecar/app.py` — `FastAPI` app with
  `GET /healthz` → `{"status": "ok", "version": scoring.__version__}`.
- [ ] `app/sidecar/__main__.py` — uvicorn launcher: `--host 127.0.0.1`, `--port 0`
  (ephemeral) by default; resolve the bound port and print `PORT=<n>` to stdout so the
  shell can capture it.
- [ ] `app/sidecar/hello_score.py` — imports `scoring`, scores a tiny fixed session
  (or builds a `balloon_curve`), prints a deterministic line (e.g.
  `HELLO_SCORE_OK optimum=11`), exits 0. This is the artifact frozen first.
- [ ] [conftest.py](../../../conftest.py): also add `app/` to `sys.path` so tests can
  `from sidecar.app import app`.
- [ ] `tests/test_sidecar.py` — `TestClient` asserts `/healthz` returns `ok` + version.

## Acceptance

- `GET /healthz` returns `{"status":"ok","version": …}` via `TestClient`.
- `python app/sidecar/hello_score.py` prints the deterministic line and exits 0.
- The launcher binds an ephemeral localhost port and prints it.
- 54 engine tests + the new sidecar test pass.
