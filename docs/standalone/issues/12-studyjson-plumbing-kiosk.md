# 12 — study.json dialog/fs plumbing (UI deferred) + kiosk/fullscreen

**Phase 2 · SPEC §10 · depends on: 10**

## Context

Completes SPEC §10's Tauri responsibility list. Wires the **native load/save
plumbing** for `study.json` (the serialized `TaskConfig`) with the minimal
`dialog`/`fs` capabilities from issue 10, and adds a **kiosk/fullscreen** run mode
for labs. The Study-Setup UI that produces and consumes `study.json` is **Phase 3** —
this issue only stands up the seam so Phase 3 can call into it (decision taken this
session: *plumbing now, UI in Phase 3*).

## Scope

- [ ] Native file-dialog plumbing: a thin `load_study` / `save_study` path (a Rust
  command using `tauri-plugin-dialog` + `tauri-plugin-fs`, or direct JS plugin
  calls) that reads/writes a `study.json` text file at a user-chosen path. **No
  config-editing UI.**
- [ ] Confirm `app/src-tauri/capabilities/default.json` scopes stay minimal
  (`dialog` open/save + `fs` read/write text only; no shell, no internet HTTP).
- [ ] Kiosk/fullscreen: a `set_fullscreen` Tauri command (and/or an `F11`
  accelerator) toggling the window fullscreen; default windowed.
- [ ] (Optional) a tiny dev affordance to exercise the load/save path manually,
  ignored once Phase 3's Study Setup wires the real UI.

## Acceptance

- A `study.json` can be saved to and loaded from a user-chosen path via the native
  dialog (verified manually or via a thin command test).
- The fullscreen/kiosk toggle works in `tauri dev`.
- The capability surface stays minimal (`dialog` + `fs` only).
- `npm test`, `tsc --noEmit`, and `vite build` stay green.
