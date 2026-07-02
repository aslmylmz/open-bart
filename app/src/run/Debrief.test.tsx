import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { taskStrings } from "../lib/i18n";
import { Debrief } from "./Debrief";

const t = taskStrings("en");

afterEach(cleanup);

describe("Debrief (participant thank-you screen)", () => {
  it("thanks the participant and shows the high-level summary", () => {
    render(<Debrief language="en" earnings={12.5} balloonsCompleted={30} />);

    expect(screen.getByText(t.thankYouTitle)).toBeTruthy();
    expect(screen.getByText(t.totalEarnings)).toBeTruthy();
    expect(screen.getByText("$12.50")).toBeTruthy();
    expect(screen.getByText(`30 ${t.balloonsWord}`)).toBeTruthy();
  });

  it("exposes no clinical metrics to the participant", () => {
    render(<Debrief language="en" earnings={12.5} balloonsCompleted={30} />);

    // Spot-check the labels the old debrief leaked; the detailed metrics stay
    // researcher-only, in the session files (Issue 28).
    const leakedLabels = [
      /Dürtüsellik/i,
      /impulsiv/i,
      /Uyum Stratejisi/i,
      /Öğrenme Hızı/i,
      /z=/,
    ];
    for (const leaked of leakedLabels) {
      expect(screen.queryByText(leaked)).toBeNull();
    }
  });
});
