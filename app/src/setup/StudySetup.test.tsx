import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { DEFAULT_STUDY, type TaskConfig } from "../lib/config";
import { StudySetup } from "./StudySetup";

// The form validates through the sidecar and the embedded EV preview fetches
// /preview; stub the api module so nothing touches the network.
const validateConfig = vi.fn().mockResolvedValue({ ok: true, errors: [] });
const preview = vi.fn().mockResolvedValue({ curves: {} });
vi.mock("../lib/api", () => ({
  validateConfig: (...args: unknown[]) => validateConfig(...args),
  preview: (...args: unknown[]) => preview(...args),
}));

// Save/load/folder-picking go through native Tauri dialogs — none exist in jsdom.
vi.mock("../lib/desktop", () => ({
  saveStudy: vi.fn(),
  loadStudy: vi.fn(),
  selectOutputDir: vi.fn(),
}));

// StudySetup is controlled; a stateful harness lets removals actually re-render.
function Harness({ initial }: { initial: TaskConfig }) {
  const [config, setConfig] = useState(initial);
  return (
    <StudySetup config={config} onChange={setConfig} onTestRun={() => {}} onStartRun={() => {}} />
  );
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function removeButtons() {
  return screen.getAllByRole("button", { name: /^remove$/i });
}

describe("Color profile remove — two-step inline confirm", () => {
  it("arms on the first click instead of removing", async () => {
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(removeButtons()[0]);

    // Nothing is removed yet; the clicked button now asks for confirmation.
    expect(screen.getByRole("button", { name: /confirm remove/i })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /remove/i })).toHaveLength(3);
    expect(screen.getByDisplayValue("purple")).toBeTruthy();
  });

  it("removes the profile on the confirming second click", async () => {
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(removeButtons()[0]);
    await userEvent.click(screen.getByRole("button", { name: /confirm remove/i }));

    expect(screen.getAllByRole("button", { name: /remove/i })).toHaveLength(2);
    expect(screen.queryByDisplayValue("purple")).toBeNull();
    expect(screen.getByDisplayValue("teal")).toBeTruthy();
  });

  it("reverts to the quiet state after ~3s without a confirm", () => {
    vi.useFakeTimers();
    render(<Harness initial={DEFAULT_STUDY} />);

    fireEvent.click(removeButtons()[0]);
    expect(screen.getByRole("button", { name: /confirm remove/i })).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(3100);
    });

    // Armed state expired: all three profiles intact, no confirm button left.
    expect(screen.queryByRole("button", { name: /confirm remove/i })).toBeNull();
    expect(removeButtons()).toHaveLength(3);
  });

  it("only arms one profile at a time", async () => {
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(removeButtons()[0]);
    // Arming a second profile disarms the first — a stray confirm can't
    // remove a card the researcher is no longer looking at.
    await userEvent.click(screen.getAllByRole("button", { name: /^remove$/i })[0]);

    expect(screen.getAllByRole("button", { name: /confirm remove/i })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: /remove/i })).toHaveLength(3);
  });

  it("disables Remove when only one profile remains", () => {
    render(<Harness initial={{ ...DEFAULT_STUDY, colors: [DEFAULT_STUDY.colors[0]] }} />);

    const button = screen.getByRole<HTMLButtonElement>("button", { name: /^remove$/i });
    expect(button.disabled).toBe(true);
  });
});
