# 66 — Build the docs in CI (fail on warning)

**Docs · depends on: [65](65-docs-build-warning-clean.md)**

Status: done

## Context

`.readthedocs.yaml` sets `fail_on_warning: true` with a comment that regressions
(orphaned pages, broken cross-references) are "caught in CI." They are not: `ci.yml`
runs the four code gates (pytest, vitest, tsc, vite build) but **never builds the
docs**. So a documentation warning only turns the hosted RTD build red after merge —
never a pull request. Doc regressions can merge silently, and the RTD comment is
currently inaccurate.

## Scope

- [x] Add a docs-build step/job that runs `sphinx-build -b html -W` (mirroring
      `.readthedocs.yaml`) with `docs/requirements.txt`, in `ci.yml` or a small
      dedicated `docs.yml`, on push + pull_request.
- [x] Keep it fast and isolated — Python only (no Node, no PyInstaller freeze); install
      just the docs requirements, not the whole engine, unless autodoc needs the package
      importable (it imports `scoring` for the API reference, with numpy/scipy/pandas/
      matplotlib mocked — install accordingly).

## Acceptance

- An introduced doc warning (e.g. an orphaned page or a dead cross-reference) fails the
  CI job; a clean tree is green.
- The `.readthedocs.yaml` "caught in CI" comment is now accurate.

## Comments

Source: 2026-07-05 docs-finalization request. **Blocked by issue 65** — the tree must
build warning-clean before a fail-on-warning gate can be turned on, or it lands red.
Complements RTD's own `fail_on_warning` by catching regressions pre-merge.
