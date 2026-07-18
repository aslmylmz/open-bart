import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DataHub } from "./DataHub";
import type { HubView } from "../lib/hub";

// The tab drives the sidecar's /hub/* routes and the native folder pickers;
// stub both modules so nothing touches the network or Tauri.
const ingestSources = vi.fn();
const rebuildHub = vi.fn();
vi.mock("../lib/hub", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/hub")>()),
  ingestSources: (...args: unknown[]) => ingestSources(...args),
  rebuildHub: (...args: unknown[]) => rebuildHub(...args),
}));

const selectFolder = vi.fn();
const onFolderDrop = vi.fn();
vi.mock("../lib/desktop", () => ({
  selectFolder: (...args: unknown[]) => selectFolder(...args),
  onFolderDrop: (...args: unknown[]) => onFolderDrop(...args),
}));

/** A clean, ready-to-rebuild view — the common fixture; override per test. */
function cleanView(over: Partial<HubView> = {}): HubView {
  return {
    ok: true,
    error: null,
    title: "Stress 2003",
    slug: "stress2003",
    sources: [{ folder: "/data/s1", stations: 1, sessions: 3 }],
    configured_mode: "advanced",
    mode: "advanced",
    mode_source: "configured",
    will_rebuild: 3,
    held: 0,
    attention: 0,
    partitions: 1,
    findings: [
      { code: "clean_ingest", group: "info", message: "3 sessions ingested cleanly", loud: false, sessions: 3 },
    ],
    files: [
      { path: "stress2003_provenance.json", reconstructed: true },
      { path: "stress2003_results.csv", reconstructed: false },
      { path: "stress2003_trials.csv", reconstructed: false },
      { path: "stress2003_data_dictionary.md", reconstructed: false },
      { path: "stress2003_ingestion_report.md", reconstructed: false },
    ],
    ...over,
  };
}

