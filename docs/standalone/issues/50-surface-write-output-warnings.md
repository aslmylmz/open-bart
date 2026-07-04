# 50 — Surface `/write-output` warnings in the UI

**Bugfix · depends on: 49**

Status: ready-for-agent

## Context

Post-audit hardening (Quality Kaizen cycle 01, finding **F2**;
`docs/standalone/QUALITY-KAIZEN.md`). The sidecar's `/write-output` already
returns a `warnings[]` array for exactly the recoverable failures that matter to
a lab: the master/trials CSV was locked (open in Excel) so the row was diverted
to a timestamped `*_unmerged_*.csv` sibling, a header migration ran, or
provenance could not be written. But the client's `persistSession` is typed
`Promise<void>` and **discards the response body**, so none of these warnings
ever reach a human. A researcher who peeks at the master CSV mid-session forks
their data into sibling files and only discovers the fragmentation at merge
time. This slice makes the warnings the sidecar already computes actually
visible.

## Scope

- [ ] `persistSession` returns the write result (path + `warnings[]`) instead of
      `void`; the completion flow reads it (building on the awaited result from
      issue 49).
- [ ] Any warnings render in a **non-blocking, researcher-visible** notice after
      the session (sibling-fork warnings especially must be hard to miss).
- [ ] No warnings → no notice; the participant-facing debrief is unaffected.

## Acceptance

- A master CSV locked/held open during a completed session produces a visible
  "saved to `…_unmerged_…`, merge by hand" notice carrying the sibling path.
- A clean write shows no notice.
- A test asserts a warning-bearing `/write-output` response reaches the UI layer.
- `pytest`, `vitest`, `tsc --noEmit`, `vite build` stay green.

## Comments

Source: 2026-07-04 research audit, register row F2. Blocked by 49 because both
rewrite the same completion path (`handleSubmit` + `persistSession`); doing them
in sequence avoids a merge conflict on the same lines.
