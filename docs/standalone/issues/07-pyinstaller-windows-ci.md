# 07 — PyInstaller freeze + Windows CI (the de-risk gate)

**Phase 1 · SPEC §9, §12, §18 · depends on: 06**

## Context

This is the **gate** for the rest of Phase 1: prove a PyInstaller-frozen sidecar runs
on **Windows** before building any real endpoints or UI (SPEC §9, §18). Neither
PyInstaller nor Tauri cross-compiles from macOS, so Windows artifacts come from CI
(SPEC §12). We freeze the tiny `hello_score.py` from issue 06 first — if numpy freezes
and runs frozen on Windows, the heavy risk is retired.

## Scope

- [ ] `app/sidecar/hello-score.spec` (or a documented PyInstaller CLI invocation) —
  one-file freeze of `app/sidecar/hello_score.py`, with `scoring` collected.
- [ ] `.github/workflows/sidecar-windows.yml`:
  - `runs-on: windows-latest`; trigger on push to `feat/standalone-instrument`
    (paths: `app/sidecar/**`, `scoring/**`, `pyproject.toml`, the workflow) +
    `workflow_dispatch`.
  - `actions/setup-python@v5` (3.12), `pip install -e ".[sidecar,build]"`.
  - Run `pytest` on Windows (confirms the scipy-free engine is cross-platform).
  - `pyinstaller` the hello-score; **run the produced `.exe`** and assert it exits 0
    and prints the deterministic line from issue 06.
  - `actions/upload-artifact@v4` with the frozen exe (this is the open progress record).

## Acceptance

- The workflow is **green** on `windows-latest`.
- The frozen `hello-score.exe` runs on Windows and prints the expected line.
- `pytest` passes on Windows.
- The frozen exe is uploaded as a CI artifact.

> Verified in CI only — macOS dev machines cannot produce/run the Windows binary
> (SPEC §12). Locally, confirm the freeze command succeeds for the **macOS** target.
