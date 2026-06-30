import { describe, expect, it } from "vitest";

import { HAZARD_FAMILIES } from "../lib/config";
import { defaultHazard } from "./familyParams";

describe("defaultHazard", () => {
  it("produces a spec tagged with the requested family for every family", () => {
    for (const family of HAZARD_FAMILIES) {
      expect(defaultHazard(family, 32).family).toBe(family);
    }
  });

  it("defaults scalar params from FAMILY_PARAMS", () => {
    const h = defaultHazard("logistic", 32);
    if (h.family !== "logistic") throw new Error("wrong family");
    expect(h.h_max).toBe(0.9);
    expect(h.midpoint).toBe(16);
    expect(h.steepness).toBe(0.3);
  });

  it("seeds the array families well-formed against maxPumps", () => {
    const step = defaultHazard("step", 32);
    if (step.family !== "step") throw new Error("wrong family");
    expect(step.levels.length).toBe(step.breakpoints.length + 1);
    expect(step.breakpoints[0]).toBeGreaterThanOrEqual(1);

    const tabular = defaultHazard("tabular", 8);
    if (tabular.family !== "tabular") throw new Error("wrong family");
    expect(tabular.values).toHaveLength(8);
    expect(tabular.values.every((v) => v >= 0 && v <= 1)).toBe(true);
  });
});
