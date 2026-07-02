import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BartGame from "./BartGame";
import type { TaskConfig } from "./lib/config";
import { taskStrings } from "./lib/i18n";

// The task only talks to the sidecar on submit; stub the api module so component
// tests never touch the network (same convention as RunFlow.test.tsx).
vi.mock("./lib/api", () => ({
  submitSession: vi.fn(),
  persistSession: vi.fn(),
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

afterEach(cleanup);

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

  it("tracks completed balloons in an accessible timeline", async () => {
    renderGame();
    await startTask();

    // The track is present (and empty) from the first balloon on.
    const track = screen.getByRole("list", { name: t.progressLabel });
    expect(within(track).queryAllByRole("listitem")).toHaveLength(0);

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));

    // One dot appears once the collect feedback resolves into the next balloon.
    await waitFor(() => expect(within(track).getAllByRole("listitem")).toHaveLength(1), {
      timeout: 3000,
    });
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
});
