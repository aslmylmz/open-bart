import { afterEach, describe, expect, it, vi } from "vitest";

import { resolveApiUrl, scoringEndpoint } from "./api";

afterEach(() => {
  vi.unstubAllEnvs();
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
