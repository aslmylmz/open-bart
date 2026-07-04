import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BartGame from "./BartGame";
import type { TaskConfig } from "./lib/config";
import { taskStrings } from "./lib/i18n";

// The task only talks to the sidecar on submit; stub the api module so component
// tests never touch the network (same convention as RunFlow.test.tsx).
const submitSession = vi.fn();
const persistSession = vi.fn();
vi.mock("./lib/api", () => ({
  submitSession: (...args: unknown[]) => submitSession(...args),
  persistSession: (...args: unknown[]) => persistSession(...args),
}));

const t = taskStrings("en");

// One color, two balloons, hazard 0 at every pump — deterministic: no balloon
// ever pops, so the flow is driven purely by Pump/Collect clicks.
const TEST_CONFIG: TaskConfig = {
  schema_version: "1.0",
  title: "Component test study",
  language: "en",
  reward_per_pump: 0.25,
  seed: 42,
  output_dir: ".",
  colors: [
    {
      name: "purple",
      label: "Purple",
      display_hex: "#7c3aed",
      max_pumps: 8,
      trials: 2,
      hazard: { family: "dynamic" },
    },
  ],
};

const SAFE_HAZARDS = { purple: [0, 0, 0, 0, 0, 0, 0, 0] };

function renderGame() {
  render(<BartGame config={TEST_CONFIG} hazards={SAFE_HAZARDS} candidateId="P001" />);
}

async function startTask() {
  await userEvent.click(screen.getByRole("button", { name: t.startButton }));
}

afterEach(() => {
  cleanup();
  submitSession.mockReset();
  persistSession.mockReset();
});

