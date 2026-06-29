# 09 — Full frozen sidecar (`bart-sidecar`): PyInstaller spec + macOS freeze

**Phase 2 · SPEC §9, §18 · depends on: 08 (Phase 1 done)**

## Context

Phase 1 froze a tiny **hello-score** binary to prove numpy bundles and runs
(SPEC §18 risk #1). Phase 2 needs the **real** sidecar — the full FastAPI app plus
uvicorn — frozen into a single binary the Tauri shell can bundle via `externalBin`.
This issue retires the "PyInstaller bundling FastAPI/uvicorn on a per-OS binary"
risk **locally on macOS** before any Rust is wired, mirroring the de-risk-first
sequencing of issues 05/07.

The launcher already exists: [app/sidecar/\_\_main\_\_.py](../../../app/sidecar/__main__.py)
binds `127.0.0.1` on an ephemeral port, prints `PORT=<n>` to stdout, then serves
uvicorn. We freeze that entrypoint. The Windows freeze is reproduced by CI later
(Phase 4); this issue only verifies macOS.

## Scope

- [ ] `app/sidecar/sidecar.spec` (new) — mirror
  [hello-score.spec](../../../app/sidecar/hello-score.spec): script =
  `__main__.py`; `name="bart-sidecar"`; `pathex` includes `app/` so the `sidecar`
  package resolves during analysis; `hiddenimports = collect_submodules("scoring") +
  collect_submodules("sidecar") + collect_submodules("uvicorn")`; keep
  `excludes=["scipy", "matplotlib", "pandas"]`. If the frozen binary fails to boot,
  add the known uvicorn gotchas (`uvicorn.lifespan.*`, `uvicorn.protocols.*`,
  `uvicorn.loops.*`, `anyio`, `h11`).
- [ ] Build on macOS: `pyinstaller app/sidecar/sidecar.spec` → `dist/bart-sidecar`.
- [ ] [.gitignore](../../../.gitignore): ignore `app/src-tauri/binaries/`,
  `app/src-tauri/target/`, `app/src-tauri/gen/` — the frozen binary is a build
  artifact (CI reproduces it in Phase 4), not committed.

## Acceptance

- `pyinstaller app/sidecar/sidecar.spec` produces a one-file `bart-sidecar` with no
  scipy / matplotlib / pandas pulled in.
- Running `dist/bart-sidecar` prints `PORT=<n>` and serves; `GET /healthz` on that
  port returns `{"status":"ok","version": …}`.
- Smoke: `POST /score` on the frozen binary matches `scoring.score_bart` directly
  (the issue-08 acceptance, now frozen).
- The engine + sidecar test suites stay green.
