import { describe, expect, it } from "vitest";

import { DEFAULT_STUDY, type TaskConfig } from "../lib/config";
import {
  knownFieldPaths,
  mapErrorsToFields,
  retargetTouchedAfterColorRemoval,
  visibleFieldErrors,
} from "./validation";

/** A study exercising every mapping shape: a payout block, an array-family
 * hazard (step), and a scalar-family hazard (weibull, whose param locs carry
 * the pydantic union tag). */
const STUDY: TaskConfig = {
  ...DEFAULT_STUDY,
  payout: { rate: 1, currency: "$" },
  colors: [
    { ...DEFAULT_STUDY.colors[0], hazard: { family: "step", breakpoints: [4], levels: [0.05, 0.5] } },
    { ...DEFAULT_STUDY.colors[1], hazard: { family: "weibull", shape: 2 } },
  ],
};

const FIELDS = knownFieldPaths(STUDY);

describe("knownFieldPaths", () => {
  it("lists the base study fields including the QC pair", () => {
    for (const field of [
      "title",
      "language",
      "reward_per_pump",
      "seed",
      "conditions",
      "exit_passcode",
      "output_dir",
      "qc.fast_response_ms",
      "qc.zero_pump_streak",
    ]) {
      expect(FIELDS).toContain(field);
    }
  });

  it("includes payout fields only while the payout block exists", () => {
    expect(FIELDS).toContain("payout.rate");
    expect(FIELDS).toContain("payout.currency");

    const off = knownFieldPaths({ ...STUDY, payout: null });
    expect(off).not.toContain("payout.rate");
    expect(off).not.toContain("payout.currency");
  });

  it("lists each color's fields plus its current family's params", () => {
    for (const field of [
      "colors.0.name",
      "colors.0.label",
      "colors.0.display_hex",
      "colors.0.max_pumps",
      "colors.0.trials",
      "colors.0.hazard.family",
      "colors.0.hazard.breakpoints",
      "colors.0.hazard.levels",
      "colors.1.hazard.shape",
    ]) {
      expect(FIELDS).toContain(field);
    }
    // Params of families the color is not on are unknown.
    expect(FIELDS).not.toContain("colors.1.hazard.breakpoints");
    expect(FIELDS).not.toContain("colors.0.hazard.shape");
  });

  it("lists the tabular family's values field", () => {
    const tabular = knownFieldPaths({
      ...STUDY,
      colors: [{ ...DEFAULT_STUDY.colors[0], hazard: { family: "tabular", values: [0.1] } }],
    });
    expect(tabular).toContain("colors.0.hazard.values");
  });
});

