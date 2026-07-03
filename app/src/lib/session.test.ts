import { describe, expect, it } from "vitest";

import { buildSessionPayload } from "./session";

describe("buildSessionPayload", () => {
  it("produces the GameSession shape the scoring engine expects", () => {
    const events = [
      { timestamp: 1, type: "pump" as const, payload: { color: "teal" } },
    ];
    const payload = buildSessionPayload("sess-1", "cand-1", events);
    expect(payload).toEqual({
      session_id: "sess-1",
      game_type: "BART_RISK",
      candidate_id: "cand-1",
      condition: null,
      events,
    });
  });

  it("carries the assigned condition for between-subject designs", () => {
    const events = [
      { timestamp: 1, type: "pump" as const, payload: { color: "teal" } },
    ];
    const payload = buildSessionPayload("sess-1", "cand-1", events, "experimental");
    expect(payload.condition).toBe("experimental");
  });
});
