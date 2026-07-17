import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { StationBadge } from "./StationBadge";

// The badge reads and writes the per-machine station setting through the
// sidecar's /station endpoints; stub the api module so nothing touches the
// network.
const fetchStation = vi.fn();
const setStationId = vi.fn();
vi.mock("../lib/api", () => ({
  fetchStation: (...args: unknown[]) => fetchStation(...args),
  setStationId: (...args: unknown[]) => setStationId(...args),
}));

beforeEach(() => {
  fetchStation.mockResolvedValue({ ok: true, station_id: "S1", machine_uuid: "uuid-a" });
});

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

describe("StationBadge (DATA-SPEC §2.4)", () => {
  it("states the mode and this machine's station affirmatively", async () => {
    render(<StationBadge />);
    expect(screen.getByText("Standalone Mode")).toBeTruthy();
    expect(await screen.findByText("Station: S1")).toBeTruthy();
  });

  it("shows a station-less machine as 'not set' — never a bare dash", async () => {
    fetchStation.mockResolvedValue({ ok: true, station_id: null, machine_uuid: "uuid-a" });
    render(<StationBadge />);
    expect(await screen.findByText("Station: not set")).toBeTruthy();
  });

  it("sets the station in place: click, type, Enter — entered once at machine setup", async () => {
    fetchStation.mockResolvedValue({ ok: true, station_id: null, machine_uuid: "uuid-a" });
    setStationId.mockResolvedValue({ ok: true, station_id: "S2", machine_uuid: "uuid-a" });
    render(<StationBadge />);

    await userEvent.click(await screen.findByText("Station: not set"));
    await userEvent.type(screen.getByLabelText("Station ID"), "S2{Enter}");

    expect(setStationId).toHaveBeenCalledWith("S2");
    expect(await screen.findByText("Station: S2")).toBeTruthy();
  });

  it("surfaces a rejected label and keeps the stored one", async () => {
    setStationId.mockResolvedValue({
      ok: false,
      station_id: "S1",
      machine_uuid: "uuid-a",
      error: "Station ID 'S 2' cannot be used in file names.",
    });
    render(<StationBadge />);

    await userEvent.click(await screen.findByText("Station: S1"));
    await userEvent.clear(screen.getByLabelText("Station ID"));
    await userEvent.type(screen.getByLabelText("Station ID"), "S 2{Enter}");

    expect(await screen.findByRole("alert")).toBeTruthy();
    // Escape abandons the edit; the badge still shows the stored label.
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.getByText("Station: S1")).toBeTruthy());
  });
});
