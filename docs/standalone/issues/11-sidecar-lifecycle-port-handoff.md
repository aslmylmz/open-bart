# 11 — Sidecar lifecycle + runtime port handoff + session persistence

**Phase 2 · SPEC §9, §10, §13, §17 · depends on: 10 (09 for the release verify)**

## Context

The headline Phase 2 slice — it satisfies the SPEC §17 acceptance. The Rust shell
**spawns** the sidecar, reads its `PORT=<n>` handshake, **health-checks** `/healthz`,
and **kills** it on exit; it hands the ephemeral port to the webview via a
`get_sidecar_url` command so the frontend stops relying on the build-time
`VITE_API_URL` (default `:8000`); and a finished session is **persisted** locally via
the sidecar's `/write-output`. Today
[BartGame.tsx](../../../app/src/BartGame.tsx) posts to `/score` and only *displays*
results — nothing is written to disk.

Spawn uses `std::process::Command` directly (not the shell plugin) for full control
of the stdout handshake, `PYTHONPATH`/cwd, and kill-on-exit. Dev spawns
`python3 -m sidecar`; release spawns the bundled `bart-sidecar` (from issue 09).

## Scope

- [ ] `app/src-tauri/src/lib.rs` — in `setup()`, spawn the sidecar with piped
  stdout: dev (`#[cfg(debug_assertions)]`) → `python3 -m sidecar` with
  `PYTHONPATH=<app/>` and `cwd=<sessions dir>`; release → `<current_exe dir>/
  bart-sidecar` with `cwd=<sessions dir>`. Read stdout until the `PORT=<n>` line,
  then poll `GET /healthz` (~50×100ms via `ureq`) until ok. Store
  `SidecarHandle { child, base_url }` in managed `State`; log the sessions dir. The
  `cwd` is a created local **sessions dir** so the default config's `output_dir="."`
  (see [task_config.py](../../../scoring/config/task_config.py)) lands predictably.
- [ ] Kill the child on exit — `Drop` on the handle and/or `RunEvent::ExitRequested`.
- [ ] `#[tauri::command] get_sidecar_url(state) -> String` returns `base_url`.
- [ ] [app/src/lib/api.ts](../../../app/src/lib/api.ts): module-level override +
  `setApiBaseUrl(url)`; `resolveApiUrl()` = override ?? env ?? `localhost:8000`;
  async `initSidecarUrl()` that, when `isTauri()`, `invoke('get_sidecar_url')` →
  `setApiBaseUrl`; `persistSession(payload)` → `POST /write-output` with
  `{ session: payload }`.
- [ ] [app/src/main.tsx](../../../app/src/main.tsx): `await initSidecarUrl()` before
  `createRoot(...).render(...)` so the first `/score` uses the right port.
- [ ] [app/src/BartGame.tsx](../../../app/src/BartGame.tsx): after the existing
  `submitSession` (≈line 295), best-effort `persistSession(payload)` (log the
  returned file paths).
- [ ] [app/sidecar/models.py](../../../app/sidecar/models.py):
  `WriteOutputRequest.config: TaskConfig | None = None`.
  [app/sidecar/app.py](../../../app/sidecar/app.py): `write_output` uses
  `req.config or DEFAULT_TASK_CONFIG` (mirrors how `/score` already defaults).
- [ ] Tests: [api.test.ts](../../../app/src/lib/api.test.ts) — `setApiBaseUrl`
  override wins and `resolveApiUrl` still defaults without override/env;
  `tests/test_sidecar.py` — `/write-output` with `config` omitted writes the 3 files
  using `DEFAULT_TASK_CONFIG` (`monkeypatch.chdir(tmp_path)` so `output_dir="."`
  resolves to a temp dir).

## Acceptance

- **`tauri dev` (macOS): a full session runs end-to-end**; the sessions dir gets
  `*_events.jsonl`, `*_metrics.json`, `*_config.json`; displayed metrics match a
  direct `score_bart` run.
- **Zero network:** CSP has no remote origins; the sidecar is `127.0.0.1` only
  (spot-check `lsof -i -nP` shows localhost only during a run).
- The sidecar is killed when the app exits (no orphan process).
- **Release verify (uses issue 09's binary):** `npm run tauri build` bundles
  `bart-sidecar` via `externalBin`; the built `.app` runs a session via the release
  spawn path.
- `npm test`, `tsc --noEmit`, `vite build`, and `pytest` all stay green.
