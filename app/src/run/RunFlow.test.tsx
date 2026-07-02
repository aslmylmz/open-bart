import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DEFAULT_STUDY } from "../lib/config";
import { taskStrings } from "../lib/i18n";
import { RunFlow } from "./RunFlow";

// The loading phase fetches hazard vectors from the sidecar; stub it so the
// component under test never touches the network. Individual tests override the
// resolved/rejected value as needed.
const preview = vi.fn();
vi.mock("../lib/api", () => ({ preview: (...args: unknown[]) => preview(...args) }));

const t = taskStrings("en");

afterEach(() => {
  cleanup();
  preview.mockReset();
});

describe("RunFlow phase machine", () => {
  it("shows consent first and advances to the ID phase on agree", async () => {
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} />);

    expect(screen.getByText(t.consentTitle)).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));

    expect(screen.getByText(t.idPrompt)).toBeTruthy();
  });

  it("disables Continue on the ID phase until an ID is entered", async () => {
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));

    const cont = screen.getByRole<HTMLButtonElement>("button", { name: t.idContinue });
    expect(cont.disabled).toBe(true);

    await userEvent.type(screen.getByPlaceholderText(t.idPlaceholder), "P001");
    expect(cont.disabled).toBe(false);
  });

  async function reachLoading() {
    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));
    await userEvent.type(screen.getByPlaceholderText(t.idPlaceholder), "P001");
    await userEvent.click(screen.getByRole("button", { name: t.idContinue }));
  }

  it("exposes an accessible spinner while the task is loading", async () => {
    preview.mockReturnValue(new Promise(() => {})); // never resolves — stay in loading
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} />);

    await reachLoading();

    const status = screen.getByRole("status");
    expect(status.textContent).toContain(t.analyzing);
  });

  it("surfaces a load failure as an alert and retries back into loading", async () => {
    preview
      .mockRejectedValueOnce(new Error("sidecar unreachable"))
      .mockReturnValue(new Promise(() => {})); // retry stays in loading
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} />);

    await reachLoading();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("sidecar unreachable");

    await userEvent.click(screen.getByRole("button", { name: t.retry }));

    expect(await screen.findByRole("status")).toBeTruthy();
  });

  it("calls onExit when the back button is pressed", async () => {
    const onExit = vi.fn();
    render(<RunFlow config={DEFAULT_STUDY} onExit={onExit} />);

    await userEvent.click(screen.getByRole("button", { name: /back to setup/i }));

    expect(onExit).toHaveBeenCalledTimes(1);
  });
});
