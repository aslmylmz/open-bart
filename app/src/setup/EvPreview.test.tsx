import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";

import type { CurvePreview } from "../lib/api";
import { DEFAULT_STUDY } from "../lib/config";
import { EvPreview } from "./EvPreview";

// The preview fetches /preview through the api module — stub it so nothing
// touches the network (DESIGN-SPEC §5's component-test seam).
const preview = vi.fn();
vi.mock("../lib/api", () => ({
  preview: (...args: unknown[]) => preview(...args),
}));

/** A tiny well-formed curve — values are arbitrary but valid; only the stat
 * readouts (`optimum`, `optimal_ev`) are asserted on. */
function curve(optimum: number, optimal_ev: number): CurvePreview {
  return {
    hazard: [0.1, 0.2, 0.4],
    survival: [1, 0.9, 0.72, 0.43],
    ev: [0, 0.9, 1.4, 1.2],
    optimum,
    optimal_ev,
  };
}

/** Curves for DEFAULT_STUDY's three colors, stats matching the mockup. */
const CURVES = {
  curves: { purple: curve(64, 8), teal: curve(16, 2), orange: curve(4, 0.5) },
};

/** Flush the fetch debounce plus the resolved promise. Timings here mirror
 * EvPreview.tsx's PREVIEW_DEBOUNCE_MS (200) and RECOMPUTING_GUARD_MS (300);
 * both are spec numbers (§2.6), so the tests pin them deliberately. */
async function flushPreview() {
  await act(async () => {
    vi.advanceTimersByTime(250);
  });
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
});

describe("First render (§2.6)", () => {
  it("shows a computing… skeleton per color until the first curves land", async () => {
    vi.useFakeTimers();
    let resolveFirst!: (value: typeof CURVES) => void;
    preview.mockImplementation(() => new Promise((resolve) => (resolveFirst = resolve)));
    render(<EvPreview config={DEFAULT_STUDY} />);

    // Even a slow first fetch stays "computing…" — recomputing is for refetches.
    await act(async () => {
      vi.advanceTimersByTime(600);
    });
    expect(screen.getAllByText("computing…")).toHaveLength(DEFAULT_STUDY.colors.length);
    expect(screen.queryByText("recomputing…")).toBeNull();

    await act(async () => {
      resolveFirst(CURVES);
    });
    expect(screen.queryByText("computing…")).toBeNull();
    expect(screen.getByText("opt 64 · EV 8.00")).toBeTruthy();
  });
});

describe("Recomputing state (§2.6)", () => {
  it("appears once a refetch outlives the flicker guard, and clears when it lands", async () => {
    vi.useFakeTimers();
    preview.mockResolvedValue(CURVES);
    const { rerender } = render(<EvPreview config={DEFAULT_STUDY} />);
    await flushPreview();

    let resolveSlow!: (value: typeof CURVES) => void;
    preview.mockImplementation(() => new Promise((resolve) => (resolveSlow = resolve)));
    rerender(<EvPreview config={{ ...DEFAULT_STUDY, reward_per_pump: 0.5 }} />);

    // Debounce fired, request in flight — still inside the ~300ms guard.
    await act(async () => {
      vi.advanceTimersByTime(200);
    });
    expect(screen.queryByText("recomputing…")).toBeNull();

    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(screen.getByText("recomputing…")).toBeTruthy();
    // The last-good plot stays up underneath.
    expect(screen.getByText("opt 64 · EV 8.00")).toBeTruthy();

    await act(async () => {
      resolveSlow(CURVES);
    });
    expect(screen.queryByText("recomputing…")).toBeNull();
  });

  it("never appears for responses faster than the flicker guard", async () => {
    vi.useFakeTimers();
    preview.mockResolvedValue(CURVES);
    const { rerender } = render(<EvPreview config={DEFAULT_STUDY} />);
    await flushPreview();

    rerender(<EvPreview config={{ ...DEFAULT_STUDY, reward_per_pump: 0.5 }} />);
    await flushPreview();
    await act(async () => {
      vi.advanceTimersByTime(600);
    });

    expect(screen.queryByText("recomputing…")).toBeNull();
  });
});

describe("Stale state (§2.6)", () => {
  it("marks the preview stale when the refetch fails, keeping the last-good curves", async () => {
    vi.useFakeTimers();
    preview.mockResolvedValue(CURVES);
    const { rerender } = render(<EvPreview config={DEFAULT_STUDY} />);
    await flushPreview();

    preview.mockRejectedValue(new Error("reward_per_pump: Input should be greater than 0"));
    rerender(<EvPreview config={{ ...DEFAULT_STUDY, reward_per_pump: 0 }} />);
    await flushPreview();

    expect(screen.getByText("stale — fix errors to update")).toBeTruthy();
    expect(screen.getByText("opt 64 · EV 8.00")).toBeTruthy();
  });

  it("holds the stale marker through a slow revalidating fetch, then clears on success", async () => {
    vi.useFakeTimers();
    preview.mockResolvedValue(CURVES);
    const { rerender } = render(<EvPreview config={DEFAULT_STUDY} />);
    await flushPreview();

    preview.mockRejectedValue(new Error("invalid"));
    rerender(<EvPreview config={{ ...DEFAULT_STUDY, reward_per_pump: 0 }} />);
    await flushPreview();

    // The fix is in flight: even past the flicker guard the marker stays
    // "stale" rather than blinking over to "recomputing…".
    let resolveSlow!: (value: typeof CURVES) => void;
    preview.mockImplementation(() => new Promise((resolve) => (resolveSlow = resolve)));
    rerender(<EvPreview config={DEFAULT_STUDY} />);
    await act(async () => {
      vi.advanceTimersByTime(600);
    });
    expect(screen.getByText("stale — fix errors to update")).toBeTruthy();
    expect(screen.queryByText("recomputing…")).toBeNull();

    await act(async () => {
      resolveSlow(CURVES);
    });
    expect(screen.queryByText("stale — fix errors to update")).toBeNull();
  });
});

describe("Stat chips & legend (§2.6)", () => {
  it("renders a chip per color: label plus `opt <n> · EV <x.xx>`", async () => {
    vi.useFakeTimers();
    preview.mockResolvedValue(CURVES);
    render(<EvPreview config={DEFAULT_STUDY} />);
    await flushPreview();

    expect(screen.getByText("Purple")).toBeTruthy();
    expect(screen.getByText("opt 64 · EV 8.00")).toBeTruthy();
    expect(screen.getByText("Teal")).toBeTruthy();
    expect(screen.getByText("opt 16 · EV 2.00")).toBeTruthy();
    expect(screen.getByText("Orange")).toBeTruthy();
    expect(screen.getByText("opt 4 · EV 0.50")).toBeTruthy();
  });

  it("renders one shared legend below the panels", async () => {
    vi.useFakeTimers();
    preview.mockResolvedValue(CURVES);
    render(<EvPreview config={DEFAULT_STUDY} />);
    await flushPreview();

    expect(screen.getByText("EV (profile color)")).toBeTruthy();
    expect(screen.getByText("Survival")).toBeTruthy();
    expect(screen.getByText("Hazard")).toBeTruthy();
    expect(screen.getByText("optimum")).toBeTruthy();
  });
});
