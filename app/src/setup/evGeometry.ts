/** Pure geometry for the live EV preview (SPEC §7.3).
 *
 * Turns one color's precomputed curve (the sidecar's `/preview` `CurvePreview`)
 * into SVG polyline point-strings + the optimum marker x, scaled into a plot box.
 * No DOM/React, so it is fully unit-testable; `EvPreview.tsx` is the thin shell
 * that fetches the curves and renders these strings.
 */

import type { CurvePreview } from "../lib/api";

export type { CurvePreview };

export interface PlotBox {
  width: number;
  height: number;
  padding: number;
}

export interface CurveGeometry {
  hazard: string;
  survival: string;
  ev: string;
  /** x of the optimum stop, for a vertical marker line. */
  optimumX: number;
}

function fmt(n: number): string {
  return `${Math.round(n * 100) / 100}`;
}

/** Scale a color's curve into `box`. Survival/hazard share the [0,1] axis; EV is
 * scaled by its own max (`optimal_ev`). Degenerate inputs (empty vectors, a flat
 * zero EV) yield valid strings rather than NaN, so an in-progress edit can't crash
 * the plot. */
export function curveGeometry(curve: CurvePreview, box: PlotBox): CurveGeometry {
  const { width, height, padding } = box;
  const n = curve.ev.length - 1; // stops 0..n
  const innerW = width - 2 * padding;
  const innerH = height - 2 * padding;

  const xAt = (s: number): number => padding + (n <= 0 ? 0 : (s / n) * innerW);
  const yAt = (v: number, vMax: number): number =>
    height - padding - (vMax <= 0 ? 0 : (v / vMax) * innerH);

  const survival = curve.survival.map((v, s) => `${fmt(xAt(s))},${fmt(yAt(v, 1))}`).join(" ");
  const ev = curve.ev.map((v, s) => `${fmt(xAt(s))},${fmt(yAt(v, curve.optimal_ev))}`).join(" ");
  const hazard = curve.hazard.map((v, i) => `${fmt(xAt(i + 1))},${fmt(yAt(v, 1))}`).join(" ");

  return { hazard, survival, ev, optimumX: xAt(curve.optimum) };
}
