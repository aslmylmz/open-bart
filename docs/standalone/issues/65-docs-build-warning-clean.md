# 65 — Documentation build: warning-clean Sphinx pipeline matching the current tree

**Docs · depends on: none**

Status: done

## Context

The Sphinx / Read the Docs pipeline (`docs/conf.py`, `.readthedocs.yaml` with
`fail_on_warning: true`) is mostly healthy: internal dev docs are excluded in
`conf.py` (`adr/**`, `agents/**`, `client-brief.md`, `standalone/issues/**`,
`standalone/QUALITY-KAIZEN.md`) or marked `orphan:` (`standalone/DESIGN.md`,
`standalone/SPEC.md`, `standalone/VERIFY-WINDOWS.md`), and the researcher pages sit in
the `index.md` toctree. But two things are off:

1. `docs/conf.py` declares `version = "0.2"` while `release = "1.0.0"` — the theme shows
   a stale short version.
2. No one has confirmed a clean `fail_on_warning` build against the current tree after
   the cycle-02 doc edits (issue 58 data dictionary, the VERIFY-WINDOWS kiosk section,
   the SPEC §7.2 seed note, etc.). RTD builds on push, so a single new warning silently
   fails the hosted build.

## Scope

- [x] Fix `docs/conf.py` `version = "0.2"` → `"1.0"` (the X.Y of `release` 1.0.0).
- [x] Build locally with the pinned deps and fail-on-warning:
      `pip install -r docs/requirements.txt` then
      `sphinx-build -b html -W --keep-going docs docs/_build/html`; resolve every
      warning (orphaned pages, broken cross-references, missing toctree entries,
      duplicate labels).
- [x] Confirm each page under `docs/` is intentionally in a toctree, marked `orphan:`,
      or excluded in `conf.py` (no accidental inclusions/exclusions).

## Acceptance

- `sphinx-build -W` completes clean locally against `docs/requirements.txt`; the RTD
  build for the branch is green.
- The rendered short version reads 1.0 (not 0.2).
- No researcher page is accidentally dropped from the toctree and no dev-only page is
  accidentally published.

## Comments

Source: 2026-07-05 docs-finalization request. Docs only — engine/webview untouched, so
no re-freeze and the four code gates are unaffected. Sphinx 9.1.0 is available in the
miniforge env; install `docs/requirements.txt` into it (or a venv) to reproduce the RTD
build.
