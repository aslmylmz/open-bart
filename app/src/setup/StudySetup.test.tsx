import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { DEFAULT_STUDY, type TaskConfig } from "../lib/config";
import { StudySetup } from "./StudySetup";
import type { StudySnapshot } from "./studyForm";

// The form validates through the sidecar, the embedded EV preview fetches
// /preview, and the Standalone badge reads the per-machine station setting;
// stub the api module so nothing touches the network.
const validateConfig = vi.fn();
const preview = vi.fn();
const fetchStation = vi.fn();
const setStationId = vi.fn();
vi.mock("../lib/api", () => ({
  validateConfig: (...args: unknown[]) => validateConfig(...args),
  preview: (...args: unknown[]) => preview(...args),
  fetchStation: (...args: unknown[]) => fetchStation(...args),
  setStationId: (...args: unknown[]) => setStationId(...args),
}));

// Save/load/folder-picking go through native Tauri dialogs — none exist in jsdom.
const saveStudy = vi.fn();
const loadStudy = vi.fn();
const selectOutputDir = vi.fn();
vi.mock("../lib/desktop", () => ({
  saveStudy: (...args: unknown[]) => saveStudy(...args),
  loadStudy: (...args: unknown[]) => loadStudy(...args),
  selectOutputDir: (...args: unknown[]) => selectOutputDir(...args),
}));

// StudySetup is controlled; a stateful harness lets removals actually re-render.
// It mirrors the App shell: config and the saved-file snapshot live here and
// survive `mounted={false}` (a run trip unmounts StudySetup — §2.1's "last
// saved/loaded" must not reset with it).
function Harness({ initial, mounted = true }: { initial: TaskConfig; mounted?: boolean }) {
  const [config, setConfig] = useState(initial);
  const [snapshot, setSnapshot] = useState<StudySnapshot>({ path: null, config: initial });
  if (!mounted) return null;
  return (
    <StudySetup
      config={config}
      onChange={setConfig}
      snapshot={snapshot}
      onSnapshotChange={setSnapshot}
      onTestRun={() => {}}
      onStartRun={() => {}}
    />
  );
}

/** Pin what jsdom leaves blank: the platform string the chips and shortcut
 * matching read. Shadowing the prototype getter with an own property keeps the
 * stub local to one test; afterEach deletes it. */
function stubPlatform(value: string) {
  Object.defineProperty(window.navigator, "platform", { value, configurable: true });
}

beforeEach(() => {
  validateConfig.mockResolvedValue({ ok: true, errors: [] });
  preview.mockResolvedValue({ curves: {} });
  fetchStation.mockResolvedValue({ ok: true, station_id: "S1", machine_uuid: "uuid-a" });
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.resetAllMocks();
  delete (window.navigator as { platform?: string }).platform;
});

function removeButtons() {
  return screen.getAllByRole("button", { name: /^remove$/i });
}

describe("Identity bar (§2.1)", () => {
  it("shows the breadcrumb with the study title and the file identity line", () => {
    stubPlatform("MacIntel");
    render(<Harness initial={DEFAULT_STUDY} />);

    expect(screen.getByText("Study Setup")).toBeTruthy();
    expect(screen.getByText(DEFAULT_STUDY.title)).toBeTruthy();
    expect(screen.getByText("default study — not saved to file yet")).toBeTruthy();
  });

  it("owns Save and Load — the old save/load band is gone", () => {
    stubPlatform("MacIntel");
    render(<Harness initial={DEFAULT_STUDY} />);

    expect(screen.getByRole("button", { name: /save/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /load/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /save study/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /load study/i })).toBeNull();
  });

  it("renders ⌘ chips on macOS", () => {
    stubPlatform("MacIntel");
    render(<Harness initial={DEFAULT_STUDY} />);

    expect(screen.getByText("⌘S")).toBeTruthy();
    expect(screen.getByText("⌘O")).toBeTruthy();
  });

  it("renders Ctrl chips off macOS", () => {
    stubPlatform("Win32");
    render(<Harness initial={DEFAULT_STUDY} />);

    expect(screen.getByText("Ctrl+S")).toBeTruthy();
    expect(screen.getByText("Ctrl+O")).toBeTruthy();
  });
});

