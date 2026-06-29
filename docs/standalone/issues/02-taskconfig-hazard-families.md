# 02 — `scoring/config/`: TaskConfig + hazard family library

**Phase 0 · SPEC §5–§7 · depends on: 01**

## Context

A single pydantic `TaskConfig` must be the **one source of truth** driving both how
balloons burst (task) and where the EV-optimum sits (scoring). This lands a new
`scoring/config/` subpackage. The current engine hardwires the linear hazard
`h(k)=k/N` at [bart.py:30-44](../../../scoring/bart.py#L30-L44); **this issue builds the
model**, issue 03 rewires the engine to consume it.

## Scope

### Models (pydantic v2)

- [ ] `TaskConfig`: `schema_version`, `title`, `language` (`tr|en`), `reward_per_pump`,
  `seed`, `output_dir`, `colors: list[ColorProfile]`.
- [ ] `ColorProfile`: `name`, `label`, `display_hex`, `max_pumps` (N), `trials`,
  `hazard: HazardSpec`.
- [ ] `HazardSpec`: discriminated union on `family`. Each family is its own model with
  range-validated params and a `hazard_vector(n) -> list[float]` method.

### Families (SPEC §7.2) — each clamped to `[0,1]` over `k = 1..N`

- [ ] `linear` `k/N` (default) · `constant` `p` · `weibull` `(m/N)(k/N)^(m-1)` ·
  `rayleigh` `k/σ²` · `exponential` `1−e^(−λ)` · `gompertz` `a·e^(bk)` ·
  `logistic` `H_max/(1+e^(−r_s(k−k0)))` · `lognormal` (via scipy) ·
  `uniform` (Lejuez) `1/(N−k+1)` · `step` (breakpoints/levels) ·
  `tabular` (explicit `h[1..N]` array — data, not code).

### Precompute + optimum (SPEC §6)

- [ ] On load, per color, cache: hazard `h[k]`; survival `S(s)=Π(1−h[k])` with `S(0)=1`;
  `EV(s)=reward·s·S(s)`; numeric `s* = argmax_{1≤s≤N} EV(s)`.
- [ ] Optimum is **numeric** — full scan `1..N`. Do **not** reuse the `ev < best*0.5`
  early-break at [bart.py:58-59](../../../scoring/bart.py#L58-L59); it assumes a unimodal
  EV curve and would stop early on non-monotone families (e.g. lognormal).
- [ ] `reward_per_pump` scales EV uniformly ⇒ it must **not** move `s*` (assert in a test).

### Validation

- [ ] Param domains enforced via pydantic `Field` constraints, with clear messages.
- [ ] Reject `NaN`/`inf` hazards and any raw `h(k) > 1` before `max_pumps`; clamp the
  final working vector to `[0,1]` (so `h(N)=1` at the cap is fine).
- [ ] Provide a `DEFAULT_TASK_CONFIG` constant = the validated `128/32/8` linear study
  (reward `0.25`), reused by issue 03 as the engine default.

## Acceptance

- One test **per family**: numeric optimum vs the §7.2 closed-form sanity value
  (`linear ≈ √N` → 11/5/2; `constant-p ≈ 1/p`; `uniform ≈ N/2`; `rayleigh ≈ σ`).
- Reward-invariance test: changing `reward_per_pump` does not change `s*`.
- The default linear config reproduces `_compute_ev`'s EV exactly for `N = 128/32/8`
  (peak EV `6.46/3.04/1.31`, `s* = 11/5/2`).
