import { describe, expect, it } from "vitest";

import { seedNotice } from "./standaloneNotices";

describe("seedNotice (DATA-SPEC §2.5)", () => {
  it("is absent outside Standalone Mode, seed or not", () => {
    expect(seedNotice(false, true)).toBeNull();
    expect(seedNotice(false, false)).toBeNull();
  });

  it("is absent under fresh randomness — the hazard needs a fixed seed", () => {
    expect(seedNotice(true, false)).toBeNull();
  });

  it("warns loudly under standalone + fixed seed: shared IDs mean identical sequences", () => {
    const notice = seedNotice(true, true);
    expect(notice?.tone).toBe("warning");
    expect(notice?.text).toContain("identical sequences");
    expect(notice?.text).toContain("globally unique");
  });

  it("downgrades to an informational note once auto-generated IDs defuse the hazard (I18)", () => {
    const notice = seedNotice(true, true, true);
    expect(notice?.tone).toBe("info");
    expect(notice?.text).toContain("independent across stations");
  });
});
