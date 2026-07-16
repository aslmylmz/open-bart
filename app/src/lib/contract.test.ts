import { describe, expect, it } from "vitest";

import contract from "./contract.generated.json";
import {
  HAZARD_FAMILIES,
  type ColorProfile,
  type ConstantHazard,
  type DynamicHazard,
  type ExponentialHazard,
  type GompertzHazard,
  type HazardFamily,
  type LejuezHazard,
  type LogisticHazard,
  type LognormalHazard,
  type PayoutConversion,
  type QCThresholds,
  type RayleighHazard,
  type StepHazard,
  type TabularHazard,
  type TaskConfig,
  type WeibullHazard,
} from "./config";
import type { SessionPayload } from "./session";

/**
 * Parity guard for the hand-written TS mirrors of the pydantic input contracts.
 *
 * Each `Record<keyof T, true>` sentinel forces the literal to name every field
 * of the TS type — `tsc` errors on a missing or excess key — so the sentinel's
 * keys are the TS type's field set as runtime data. Comparing that set to the
 * committed contract (derived from the pydantic JSON schema by
 * `tests/test_ts_contract.py`) makes drift a failing test in both directions:
 *   - a field added on the Python side fails here until the TS type gains it;
 *   - a field added only on the TS side fails here (the contract lacks it).
 * This extends the `HAZARD_FAMILY_SET` idiom already in config.ts.
 *
 * Scope = the round-trip input contracts. Read-only projections (Debrief's
 * `AssessmentResult` and the api.ts response DTOs) are deliberate subsets and
 * are intentionally NOT guarded here. Regenerate the contract after a pydantic
 * change with `python tests/test_ts_contract.py`.
 */
const keysOf = (sentinel: Record<string, true>): string[] => Object.keys(sentinel).sort();

const TASK_CONFIG: Record<keyof TaskConfig, true> = {
  schema_version: true,
  title: true,
  language: true,
  reward_per_pump: true,
  currency: true,
  seed: true,
  output_dir: true,
  colors: true,
  conditions: true,
  exit_passcode: true,
  qc: true,
  payout: true,
  standalone: true,
  metrics_mode: true,
};

const COLOR_PROFILE: Record<keyof ColorProfile, true> = {
  name: true,
  label: true,
  display_hex: true,
  max_pumps: true,
  trials: true,
  hazard: true,
};

const QC_THRESHOLDS: Record<keyof QCThresholds, true> = {
  fast_response_ms: true,
  zero_pump_streak: true,
};

const PAYOUT_CONVERSION: Record<keyof PayoutConversion, true> = {
  rate: true,
  currency: true,
};

const SESSION_PAYLOAD: Record<keyof SessionPayload, true> = {
  session_id: true,
  game_type: true,
  candidate_id: true,
  condition: true,
  duplicate_acknowledged: true,
  practice: true,
  events: true,
};

const HAZARD_PARAMS: Record<HazardFamily, string[]> = {
  dynamic: keysOf({ family: true } satisfies Record<keyof DynamicHazard, true>),
  constant: keysOf({ family: true, p: true } satisfies Record<keyof ConstantHazard, true>),
  lejuez: keysOf({ family: true } satisfies Record<keyof LejuezHazard, true>),
  rayleigh: keysOf({ family: true, sigma: true } satisfies Record<keyof RayleighHazard, true>),
  exponential: keysOf({ family: true, rate: true } satisfies Record<keyof ExponentialHazard, true>),
  weibull: keysOf({ family: true, shape: true } satisfies Record<keyof WeibullHazard, true>),
  gompertz: keysOf({ family: true, a: true, b: true } satisfies Record<keyof GompertzHazard, true>),
  logistic: keysOf(
    { family: true, h_max: true, midpoint: true, steepness: true } satisfies Record<
      keyof LogisticHazard,
      true
    >,
  ),
  lognormal: keysOf({ family: true, mu: true, sigma: true } satisfies Record<keyof LognormalHazard, true>),
  step: keysOf({ family: true, breakpoints: true, levels: true } satisfies Record<keyof StepHazard, true>),
  tabular: keysOf({ family: true, values: true } satisfies Record<keyof TabularHazard, true>),
};

describe("pydantic↔TS contract parity", () => {
  it("TaskConfig matches the pydantic contract", () => {
    expect(keysOf(TASK_CONFIG)).toEqual([...contract.TaskConfig].sort());
  });

  it("ColorProfile matches", () => {
    expect(keysOf(COLOR_PROFILE)).toEqual([...contract.ColorProfile].sort());
  });

  it("QCThresholds matches", () => {
    expect(keysOf(QC_THRESHOLDS)).toEqual([...contract.QCThresholds].sort());
  });

  it("PayoutConversion matches", () => {
    expect(keysOf(PAYOUT_CONVERSION)).toEqual([...contract.PayoutConversion].sort());
  });

  it("SessionPayload matches GameSession", () => {
    expect(keysOf(SESSION_PAYLOAD)).toEqual([...contract.GameSession].sort());
  });

  it("every hazard family's params match", () => {
    for (const family of HAZARD_FAMILIES) {
      expect(HAZARD_PARAMS[family]).toEqual([...contract.HazardSpec[family]].sort());
    }
  });
});
