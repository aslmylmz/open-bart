# 69 — Community health files for JOSS (Code of Conduct + CONTRIBUTING coverage)

**Docs · depends on: none**

Status: done

## Context

JOSS's review checklist asks for **community guidelines**: how to contribute, how to
report issues/problems, and how to seek support — plus a code of conduct is expected of
a healthy open-source project. The repo already has `LICENSE`, `CONTRIBUTING.md`,
`CITATION.cff`, and the `paper/`, but **`CODE_OF_CONDUCT.md` is missing** — the one
community-health file not present. This is more likely to draw a reviewer comment than
any amount of internal dev scaffolding (which is already off the published docs site).

## Scope

- [x] Add `CODE_OF_CONDUCT.md` at the repo root (Contributor Covenant 2.1 is the
      conventional choice; fill in the maintainer contact for reports).
- [x] Verify `CONTRIBUTING.md` covers the three things JOSS looks for — how to
      contribute, how to report a bug/issue, and how to get support — and add whatever is
      missing (it can point at the local `.md` issue tracker convention in
      `docs/agents/issue-tracker.md`).
- [x] Link both from the README (a short "Contributing" / "Community" line) and link the
      Code of Conduct from `CONTRIBUTING.md`.

## Acceptance

- `CODE_OF_CONDUCT.md` exists at the root and is linked from `CONTRIBUTING.md` and the
  README.
- `CONTRIBUTING.md` visibly covers contribute + report-issue + get-support.
- The JOSS "community guidelines" checklist item is satisfiable by pointing at these
  files.

## Comments

Source: 2026-07-05 pre-JOSS readiness (follow-up to the docs-finalization batch 65–68).
Docs/meta only — no code, no re-freeze. Record the completion against the JOSS section of
the release checklist (issue 34).
