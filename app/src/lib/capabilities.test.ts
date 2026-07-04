import { describe, expect, it } from "vitest";

import capability from "../../src-tauri/capabilities/default.json";

// The kiosk lock (`setKioskLock`) and the F11 toggle (`toggleFullscreen`) in
// lib/desktop.ts call the Tauri window setters `setFullscreen` / `setAlwaysOnTop`.
// In Tauri v2 every core command is gated by the capability ACL; if a setter is
// not granted the call is rejected at runtime and the callers swallow it
// (`.catch(() => {})`), so the window lock silently no-ops in a real build. The
// webview tests mock lib/desktop and cannot see the ACL, so this guard reads the
// shipped capability set directly (issue 64 / register F15).
const permissions = capability.permissions as string[];

describe("Tauri capability set (issue 64)", () => {
  it("grants the window setters the kiosk lock and F11 toggle invoke", () => {
    expect(permissions).toContain("core:window:allow-set-fullscreen");
    expect(permissions).toContain("core:window:allow-set-always-on-top");
  });
});
