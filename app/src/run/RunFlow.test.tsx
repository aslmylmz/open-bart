import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DEFAULT_STUDY } from "../lib/config";
import { taskStrings } from "../lib/i18n";
import { RunFlow } from "./RunFlow";

// The run flow talks to the sidecar at three points: /check-id when the ID is
// submitted, /preview before the task, and /score + /write-output on submit
// (via BartGame). Stub the whole api module so tests never touch the network;
// individual tests override values as needed.
const preview = vi.fn();
const checkId = vi.fn();
const submitSession = vi.fn();
const persistSession = vi.fn();
vi.mock("../lib/api", () => ({
  preview: (...args: unknown[]) => preview(...args),
  checkId: (...args: unknown[]) => checkId(...args),
  submitSession: (...args: unknown[]) => submitSession(...args),
  persistSession: (...args: unknown[]) => persistSession(...args),
}));

// The kiosk lock drives the native window (fullscreen + always-on-top) via
// lib/desktop; stub it — there is no Tauri window under jsdom.
const setKioskLock = vi.fn().mockResolvedValue(undefined);
vi.mock("../lib/desktop", () => ({
  setKioskLock: (...args: unknown[]) => setKioskLock(...args),
}));

const t = taskStrings("en");

// A one-balloon, zero-hazard study so a whole participant flow — consent →
// ID → task → submit — runs deterministically in a test.
const tinyStudy = {
  ...DEFAULT_STUDY,
  colors: [
    {
      name: "purple",
      label: "Purple",
      display_hex: "#7c3aed",
      max_pumps: 8,
      trials: 1,
      hazard: { family: "dynamic" as const },
    },
  ],
};
const tinyPreview = {
  curves: { purple: { hazard: [0, 0, 0, 0, 0, 0, 0, 0], survival: [], ev: [], optimum: 1, optimal_ev: 0 } },
};

beforeEach(() => {
  // Default: a fresh, valid ID — tests for duplicates/invalid IDs override.
  checkId.mockResolvedValue({ ok: true, sessions: 0, error: null });
});

afterEach(() => {
  cleanup();
  preview.mockReset();
  checkId.mockReset();
  submitSession.mockReset();
  persistSession.mockReset();
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

describe("condition assignment on the ID screen (issue 37)", () => {
  const conditionedStudy = { ...DEFAULT_STUDY, conditions: ["control", "experimental"] };

  it("requires a condition choice before the task can start", async () => {
    render(<RunFlow config={conditionedStudy} onExit={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));

    const dropdown = screen.getByLabelText<HTMLSelectElement>(t.conditionLabel);
    const cont = screen.getByRole<HTMLButtonElement>("button", { name: t.idContinue });

    // An ID alone is not enough: the assignment is part of starting a session.
    await userEvent.type(screen.getByPlaceholderText(t.idPlaceholder), "P001");
    expect(cont.disabled).toBe(true);

    await userEvent.selectOptions(dropdown, "experimental");
    expect(cont.disabled).toBe(false);
  });

  it("offers exactly the preset's declared condition names — no typing, no typos", async () => {
    render(<RunFlow config={conditionedStudy} onExit={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));

    const options = screen
      .getAllByRole<HTMLOptionElement>("option")
      .map((o) => o.value)
      .filter((v) => v !== "");
    expect(options).toEqual(["control", "experimental"]);
  });

  it("shows no condition UI for a study without conditions", async () => {
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));

    expect(screen.queryByLabelText(t.conditionLabel)).toBeNull();
  });

  it("carries the dropdown choice through the task into the submitted session", async () => {
    const conditionedTinyStudy = { ...tinyStudy, conditions: ["control", "experimental"] };
    preview.mockResolvedValue(tinyPreview);
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockResolvedValue({});

    render(<RunFlow config={conditionedTinyStudy} onExit={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));
    await userEvent.type(screen.getByPlaceholderText(t.idPlaceholder), "P001");
    await userEvent.selectOptions(screen.getByLabelText(t.conditionLabel), "control");
    await userEvent.click(screen.getByRole("button", { name: t.idContinue }));

    await userEvent.click(await screen.findByRole("button", { name: t.startButton }));
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));

    await waitFor(() => expect(submitSession).toHaveBeenCalledTimes(1));
    const [payload] = submitSession.mock.calls[0] as [{ condition: string | null; candidate_id: string }];
    expect(payload.condition).toBe("control");
    expect(payload.candidate_id).toBe("P001");
  });
});

