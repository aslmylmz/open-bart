import { afterEach, describe, expect, it, vi } from "vitest";

import {
  initSidecarUrl,
  persistSession,
  resolveApiUrl,
  scoringEndpoint,
  preview,
  setApiBaseUrl,
  submitSession,
  validateConfig,
} from "./api";
import { DEFAULT_STUDY } from "./config";
import type { SessionPayload } from "./session";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  setApiBaseUrl(null);
});

describe("setApiBaseUrl", () => {
  it("overrides the env and default (how the Tauri sidecar port is injected)", () => {
    vi.stubEnv("VITE_API_URL", "http://127.0.0.1:9999");
    setApiBaseUrl("http://127.0.0.1:5000");
    expect(resolveApiUrl()).toBe("http://127.0.0.1:5000");
  });

  it("clearing the override restores the default", () => {
    setApiBaseUrl("http://127.0.0.1:5000");
    setApiBaseUrl(null);
    expect(resolveApiUrl()).toBe("http://localhost:8000");
  });
});

describe("resolveApiUrl", () => {
  it("defaults to the local sidecar when VITE_API_URL is unset", () => {
    expect(resolveApiUrl()).toBe("http://localhost:8000");
  });

  it("honors VITE_API_URL when provided", () => {
    vi.stubEnv("VITE_API_URL", "http://127.0.0.1:9999");
    expect(resolveApiUrl()).toBe("http://127.0.0.1:9999");
  });
});

describe("scoringEndpoint", () => {
  it("targets the sidecar /score route on the resolved base URL", () => {
    expect(scoringEndpoint()).toBe("http://localhost:8000/score");
  });
});

describe("initSidecarUrl", () => {
  it("is a no-op outside Tauri, leaving the resolved URL at its default", async () => {
    await initSidecarUrl();
    expect(resolveApiUrl()).toBe("http://localhost:8000");
  });
});

describe("persistSession", () => {
  it("POSTs the finished session to the sidecar /write-output", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal("fetch", fetchMock);

    await persistSession({
      session_id: "s",
      game_type: "BART_RISK",
      candidate_id: "c",
      events: [],
    });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/write-output");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      session: { session_id: "s", game_type: "BART_RISK", candidate_id: "c", events: [] },
    });
  });
});

describe("validateConfig", () => {
  it("POSTs the config to /validate-config and returns the sidecar's verdict", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: false, errors: ["colors.0.max_pumps: must be > 0"] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await validateConfig(DEFAULT_STUDY);

    expect(result).toEqual({ ok: false, errors: ["colors.0.max_pumps: must be > 0"] });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/validate-config");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual(DEFAULT_STUDY);
  });
});

describe("preview", () => {
  it("POSTs the config to /preview and returns the per-color curves", async () => {
    const curves = {
      purple: { hazard: [0.5], survival: [1, 0.5], ev: [0, 0.25], optimum: 1, optimal_ev: 0.25 },
    };
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ curves }) });
    vi.stubGlobal("fetch", fetchMock);

    const result = await preview(DEFAULT_STUDY);

    expect(result).toEqual({ curves });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/preview");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual(DEFAULT_STUDY);
  });
});

describe("submitSession", () => {
  const payload: SessionPayload = {
    session_id: "s",
    game_type: "BART_RISK",
    candidate_id: "c",
    events: [],
  };

  it("POSTs { session } to /score and returns the parsed assessment", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ session_id: "s", raw_metrics: {} }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await submitSession(payload);

    expect(result).toEqual({ session_id: "s", raw_metrics: {} });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/score");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ session: payload });
  });

  it("wraps the session with the study config when one is provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal("fetch", fetchMock);

    await submitSession(payload, DEFAULT_STUDY);

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      session: payload,
      config: DEFAULT_STUDY,
    });
  });
});
