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

describe("participant copy is hazard-family-neutral (issue 62)", () => {
  // The instrument ships constant/Lejuez families where the per-pump burst
  // probability does NOT rise, and CONTEXT.md keeps the hazard structure hidden
  // from participants. So the consent + instruction copy must not claim the pop
  // chance rises per pump (factually wrong for those families, and a priming leak).
  const risingHazardClaim = /raises? the chance|more likely to pop|olasılığını artır|riskini artır/i;

  it("en consent + instructions make no per-pump rising-hazard claim", () => {
    const s = taskStrings("en");
    expect(s.consentBody).not.toMatch(risingHazardClaim);
    expect(s.instructions).not.toMatch(risingHazardClaim);
  });

  it("tr consent + instructions make no per-pump rising-hazard claim", () => {
    const s = taskStrings("tr");
    expect(s.consentBody).not.toMatch(risingHazardClaim);
    expect(s.instructions).not.toMatch(risingHazardClaim);
  });

  it("still warns the pop costs that balloon's money (neutral, not vacuous)", () => {
    // Neutrality must not drop the risk warning: consent and instructions still
    // tell the participant a pop loses that balloon's money — the classic-BART cue.
    const en = taskStrings("en");
    expect(en.consentBody).toMatch(/lose .*money/i);
    expect(en.instructions).toMatch(/lose .*money/i);
    const tr = taskStrings("tr");
    expect(tr.consentBody).toMatch(/parasını kaybeders/i);
    expect(tr.instructions).toMatch(/parasını kaybeders/i);
  });
});

describe("action buttons stay measurement-neutral (issue 63)", () => {
  // The 💰/🎈 on Collect/Pump are reward-priming / arousal cues that work against
  // the sterile Light Posture (CONTEXT.md). The button labels must be plain text;
  // \p{Extended_Pictographic} matches emoji but not the Turkish letters (ş/ı/ğ).
  const emoji = /\p{Extended_Pictographic}/u;

  it("en Pump/Collect labels carry no emoji", () => {
    const s = taskStrings("en");
    expect(s.pumpButton).not.toMatch(emoji);
    expect(s.collectButton).not.toMatch(emoji);
  });

  it("tr Pump/Collect labels carry no emoji", () => {
    const s = taskStrings("tr");
    expect(s.pumpButton).not.toMatch(emoji);
    expect(s.collectButton).not.toMatch(emoji);
  });

  it("keeps the keyboard-hint mapping (Space→pump, Enter→collect) in both languages", () => {
    for (const lang of ["en", "tr"] as const) {
      const s = taskStrings(lang);
      expect(s.pumpButton).toMatch(/\((Space|Boşluk)\)/);
      expect(s.collectButton).toMatch(/\(Enter\)/);
    }
  });
});
