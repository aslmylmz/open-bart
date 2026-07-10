import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

// The desktop module fronts native Tauri dialogs and window calls, none of
// which exist in jsdom. Every export App or its children touch must be here.
const saveStudy = vi.fn();
const loadStudy = vi.fn();
const selectOutputDir = vi.fn();
const toggleFullscreen = vi.fn();
const setKioskLock = vi.fn();
vi.mock("./lib/desktop", () => ({
  saveStudy: (...args: unknown[]) => saveStudy(...args),
  loadStudy: (...args: unknown[]) => loadStudy(...args),
  selectOutputDir: (...args: unknown[]) => selectOutputDir(...args),
  toggleFullscreen: (...args: unknown[]) => toggleFullscreen(...args),
  setKioskLock: (...args: unknown[]) => setKioskLock(...args),
}));

const t = taskStrings("en");

beforeEach(() => {
  fetchHealth.mockRejectedValue(new Error("no sidecar in tests"));
  validateConfig.mockResolvedValue({ ok: true, errors: [] });
  preview.mockResolvedValue({ curves: {} });
  // Cancelled-dialog semantics: the flows run but change nothing.
  saveStudy.mockResolvedValue(null);
  loadStudy.mockResolvedValue(null);
  toggleFullscreen.mockResolvedValue(false);
  setKioskLock.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  delete (window.navigator as { platform?: string }).platform;
});

/** Pin the platform string the shortcut layer reads (jsdom leaves it blank). */
function stubPlatform(value: string) {
  Object.defineProperty(window.navigator, "platform", { value, configurable: true });
}

describe("Save/Load shortcuts (§2.7)", () => {
  it("⌘S fires the save flow in setup mode", async () => {
    stubPlatform("MacIntel");
    render(<App />);
    await screen.findByRole("button", { name: /save/i });

    fireEvent.keyDown(window, { key: "s", metaKey: true });

    await waitFor(() => expect(saveStudy).toHaveBeenCalled());
  });

  it("⌘O fires the load flow in setup mode", async () => {
    stubPlatform("MacIntel");
    render(<App />);
    await screen.findByRole("button", { name: /load/i });

    fireEvent.keyDown(window, { key: "o", metaKey: true });

    await waitFor(() => expect(loadStudy).toHaveBeenCalled());
  });

  it("stays inert during a run — the participant surface owns the keyboard", async () => {
    stubPlatform("MacIntel");
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: /start run/i }));
    await screen.findByText(t.consentTitle);

    fireEvent.keyDown(window, { key: "s", metaKey: true });
    fireEvent.keyDown(window, { key: "o", metaKey: true });

    // Nothing to await: give any stray handler a microtask to surface. The
    // dialog spies are the signal — validateConfig may legitimately fire from
    // setup mode's debounced live validation (§2.5) before the run started.
    await Promise.resolve();
    expect(saveStudy).not.toHaveBeenCalled();
    expect(loadStudy).not.toHaveBeenCalled();
  });
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
