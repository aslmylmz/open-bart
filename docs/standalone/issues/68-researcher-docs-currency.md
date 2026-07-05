# 68 — Researcher docs content currency

**Docs · depends on: none**

Status: done

## Context

Alongside the README (issue 67), the **published** researcher-facing pages should match
current behavior. Several cycle-02 changes may not be reflected on Read the Docs:

- the `exit_passcode` kiosk in-app lock (issue 44) — `docs/standalone/KIOSK.md`,
- practice / Test Run mode + the no-recording debrief in the flow (issues 43, 59) —
  the researcher quickstart,
- the per-participant seed model (issue 61) — SPEC §7.2 was updated; verify
  `task_design.md` / any published seed description agree,
- the hazard-family-agnostic participant instructions (issue 62) — anywhere the
  consent/instruction copy is quoted or described,
- `data_outputs.md` was updated doc-first in issue 58 (the `orange_avg_pumps` caveat) —
  confirm it still matches the CSV writer in `app/sidecar`.

This is a targeted audit-and-fix, not a rewrite: only pages that describe pre-cycle-02
behavior need changes.

## Scope

- [x] Reconcile `docs/standalone/KIOSK.md` with the shipped `exit_passcode` lock (what it
      does and its honest limits — deterrence, not OS-level lockdown).
- [x] Ensure the researcher quickstart covers practice/Test Run mode and the no-recording
      debrief.
- [x] Verify the published seed model matches issue 61 (reproducible from `seed` + ID,
      per-participant) and that instruction copy is described as hazard-neutral (issue 62).
- [x] Confirm `data_outputs.md` Master-CSV columns match `app/sidecar`'s writer (issue 58).

## Acceptance

- Each listed page matches the shipped behavior, cross-checked against the code.
- No researcher-facing page still describes pre-cycle-02 behavior.
- The build stays warning-clean (any new cross-references resolve — see issue 65).

## Comments

Source: 2026-07-05 docs-finalization request. Pairs with issue 65's warning-clean build;
can be folded into 65 if the audit turns up little. Distinct from the README pass (67):
this is the deep researcher documentation, that is the index.
