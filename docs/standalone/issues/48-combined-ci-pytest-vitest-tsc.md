# 48 — Combined CI: run pytest + vitest + tsc together

**Chore · depends on: 46**

Status: done

## Context

The pydantic↔TypeScript parity guard from issue 46 spans two suites — a Python
contract test and a TS vitest / `tsc` check. Today no CI job runs both:
`.github/workflows` covers the Windows sidecar / release and the JOSS paper, and
the `pytest` / `npm test` / `tsc` / `vite build` gates are run by hand. So the
parity guard — and the other gates — only fire when a developer remembers to run
both suites locally. A single CI job that runs the full gate set closes that gap
and makes contract drift a red build rather than a missed local step.

## Scope

- [ ] A CI workflow runs, on push / PR, the full gate set: `pytest` (repo root),
      and from `app/`: `npm test`, `tsc --noEmit`, `vite build`.
- [ ] The job provisions both toolchains (the Python env the Sidecar/scoring
      package uses, and Node for the webview) and does **not** require the
      gitignored frozen sidecar binary — the parity and unit suites don't need
      it.
- [ ] Green on `feat/standalone-instrument`, and demonstrably red when a contract
      drift (issue 46) is introduced.

## Acceptance

- Pushing a branch that drops `qc` from the TS `TaskConfig` (or otherwise breaks
  the contract) produces a red CI run.
- A clean branch produces a green CI run exercising pytest + vitest + tsc +
  vite build.
- No dependency on the gitignored frozen sidecar artifact.

## Comments

**2026-07-04 — implemented.** Added `.github/workflows/ci.yml`: one `gates` job
on `ubuntu-latest` running the full local gate set. Python leg — `setup-python`
3.12, `pip install -e ".[sidecar,dev]"` (sidecar → fastapi/uvicorn for
`test_sidecar`'s in-process `TestClient`; dev → pytest/httpx; no `build`/`scripts`
extras, since nothing freezes and the engine is scipy-free), then `pytest -q`.
Webview leg — `setup-node` 20 with `cache: npm` keyed on `app/package-lock.json`
(tracked and in sync, so `npm ci` is reproducible), then `npm test` / `npm run
typecheck` / `npm run build`. Triggers on push to `main` +
`feat/standalone-instrument`, on every `pull_request`, and `workflow_dispatch`;
a `concurrency` group cancels superseded runs. No frozen sidecar binary is
touched — the Python suite drives the FastAPI app via `TestClient` and the vitest
suite mocks the sidecar API, so the parity/unit suites need no `externalBin`.

CI YAML has no meaningful red→green unit to write (a test that string-matched the
workflow would be exactly the implementation-coupled anti-pattern), so the
"behavior" verified is the acceptance itself: **clean → green, drift → red**,
exercised against the identical commands CI runs. **Green:** locally pytest
**161** ✅, vitest **128** ✅, tsc ✅, vite build ✅; the YAML parses to the six
expected gate commands. **Red-on-drift:** dropping `qc?` from the TS `TaskConfig`
made `npm run typecheck` (the CI `tsc --noEmit` step) fail, led by the issue-46
contract sentinel — `contract.test.ts: 'qc' does not exist in type
'Record<keyof TaskConfig, true>'` — plus the downstream usages; restoring the
field returned tsc to green. (That drift is type-level, so `tsc` catches it; the
vitest runtime guard is the other side of the two-sided contract, catching a
pydantic-side change.) The `gh` CLI was unavailable in the authoring
environment, so the remote run itself is confirmed on the Actions tab rather than
watched from the shell.

**2026-07-04 — first CI run was red; fixed.** Run #1 (`2517471`) failed at the
`pytest` step: `test_paper.py::test_paper_build_workflow_compiles_the_manuscript`
does `import yaml` to parse `paper.yml`, but **PyYAML was undeclared** — present
in local/dev environments by luck (conda base), absent from the clean
`.[sidecar,dev]` install CI does. This was a latent bug the first clean-room run
surfaced (the test fails in any fresh env, not just CI). Fixed at the source:
added `pyyaml>=6` to the `dev` extra so the suite declares what it needs.
Reproduced both states in a throwaway py3.12 venv installing exactly
`.[sidecar,dev]`: before → `1 failed, 158 passed, 2 skipped`; after → `159
passed, 2 skipped`. The 2 skips are by design (scipy `importorskip` in
test_config; one platform-guarded test) — the engine is scipy-free, so scipy is
not a CI dep. Re-verified the run via the public REST API (the on-PATH `gh` is a
miniforge "browser opener", not the GitHub CLI; the real CLI is not installed).
