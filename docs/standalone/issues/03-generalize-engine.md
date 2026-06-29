# 03 — Generalize the engine off hardcoded constants

**Phase 0 · SPEC §8 · depends on: 02**

## Context

`scoring/bart.py` assumes the linear model with hardcoded optima and caps. Route
everything through the `TaskConfig` vectors from issue 02 — **without regressing the
23 existing tests**, which directly import `_compute_ev`, `_compute_ev_optimal`,
`_compute_survival_probability`, and `COLOR_PROFILES`.

## Hardcoded constants to audit out (derive from config)

- [ ] `COLOR_PROFILES = {purple:128, teal:32, orange:8}` —
  [bart.py:17-21](../../../scoring/bart.py#L17-L21).
- [ ] `optimal_stops = {11.0, 5.0, 2.0}` and `max_pumps_caps = {128,32,8}` in
  `_calculate_risk_adjustment_score` —
  [bart.py:535-536](../../../scoring/bart.py#L535-L536).
- [ ] Money rate `0.25` hardcoded at
  [bart.py:1101](../../../scoring/bart.py#L1101) → from `reward_per_pump`.

## Scope

- [ ] Generalize `_compute_ev` / `_compute_ev_optimal` / `_compute_survival_probability`
  to work off a hazard spec / precomputed vectors and return the **numeric** argmax.
- [ ] Let `score_bart` accept an optional `TaskConfig` (default = `DEFAULT_TASK_CONFIG`,
  the linear `128/32/8` study) so existing call sites keep working unchanged.
- [ ] Keep the public symbols the tests import — back `COLOR_PROFILES` and the optima
  with the default config instead of literals, rather than deleting them.
- [ ] **(Optional, SPEC §8.4)** Migrate the Pydantic V1-style validators to V2 in
  [scoring/schemas/__init__.py](../../../scoring/schemas/__init__.py)
  (`@validator` → `@field_validator`; `min_items` → `min_length`) to clear the 3
  deprecation warnings.

## Acceptance

- All **23** existing tests pass unchanged.
- The default linear config still yields optima `11/5/2` and the `√N` approximation.
- `test_color_profiles_constant` and `test_money_collected_matches_reward_rule`
  (the `$0.25` rule) still pass.
- New family-driven tests from issue 02 pass against the generalized engine.
