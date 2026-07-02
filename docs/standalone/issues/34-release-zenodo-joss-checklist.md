# 34 — Release, Zenodo archive, and JOSS pre-submission checklist

**Release · depends on: 29, 30, 31, 32, 33**

Status: ready-for-agent

## Context

JOSS reviews a tagged, archived release: the submitted version must exist as a
GitHub release and a Zenodo archive whose DOI the paper cites.
[CITATION.cff](../../../CITATION.cff) still carries the pre-instrument abstract
at v0.2.0 (concept DOI 10.5281/zenodo.20592164). The v0.2.0 release flow
(version bump across all manifests → tag → `windows-release.yml`) is the
template.

## Scope

- [ ] Version bump to the next release across every manifest (`scoring/__init__.py`,
      `docs/conf.py`, `tauri.conf.json`, `Cargo.toml`/`.lock`, `package.json`/
      `-lock.json`, `CITATION.cff`) — same set as the v0.2.0 release.
- [ ] Rewrite `CITATION.cff` (abstract → the instrument, date, version).
- [ ] Note: merging `feat/standalone-instrument` to `main` and pushing the tag
      require explicit user authorization — stop and ask at that step.
- [ ] Tag → verify `windows-release.yml` produces the installer; run the
      `VERIFY-WINDOWS.md` manual pass on the new build.
- [ ] Archive the release as a new Zenodo version under the concept DOI; wire the
      version DOI into `paper.md`, `README.md` badge, and `CITATION.cff`.
- [ ] Run the JOSS pre-submission checklist (OSI license, contribution
      guidelines, automated tests, documentation, paper format/word count,
      archive DOI) and record the results as a comment on this issue.
      **Do not submit** — submission is the author's action.

## Acceptance

- Tagged release builds and installs; manual Windows verification passes.
- Zenodo version DOI minted and referenced consistently across paper, README,
  and CITATION.cff.
- Every checklist item recorded as passing (or explicitly waived by the user).
- `pytest`, `npm test`, `tsc`, `vite build` stay green.
