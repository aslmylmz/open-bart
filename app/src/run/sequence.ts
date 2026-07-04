/** Seeded balloon sequence + PRNG for the Run task (SPEC §7.2).
 *
 * The task bursts client-side from the precomputed hazard vectors (`/preview`),
 * drawing from a seeded PRNG so the same `seed` reproduces the same balloon order
 * and the same burst draws — the replay/QA guarantee. Pure and unit-testable;
 * `BartGame.tsx` consumes `buildSequence` and draws against each balloon's hazard.
 */

import type { TaskConfig } from "../lib/config";

/** One balloon to present: a color (display info + cap) paired with its hazard
 * vector, so the task draws `u < hazard[k-1]` per pump. */
export interface Balloon {
  colorName: string;
  label: string;
  displayHex: string;
  maxPumps: number;
  hazard: number[];
}

/** xmur3: hash a string to a well-distributed uint32. Used to fold a participant
 * ID into the run seed so IDs (not just numbers) can drive reproducibility. */
function hashId(id: string): number {
  let h = 1779033703 ^ id.length;
  for (let i = 0; i < id.length; i++) {
    h = Math.imul(h ^ id.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  h = Math.imul(h ^ (h >>> 16), 2246822507);
  h = Math.imul(h ^ (h >>> 13), 3266489909);
  return (h ^ (h >>> 16)) >>> 0;
}

/** The per-run PRNG seed (SPEC §7.2, issue 61). A **study-level** `seed` alone
 * would give every participant the identical shuffle + burst sequence (a D3 order
 * confound); instead the run seed mixes the study seed with the participant ID, so:
 *
 *   - a set `studySeed` reproduces each participant exactly from `(seed, id)` while
 *     different participants diverge — reproducible-yet-independent;
 *   - a `null` studySeed yields a fresh random seed per run (the v1.0.0 default).
 *
 * The reproducible escape hatch is by construction: re-running a study `seed` with
 * the same participant ID replays that run byte-identically (and a fixed-ID demo,
 * e.g. practice mode, shares one sequence). */
export function deriveRunSeed(studySeed: number | null, candidateId: string): number {
  if (studySeed === null) return (Math.random() * 2 ** 32) >>> 0;
  // splitmix32-style avalanche of (seed XOR idHash) so the study seed and the ID
  // both diffuse across all 32 bits — neighbouring IDs don't yield neighbouring runs.
  let x = ((studySeed >>> 0) ^ hashId(candidateId)) >>> 0;
  x = Math.imul(x ^ (x >>> 16), 0x45d9f3b) >>> 0;
  x = Math.imul(x ^ (x >>> 16), 0x45d9f3b) >>> 0;
  return (x ^ (x >>> 16)) >>> 0;
}

/** mulberry32: a tiny, fast, well-distributed seeded PRNG returning [0, 1). */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Build the run's balloon order: `trials` balloons per color (each carrying that
 * color's hazard vector), then a seeded Fisher-Yates shuffle. With the same seed
 * (same `rng`) the order is identical run to run. */
export function buildSequence(
  config: TaskConfig,
  hazards: Record<string, number[]>,
  rng: () => number,
): Balloon[] {
  const balloons: Balloon[] = [];
  for (const color of config.colors) {
    for (let i = 0; i < color.trials; i++) {
      balloons.push({
        colorName: color.name,
        label: color.label,
        displayHex: color.display_hex,
        maxPumps: color.max_pumps,
        hazard: hazards[color.name] ?? [],
      });
    }
  }
  for (let i = balloons.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [balloons[i], balloons[j]] = [balloons[j], balloons[i]];
  }
  return balloons;
}