describe("BartGame gameplay screen", () => {
  it("shows the current earnings once, below the balloon, updating per pump", async () => {
    renderGame();
    await startTask();

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));

    // The pumped amount appears exactly once — as the static counter under the
    // balloon, not as text inside the balloon (Issue 27).
    const matches = screen.getAllByText(/\$0\.50/);
    expect(matches).toHaveLength(1);
    expect(matches[0].textContent).toBe(`${t.currentLabel}: $0.50`);
  });

  it("advances the balloon counter and running total after a collect", async () => {
    renderGame();
    await startTask();

    expect(screen.getByText(`${t.balloonLabel} 1/2`)).toBeTruthy();
    expect(screen.getByText(`${t.totalLabel} $0.00`)).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));

    // The collect feedback lasts ~1s before the next balloon begins.
    expect(
      await screen.findByText(`${t.balloonLabel} 2/2`, undefined, { timeout: 3000 }),
    ).toBeTruthy();
    expect(screen.getByText(`${t.totalLabel} $0.25`)).toBeTruthy();
  });

  it("shows the whole session on the progress timeline, filling dots as balloons resolve", async () => {
    renderGame();
    await startTask();

    // One dot per balloon in the session (CONTEXT.md Gameplay Layout: hollow =
    // upcoming), so the participant sees full session progress from the start.
    const track = screen.getByRole("list", { name: t.progressLabel });
    expect(within(track).getAllByRole("listitem")).toHaveLength(2);
    expect(within(track).getAllByLabelText(new RegExp(t.statusUpcoming))).toHaveLength(2);

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));

    // Dot 1 fills as collected once the feedback resolves; the track keeps one
    // dot per balloon.
    await waitFor(
      () =>
        expect(
          within(track).getByLabelText(`${t.balloonLabel} 1: ${t.statusCollected}`),
        ).toBeTruthy(),
      { timeout: 3000 },
    );
    expect(within(track).getAllByRole("listitem")).toHaveLength(2);
  });

  it("offers Back to setup on the instructions screen but hides it mid-trial", async () => {
    const onExit = vi.fn();
    render(
      <BartGame
        config={TEST_CONFIG}
        hazards={SAFE_HAZARDS}
        candidateId="P001"
        onExit={onExit}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /back to setup/i }));
    expect(onExit).toHaveBeenCalledTimes(1);

    // Once a balloon is live there is no exit — prevents accidental mid-trial exits.
    await startTask();
    expect(screen.queryByRole("button", { name: /back to setup/i })).toBeNull();
  });

  it("lands on the participant thank-you screen after submitting a finished session", async () => {
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockResolvedValue({});
    renderGame();
    await startTask();

    // Resolve both balloons with one pump + collect each (hazard 0 — never pops),
    // waiting out the ~1s feedback between them.
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(`${t.balloonLabel} 2/2`, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));

    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));

    // The debrief shows the session's own earnings and balloon count.
    expect(await screen.findByText(t.thankYouTitle)).toBeTruthy();
    expect(screen.getByText("$0.50")).toBeTruthy();
    expect(screen.getByText(`2 ${t.balloonsWord}`)).toBeTruthy();
  });

  it("keeps the participant off the thank-you screen when the save fails (issue 49)", async () => {
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockRejectedValue(new Error("output directory is not writable"));
    renderGame();
    await startTask();

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(`${t.balloonLabel} 2/2`, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));

    // The write failed, so the session was NOT recorded: the participant must
    // never see the "recorded" confirmation. A retryable error keeps them on the
    // finished screen instead (issue 49 / kaizen F1).
    expect(await screen.findByText(t.saveError)).toBeTruthy();
    expect(screen.queryByText(t.thankYouTitle)).toBeNull();
    expect(screen.getByRole("button", { name: t.seeResults })).toBeTruthy();
  });

  it("reaches the thank-you once a failed save is retried and succeeds (issue 49)", async () => {
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockRejectedValueOnce(new Error("output directory is not writable"));
    persistSession.mockResolvedValue({});
    renderGame();
    await startTask();

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(`${t.balloonLabel} 2/2`, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });

    // First attempt: the write fails, so no confirmation and the button stays.
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));
    expect(await screen.findByText(t.saveError)).toBeTruthy();
    expect(screen.queryByText(t.thankYouTitle)).toBeNull();

    // Retry: the write lands this time, so the session is recorded and only now
    // does the debrief appear.
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));
    expect(await screen.findByText(t.thankYouTitle)).toBeTruthy();
  });

  it("surfaces a write warning to the researcher on the debrief (issue 50)", async () => {
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockResolvedValue({
      warnings: [
        "Could not update study_results.csv (Permission denied) — the file may be " +
          "open in another program (e.g. Excel) or damaged. The session's rows were " +
          "saved to study_results_unmerged_20260704T000000000000Z.csv; merge them " +
          "into the main file by hand.",
      ],
    });
    renderGame();
    await startTask();

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(`${t.balloonLabel} 2/2`, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));

    // The write succeeded (to a sibling file), so the debrief still shows — but
    // the researcher is now told the master CSV was locked and where the rows
    // landed, instead of the warning being silently dropped (issue 50 / F2).
    expect(await screen.findByText(t.thankYouTitle)).toBeTruthy();
    expect(screen.getByText(/study_results_unmerged_.*\.csv/)).toBeTruthy();
  });

  it("shows no save-warning notice when the write is clean (issue 50)", async () => {
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockResolvedValue({ warnings: [] });
    renderGame();
    await startTask();

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(`${t.balloonLabel} 2/2`, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));

    // A clean write must not raise a notice — the debrief stays uncluttered.
    expect(await screen.findByText(t.thankYouTitle)).toBeTruthy();
    expect(screen.queryByText(t.saveWarningTitle)).toBeNull();
  });

  it("shows debrief earnings in the study's configured currency (issue 55)", async () => {
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockResolvedValue({ warnings: [] });
    render(
      <BartGame
        config={{ ...TEST_CONFIG, currency: "€" }}
        hazards={SAFE_HAZARDS}
        candidateId="P001"
      />,
    );
    await startTask();

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(`${t.balloonLabel} 2/2`, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));

    // The debrief earnings figure uses the study's currency, not a hardcoded $.
    expect(await screen.findByText(t.thankYouTitle)).toBeTruthy();
    expect(screen.getByText("€0.50")).toBeTruthy();
    expect(screen.queryByText("$0.50")).toBeNull();
  });

  it("shows in-task earnings in the study's configured currency (issue 55)", async () => {
    render(
      <BartGame
        config={{ ...TEST_CONFIG, currency: "₺" }}
        hazards={SAFE_HAZARDS}
        candidateId="P001"
      />,
    );
    await startTask();

    // Running total and per-pump current earnings both use the study's currency.
    expect(screen.getByText(`${t.totalLabel} ₺0.00`)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    expect(screen.getByText(`${t.currentLabel}: ₺0.25`)).toBeTruthy();
  });

  it("shows the engine-computed payout on the debrief (issue 41)", async () => {
    submitSession.mockResolvedValue({
      session_id: "s-1",
      raw_metrics: { payout_amount: 0.73, payout_currency: "₺" },
    });
    persistSession.mockResolvedValue({});
    renderGame();
    await startTask();

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(`${t.balloonLabel} 2/2`, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));

    // The debrief shows the amount owed exactly as the engine computed it —
    // the client never re-derives or re-rounds.
    expect(await screen.findByText(t.payoutLabel)).toBeTruthy();
    expect(screen.getByText("0.73 ₺")).toBeTruthy();
  });

  it("submits the assigned condition with the session (issue 37)", async () => {
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockResolvedValue({});
    render(
      <BartGame
        config={TEST_CONFIG}
        hazards={SAFE_HAZARDS}
        candidateId="P001"
        condition="experimental"
      />,
    );
    await startTask();

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(`${t.balloonLabel} 2/2`, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));

    await waitFor(() => expect(submitSession).toHaveBeenCalledTimes(1));
    const [payload] = submitSession.mock.calls[0] as [{ condition: string | null }];
    expect(payload.condition).toBe("experimental");
    // The persisted session carries the same assignment (one payload, two sinks).
    await waitFor(() => expect(persistSession).toHaveBeenCalledTimes(1));
    expect((persistSession.mock.calls[0] as [{ condition: string | null }])[0].condition).toBe(
      "experimental",
    );
  });
});
