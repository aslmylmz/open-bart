# 35 — Stale-bundle guard: sidecar version handshake + readable 422s

**Bugfix · depends on: none**

Status: ready-for-agent

## Context

A local `tauri build` bundles whatever frozen sidecar sits in
`app/src-tauri/binaries/` — a manual, gitignored artifact. A stale binary
(frozen before the hazard nomenclature update) boots fine, then rejects every
request: the frontend sends `family: "dynamic"` and the old engine's
discriminated union expects `'linear'/'uniform'/...`, so `/preview`,
`/validate-config`, `/score`, and `/write-output` all return 422 — the whole
chain fails.

Diagnosed 2026-07-02 with a differential repro (same `DEFAULT_STUDY` payload,
stale binary → 422 `union_tag_invalid` ×3, current code → 200). Two defects
beneath the symptom:

1. **No version handshake.** `/healthz` already reports the sidecar version
   and the shell polls it at boot, but nothing compared it to the app version;
   a mismatched bundle failed far downstream with no explanation.
2. **Unreadable validation errors.** `postJson` passed FastAPI's 422 `detail`
   (an array of objects) straight to `new Error(...)`, rendering the EV
   Preview banner as `[object Object],[object Object],[object Object]` and
   hiding the actual message.

## Scope

- [ ] `postJson` formats `detail` arrays as `path.to.field: message` lines
      (readable banner; regression test in `api.test.ts`).
- [ ] `fetchHealth()` in the API client; `VersionGuard` component compares the
      sidecar's `/healthz` version against `__APP_VERSION__` (vite `define`
      from package.json) at boot and hard-blocks with a researcher-facing
      explanation on mismatch. Unreachable sidecars do not block (RunFlow owns
      connection errors); tests in `VersionGuard.test.tsx`.
- [ ] Refresh `app/src-tauri/binaries/bart-sidecar-aarch64-apple-darwin` from
      the current freeze so local bundles ship the matching engine.

## Acceptance

- The stale-bundle repro (`/preview` with the default study) returns 200
  against the refreshed bundled binary.
- A deliberately mismatched sidecar version renders the block screen naming
  both versions instead of `[object Object]` banners.
- 422s anywhere in the chain surface per-field messages.
- `npm test`, `tsc`, `vite build`, `pytest` stay green.

## Comments

**2026-07-02 — diagnosed and fixed.** Root cause confirmed by differential
loop; the local-build gotcha (re-freeze + copy before `tauri build`) is also
documented in the VersionGuard's block screen itself and in issue 34's notes
(editable install must be compat-mode for PyInstaller to see `scoring`).
