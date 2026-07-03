import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "./App";
import { taskStrings } from "./lib/i18n";

// App renders the whole shell: VersionGuard (fetchHealth on mount), Study
// Setup (validateConfig + the EV preview), and the Run flow. Stub the api
// module so nothing touches the network; the guard's fetch failure leaves it
// open by design (issue 35).
const fetchHealth = vi.fn();
const preview = vi.fn();
const validateConfig = vi.fn();
const checkId = vi.fn();
const submitSession = vi.fn();
const persistSession = vi.fn();
vi.mock("./lib/api", () => ({
  fetchHealth: (...args: unknown[]) => fetchHealth(...args),
  preview: (...args: unknown[]) => preview(...args),
  validateConfig: (...args: unknown[]) => validateConfig(...args),
  checkId: (...args: unknown[]) => checkId(...args),
  submitSession: (...args: unknown[]) => submitSession(...args),
  persistSession: (...args: unknown[]) => persistSession(...args),
}));

const t = taskStrings("en");

beforeEach(() => {
  fetchHealth.mockRejectedValue(new Error("no sidecar in tests"));
  validateConfig.mockResolvedValue({ ok: true, errors: [] });
  preview.mockResolvedValue({ curves: {} });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("Test Run control (issue 43)", () => {
  it("starts a bannered practice session, leaving Start run official", async () => {
    render(<App />);

    // Both controls live side by side in the Researcher View.
    const testRun = screen.getByRole("button", { name: /test run/i });
    expect(screen.getByRole("button", { name: /start run/i })).toBeTruthy();

    await userEvent.click(testRun);

    // The participant flow opens in practice mode: bannered from consent on.
    expect(await screen.findByText(t.consentTitle)).toBeTruthy();
    expect(screen.getByText(t.practiceBanner)).toBeTruthy();
  });

  it("keeps the normal Start run path banner-free", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: /start run/i }));

    expect(await screen.findByText(t.consentTitle)).toBeTruthy();
    expect(screen.queryByText(t.practiceBanner)).toBeNull();
  });
});
