import { describe, expect, it } from "vitest";

import { STRINGS, taskStrings } from "./i18n";

describe("task strings", () => {
  it("define the same keys in every language (no missing translations)", () => {
    expect(Object.keys(STRINGS.en).sort()).toEqual(Object.keys(STRINGS.tr).sort());
  });

  it("selects the table for the requested language", () => {
    expect(taskStrings("en")).toBe(STRINGS.en);
    expect(taskStrings("tr")).toBe(STRINGS.tr);
    expect(taskStrings("en").startButton).not.toBe(taskStrings("tr").startButton);
  });
});
