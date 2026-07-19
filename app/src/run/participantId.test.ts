import { describe, expect, it, vi } from "vitest";

import { PARTICIPANT_ID_MAX, PARTICIPANT_ID_MIN, generateParticipantId } from "./participantId";

describe("generateParticipantId", () => {
  it("always produces a 9-digit integer whose first digit is non-zero", () => {
    // A leading zero is what Excel and SPSS silently strip on import, breaking
    // the join against the researcher's own roster (DATA-SPEC §3.2).
    for (let i = 0; i < 2000; i++) {
      expect(generateParticipantId()).toMatch(/^[1-9][0-9]{8}$/);
    }
  });

  it("spans the whole 9-digit space at both edges", () => {
    // The collision resistance is the point: the draw must actually reach the
    // ends of [100000000, 999999999], not sit inside a narrower band.
    const random = vi.spyOn(Math, "random");
    random.mockReturnValue(0);
    expect(generateParticipantId()).toBe(String(PARTICIPANT_ID_MIN));
    // 1 is out of Math.random's range; the largest representable draw below it
    // must still land on the top of the range, never one past it.
    random.mockReturnValue(1 - Number.EPSILON / 2);
    expect(generateParticipantId()).toBe(String(PARTICIPANT_ID_MAX));
    random.mockRestore();
  });

  it("does not repeat itself across a realistic study's worth of draws", () => {
    const drawn = new Set<string>();
    for (let i = 0; i < 1000; i++) drawn.add(generateParticipantId());
    expect(drawn.size).toBe(1000);
  });

  it("produces a slug-safe ID the sidecar's filename rule accepts verbatim", () => {
    // check_id rejects any ID the output filenames would rewrite; a bare
    // integer passes trivially, which is why §3.2 needs no new endpoint.
    const id = generateParticipantId();
    expect(id).toBe(id.trim());
    expect(id).toMatch(/^[A-Za-z0-9._-]+$/);
  });
});
