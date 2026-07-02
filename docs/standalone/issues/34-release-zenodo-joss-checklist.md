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

## Comments

**2026-07-02 — JOSS pre-submission checklist (v1.0.0 branch state, pre-tag):**

| Requirement | Status | Evidence |
|---|---|---|
| OSI-approved license | ✅ | MIT, `LICENSE` at repo root, badge + docs |
| Public, browsable repository | ✅ | github.com/aslmylmz/metu-risk-persona |
| Substantial scholarly effort | ✅ | scoring engine (40+ metrics), 11-family configurable instrument, MC verification, 3+ months history |
| Statement of need (README + docs) | ✅ | README lead + docs landing page; guarded by `tests/test_readme.py` |
| Installation instructions | ✅ | README (installer + pip), `docs/installation.md`, researcher quickstart |
| Example usage | ✅ | README quick start, `docs/quickstart.md`, `docs/standalone/quickstart.md` |
| API documentation | ✅ | Sphinx autodoc on Read the Docs; builds 0-warning (`tests/test_docs.py`) |
| Automated tests | ✅ | pytest 107, vitest 71, tsc; CI on Windows (sidecar) + paper build |
| Community guidelines | ✅ | `CONTRIBUTING.md` |
| Paper: 250–1000 words, summary + need + refs | ✅ | 758 words; guarded by `tests/test_paper.py` |
| Paper compiles with Open Journals toolchain | ✅ | CI run 28594904052, `joss-paper` artifact (506 KB) |
| Author ORCID + affiliation | ✅ | frontmatter of `paper/paper.md` |
| Version consistency across manifests | ✅ | 1.0.0 everywhere; guarded by `tests/test_release.py` |
| **Tagged release** | ⏳ pending | requires user authorization: merge to main + push `v1.0.0` |
| **Windows installer verified** | ⏳ pending | `windows-release.yml` on tag + manual `VERIFY-WINDOWS.md` pass |
| **Zenodo archive of v1.0.0** | ⏳ pending | auto-archives on GitHub release under concept DOI 10.5281/zenodo.20592164 |
| **Submission to JOSS** | ⛔ author action | never automated |

Notes: the concept DOI (10.5281/zenodo.20592164) is cited in README/CITATION/docs and
always resolves to the latest version — the version-specific DOI minted by Zenodo after
the release can be added to the JOSS submission form directly. Local PyInstaller freeze
of the 1.0.0 sidecar verified on macOS (both gated frozen tests pass); the editable
install must be compat-mode (`pip install -e . --config-settings editable_mode=compat`)
for `collect_submodules("scoring")` to see the package.
