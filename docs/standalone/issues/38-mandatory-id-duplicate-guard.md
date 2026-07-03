# 38 — Mandatory participant ID + duplicate-ID warn-confirm

**Feature · depends on: none**

Status: ready-for-agent

## Context

The ID screen currently accepts a blank entry and falls back to `"anonymous"`,
so unattributable sessions can pile up silently. Session files are timestamped
so nothing is ever overwritten — the missing guardrail is against *accidental
ID reuse* by rotating RAs (client brief 3A).

Grill decisions: the ID becomes **mandatory**, and a known ID triggers a
**warn-confirm**, not a hard block — duplicate IDs are legitimate in
multi-session/retest designs, and a passcode wall everyone hits on purpose
just trains people to bypass warnings. The sidecar owns all file I/O
(CONTEXT.md), so the duplicate check is a sidecar concern; the webview never
scans the filesystem.

## Scope

- [ ] The ID screen requires a non-empty participant ID before a session can
      start; the `"anonymous"` fallback is removed (participant-facing copy in
      both languages).
- [ ] A sidecar check scans the study's output directory for existing session
      files matching the entered ID and reports how many sessions it already
      has.
- [ ] On a known ID the RA sees a warning ("Subject 004 already has 1 session
      — continue or cancel?"); continuing is allowed, canceling returns to the
      ID screen.
- [ ] The acknowledgment (duplicate detected + RA chose to continue) is
      recorded in the session files so accidents remain visible in the data.
- [ ] Empty/whitespace and filesystem-hostile IDs are rejected with a readable
      message (the existing slug rules stay the single source of truth).
- [ ] Data-outputs docs describe the acknowledgment field.

## Acceptance

- A session cannot start without an ID; there is no path that produces an
  `"anonymous"` session.
- Entering an ID with existing sessions in the output dir shows the warning;
  cancel returns to the ID screen, continue runs and stamps the acknowledgment
  in the session files — covered by tests on both sides of the boundary.
- A fresh ID starts with no friction (no dialog).
- `pytest`, `npm test`, `tsc`, `vite build` stay green.

## Comments

**2026-07-03 — implemented (TDD).** New sidecar endpoint `POST /check-id`
`{candidate_id, config?}` → `{ok, sessions, error}`: rejects empty/whitespace
and filesystem-hostile IDs with a readable message (`_slug(id) == id` — the
existing slug rules stay the single source of truth, so the ID in the data
always matches the filenames), and counts the ID's recorded sessions by exact
stem match on `*_events.jsonl` (strict timestamp regex, so `P001` never counts
`P001_2`'s sessions — covered by a prefix-cousin test). The webview never scans
the filesystem. RunFlow: Continue now vets the ID — invalid → localized inline
message (en/tr); known ID → warn-confirm card naming the ID and count (Cancel
returns to the ID screen, nothing started; Continue proceeds and sets the
flag); fresh ID → straight to loading, no friction. If `/check-id` itself is
unreachable the flow proceeds — a down sidecar surfaces on the loading screen's
own retry path rather than dead-ending the guard. The `"anonymous"` fallback is
removed (`GameSession.candidate_id`'s schema default stays for scoring-library
callers; the instrument always sends a vetted, trimmed ID).
`GameSession.duplicate_acknowledged` (default false) rides the session and is
stamped into the `*_session.json` envelope, as the ADR 0001 amendment
anticipated; documented in data-outputs. Tests: 7 sidecar (/check-id ×6 +
envelope) and 4 RunFlow behaviors incl. an end-to-end continue-past-warning →
payload check. Gates: pytest 131 ✅, npm test 92 ✅, tsc ✅, vite build ✅.