describe("Unsaved dot (§2.1)", () => {
  it("is absent at rest and appears once the study is edited", async () => {
    stubPlatform("MacIntel");
    render(<Harness initial={DEFAULT_STUDY} />);

    expect(screen.queryByRole("img", { name: /unsaved changes/i })).toBeNull();

    await userEvent.type(screen.getByDisplayValue(DEFAULT_STUDY.title), "!");

    expect(screen.getByRole("img", { name: /unsaved changes/i })).toBeTruthy();
  });

  it("clears after a successful save", async () => {
    stubPlatform("MacIntel");
    saveStudy.mockResolvedValue("/tmp/studies/study.json");
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.type(screen.getByDisplayValue(DEFAULT_STUDY.title), "!");
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(await screen.findByText("Saved to /tmp/studies/study.json")).toBeTruthy();
    expect(screen.queryByRole("img", { name: /unsaved changes/i })).toBeNull();
  });
});

describe("Save/load feedback — line 2's transient slot (§2.1)", () => {
  it("shows 'Saved to <path>' for ~4s, then reverts to the file identity", async () => {
    stubPlatform("MacIntel");
    vi.useFakeTimers();
    saveStudy.mockResolvedValue("/tmp/studies/study.json");
    render(<Harness initial={DEFAULT_STUDY} />);

    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    // Flush the validate + save promises (microtasks are unaffected by fake timers).
    await act(async () => {});

    expect(screen.getByText("Saved to /tmp/studies/study.json")).toBeTruthy();

    act(() => {
      vi.advanceTimersByTime(4100);
    });

    expect(screen.queryByText("Saved to /tmp/studies/study.json")).toBeNull();
    expect(screen.getByText("study.json — /tmp/studies")).toBeTruthy();
  });

  it("reports a cancelled save dialog", async () => {
    stubPlatform("MacIntel");
    saveStudy.mockResolvedValue(null);
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(await screen.findByText("Save cancelled.")).toBeTruthy();
  });

  it("reports a cancelled load dialog", async () => {
    stubPlatform("MacIntel");
    loadStudy.mockResolvedValue(null);
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    expect(await screen.findByText("Load cancelled.")).toBeTruthy();
  });

  it("reports a save that fails validation transport — the sidecar rejected, not the config", async () => {
    stubPlatform("MacIntel");
    validateConfig.mockRejectedValueOnce(new Error("sidecar offline"));
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(await screen.findByText("Save failed: sidecar offline")).toBeTruthy();
    expect(saveStudy).not.toHaveBeenCalled();
  });

  it("reports a failed write", async () => {
    stubPlatform("MacIntel");
    saveStudy.mockRejectedValueOnce(new Error("disk full"));
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(await screen.findByText("Save failed: disk full")).toBeTruthy();
  });

  it("keeps the current study when validation transport fails during a load", async () => {
    stubPlatform("MacIntel");
    loadStudy.mockResolvedValue({
      path: "/data/pilot.json",
      text: JSON.stringify({ ...DEFAULT_STUDY, title: "Loaded pilot" }),
    });
    validateConfig.mockRejectedValueOnce(new Error("sidecar offline"));
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    expect(await screen.findByText("Could not load: sidecar offline")).toBeTruthy();
    expect(screen.getByDisplayValue(DEFAULT_STUDY.title)).toBeTruthy();
    expect(screen.queryByDisplayValue("Loaded pilot")).toBeNull();
  });

  it("clears stale transient feedback when a load succeeds", async () => {
    stubPlatform("MacIntel");
    loadStudy.mockResolvedValueOnce(null).mockResolvedValueOnce({
      path: "/data/pilot.json",
      text: JSON.stringify({ ...DEFAULT_STUDY, title: "Loaded pilot" }),
    });
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /load/i }));
    await screen.findByText("Load cancelled.");

    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    // The new file identity shows immediately — no leftover cancellation
    // message holds the slot for the rest of its ~4s.
    expect(await screen.findByText("pilot.json — /data")).toBeTruthy();
    expect(screen.queryByText("Load cancelled.")).toBeNull();
  });

  it("replaces the study and the file identity on a valid load", async () => {
    stubPlatform("MacIntel");
    const loaded = { ...DEFAULT_STUDY, title: "Loaded pilot" };
    loadStudy.mockResolvedValue({ path: "/data/pilot.json", text: JSON.stringify(loaded) });
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    expect(await screen.findByText("pilot.json — /data")).toBeTruthy();
    expect(screen.getByDisplayValue("Loaded pilot")).toBeTruthy();
    // The freshly loaded study is the new snapshot — no unsaved dot.
    expect(screen.queryByRole("img", { name: /unsaved changes/i })).toBeNull();
  });
});

