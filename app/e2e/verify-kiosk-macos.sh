#!/usr/bin/env bash
#
# verify-kiosk-macos.sh — objective macOS QA for the kiosk lock (issue 60 / register F11).
#
# Why this exists, and why it is screenshot-based rather than a headless boolean:
#   - The kiosk lock's fullscreen + always-on-top only exist in a real Tauri window
#     (issue 44); the webview vitest suite mocks lib/desktop, so it cannot see them.
#   - tauri-driver (the usual Tauri E2E path) supports only Windows/Linux — macOS
#     WKWebView exposes no WebDriver interface, so it cannot drive this on a Mac.
#   - macOS moves a *programmatically* fullscreened window into its own Space, which
#     makes AXFullScreen / window enumeration unreliable (reads flip-flop or throw
#     "Invalid index"). The one dependable observable is a screenshot: a real
#     fullscreen kiosk covers the whole display with NO dock, menu bar, or other
#     windows visible.
#
# So this script drives the app into a passcode-locked run and captures before/after
# screenshots for review. "Fullscreen engaged" = the locked capture shows only the
# participant screen — no dock, no menu bar, no other apps.
#
# Prerequisites (one-time, System Settings → Privacy & Security):
#   - Accessibility     → enable your terminal / host app (to activate the window).
#   - Screen Recording  → enable your terminal / host app (for screencapture).
#   - The app running under a real Tauri build:
#       cd app && BART_SIDECAR_PYTHON=<python-with-uvicorn> npm run tauri dev
#   - A study with an Exit passcode set, and the participant flow started (the lock
#     engages the moment the run begins — at the "Before you begin" screen).
#
# Usage:  app/e2e/verify-kiosk-macos.sh [output-dir]
# Exit:   0 if the app window left the active Space while locked (fullscreen signal);
#         non-zero otherwise. Always review the captured PNGs — they are the real proof.

set -euo pipefail

PROC="bart-instrument"          # dev binary; a bundled build shows as "BART Instrument"
OUT="${1:-$(mktemp -d)}"
mkdir -p "$OUT"

app_windows() {
  osascript -e "tell application \"System Events\" to return count of windows of (first application process whose name is \"$PROC\")" 2>/dev/null || echo "err"
}

if ! pgrep -f "$PROC" >/dev/null 2>&1; then
  echo "FAIL: the '$PROC' app is not running — start 'npm run tauri dev' first." >&2
  exit 2
fi

# Bring the app forward and capture whatever screen it is on right now (the locked run).
osascript -e "tell application \"System Events\" to set frontmost of (first application process whose name is \"$PROC\") to true" >/dev/null 2>&1 || true
sleep 1.5

wins="$(app_windows)"
shot="$OUT/kiosk-$(date +%Y%m%d-%H%M%S).png"
screencapture -x "$shot"

echo "capture:            $shot"
echo "windows-in-space:   $wins   (0 or 'err'/Invalid = window is on its own fullscreen Space)"
echo
echo "Review '$shot': a real kiosk lock fills the whole display with NO dock, menu"
echo "bar, or other windows. Cross-check always-on-top manually (try Cmd-Tab to another"
echo "app — the locked window must stay in front)."

# The dependable programmatic signal on macOS: a fullscreened window is no longer a
# normal window in the active Space, so the count is 0 (or the read throws).
case "$wins" in
  0|err) echo; echo "PASS (signal): the locked window is not a normal window in the active Space."; exit 0 ;;
  *)     echo; echo "INCONCLUSIVE: $wins normal window(s) in the active Space — is a locked run actually active?"; exit 1 ;;
esac
