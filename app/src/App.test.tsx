import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
// which exist in jsdom. Every export App or its children touch must be here —
// including the Data Hub's folder pickers and drag-drop channel.
const saveStudy = vi.fn();
const loadStudy = vi.fn();
const selectOutputDir = vi.fn();
const selectFolder = vi.fn();
const onFolderDrop = vi.fn();
const toggleFullscreen = vi.fn();
const setKioskLock = vi.fn();
vi.mock("./lib/desktop", () => ({
  saveStudy: (...args: unknown[]) => saveStudy(...args),
  loadStudy: (...args: unknown[]) => loadStudy(...args),
  selectOutputDir: (...args: unknown[]) => selectOutputDir(...args),
  selectFolder: (...args: unknown[]) => selectFolder(...args),
  onFolderDrop: (...args: unknown[]) => onFolderDrop(...args),
  toggleFullscreen: (...args: unknown[]) => toggleFullscreen(...args),
  setKioskLock: (...args: unknown[]) => setKioskLock(...args),
}));

// The Data Hub tab drives the sidecar's /hub/* routes; stub the client so a
// mount never reaches the network.
const ingestSources = vi.fn();
const rebuildHub = vi.fn();
vi.mock("./lib/hub", () => ({
  ingestSources: (...args: unknown[]) => ingestSources(...args),
  rebuildHub: (...args: unknown[]) => rebuildHub(...args),
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
  onFolderDrop.mockResolvedValue(() => {});
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

describe("Mode switch choreography (issue 06, DESIGN-SPEC §3.1)", () => {
  // jsdom has no stylesheet, so the shell falls back to the spec's token
  // values — the advances below (200ms out, 250ms hold, 250ms in) pin those
  // §3.1 numbers deliberately, mirroring tokens.css.
  afterEach(() => {
    vi.useRealTimers();
    delete (window as { matchMedia?: unknown }).matchMedia;
  });

  /** jsdom has no matchMedia at all; give it one with a fixed verdict. */
  function stubReducedMotion(matches: boolean) {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: (media: string) => ({ matches, media }),
    });
  }

  async function advance(ms: number) {
    await act(async () => {
      vi.advanceTimersByTime(ms);
    });
  }

  it("stages the handoff: setup holds through the fade-out, then the participant surface", async () => {
    vi.useFakeTimers();
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /start run/i }));

    // Fade-out: the researcher surface is still the mounted one — the frame
    // is veiling it; the participant never glimpses a half-built consent.
    expect(screen.queryByText(t.consentTitle)).toBeNull();
    expect(screen.getByRole("button", { name: /start run/i })).toBeTruthy();

    // End of fade-out: surfaces swap under the opaque hold.
    await advance(200);
    expect(screen.getByText(t.consentTitle)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /start run/i })).toBeNull();

    // Hold, then fade-in, complete without incident. (Each stage arms its
    // timer from an effect, so the clock must advance stage by stage.)
    await advance(250);
    await advance(250);
    expect(screen.getByText(t.consentTitle)).toBeTruthy();
  });

  it("keeps the Test run banner up from the first lit frame", async () => {
    vi.useFakeTimers();
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /test run/i }));
    await advance(200);

    // The banner is mounted while the veil is still opaque — there is no
    // first frame without it.
    expect(screen.getByText(t.practiceBanner)).toBeTruthy();
  });

  it("brings the researcher home on a plain fade — swap at ~200ms, no hold", async () => {
    vi.useFakeTimers();
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /start run/i }));
    await advance(200); // out
    await advance(250); // hold
    await advance(250); // in — ceremony over, consent up

    fireEvent.click(screen.getByRole("button", { name: /back to setup/i }));

    // The run surface stays put while the fade runs…
    expect(screen.getByText(t.consentTitle)).toBeTruthy();

    // …and the swap lands after the plain ~200ms fade.
    await advance(200);
    expect(screen.getByRole("button", { name: /start run/i })).toBeTruthy();
    expect(screen.queryByText(t.consentTitle)).toBeNull();
    await advance(200); // fade-in home completes
  });

  it("cuts instantly both ways under prefers-reduced-motion", () => {
    stubReducedMotion(true);
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /start run/i }));
    expect(screen.getByText(t.consentTitle)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /back to setup/i }));
    expect(screen.getByRole("button", { name: /start run/i })).toBeTruthy();
    expect(screen.queryByText(t.consentTitle)).toBeNull();
  });
});

describe("Researcher workspace tabs (DATA-SPEC §7.1)", () => {
  it("switches between Study Setup and the Data Hub as peer tabs", async () => {
    render(<App />);
    // Study Setup is the default workspace.
    expect(await screen.findByRole("button", { name: /save/i })).toBeTruthy();

    await userEvent.click(screen.getByRole("tab", { name: /data hub/i }));

    // The Data Hub takes over the researcher shell (its Sources prompt shows);
    // Study Setup's Save action is gone.
    expect(await screen.findByText(/add source folders/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /save/i })).toBeNull();

    await userEvent.click(screen.getByRole("tab", { name: /study setup/i }));
    expect(await screen.findByRole("button", { name: /save/i })).toBeTruthy();
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
