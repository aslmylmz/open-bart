import { describe, expect, it } from "vitest";

import { DEFAULT_STUDY } from "../lib/config";
import {
  addColor,
  DEFAULT_PAYOUT,
  DEFAULT_QC,
  parseConditionList,
  parseExitPasscode,
  parseNumberList,
  parseStudy,
  removeColor,
  setColorHazardFamily,
  setHazardParam,
  setPayoutEnabled,
  setPayoutField,
  setQcField,
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

describe("setQcField", () => {
  it("materializes qc from the defaults when the study has none, patching the edited field", () => {
    // The default study omits qc (absent = engine defaults); editing one field
    // seeds the block so the untouched threshold keeps its literature default.
    const next = setQcField(DEFAULT_STUDY, { fast_response_ms: 250 });
    expect(next.qc).toEqual({ fast_response_ms: 250, zero_pump_streak: DEFAULT_QC.zero_pump_streak });
  });

  it("patches one threshold on an existing qc block, leaving the sibling", () => {
    const withQc = setQcField(DEFAULT_STUDY, { fast_response_ms: 80 });
    const next = setQcField(withQc, { zero_pump_streak: 7 });
    expect(next.qc).toEqual({ fast_response_ms: 80, zero_pump_streak: 7 });
  });

  it("does not mutate the input config", () => {
    setQcField(DEFAULT_STUDY, { fast_response_ms: 250 });
    expect(DEFAULT_STUDY.qc).toBeUndefined();
  });
});

describe("setPayoutEnabled", () => {
  it("materializes a default payout block when enabled on a study with none", () => {
    // The default study has no payout (v1.0.0 behavior); enabling seeds a valid
    // starting block the researcher can then edit.
    const next = setPayoutEnabled(DEFAULT_STUDY, true);
    expect(next.payout).toEqual(DEFAULT_PAYOUT);
  });

  it("clears the payout to null when disabled — the no-payout state", () => {
    const withPayout = setPayoutEnabled(DEFAULT_STUDY, true);
    const next = setPayoutEnabled(withPayout, false);
    expect(next.payout).toBeNull();
  });

  it("keeps the existing payout block when re-enabled (no clobber)", () => {
    const custom = { ...DEFAULT_STUDY, payout: { rate: 3.5, currency: "₺" } };
    expect(setPayoutEnabled(custom, true).payout).toEqual({ rate: 3.5, currency: "₺" });
  });
});

describe("setPayoutField", () => {
  it("patches one payout field on an existing block, leaving the sibling", () => {
    const withPayout = setPayoutEnabled(DEFAULT_STUDY, true);
    const next = setPayoutField(withPayout, { rate: 4.2 });
    expect(next.payout).toEqual({ rate: 4.2, currency: DEFAULT_PAYOUT.currency });
  });

  it("updates the currency label", () => {
    const withPayout = setPayoutEnabled(DEFAULT_STUDY, true);
    const next = setPayoutField(withPayout, { currency: "₺" });
    expect(next.payout).toEqual({ rate: DEFAULT_PAYOUT.rate, currency: "₺" });
  });

  it("does not mutate the input config", () => {
    const withPayout = setPayoutEnabled(DEFAULT_STUDY, true);
    setPayoutField(withPayout, { rate: 9 });
    expect(withPayout.payout).toEqual(DEFAULT_PAYOUT);
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

  it("round-trips edited qc thresholds and a payout block (issue 47)", () => {
    const study = setPayoutField(
      setQcField(DEFAULT_STUDY, { fast_response_ms: 250, zero_pump_streak: 8 }),
      { rate: 2.5, currency: "₺" },
    );
    const reloaded = parseStudy(JSON.stringify(study));
    expect(reloaded.qc).toEqual({ fast_response_ms: 250, zero_pump_streak: 8 });
    expect(reloaded.payout).toEqual({ rate: 2.5, currency: "₺" });
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

describe("parseExitPasscode", () => {
  it("trims the entry to the passcode the researcher will type at the prompt", () => {
    expect(parseExitPasscode("  1234 ")).toBe("1234");
  });

  it("returns null for blank input — the study has no kiosk lock", () => {
    expect(parseExitPasscode("")).toBeNull();
    expect(parseExitPasscode("   ")).toBeNull();
  });
});
