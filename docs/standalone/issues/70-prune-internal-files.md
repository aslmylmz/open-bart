# 70 — Prune internal-only files from the public repo (pre-JOSS)

**Docs · depends on: none**

Status: done

## Context

JOSS reviewers browse the GitHub tree, not just the published docs. Internal dev
artifacts are neither required nor penalized, and the researcher-facing site is already
clean — `docs/conf.py` excludes `adr/**`, `agents/**`, `client-brief.md`,
`standalone/issues/**`, and `standalone/QUALITY-KAIZEN.md` from the Read the Docs build.
But a couple of tracked files read as **genuinely internal**, not documentation, and are
worth removing from the public tree before submission:

- `docs/client-brief.md` — a private client brief (tracked in the public repo), not
  project documentation.
- `docs/agents/` — AI-agent workflow instructions (issue-tracker + triage-label +
  domain conventions); harmless, but a keep-or-remove judgement call.

Deliberately **keep**: the issue tracker (`standalone/issues/`), `docs/adr/`, and
`QUALITY-KAIZEN.md` — normal engineering artifacts that read as rigor, already off the
published site.

Marked **ready-for-human** because it deletes the maintainer's own in-progress
`client-brief.md`; the maintainer should confirm the removal (and the `docs/agents/`
decision).

## Scope

- [x] `git rm` `docs/client-brief.md` from the tracked tree (or move it to a private,
      untracked location).
- [x] Decide `docs/agents/`: remove from the public tree, or keep with a one-line
      rationale (it documents the local issue-tracker convention that `CONTRIBUTING.md`
      may reference — see issue 69).
- [x] Confirm no published page (README, `docs/**` in the toctree) links to anything
      removed; drop now-dead `conf.py` exclude entries if their targets are gone (a
      pattern for an absent path is a harmless no-op, but keep it tidy).

## Acceptance

- The internal-only files are gone from the public tree (or explicitly kept with a
  recorded rationale).
- The docs build stays warning-clean (no dangling cross-references introduced — see
  issue 65) and no README/site link points at a removed file.
- The public-vs-internal decision is recorded in the release checklist (issue 34).

## Comments

Source: 2026-07-05 pre-JOSS readiness (follow-up to 65–68). Docs/meta only. The bigger
JOSS wins are the front door (README + RTD, issues 67/65) and community guidelines
(issue 69), not hiding the tracker — this issue is just trimming the two files that are
genuinely not for publication.
