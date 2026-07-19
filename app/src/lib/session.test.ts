import { describe, expect, it } from "vitest";

import { buildSessionPayload } from "./session";

describe("buildSessionPayload", () => {
  it("produces the GameSession shape the scoring engine expects", () => {
    const events = [
      { timestamp: 1, type: "pump" as const, payload: { color: "teal" } },
    ];
    const payload = buildSessionPayload({
      sessionId: "sess-1",
      candidateId: "cand-1",
      events,
    });
    expect(payload).toEqual({
      session_id: "sess-1",
      game_type: "BART_RISK",
      candidate_id: "cand-1",
      condition: null,
      duplicate_acknowledged: false,
      practice: false,
      id_source: null,
      events,
    });
  });

  it("carries the assigned condition for between-subject designs", () => {
    const events = [
      { timestamp: 1, type: "pump" as const, payload: { color: "teal" } },
    ];
    const payload = buildSessionPayload({
      sessionId: "sess-1",
      candidateId: "cand-1",
      events,
      condition: "experimental",
    });
    expect(payload.condition).toBe("experimental");
  });

  it("records that the researcher continued past a duplicate-ID warning", () => {
    const events = [
      { timestamp: 1, type: "pump" as const, payload: { color: "teal" } },
    ];
    const payload = buildSessionPayload({
      sessionId: "sess-1",
      candidateId: "cand-1",
      events,
      duplicateAcknowledged: true,
    });
    expect(payload.duplicate_acknowledged).toBe(true);
  });

  it("stamps Test Run sessions as practice (issue 43)", () => {
    const events = [
      { timestamp: 1, type: "pump" as const, payload: { color: "teal" } },
    ];
    const payload = buildSessionPayload({
      sessionId: "sess-1",
      candidateId: "TEST",
      events,
      practice: true,
    });
    expect(payload.practice).toBe(true);
  });

  it("records that the Generate button produced the ID (DATA-SPEC §3.2)", () => {
    const events = [
      { timestamp: 1, type: "pump" as const, payload: { color: "teal" } },
    ];
    const payload = buildSessionPayload({
      sessionId: "sess-1",
      candidateId: "482910375",
      events,
      idSource: "generated",
    });
    expect(payload.id_source).toBe("generated");
  });

  it("records that the ID was typed rather than generated", () => {
    const events = [
      { timestamp: 1, type: "pump" as const, payload: { color: "teal" } },
    ];
    const payload = buildSessionPayload({
      sessionId: "sess-1",
      candidateId: "cand-1",
      events,
      idSource: "manual",
    });
    expect(payload.id_source).toBe("manual");
  });
});
