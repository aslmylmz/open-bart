import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ingestSources, rebuildHub } from "./hub";

// The client fronts the sidecar's /hub/* routes; stub fetch so nothing touches
// the network. resolveApiUrl falls back to the default base URL outside Tauri.
const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

function ok(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body) };
}

describe("ingestSources", () => {
  it("posts the sources and mode, returning the view", async () => {
    const view = { ok: true, title: "Study", will_rebuild: 3 };
    fetchMock.mockResolvedValue(ok(view));

    const result = await ingestSources(["/a", "/b"], "classic");

    expect(result).toEqual(view);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/hub\/ingest$/);
    expect(JSON.parse(init.body)).toEqual({ sources: ["/a", "/b"], mode: "classic" });
  });

  it("sends mode: null when no override is given", async () => {
    fetchMock.mockResolvedValue(ok({ ok: true }));

    await ingestSources(["/a"]);

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      sources: ["/a"],
      mode: null,
    });
  });

  it("surfaces the sidecar's detail on a non-2xx", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "boom" }),
    });

    await expect(ingestSources(["/a"])).rejects.toThrow("boom");
  });
});

describe("rebuildHub", () => {
  it("posts sources, out, mode, and force, returning the result", async () => {
    const written = { ok: true, status: "written", files: ["x_results.csv"] };
    fetchMock.mockResolvedValue(ok(written));

    const result = await rebuildHub(["/a"], "/out", "advanced", true);

    expect(result).toEqual(written);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/hub\/rebuild$/);
    expect(JSON.parse(init.body)).toEqual({
      sources: ["/a"],
      out: "/out",
      mode: "advanced",
      force: true,
    });
  });

  it("defaults force to false and mode to null", async () => {
    fetchMock.mockResolvedValue(ok({ ok: false, status: "needs_force" }));

    await rebuildHub(["/a"], "/out");

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      sources: ["/a"],
      out: "/out",
      mode: null,
      force: false,
    });
  });
});
