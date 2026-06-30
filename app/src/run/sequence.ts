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
