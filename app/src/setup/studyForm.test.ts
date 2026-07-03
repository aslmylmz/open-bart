import { describe, expect, it } from "vitest";

import { DEFAULT_STUDY } from "../lib/config";
import {
  addColor,
  parseConditionList,
  parseNumberList,
  parseStudy,
  removeColor,
  setColorHazardFamily,
  setHazardParam,
} from "./studyForm";

describe("setColorHazardFamily", () => {
  it("swaps the color's hazard to the family's defaults", () => {
    const next = setColorHazardFamily(DEFAULT_STUDY, 1, "constant");
    expect(next.colors[1].hazard).toEqual({ family: "constant", p: 0.1 });
  });

  it("does not mutate the input config", () => {
    setColorHazardFamily(DEFAULT_STUDY, 1, "constant");
    expect(DEFAULT_STUDY.colors[1].hazard).toEqual({ family: "dynamic" });
  });
});

describe("setHazardParam", () => {
  it("updates a scalar param on the color's current hazard", () => {
    const constant = setColorHazardFamily(DEFAULT_STUDY, 0, "constant");
    const next = setHazardParam(constant, 0, "p", 0.4);
    expect(next.colors[0].hazard).toEqual({ family: "constant", p: 0.4 });
  });
});

describe("removeColor", () => {
  it("removes the color at the given index", () => {
    const next = removeColor(DEFAULT_STUDY, 0);
    expect(next.colors.map((c) => c.name)).toEqual(["teal", "orange"]);
  });

  it("keeps at least one color (no-op when only one remains)", () => {
    const single = { ...DEFAULT_STUDY, colors: [DEFAULT_STUDY.colors[0]] };
    expect(removeColor(single, 0)).toEqual(single);
  });
});

describe("addColor", () => {
  it("appends a color with a name not already in use", () => {
    const next = addColor(DEFAULT_STUDY);
    expect(next.colors).toHaveLength(DEFAULT_STUDY.colors.length + 1);
    const names = next.colors.map((c) => c.name);
    expect(new Set(names).size).toBe(names.length);
  });
});

describe("parseNumberList", () => {
  it("parses a comma-separated list of numbers", () => {
    expect(parseNumberList("1, 2.5, 3")).toEqual([1, 2.5, 3]);
  });

  it("ignores blank and non-numeric entries", () => {
    expect(parseNumberList("0.1, , 0.5, x")).toEqual([0.1, 0.5]);
  });
});

describe("parseStudy", () => {
  it("parses serialized study JSON back into a config", () => {
    expect(parseStudy(JSON.stringify(DEFAULT_STUDY))).toEqual(DEFAULT_STUDY);
  });

  it("throws on malformed JSON so the loader can surface an error", () => {
    expect(() => parseStudy("{not valid json")).toThrow();
  });

  it("round-trips a study's declared conditions (issue 37)", () => {
    const study = { ...DEFAULT_STUDY, conditions: ["control", "experimental"] };
    expect(parseStudy(JSON.stringify(study))).toEqual(study);
  });
});

describe("parseConditionList", () => {
  it("parses comma-separated condition names, trimming whitespace", () => {
    expect(parseConditionList("control, experimental")).toEqual([
      "control",
      "experimental",
    ]);
  });

  it("drops blank entries (trailing commas while typing)", () => {
    expect(parseConditionList("control, , experimental,")).toEqual([
      "control",
      "experimental",
    ]);
  });

  it("returns an empty list for blank input — the study has no conditions", () => {
    expect(parseConditionList("   ")).toEqual([]);
  });
});
