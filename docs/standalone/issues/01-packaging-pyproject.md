# 01 — Packaging: `pyproject.toml`, make `scoring` installable

**Phase 0 · SPEC §16–§17 · depends on: none**

## Context

`scoring` is currently importable only through a `sys.path` hack in
[conftest.py](../../../conftest.py). The Phase 1 sidecar and a clean editable dev
loop both need `scoring` to be a real installable package. There is no
`pyproject.toml` yet; dependencies live in [requirements.txt](../../../requirements.txt)
(numpy, scipy, pydantic ≥2.6, plus matplotlib/pandas for `scripts/`).

## Scope

- [ ] Add a PEP 621 `pyproject.toml` declaring package `scoring` (incl.
  `scoring.schemas` and the new `scoring.config`), a version, `requires-python` ≥3.10,
  and runtime deps (numpy, scipy, pydantic).
- [ ] Pick a build backend (hatchling or setuptools).
- [ ] Optional-dependency groups: `scripts` (matplotlib, pandas), `dev` (pytest).
- [ ] Confirm `pip install -e .` works and `from scoring.bart import score_bart`
  resolves without the conftest path hack.
- [ ] Leave `conftest.py` in place (harmless once installed; keeps uninstalled runs
  working too).
- [ ] Reconcile `requirements.txt` with the new extras (keep, or point it at them).

## Acceptance

- `pip install -e .` succeeds in a clean virtualenv.
- `pytest` still passes all **23** tests (installed or not).
- `python -c "import scoring; import scoring.schemas"` works from any working dir.

## Notes

- The engine imports `scipy.stats` at [bart.py:8](../../../scoring/bart.py#L8), so scipy
  stays a hard dependency for now. SPEC §3/§18 flags trimming scipy to shrink the frozen
  sidecar — that is a later optimization, not part of this issue.
