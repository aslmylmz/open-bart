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

/** Data-quality flag thresholds (issue 40; mirrors `QCThresholds`). Optional in a
 * `study.json`: absent means the engine's literature-informed defaults. */
export interface QCThresholds {
  fast_response_ms: number;
  zero_pump_streak: number;
}

/** Real-world payout conversion (issue 41; mirrors `PayoutConversion`). Optional:
 * absent/null means no payout anywhere — the v1.0.0 behavior. */
export interface PayoutConversion {
  rate: number;
  currency: string;
}

export interface TaskConfig {
  schema_version: string;
  title: string;
  language: Language;
  reward_per_pump: number;
  /** Freeform label/symbol for the task-earnings units (issue 55). Optional:
   * absent means the default "$" — shown with in-task money and the debrief
   * earnings. Distinct from `payout.currency` (the converted payout label). */
  currency?: string;
  /** RNG seed for the client burst sequence (SPEC §7.2). Mixed with the
   * participant ID at run start (issue 61), so a fixed seed reproduces each
   * participant from `(seed, id)` while participants diverge; `null` → a fresh
   * run each time. Webview-only — the scoring engine never reads it. */
  seed: number | null;
  output_dir: string;
  colors: ColorProfile[];
  /** Allowed condition names for between-subject designs (issue 37). Optional:
   * a v1.0.0 `study.json` has no such key, meaning "no conditions". */
  conditions?: string[];
  /** Optional in-app kiosk lock (issue 44): while a session runs, every exit
   * path asks for this passcode. Deterrence, not security — it stops a
   * curious participant, not an attacker with the preset file. Absent or
   * null means exits are ungated (v1.0.0 behavior). */
  exit_passcode?: string | null;
  /** Data-quality flag thresholds (issue 40). Optional: absent means the
   * engine's literature-informed defaults. */
  qc?: QCThresholds;
  /** Real-world payout conversion (issue 41). Optional/null: absent means no
   * payout anywhere — the v1.0.0 behavior. */
  payout?: PayoutConversion | null;
  /** Multi-station deployment mode: when true, stations write only per-session
   * files (no live master-CSV appends) and the Hub rebuilds study-level
   * outputs. A config field, not a per-machine setting, so every station of a
   * study agrees by construction. Optional: absent means off — the v1.0.0
   * single-station behavior. */
  standalone?: boolean;
  /** Reported metrics surface: the engine always computes the full advanced
   * metrics; "classic" projects every output down to the classic BART canon.
   * Optional: absent means "advanced" — the v1.0.0 behavior. */
  metrics_mode?: "classic" | "advanced";
  /** Offer a Generate button on the ID screen that fills in a random 9-digit
   * participant ID (DATA-SPEC §3.2) — an opt-in guard against cross-station
   * ID collisions. The field stays editable and manual entry stays freeform.
   * Independent of `standalone`. Optional: absent means off (v1.0.0). */
  auto_participant_id?: boolean;
}

/** The validated default study: the original 128/32/8 dynamic hazard, $0.25/pump.
 * Mirrors `scoring.config.DEFAULT_TASK_CONFIG` so the app boots usable before any
 * editing and downstream issues (14–16) have a known-good starting config. */
export const DEFAULT_STUDY: TaskConfig = {
  schema_version: "1.1",
  title: "Dynamic Hazard Rate BART (default dynamic study)",
  language: "en",
  reward_per_pump: 0.25,
  currency: "$",
  seed: null,
  output_dir: ".",
  colors: [
    { name: "purple", label: "Purple", display_hex: "#7c3aed", max_pumps: 128, trials: 10, hazard: { family: "dynamic" } },
    { name: "teal", label: "Teal", display_hex: "#14b8a6", max_pumps: 32, trials: 10, hazard: { family: "dynamic" } },
    { name: "orange", label: "Orange", display_hex: "#f97316", max_pumps: 8, trials: 10, hazard: { family: "dynamic" } },
  ],
};
