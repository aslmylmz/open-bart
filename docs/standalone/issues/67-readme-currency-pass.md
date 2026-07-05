# 67 — README currency pass (the GitHub index)

**Docs · depends on: none**

Status: done

## Context

The root `README.md` predates cycle-02 (dated 2026-07-02) and no longer matches the
shipped instrument. It describes the kiosk as "F11 toggles fullscreen kiosk mode"
(`README.md:43`), which predates the `exit_passcode` **in-app lock** (issue 44:
fullscreen + always-on-top + passcode-gated mid-session exit + capture-phase Escape/F11
swallow). It also omits researcher-facing features that shipped after it was written:

- practice / **Test Run** mode — the persistent "data not recorded" banner, `practice/`
  routing, and the no-recording debrief (issues 43, 59),
- **per-participant reproducible seed** — a fixed study `seed` now reproduces each
  participant from `(seed, id)` while participants diverge (issue 61),
- the optional study fields — **conditions** (37), **payout** conversion (41),
  **currency** label (55), and **QC thresholds** (40).

The README is the GitHub front page and the Zenodo/JOSS entry point, so it must
represent the shipped feature set — at index altitude, linking into `docs/` rather than
duplicating detail.

## Scope

- [x] Correct the kiosk description: the `exit_passcode` in-app lock (passcode-gated
      mid-session exit, fullscreen + always-on-top while locked, Escape/F11 swallowed),
      with F11 as the plain fullscreen toggle when no passcode is set.
- [x] Add the missing shipped capabilities to the researcher walkthrough: practice/Test
      Run mode (banner + `practice/` routing + no-recording debrief), the per-participant
      reproducible seed, and the optional study fields (conditions, payout, currency, QC).
- [x] Verify the badges (RTD, DOI, release, license), the CITATION bibtex/version
      (1.0.0), and that every in-repo link/path resolves; reconcile the
      repository-structure block with the tree (e.g. `app/e2e/`).

## Acceptance

- No stale claim remains — the F11-only kiosk line is gone and the shipped feature set
  is represented.
- All README links/paths resolve; badges and the citation block are current.
- The README stays at index altitude (links into `docs/`, not a re-documentation).

## Comments

Source: 2026-07-05 docs-finalization request. Docs only. Cross-reference the SPEC and
the researcher quickstart rather than restating them; the deep detail belongs on Read
the Docs (see issue 68 for the docs-page currency pass).