describe("Test Run / practice mode (issue 43)", () => {
  it("banners the practice session from the first screen and skips the ID guardrails", async () => {
    preview.mockReturnValue(new Promise(() => {})); // hold in loading
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} practice />);

    // The banner is up before anything else happens — consent screen included.
    expect(screen.getByText(t.practiceBanner)).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));

    // The ID is auto-filled with the test marker; the banner stays.
    const input = screen.getByPlaceholderText<HTMLInputElement>(t.idPlaceholder);
    expect(input.value).toBe("TEST");
    expect(screen.getByText(t.practiceBanner)).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: t.idContinue }));

    // Straight to loading: practice is exempt from the mandatory-ID /
    // duplicate-ID guardrails (issue 38) — /check-id is never consulted.
    expect(await screen.findByRole("status")).toBeTruthy();
    expect(checkId).not.toHaveBeenCalled();
    expect(screen.getByText(t.practiceBanner)).toBeTruthy();
  });

  it("keeps the banner up through gameplay and debrief and stamps the session", async () => {
    preview.mockResolvedValue(tinyPreview);
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockResolvedValue({});

    render(<RunFlow config={tinyStudy} onExit={() => {}} practice />);
    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));
    await userEvent.click(screen.getByRole("button", { name: t.idContinue }));

    // Gameplay: the banner never leaves.
    await userEvent.click(await screen.findByRole("button", { name: t.startButton }));
    expect(screen.getByText(t.practiceBanner)).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));

    // The session is stamped: no path from the Test Run control to an
    // unstamped session.
    await waitFor(() => expect(submitSession).toHaveBeenCalledTimes(1));
    const [payload] = submitSession.mock.calls[0] as [
      { practice: boolean; candidate_id: string },
    ];
    expect(payload.practice).toBe(true);
    expect(payload.candidate_id).toBe("TEST");
    await waitFor(() => expect(persistSession).toHaveBeenCalledTimes(1));
    const [persisted] = persistSession.mock.calls[0] as [{ practice: boolean }];
    expect(persisted.practice).toBe(true);

    // Debrief: still bannered.
    expect(screen.getByText(t.practiceBanner)).toBeTruthy();
  });

  it("shows no banner and keeps the ID empty in an official run", async () => {
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} />);

    expect(screen.queryByText(t.practiceBanner)).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));

    expect(screen.queryByText(t.practiceBanner)).toBeNull();
    const input = screen.getByPlaceholderText<HTMLInputElement>(t.idPlaceholder);
    expect(input.value).toBe("");
  });
});

describe("kiosk in-app lock (issue 44)", () => {
  const lockedStudy = { ...DEFAULT_STUDY, exit_passcode: "1234" };

  it("gates the back button behind a passcode prompt instead of exiting", async () => {
    const onExit = vi.fn();
    render(<RunFlow config={lockedStudy} onExit={onExit} />);

    await userEvent.click(screen.getByRole("button", { name: /back to setup/i }));

    expect(onExit).not.toHaveBeenCalled();
    expect(screen.getByText(t.lockTitle)).toBeTruthy();
  });

  it("keeps a wrong entry in-session and lets a correct entry exit", async () => {
    const onExit = vi.fn();
    render(<RunFlow config={lockedStudy} onExit={onExit} />);
    await userEvent.click(screen.getByRole("button", { name: /back to setup/i }));

    // Wrong passcode: readable error, still in the session, entry cleared.
    await userEvent.type(screen.getByPlaceholderText(t.lockPlaceholder), "9999");
    await userEvent.click(screen.getByRole("button", { name: t.lockConfirm }));
    expect(onExit).not.toHaveBeenCalled();
    expect((await screen.findByRole("alert")).textContent).toBe(t.lockWrong);
    expect(screen.getByPlaceholderText<HTMLInputElement>(t.lockPlaceholder).value).toBe("");

    // Correct passcode: the researcher leaves.
    await userEvent.type(screen.getByPlaceholderText(t.lockPlaceholder), "1234");
    await userEvent.click(screen.getByRole("button", { name: t.lockConfirm }));
    expect(onExit).toHaveBeenCalledTimes(1);
  });

  it("returns to the session unharmed on cancel", async () => {
    const onExit = vi.fn();
    render(<RunFlow config={lockedStudy} onExit={onExit} />);
    await userEvent.click(screen.getByRole("button", { name: /back to setup/i }));

    await userEvent.click(screen.getByRole("button", { name: t.lockCancel }));

    expect(onExit).not.toHaveBeenCalled();
    expect(screen.queryByText(t.lockTitle)).toBeNull();
    // Still on the consent screen where the exit was attempted.
    expect(screen.getByText(t.consentTitle)).toBeTruthy();
  });

  it("swallows Escape and F11 into the passcode prompt while locked", async () => {
    const onExit = vi.fn();
    render(<RunFlow config={lockedStudy} onExit={onExit} />);

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByText(t.lockTitle)).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: t.lockCancel }));
    expect(screen.queryByText(t.lockTitle)).toBeNull();

    fireEvent.keyDown(window, { key: "F11" });
    expect(screen.getByText(t.lockTitle)).toBeTruthy();
    expect(onExit).not.toHaveBeenCalled();
  });

  it("does not intercept keys when the study has no passcode", () => {
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} />);

    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.keyDown(window, { key: "F11" });

    expect(screen.queryByText(t.lockTitle)).toBeNull();
  });

  it("holds the window fullscreen and always-on-top only while locked", () => {
    render(<RunFlow config={lockedStudy} onExit={() => {}} />);
    expect(setKioskLock).toHaveBeenCalledWith(true);

    cleanup(); // leaving the flow releases the window
    expect(setKioskLock).toHaveBeenLastCalledWith(false);

    setKioskLock.mockClear();
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} />);
    expect(setKioskLock).not.toHaveBeenCalled();
  });

  it("disengages at debrief: completion never asks for the passcode", async () => {
    const onExit = vi.fn();
    const lockedTinyStudy = { ...tinyStudy, exit_passcode: "1234" };
    preview.mockResolvedValue(tinyPreview);
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockResolvedValue({});

    render(<RunFlow config={lockedTinyStudy} onExit={onExit} />);
    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));
    await userEvent.type(screen.getByPlaceholderText(t.idPlaceholder), "P001");
    await userEvent.click(screen.getByRole("button", { name: t.idContinue }));
    await userEvent.click(await screen.findByRole("button", { name: t.startButton }));
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));
    await screen.findByText(t.thankYouTitle);

    // Researcher hand-back: the window lock is released at debrief…
    expect(setKioskLock).toHaveBeenLastCalledWith(false);

    // …and leaving needs no passcode.
    await userEvent.click(screen.getByRole("button", { name: /back to setup/i }));
    expect(screen.queryByText(t.lockTitle)).toBeNull();
    expect(onExit).toHaveBeenCalledTimes(1);
  });
});

