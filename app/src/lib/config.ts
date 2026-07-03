/** TypeScript mirror of the `scoring.config` schema (the single source of truth).
 *
 * Field names match the pydantic JSON exactly (snake_case), so a `TaskConfig`
 * serializes straight to `study.json` and is accepted verbatim by the sidecar's
 * `/validate-config` and `/preview`. These types are a typing convenience only:
 * the Python models in `scoring/config/` stay authoritative, and the sidecar
 * remains the authority on validation (Study Setup posts candidates to
 * `/validate-config` rather than re-encoding pydantic's rules here).
 */

// ── Hazard families (discriminated union on `family`; mirrors hazards.py) ──────

export interface DynamicHazard {
  family: "dynamic";
}

export interface ConstantHazard {
  family: "constant";
  p: number;
}

export interface LejuezHazard {
  family: "lejuez";
}

export interface RayleighHazard {
  family: "rayleigh";
  sigma: number;
}

export interface ExponentialHazard {
  family: "exponential";
  rate: number;
}

export interface WeibullHazard {
  family: "weibull";
  shape: number;
}

export interface GompertzHazard {
  family: "gompertz";
  a: number;
  b: number;
}

export interface LogisticHazard {
  family: "logistic";
  h_max: number;
  midpoint: number;
  steepness: number;
}

export interface LognormalHazard {
  family: "lognormal";
  mu: number;
  sigma: number;
}

export interface StepHazard {
  family: "step";
  breakpoints: number[];
  levels: number[];
}

export interface TabularHazard {
  family: "tabular";
  values: number[];
}

export type HazardSpec =
  | DynamicHazard
  | ConstantHazard
  | LejuezHazard
  | RayleighHazard
  | ExponentialHazard
  | WeibullHazard
  | GompertzHazard
  | LogisticHazard
  | LognormalHazard
  | StepHazard
  | TabularHazard;

/** The `family` discriminator of any hazard spec. */
export type HazardFamily = HazardSpec["family"];

/** Every hazard family, for dropdowns and as a drift guard against hazards.py.
 * The `Record<HazardFamily, true>` makes a family added to the union but omitted
 * here a compile-time error (a missing key fails `tsc`). */
const HAZARD_FAMILY_SET: Record<HazardFamily, true> = {
  dynamic: true,
  constant: true,
  lejuez: true,
  rayleigh: true,
  exponential: true,
  weibull: true,
  gompertz: true,
  logistic: true,
  lognormal: true,
  step: true,
  tabular: true,
};

export const HAZARD_FAMILIES = Object.keys(HAZARD_FAMILY_SET) as HazardFamily[];

// ── Study config (mirrors task_config.py) ─────────────────────────────────────

export type Language = "tr" | "en";

export interface ColorProfile {
  name: string;
  label: string;
  display_hex: string;
  max_pumps: number;
  trials: number;
  hazard: HazardSpec;
}

export interface TaskConfig {
  schema_version: string;
  title: string;
  language: Language;
  reward_per_pump: number;
  seed: number | null;
  output_dir: string;
  colors: ColorProfile[];
  /** Allowed condition names for between-subject designs (issue 37). Optional:
   * a v1.0.0 `study.json` has no such key, meaning "no conditions". */
  conditions?: string[];
}

/** The validated default study: the original 128/32/8 dynamic hazard, $0.25/pump.
 * Mirrors `scoring.config.DEFAULT_TASK_CONFIG` so the app boots usable before any
 * editing and downstream issues (14–16) have a known-good starting config. */
export const DEFAULT_STUDY: TaskConfig = {
  schema_version: "1.0",
  title: "Dynamic Hazard Rate BART (default dynamic study)",
  language: "en",
  reward_per_pump: 0.25,
  seed: null,
  output_dir: ".",
  colors: [
    { name: "purple", label: "Purple", display_hex: "#7c3aed", max_pumps: 128, trials: 10, hazard: { family: "dynamic" } },
    { name: "teal", label: "Teal", display_hex: "#14b8a6", max_pumps: 32, trials: 10, hazard: { family: "dynamic" } },
    { name: "orange", label: "Orange", display_hex: "#f97316", max_pumps: 8, trials: 10, hazard: { family: "dynamic" } },
  ],
};
