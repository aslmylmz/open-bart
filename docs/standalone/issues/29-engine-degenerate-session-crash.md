# 29 — Engine hardening: degenerate-session scoring crash

**Engine · depends on: none**

Status: done

## Context

A latent crash was found during Phase 1 (2026-06-29) and parked as out of scope:
`score_bart` raises on degenerate-but-valid sessions (e.g. a single-color or
single-balloon session). `_compute_ev_efficiency_uniformity` returns `None` when
there are not enough per-color efficiencies to compare, and the behavioral-profile
classifier then compares that `None` numerically (`_unif < 0.35` and friends around
[scoring/bart.py:862](../../../scoring/bart.py)), raising `TypeError`.

JOSS reviewers exercise minimal examples. Any session that passes the validators
must score without an exception — this is the prefactoring slice that de-risks the
paper's "transparent, reusable scoring engine" claim.

## Scope

- [ ] Regression tests first (tdd): single-color session, single-balloon session,
      and the smallest session the validation pipeline accepts.
- [ ] Fix the behavioral-profile classifier to tolerate
      `ev_efficiency_uniformity is None` (explicit guard or documented fallback —
      do not silently coerce to `0.0` where it changes the narrative style).
- [ ] Audit the rest of the profile-classification branch for other
      `Optional` metrics compared numerically.
- [ ] Sweep: score one synthetic session per curated hazard family via
      `TaskConfig` and assert no exception.

## Acceptance

- Degenerate sessions return a metrics object (with `None` uniformity or the
  documented fallback) instead of raising.
- New regression tests cover the crash and the per-family sweep.
- All existing pytest suites stay green.