describe("mandatory ID + duplicate warn-confirm (issue 38)", () => {
  async function submitId(id = "P001") {
    await userEvent.click(screen.getByRole("button", { name: t.consentAgree }));
    await userEvent.type(screen.getByPlaceholderText(t.idPlaceholder), id);
    await userEvent.click(screen.getByRole("button", { name: t.idContinue }));
  }

  it("starts a fresh ID with no friction — no dialog on the way to the task", async () => {
    preview.mockReturnValue(new Promise(() => {})); // hold in loading
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} />);

    await submitId();

    expect(await screen.findByRole("status")).toBeTruthy(); // loading spinner
    expect(checkId).toHaveBeenCalledWith("P001", DEFAULT_STUDY);
    expect(screen.queryByText(t.duplicateTitle)).toBeNull();
  });

  it("warns when the ID already has sessions and cancel returns to the ID screen", async () => {
    checkId.mockResolvedValue({ ok: true, sessions: 2, error: null });
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} />);

    await submitId();

    // The warning names the ID and its session count; nothing has started yet.
    expect(await screen.findByText(t.duplicateTitle)).toBeTruthy();
    expect(screen.getByText(/P001/).textContent).toContain("2");
    expect(preview).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: t.duplicateCancel }));

    // Back on the ID screen, free to correct the ID.
    expect(screen.getByPlaceholderText(t.idPlaceholder)).toBeTruthy();
    expect(screen.queryByText(t.duplicateTitle)).toBeNull();
  });

  it("stamps the acknowledgment into the session when the RA continues anyway", async () => {
    checkId.mockResolvedValue({ ok: true, sessions: 1, error: null });
    preview.mockResolvedValue(tinyPreview);
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockResolvedValue({});

    render(<RunFlow config={tinyStudy} onExit={() => {}} />);
    await submitId();
    await userEvent.click(await screen.findByRole("button", { name: t.duplicateContinue }));

    await userEvent.click(await screen.findByRole("button", { name: t.startButton }));
    await userEvent.click(screen.getByRole("button", { name: t.pumpButton }));
    await userEvent.click(screen.getByRole("button", { name: t.collectButton }));
    await screen.findByText(t.finishedTitle, undefined, { timeout: 3000 });
    await userEvent.click(screen.getByRole("button", { name: t.seeResults }));

    await waitFor(() => expect(submitSession).toHaveBeenCalledTimes(1));
    const [payload] = submitSession.mock.calls[0] as [
      { candidate_id: string; duplicate_acknowledged: boolean },
    ];
    expect(payload.duplicate_acknowledged).toBe(true);
    expect(payload.candidate_id).toBe("P001");
  });

  it("shows a readable localized message for an ID the sidecar rejects", async () => {
    checkId.mockResolvedValue({ ok: false, sessions: 0, error: "unusable in file names" });
    render(<RunFlow config={DEFAULT_STUDY} onExit={() => {}} />);

    await submitId("004/E");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe(t.idInvalid);
    // Still on the ID screen; no dialog, no task start.
    expect(screen.getByPlaceholderText(t.idPlaceholder)).toBeTruthy();
    expect(preview).not.toHaveBeenCalled();
  });
});