describe("Snapshot survives a run trip (§2.1 'last saved/loaded')", () => {
  it("keeps the unsaved dot and file identity across an unmount/remount", async () => {
    stubPlatform("MacIntel");
    saveStudy.mockResolvedValue("/tmp/studies/study.json");
    const { rerender } = render(<Harness initial={DEFAULT_STUDY} />);

    // Save, then edit: the study is now dirty against its file.
    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await screen.findByText("Saved to /tmp/studies/study.json");
    await userEvent.type(screen.getByDisplayValue(DEFAULT_STUDY.title), "!");
    expect(screen.getByRole("img", { name: /unsaved changes/i })).toBeTruthy();

    // A run trip unmounts StudySetup while the shell keeps config + snapshot.
    rerender(<Harness initial={DEFAULT_STUDY} mounted={false} />);
    rerender(<Harness initial={DEFAULT_STUDY} />);

    expect(screen.getByRole("img", { name: /unsaved changes/i })).toBeTruthy();
    expect(screen.getByText("study.json — /tmp/studies")).toBeTruthy();
  });
});

describe("Error strip (§2.2)", () => {
  it("keeps the current study and lists the reasons when a loaded file fails validation", async () => {
    stubPlatform("MacIntel");
    loadStudy.mockResolvedValue({
      path: "/data/bad.json",
      text: JSON.stringify({ ...DEFAULT_STUDY, title: "" }),
    });
    validateConfig.mockResolvedValueOnce({ ok: false, errors: ["title must not be empty"] });
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    expect(await screen.findByText("Loaded file is invalid — keeping the current study.")).toBeTruthy();
    expect(screen.getByText("title must not be empty")).toBeTruthy();
    // The active study and its file identity are untouched.
    expect(screen.getByDisplayValue(DEFAULT_STUDY.title)).toBeTruthy();
    expect(screen.getByText("default study — not saved to file yet")).toBeTruthy();
  });

  it("rejects a file that is not valid JSON the same way", async () => {
    stubPlatform("MacIntel");
    loadStudy.mockResolvedValue({ path: "/data/broken.json", text: "{not json" });
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /load/i }));

    expect(await screen.findByText(/loaded file is invalid/i)).toBeTruthy();
    expect(screen.getByDisplayValue(DEFAULT_STUDY.title)).toBeTruthy();
  });

  it("summons the save-blocked strip with the full-pass summary and saves nothing", async () => {
    stubPlatform("MacIntel");
    validateConfig.mockResolvedValueOnce({
      ok: false,
      errors: ["reward_per_pump must be positive", "colors must not be empty"],
    });
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(await screen.findByText("Not saved — 2 errors.")).toBeTruthy();
    expect(screen.getByText("reward_per_pump must be positive")).toBeTruthy();
    expect(screen.getByText("colors must not be empty")).toBeTruthy();
    expect(saveStudy).not.toHaveBeenCalled();
  });

  it("dismisses on demand", async () => {
    stubPlatform("MacIntel");
    validateConfig.mockResolvedValueOnce({ ok: false, errors: ["some error"] });
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await screen.findByText("Not saved — 1 error.");

    await userEvent.click(screen.getByRole("button", { name: /dismiss errors/i }));

    expect(screen.queryByText("Not saved — 1 error.")).toBeNull();
    expect(screen.queryByText("some error")).toBeNull();
  });

  it("auto-clears on the next successful save", async () => {
    stubPlatform("MacIntel");
    validateConfig.mockResolvedValueOnce({ ok: false, errors: ["some error"] });
    saveStudy.mockResolvedValue("/tmp/s.json");
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await screen.findByText("Not saved — 1 error.");

    // The blocking error is fixed (the default verdict is ok again); saving
    // succeeds and takes the strip with it.
    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(await screen.findByText("Saved to /tmp/s.json")).toBeTruthy();
    expect(screen.queryByText("Not saved — 1 error.")).toBeNull();
    expect(screen.queryByText("some error")).toBeNull();
  });
});

