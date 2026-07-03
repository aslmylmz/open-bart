import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
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

const t = taskStrings("en");

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
    // A one-balloon study with zero hazard, so the whole participant flow —
    // consent → ID + condition → task → submit — runs deterministically.
    const tinyStudy = {
      ...DEFAULT_STUDY,
      conditions: ["control", "experimental"],
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
    preview.mockResolvedValue({
      curves: { purple: { hazard: [0, 0, 0, 0, 0, 0, 0, 0], survival: [], ev: [], optimum: 1, optimal_ev: 0 } },
    });
    submitSession.mockResolvedValue({ session_id: "s-1" });
    persistSession.mockResolvedValue({});

    render(<RunFlow config={tinyStudy} onExit={() => {}} />);
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
    checkId.mockResolvedValue({ ok: true, sessions: 1, error: null });
    preview.mockResolvedValue({
      curves: { purple: { hazard: [0, 0, 0, 0, 0, 0, 0, 0], survival: [], ev: [], optimum: 1, optimal_ev: 0 } },
    });
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
