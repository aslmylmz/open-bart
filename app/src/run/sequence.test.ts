import { describe, expect, it } from "vitest";

import { DEFAULT_STUDY } from "../lib/config";
import { buildSequence, mulberry32 } from "./sequence";

const threeColor = (trials: [number, number, number]) => ({
  ...DEFAULT_STUDY,
  colors: DEFAULT_STUDY.colors.map((c, i) => ({ ...c, trials: trials[i] })),
});

describe("mulberry32", () => {
  it("is deterministic: the same seed yields the same stream", () => {
    const a = mulberry32(42);
    const b = mulberry32(42);
    const seqA = [a(), a(), a()];
    const seqB = [b(), b(), b()];
    expect(seqA).toEqual(seqB);
    expect(seqA.every((x) => x >= 0 && x < 1)).toBe(true);
  });
});

describe("buildSequence", () => {
  const hazards = { purple: [0.1, 0.2], teal: [0.3], orange: [0.5] };

  it("creates `trials` balloons per color, each carrying its hazard vector", () => {
    const seq = buildSequence(threeColor([2, 1, 1]), hazards, mulberry32(1));
    expect(seq).toHaveLength(4);

    const counts: Record<string, number> = {};
    for (const b of seq) counts[b.colorName] = (counts[b.colorName] ?? 0) + 1;
    expect(counts).toEqual({ purple: 2, teal: 1, orange: 1 });

    const purple = seq.find((b) => b.colorName === "purple")!;
    expect(purple.hazard).toEqual([0.1, 0.2]);
    expect(purple.maxPumps).toBe(DEFAULT_STUDY.colors[0].max_pumps);
  });

  it("produces an identical order for the same seed (reproducible)", () => {
    const cfg = threeColor([10, 10, 10]);
    const orderA = buildSequence(cfg, hazards, mulberry32(7)).map((b) => b.colorName);
    const orderB = buildSequence(cfg, hazards, mulberry32(7)).map((b) => b.colorName);
    expect(orderA).toEqual(orderB);
  });
});