describe("Live validation — touched-then-live (§2.5)", () => {
  const REWARD_ERROR = {
    ok: false,
    errors: ["reward_per_pump: Input should be greater than 0"],
  };
  const REWARD_MESSAGE = "Input should be greater than 0";

  function breakReward() {
    fireEvent.change(screen.getByLabelText(/reward per pump/i), { target: { value: "0" } });
  }

  it("never renders an error at a field that was not blurred", async () => {
    stubPlatform("MacIntel");
    vi.useFakeTimers();
    validateConfig.mockResolvedValue(REWARD_ERROR);
    render(<Harness initial={DEFAULT_STUDY} />);

    breakReward();
    await act(async () => {
      vi.advanceTimersByTime(450);
    });

    // The sidecar has flagged the field, but first typing is never nagged.
    expect(screen.queryByText(REWARD_MESSAGE)).toBeNull();
  });

  it("renders the error under the control after blur + debounce", async () => {
    stubPlatform("MacIntel");
    vi.useFakeTimers();
    validateConfig.mockResolvedValue(REWARD_ERROR);
    render(<Harness initial={DEFAULT_STUDY} />);

    breakReward();
    fireEvent.blur(screen.getByLabelText(/reward per pump/i));
    await act(async () => {
      vi.advanceTimersByTime(450);
    });

    expect(screen.getByText(REWARD_MESSAGE)).toBeTruthy();
  });

  it("reveals an already-known error the moment its field is first blurred", async () => {
    stubPlatform("MacIntel");
    vi.useFakeTimers();
    validateConfig.mockResolvedValue(REWARD_ERROR);
    render(<Harness initial={DEFAULT_STUDY} />);

    breakReward();
    await act(async () => {
      vi.advanceTimersByTime(450);
    });
    expect(screen.queryByText(REWARD_MESSAGE)).toBeNull();

    fireEvent.blur(screen.getByLabelText(/reward per pump/i));

    expect(screen.getByText(REWARD_MESSAGE)).toBeTruthy();
  });

  it("clears the error at debounce cadence once the value is fixed", async () => {
    stubPlatform("MacIntel");
    vi.useFakeTimers();
    validateConfig.mockResolvedValue(REWARD_ERROR);
    render(<Harness initial={DEFAULT_STUDY} />);

    breakReward();
    fireEvent.blur(screen.getByLabelText(/reward per pump/i));
    await act(async () => {
      vi.advanceTimersByTime(450);
    });
    expect(screen.getByText(REWARD_MESSAGE)).toBeTruthy();

    validateConfig.mockResolvedValue({ ok: true, errors: [] });
    fireEvent.change(screen.getByLabelText(/reward per pump/i), { target: { value: "0.25" } });
    await act(async () => {
      vi.advanceTimersByTime(450);
    });

    expect(screen.queryByText(REWARD_MESSAGE)).toBeNull();
  });

  it("keeps an unmappable error off the form until a save attempt summons the strip", async () => {
    stubPlatform("MacIntel");
    vi.useFakeTimers();
    // Top-level `currency` has no Study-Setup control — unmappable by design.
    validateConfig.mockResolvedValue({
      ok: false,
      errors: ["currency: String should have at least 1 character"],
    });
    render(<Harness initial={DEFAULT_STUDY} />);

    fireEvent.blur(screen.getByLabelText(/title/i));
    await act(async () => {
      vi.advanceTimersByTime(450);
    });
    expect(screen.queryByText(/at least 1 character/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await act(async () => {});

    expect(screen.getByText("Not saved — 1 error.")).toBeTruthy();
    expect(screen.getByText("currency: String should have at least 1 character")).toBeTruthy();
  });

  it("reveals mapped errors at their fields after a save attempt and still blocks the save", async () => {
    stubPlatform("MacIntel");
    validateConfig.mockResolvedValue(REWARD_ERROR);
    render(<Harness initial={DEFAULT_STUDY} />);

    await userEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(await screen.findByText("Not saved — 1 error.")).toBeTruthy();
    // The field itself was never blurred — the save attempt reveals it.
    expect(screen.getByText(REWARD_MESSAGE)).toBeTruthy();
    expect(saveStudy).not.toHaveBeenCalled();
  });

  it("commits a blur-committed input's value on the same blur that marks it touched", () => {
    stubPlatform("MacIntel");
    render(<Harness initial={DEFAULT_STUDY} />);

    const conditions = screen.getByLabelText(/conditions/i);
    fireEvent.change(conditions, { target: { value: "control, treatment," } });
    fireEvent.blur(conditions);

    // The parsed list landed in the config (trailing comma dropped)…
    expect(screen.getByDisplayValue("control, treatment")).toBeTruthy();
    // …so the study is dirty: the commit was not swallowed by the touch wiring.
    expect(screen.getByRole("img", { name: /unsaved changes/i })).toBeTruthy();
  });

  it("stops nagging never-blurred fields once a save succeeds", async () => {
    stubPlatform("MacIntel");
    vi.useFakeTimers();
    saveStudy.mockResolvedValue("/tmp/s.json");
    render(<Harness initial={DEFAULT_STUDY} />);

    // A save attempt reveals everything…
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await act(async () => {});
    expect(screen.getByText("Saved to /tmp/s.json")).toBeTruthy();

    // …but after it succeeds, a fresh edit at an untouched field is not
    // nagged mid-typing again (§2.5 "first typing is never nagged").
    validateConfig.mockResolvedValue(REWARD_ERROR);
    breakReward();
    await act(async () => {
      vi.advanceTimersByTime(450);
    });

    expect(screen.queryByText(REWARD_MESSAGE)).toBeNull();
  });

  it("renders a cross-field error at all involved fields", async () => {
    stubPlatform("MacIntel");
    const stepStudy = {
      ...DEFAULT_STUDY,
      colors: [
        {
          ...DEFAULT_STUDY.colors[0],
          hazard: { family: "step" as const, breakpoints: [4], levels: [0.05, 0.5, 0.9] },
        },
      ],
    };
    const message = "step hazard needs len(levels) == len(breakpoints) + 1";
    validateConfig.mockResolvedValue({
      ok: false,
      errors: [`colors.0.hazard.step: Value error, ${message}`],
    });
    render(<Harness initial={stepStudy} />);

    await userEvent.click(screen.getByRole("button", { name: /save/i }));
    await screen.findByText("Not saved — 1 error.");

    // Both array params carry the shared shape error (§2.5 cross-field rule).
    expect(screen.getAllByText(message).length).toBeGreaterThanOrEqual(2);
  });
});

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

describe("Standalone Mode surfaces (DATA-SPEC §2.4/§2.5)", () => {
  const standaloneStudy: TaskConfig = { ...DEFAULT_STUDY, standalone: true };

  it("shows the persistent mode badge with this machine's station", async () => {
    render(<Harness initial={standaloneStudy} />);

    expect(screen.getByText("Standalone Mode")).toBeTruthy();
    expect(await screen.findByText("Station: S1")).toBeTruthy();
  });

  it("shows no badge for a single-station study", () => {
    render(<Harness initial={DEFAULT_STUDY} />);

    expect(screen.queryByText("Standalone Mode")).toBeNull();
    expect(fetchStation).not.toHaveBeenCalled();
  });

  it("warns inline on the seed field under standalone + a fixed seed — a note, not an error", async () => {
    render(<Harness initial={{ ...standaloneStudy, seed: 42 }} />);
    await screen.findByText("Station: S1");

    const note = screen.getByRole("note");
    expect(note.textContent).toContain("identical sequences");
    expect(note.textContent).toContain("globally unique");
    // Non-blocking: the warning is not a validation error on the field.
    expect(screen.getByPlaceholderText("Fresh randomness each run").getAttribute("aria-invalid")).toBeNull();
  });

  it("downgrades that warning to an informational note under auto-generated IDs (DATA-SPEC §3.2)", async () => {
    // The poka-yoke has addressed the hazard the warning flags: globally
    // unique IDs mean two stations can no longer replay the same sequence.
    render(
      <Harness initial={{ ...standaloneStudy, seed: 42, auto_participant_id: true }} />,
    );
    await screen.findByText("Station: S1");

    const note = screen.getByRole("note");
    expect(note.textContent).toContain("independent across stations");
    expect(note.className).toContain("is-info");
  });

  it("keeps the seed field quiet with fresh randomness or outside Standalone Mode", async () => {
    render(<Harness initial={standaloneStudy} />);
    await screen.findByText("Station: S1");
    expect(screen.queryByRole("note")).toBeNull();
    cleanup();

    render(<Harness initial={{ ...DEFAULT_STUDY, seed: 42 }} />);
    expect(screen.queryByRole("note")).toBeNull();
  });
});
