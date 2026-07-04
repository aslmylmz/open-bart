import { describe, expect, it } from "vitest";

import { DEFAULT_STUDY } from "../lib/config";
import { buildSequence, deriveRunSeed, mulberry32 } from "./sequence";

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

describe("deriveRunSeed (per-participant reproducibility, issue 61)", () => {
  const hazards = { purple: [0.1, 0.2], teal: [0.3], orange: [0.5] };
  const runOrder = (studySeed: number | null, id: string) =>
    buildSequence(threeColor([10, 10, 10]), hazards, mulberry32(deriveRunSeed(studySeed, id))).map(
      (b) => b.colorName,
    );

  it("gives two participants different run seeds under the same fixed study seed", () => {
    // The D3 fix: a fixed study seed must not collapse every participant onto one
    // sequence. Different IDs → different run seeds → divergent shuffle + bursts.
    expect(deriveRunSeed(7, "P001")).not.toBe(deriveRunSeed(7, "P002"));
    expect(runOrder(7, "P001")).not.toEqual(runOrder(7, "P002"));
  });

  it("replays byte-identically for the same (seed, participant) — the SPEC §7.2 contract", () => {
    expect(deriveRunSeed(7, "P001")).toBe(deriveRunSeed(7, "P001"));
    expect(runOrder(7, "P001")).toEqual(runOrder(7, "P001"));
  });

  it("yields a fresh seed per run when the study seed is null (v1.0.0 default)", () => {
    // No fixed seed → each run is fresh and independent, even for the same ID.
    expect(deriveRunSeed(null, "P001")).not.toBe(deriveRunSeed(null, "P001"));
  });
});
