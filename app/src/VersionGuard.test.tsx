import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { VersionGuard } from "./VersionGuard";

const fetchHealth = vi.fn();
vi.mock("./lib/api", () => ({
  fetchHealth: (...args: unknown[]) => fetchHealth(...args),
}));

afterEach(() => {
  cleanup();
  fetchHealth.mockReset();
});

describe("VersionGuard", () => {
  it("blocks the app with both versions named when the sidecar version disagrees", async () => {
    fetchHealth.mockResolvedValue({ status: "ok", version: "0.2.0" });

    render(
      <VersionGuard appVersion="1.0.0">
        <p>study setup</p>
      </VersionGuard>,
    );

    await screen.findByText(/0\.2\.0/);
    screen.getByText(/1\.0\.0/);
    expect(screen.queryByText("study setup")).toBeNull();
  });

  it("renders the app when the versions match", async () => {
    fetchHealth.mockResolvedValue({ status: "ok", version: "1.0.0" });

    render(
      <VersionGuard appVersion="1.0.0">
        <p>study setup</p>
      </VersionGuard>,
    );

    await screen.findByText("study setup");
  });

  it("does not block when the sidecar is unreachable (connection errors are handled downstream)", async () => {
    fetchHealth.mockRejectedValue(new Error("fetch failed"));

    render(
      <VersionGuard appVersion="1.0.0">
        <p>study setup</p>
      </VersionGuard>,
    );

    await screen.findByText("study setup");
  });
});
