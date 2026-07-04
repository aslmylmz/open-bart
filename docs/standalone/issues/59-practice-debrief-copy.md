# 59 — Practice-mode debrief must not claim the session was recorded

**Usability · depends on: none**

Status: ready-for-agent

## Context

Cycle-02 audit finding F10 (D1). A practice/test run shows the persistent banner
`"TEST RUN — data not recorded"` (`app/src/lib/i18n.ts:98`) on every screen, but the
debrief thank-you body still reads `"Your session has been recorded. Please let the
researcher know you are finished."` (`i18n.ts:126`). A participant (or an RA doing a
dry run) sees a direct contradiction: *not recorded* banner over a *recorded*
message. Issue 43 flagged this as a small follow-up.

Practice mode already threads through the run (`GameSession.practice`, the banner,
the `practice/` output subfolder), so the debrief has the signal it needs.

## Scope

- [ ] Add a practice-mode thank-you body string (en + tr) that makes no recording
      claim (e.g. "This was a test run — no data was recorded.").
- [ ] Have the debrief select the practice body when the session is a practice run.

## Acceptance

- In a practice run the debrief shows the no-recording copy (and the banner); a real
  run is unchanged ("…has been recorded"). Guarded by a Debrief/RunFlow test that
  currently would show the contradictory copy.
- Both languages covered; `vitest`, `tsc --noEmit`, `vite build`, `pytest` stay green.

## Comments

Source: 2026-07-04 fresh full-audit, register row F10. Evidence: `i18n.ts:98` vs `:126`;
issue 43 `## Comments`. Webview-only; no sidecar/schema change.
