/** Per-family parameter specs + sensible defaults for the Study-Setup form.
 *
 * `FAMILY_PARAMS` is the single source for each family's *scalar* numeric params
 * (the number inputs the form renders) and their defaults/ranges, mirroring the
 * pydantic constraints in `scoring/config/hazards.py`. Ranges here are input hints
 * only — the sidecar's `/validate-config` stays the authority. The two array-valued
 * families (step, tabular) carry no scalar params and are seeded by `defaultHazard`.
 */

import type { HazardFamily, HazardSpec } from "../lib/config";

export interface ParamField {
  key: string;
  label: string;
  /** "int" steps by 1; "number" allows decimals. */
  kind: "number" | "int";
  default: number;
  min?: number;
  max?: number;
  step?: number;
}

export const FAMILY_PARAMS: Record<HazardFamily, ParamField[]> = {
  linear: [],
  uniform: [],
  constant: [{ key: "p", label: "Burst probability p", kind: "number", default: 0.1, min: 0, max: 1, step: 0.01 }],
  rayleigh: [{ key: "sigma", label: "Scale σ", kind: "number", default: 8, min: 0, step: 0.5 }],
  exponential: [{ key: "rate", label: "Rate λ", kind: "number", default: 0.05, min: 0, step: 0.01 }],
  weibull: [{ key: "shape", label: "Shape m", kind: "number", default: 2, min: 0, step: 0.1 }],
  gompertz: [
    { key: "a", label: "Baseline a", kind: "number", default: 0.01, min: 0, step: 0.001 },
    { key: "b", label: "Growth b", kind: "number", default: 0.1, min: 0, step: 0.01 },
  ],
  logistic: [
    { key: "h_max", label: "Ceiling h_max", kind: "number", default: 0.9, min: 0, max: 1, step: 0.05 },
    { key: "midpoint", label: "Midpoint k0", kind: "number", default: 16, min: 0, step: 1 },
    { key: "steepness", label: "Steepness", kind: "number", default: 0.3, min: 0, step: 0.05 },
  ],
  lognormal: [
    { key: "mu", label: "Log-location μ", kind: "number", default: 2.5, step: 0.1 },
    { key: "sigma", label: "Log-shape σ", kind: "number", default: 0.5, min: 0, step: 0.1 },
  ],
  step: [],
  tabular: [],
};

/** The scalar param defaults for a family, keyed by param name. */
function scalarDefaults(family: HazardFamily): Record<string, number> {
  return Object.fromEntries(FAMILY_PARAMS[family].map((f) => [f.key, f.default]));
}

/** A valid default `HazardSpec` for `family`. Scalar params come from
 * `FAMILY_PARAMS`; the array families are seeded against the color's `maxPumps`
 * so the spec is well-formed the moment the family is selected. */
export function defaultHazard(family: HazardFamily, maxPumps: number): HazardSpec {
  switch (family) {
    case "step":
      return { family, breakpoints: [Math.max(1, Math.floor(maxPumps / 2))], levels: [0.05, 0.5] };
    case "tabular":
      return { family, values: Array.from({ length: maxPumps }, (_, i) => (i + 1) / maxPumps) };
    default:
      return { family, ...scalarDefaults(family) } as HazardSpec;
  }
}
