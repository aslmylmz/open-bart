import { describe, expect, it } from "vitest";

import { DEFAULT_STUDY, HAZARD_FAMILIES } from "./config";

describe("DEFAULT_STUDY", () => {
  it("mirrors the validated default linear study's colors (128/32/8, linear)", () => {
    expect(DEFAULT_STUDY.colors.map((c) => [c.name, c.max_pumps, c.trials])).toEqual([
      ["purple", 128, 10],
      ["teal", 32, 10],
      ["orange", 8, 10],
    ]);
    expect(DEFAULT_STUDY.colors.every((c) => c.hazard.family === "dynamic")).toBe(true);
  });

  it("mirrors the default study's top-level fields", () => {
    expect(DEFAULT_STUDY.schema_version).toBe("1.1");
    expect(DEFAULT_STUDY.language).toBe("en");
    expect(DEFAULT_STUDY.reward_per_pump).toBe(0.25);
    expect(DEFAULT_STUDY.seed).toBeNull();
    expect(DEFAULT_STUDY.output_dir).toBe(".");
  });

  it("serializes with the pydantic snake_case field names (no camelCase leakage)", () => {
    const json = JSON.stringify(DEFAULT_STUDY);
    for (const key of ["schema_version", "reward_per_pump", "output_dir", "max_pumps", "display_hex"]) {
      expect(json).toContain(`"${key}"`);
    }
    for (const camel of ["rewardPerPump", "maxPumps", "displayHex", "outputDir"]) {
      expect(json).not.toContain(camel);
    }
  });
});

describe("HAZARD_FAMILIES", () => {
  it("enumerates all 11 hazard families from the spec", () => {
    expect([...HAZARD_FAMILIES].sort()).toEqual(
      [
        "constant",
        "exponential",
        "gompertz",
        "dynamic",
        "logistic",
        "lognormal",
        "lejuez",
        "rayleigh",
        "step",
        "tabular",
        "weibull",
      ].sort(),
    );
  });
});