beforeEach(() => {
  onFolderDrop.mockResolvedValue(() => {});
  ingestSources.mockResolvedValue(cleanView());
  rebuildHub.mockResolvedValue({
    ok: true,
    status: "written",
    message: null,
    destination: "/out",
    files: ["stress2003_results.csv"],
    replaced_prior_rebuild: false,
    held: 0,
    rebuilt: 3,
  });
  selectFolder.mockResolvedValue("/data/s1");
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

function renderHub() {
  const onWorkspaceChange = vi.fn();
  render(<DataHub workspace="hub" onWorkspaceChange={onWorkspaceChange} />);
  return { onWorkspaceChange };
}

describe("empty state", () => {
  it("prompts for sources and shows no Output band before any are added", () => {
    renderHub();
    expect(screen.getByText(/add source folders to see the ingestion report/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /rebuild/i })).toBeNull();
    expect(ingestSources).not.toHaveBeenCalled();
  });
});

describe("Sources band (§7.2)", () => {
  it("adds a picked folder and scans it, showing the per-source counts", async () => {
    renderHub();
    await userEvent.click(screen.getByRole("button", { name: /choose a folder/i }));

    await waitFor(() => expect(ingestSources).toHaveBeenCalledWith(["/data/s1"], undefined));
    expect(await screen.findByText("/data/s1")).toBeTruthy();
    expect(screen.getByText(/1 station · 3 sessions/i)).toBeTruthy();
  });

  it("removes a source and re-scans the remaining set", async () => {
    selectFolder.mockResolvedValueOnce("/data/s1").mockResolvedValueOnce("/data/s2");
    ingestSources
      .mockResolvedValueOnce(cleanView())
      .mockResolvedValueOnce(cleanView({ sources: [
        { folder: "/data/s1", stations: 1, sessions: 3 },
        { folder: "/data/s2", stations: 1, sessions: 2 },
      ] }))
      .mockResolvedValue(cleanView());

    renderHub();
    await userEvent.click(screen.getByRole("button", { name: /choose a folder/i }));
    await screen.findByText("/data/s1");
    await userEvent.click(screen.getByRole("button", { name: /drop station folders/i }));
    await screen.findByText("/data/s2");

    await userEvent.click(screen.getByRole("button", { name: /remove \/data\/s1/i }));

    await waitFor(() => expect(screen.queryByText("/data/s1")).toBeNull());
    expect(ingestSources).toHaveBeenLastCalledWith(["/data/s2"], undefined);
  });
});

describe("Ingestion report band (§7.3)", () => {
  it("shows the headline stats and the three severity groups", async () => {
    ingestSources.mockResolvedValue(
      cleanView({
        held: 1,
        attention: 2,
        will_rebuild: 5,
        partitions: 2,
        findings: [
          { code: "missing_events", group: "held", message: "held: no events", loud: false, sessions: 1 },
          { code: "id_collision", group: "attention", message: "ID collision → NOT independent", loud: true, sessions: 2 },
          { code: "config_drift_partition", group: "attention", message: "config drift → partition", loud: false, sessions: 2 },
          { code: "clean_ingest", group: "info", message: "5 sessions ingested cleanly", loud: false, sessions: 5 },
        ],
      }),
    );
    renderHub();
    await userEvent.click(screen.getByRole("button", { name: /choose a folder/i }));

    expect(await screen.findByText("held: no events")).toBeTruthy();
    // Held count reflected in the stat row.
    const held = screen.getByText("held").closest(".hub-stat")!;
    expect(within(held as HTMLElement).getByText("1")).toBeTruthy();
    // Loud attention finding carries the warning marker.
    expect(screen.getByText(/ID collision → NOT independent/)).toBeTruthy();
    expect(screen.getAllByText("⚠").length).toBeGreaterThan(0);
  });

  it("leads the Clean group with the ingested count, not a bare None", async () => {
    // A fully clean dataset itemizes nothing, but the Clean group is exactly
    // what reports it (§7.3) — it must state how many ingested cleanly.
    ingestSources.mockResolvedValue(cleanView({ findings: [] }));
    renderHub();
    await userEvent.click(screen.getByRole("button", { name: /choose a folder/i }));
    await screen.findByText("stress2003_results.csv");

    expect(screen.getByText("3 sessions ingested")).toBeTruthy();
    expect(screen.getByText(/ingested cleanly from ground truth/i)).toBeTruthy();
  });

  it("surfaces the no-study abort without gating", async () => {
    ingestSources.mockResolvedValue(
      cleanView({ ok: false, error: "no study identifiable in /data/s1" }),
    );
    renderHub();
    await userEvent.click(screen.getByRole("button", { name: /choose a folder/i }));

    expect(await screen.findByText(/no study identifiable/i)).toBeTruthy();
    // No Output band when nothing is rebuildable.
    expect(screen.queryByRole("button", { name: /rebuild/i })).toBeNull();
  });
});

describe("Output band (§7.4)", () => {
  it("previews the exact file tree the writer will land", async () => {
    renderHub();
    await userEvent.click(screen.getByRole("button", { name: /choose a folder/i }));
    await screen.findByText("stress2003_results.csv");

    expect(screen.getByText("stress2003_provenance.json")).toBeTruthy();
    expect(screen.getByText(/reconstructed:true/)).toBeTruthy();
    expect(screen.getByText("stress2003_ingestion_report.md")).toBeTruthy();
  });

  it("keeps Rebuild disabled until a destination is chosen, then writes", async () => {
    renderHub();
    await userEvent.click(screen.getByRole("button", { name: /choose a folder/i }));
    const rebuild = await screen.findByRole("button", { name: /rebuild 3 sessions/i });
    expect((rebuild as HTMLButtonElement).disabled).toBe(true);

    selectFolder.mockResolvedValueOnce("/out");
    await userEvent.click(screen.getByRole("button", { name: /choose…/i }));
    await waitFor(() => expect((rebuild as HTMLButtonElement).disabled).toBe(false));

    await userEvent.click(rebuild);
    await waitFor(() =>
      expect(rebuildHub).toHaveBeenCalledWith(["/data/s1"], "/out", undefined, false),
    );
    expect(await screen.findByText(/wrote 1 file\(s\) to \/out/i)).toBeTruthy();
  });

  it("re-scans in the overridden mode when the override is chosen", async () => {
    renderHub();
    await userEvent.click(screen.getByRole("button", { name: /choose a folder/i }));
    await screen.findByText("stress2003_results.csv");

    await userEvent.click(screen.getByRole("radio", { name: /override/i }));

    await waitFor(() =>
      expect(ingestSources).toHaveBeenLastCalledWith(["/data/s1"], "classic"),
    );
  });

  it("confirms before replacing a prior rebuild, then forces it", async () => {
    rebuildHub
      .mockResolvedValueOnce({
        ok: false,
        status: "needs_force",
        message: "/out already holds a Hub rebuild — rebuilding will replace those files in place.",
        destination: "/out",
        files: [],
        replaced_prior_rebuild: false,
        held: 0,
        rebuilt: 0,
      })
      .mockResolvedValueOnce({
        ok: true,
        status: "written",
        message: null,
        destination: "/out",
        files: ["stress2003_results.csv"],
        replaced_prior_rebuild: true,
        held: 0,
        rebuilt: 3,
      });

    renderHub();
    await userEvent.click(screen.getByRole("button", { name: /choose a folder/i }));
    await screen.findByText("stress2003_results.csv");
    selectFolder.mockResolvedValueOnce("/out");
    await userEvent.click(screen.getByRole("button", { name: /choose…/i }));

    const rebuild = await screen.findByRole("button", { name: /rebuild 3 sessions/i });
    await userEvent.click(rebuild);

    // First attempt comes back needs_force; the button arms a confirm step.
    const confirm = await screen.findByRole("button", { name: /confirm replace/i });
    expect(await screen.findByText(/already holds a Hub rebuild/i)).toBeTruthy();

    await userEvent.click(confirm);
    await waitFor(() =>
      expect(rebuildHub).toHaveBeenLastCalledWith(["/data/s1"], "/out", undefined, true),
    );
    expect(await screen.findByText(/replaced a prior rebuild/i)).toBeTruthy();
  });
});

describe("workspace tabs (§7.1)", () => {
  it("switches back to Study Setup from the Hub's own bar", async () => {
    const { onWorkspaceChange } = renderHub();
    await userEvent.click(screen.getByRole("tab", { name: /study setup/i }));
    expect(onWorkspaceChange).toHaveBeenCalledWith("setup");
  });
});
