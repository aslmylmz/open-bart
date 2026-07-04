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

  it("shows the payout owed when the study converts earnings (issue 41)", () => {
    render(
      <Debrief
        language="en"
        earnings={12.5}
        balloonsCompleted={30}
        payout={{ amount: 1.25, currency: "₺" }}
      />,
    );

    expect(screen.getByText(t.payoutLabel)).toBeTruthy();
    expect(screen.getByText("1.25 ₺")).toBeTruthy();
  });

  it("localizes the payout label for Turkish studies", () => {
    const tr = taskStrings("tr");
    render(
      <Debrief
        language="tr"
        earnings={12.5}
        balloonsCompleted={30}
        payout={{ amount: 45.5, currency: "₺" }}
      />,
    );

    expect(screen.getByText(tr.payoutLabel)).toBeTruthy();
    expect(screen.getByText("45.50 ₺")).toBeTruthy();
  });

  it("shows no payout line for studies without a payout block", () => {
    render(<Debrief language="en" earnings={12.5} balloonsCompleted={30} />);

    expect(screen.queryByText(t.payoutLabel)).toBeNull();
  });

  // Issue 59 (F10): a practice/test run banners "data not recorded" on every
  // screen, so the thank-you must not contradict it by claiming the session was
  // recorded.
  it("makes no recording claim in a practice run", () => {
    render(<Debrief language="en" earnings={12.5} balloonsCompleted={30} practice />);

    expect(screen.getByText(t.thankYouBodyPractice)).toBeTruthy();
    expect(screen.queryByText(t.thankYouBody)).toBeNull();
  });

  it("keeps the recorded copy for a real (non-practice) run", () => {
    render(<Debrief language="en" earnings={12.5} balloonsCompleted={30} />);

    expect(screen.getByText(t.thankYouBody)).toBeTruthy();
    expect(screen.queryByText(t.thankYouBodyPractice)).toBeNull();
  });

  it("localizes the practice copy for Turkish studies", () => {
    const tr = taskStrings("tr");
    render(<Debrief language="tr" earnings={12.5} balloonsCompleted={30} practice />);

    expect(screen.getByText(tr.thankYouBodyPractice)).toBeTruthy();
    expect(screen.queryByText(tr.thankYouBody)).toBeNull();
  });
});
