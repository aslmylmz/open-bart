# 10 — Tauri v2 shell scaffold: window + offline CSP + capabilities

**Phase 2 · SPEC §10, §12 · depends on: 04 (Phase 0 done); parallel to 09**

## Context

Stand up the **Tauri v2** Rust shell so `tauri dev` opens a native window that loads
the existing Vite SPA ([app/src/](../../../app/src/)), with the strict offline
posture in place from the start: a CSP that blocks all remote origins and a minimal
capability surface. Keep Rust **thin** — this issue is the shell skeleton only. The
sidecar lifecycle + port handoff (11) and the study.json + kiosk plumbing (12) land
next; the Study-Setup UI is Phase 3.

Toolchain note: the Rust/Tauri toolchain is not yet installed — this issue installs
`rustup` (stable `aarch64-apple-darwin`) and adds the Tauri CLI as an `app/`
devDependency (run via `npm run tauri`, no global cargo install).

## Scope

- [ ] Install `rustup` (stable `aarch64-apple-darwin`); verify Xcode CLT
  (`xcode-select -p`).
- [ ] `app/src-tauri/Cargo.toml` (new) — `tauri` v2 + `tauri-build`;
  `tauri-plugin-dialog`, `tauri-plugin-fs`; `serde`/`serde_json`; `ureq` (sync
  health-check client, used by 11). `app/src-tauri/build.rs` → `tauri_build::build()`.
- [ ] `app/src-tauri/tauri.conf.json` (new) — `beforeDevCommand="npm run dev"`,
  `devUrl="http://localhost:5173"`, `beforeBuildCommand="npm run build"`,
  `frontendDist="../dist"`; window title; **`app.security.csp`** =
  `default-src 'self'; connect-src 'self' http://127.0.0.1:* http://localhost:*
  ws://localhost:*; img-src 'self' data:; style-src 'self' 'unsafe-inline';
  script-src 'self'` (localhost/127.0.0.1 only — sidecar + vite HMR; no remote
  origins); `bundle.externalBin=["binaries/bart-sidecar"]`; identifier e.g.
  `com.metu.bart`; macOS + Windows targets.
- [ ] `app/src-tauri/src/main.rs` + `src/lib.rs` (new) — minimal `Builder` that
  registers the `dialog`/`fs` plugins and opens the default window. (Commands +
  lifecycle land in 11.)
- [ ] `app/src-tauri/capabilities/default.json` (new) — core defaults +
  `dialog:allow-open`/`allow-save` + scoped `fs:allow-read-text-file`/
  `allow-write-text-file`. **No shell permissions.**
- [ ] App icons (via `tauri icon` or a checked-in 512px PNG).
- [ ] [app/package.json](../../../app/package.json): add `@tauri-apps/api@^2`,
  `@tauri-apps/plugin-dialog`, `@tauri-apps/plugin-fs` (deps), `@tauri-apps/cli@^2`
  (devDep), and a `"tauri": "tauri"` script.
- [ ] [app/vite.config.ts](../../../app/vite.config.ts): `clearScreen: false`,
  `server: { port: 5173, strictPort: true }`, `envPrefix: ['VITE_','TAURI_']`; keep
  the existing vitest block untouched.

## Acceptance

- `npm run tauri dev` opens a native window rendering the BART SPA on macOS.
- The CSP contains **no remote origins** — only `localhost`/`127.0.0.1` (and
  `ws://localhost` for HMR) in `connect-src`.
- The Rust crate compiles; `npm test` (7), `tsc --noEmit`, and `vite build` stay
  green.
