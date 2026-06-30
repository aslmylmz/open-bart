import { describe, expect, it } from "vitest";

import { curveGeometry } from "./evGeometry";

const box = { width: 100, height: 100, padding: 0 };

describe("curveGeometry", () => {
  it("scales survival, EV, and hazard into the plot box", () => {
    const curve = {
      hazard: [0.5, 1.0],
      survival: [1, 0.5, 0],
      ev: [0, 1, 0],
      optimum: 1,
      optimal_ev: 1,
    };
    const g = curveGeometry(curve, box);
    // x: stop s -> s/2 * 100; y (inverted): height - v/vMax * 100.
    expect(g.survival).toBe("0,0 50,50 100,100");
    expect(g.ev).toBe("0,100 50,0 100,100");
    // hazard h(k) lives at stop k (1..N): h(1)=0.5 -> (50,50), h(2)=1 -> (100,0).
    expect(g.hazard).toBe("50,50 100,0");
  });

  it("places the optimum marker at the optimum stop, honoring padding", () => {
    const curve = {
      hazard: [0.1, 0.2, 0.4, 0.8],
      survival: [1, 0.9, 0.7, 0.4, 0],
      ev: [0, 1, 2, 1, 0],
      optimum: 2,
      optimal_ev: 2,
    };
    // innerW = 120 - 2*10 = 100; xAt(2) = 10 + (2/4)*100 = 60.
    const g = curveGeometry(curve, { width: 120, height: 100, padding: 10 });
    expect(g.optimumX).toBe(60);
  });

  it("degrades gracefully on degenerate curves (no NaN)", () => {
    const empty = curveGeometry(
      { hazard: [], survival: [], ev: [], optimum: 0, optimal_ev: 0 },
      box,
    );
    expect(empty).toEqual({ hazard: "", survival: "", ev: "", optimumX: 0 });

    const flatZeroEv = curveGeometry(
      { hazard: [0, 0], survival: [1, 1, 1], ev: [0, 0, 0], optimum: 1, optimal_ev: 0 },
      box,
    );
    expect(flatZeroEv.ev).not.toContain("NaN");
  });
});