describe("mapErrorsToFields", () => {
  it("maps a leaf error onto its field with the message alone", () => {
    const mapped = mapErrorsToFields(["reward_per_pump: Input should be greater than 0"], FIELDS);
    expect(mapped.byField["reward_per_pump"]).toEqual(["Input should be greater than 0"]);
    expect(mapped.unmappable).toEqual([]);
  });

  it("maps nested locs (qc, payout, colors) onto their fields", () => {
    const mapped = mapErrorsToFields(
      [
        "qc.fast_response_ms: Input should be greater than 0",
        "payout.currency: String should have at least 1 character",
        "colors.0.max_pumps: Input should be greater than 0",
      ],
      FIELDS,
    );
    expect(mapped.byField["qc.fast_response_ms"]).toEqual(["Input should be greater than 0"]);
    expect(mapped.byField["payout.currency"]).toEqual(["String should have at least 1 character"]);
    expect(mapped.byField["colors.0.max_pumps"]).toEqual(["Input should be greater than 0"]);
  });

  it("drops the union tag pydantic puts after `hazard` in param locs", () => {
    const mapped = mapErrorsToFields(
      ["colors.1.hazard.weibull.shape: Input should be greater than 0"],
      FIELDS,
    );
    expect(mapped.byField["colors.1.hazard.shape"]).toEqual(["Input should be greater than 0"]);
  });

  it("strips pydantic's 'Value error, ' preamble from inline messages", () => {
    const mapped = mapErrorsToFields(
      ["conditions: Value error, condition names must not repeat"],
      FIELDS,
    );
    expect(mapped.byField["conditions"]).toEqual(["condition names must not repeat"]);
  });

  it("fans a cross-field container error out to all fields under it", () => {
    const mapped = mapErrorsToFields(
      ["colors.0.hazard.step: Value error, step hazard needs len(levels) == len(breakpoints) + 1"],
      FIELDS,
    );
    const message = "step hazard needs len(levels) == len(breakpoints) + 1";
    expect(mapped.byField["colors.0.hazard.breakpoints"]).toEqual([message]);
    expect(mapped.byField["colors.0.hazard.levels"]).toEqual([message]);
    expect(mapped.byField["colors.0.hazard.family"]).toEqual([message]);
    // The other color is uninvolved.
    expect(mapped.byField["colors.1.hazard.shape"]).toBeUndefined();
  });

  it("attaches an error deeper than any control to the ancestor control", () => {
    const mapped = mapErrorsToFields(["conditions.1: Input should be a valid string"], FIELDS);
    expect(mapped.byField["conditions"]).toEqual(["Input should be a valid string"]);
  });

  it("accumulates multiple errors on one field in order", () => {
    const mapped = mapErrorsToFields(
      ["title: first problem", "title: second problem"],
      FIELDS,
    );
    expect(mapped.byField["title"]).toEqual(["first problem", "second problem"]);
  });

  it("keeps a pathless error verbatim as unmappable", () => {
    const mapped = mapErrorsToFields(["Validation request failed (500)"], FIELDS);
    expect(mapped.byField).toEqual({});
    expect(mapped.unmappable).toEqual(["Validation request failed (500)"]);
  });

  it("keeps an error on an unrendered field verbatim as unmappable", () => {
    // Top-level `currency` is valid in study.json but has no Study-Setup control.
    const mapped = mapErrorsToFields(
      ["currency: String should have at least 1 character"],
      FIELDS,
    );
    expect(mapped.byField).toEqual({});
    expect(mapped.unmappable).toEqual(["currency: String should have at least 1 character"]);
  });
});

describe("visibleFieldErrors — the touched-then-live rule", () => {
  const mapped = mapErrorsToFields(
    [
      "reward_per_pump: Input should be greater than 0",
      "colors.0.max_pumps: Input should be greater than 0",
    ],
    FIELDS,
  );

  it("shows nothing while no field is touched and no save was attempted", () => {
    expect(visibleFieldErrors(mapped, new Set(), false)).toEqual({});
  });

  it("shows only the touched field's errors", () => {
    const visible = visibleFieldErrors(mapped, new Set(["reward_per_pump"]), false);
    expect(visible["reward_per_pump"]).toEqual(["Input should be greater than 0"]);
    expect(visible["colors.0.max_pumps"]).toBeUndefined();
  });

  it("shows every mapped error after a save attempt, touched or not", () => {
    const visible = visibleFieldErrors(mapped, new Set(), true);
    expect(visible["reward_per_pump"]).toEqual(["Input should be greater than 0"]);
    expect(visible["colors.0.max_pumps"]).toEqual(["Input should be greater than 0"]);
  });
});

describe("retargetTouchedAfterColorRemoval", () => {
  it("drops the removed color's entries and shifts later colors down one", () => {
    const touched = new Set(["title", "colors.0.name", "colors.1.trials", "colors.2.max_pumps"]);
    const out = retargetTouchedAfterColorRemoval(touched, 1);
    expect([...out].sort()).toEqual(["colors.0.name", "colors.1.max_pumps", "title"]);
  });

  it("leaves earlier colors and non-color fields alone", () => {
    const out = retargetTouchedAfterColorRemoval(new Set(["colors.0.label", "seed"]), 2);
    expect([...out].sort()).toEqual(["colors.0.label", "seed"]);
  });
});
