import { describe, expect, it } from "vitest";

import type { WriteOutputResult } from "../lib/api";
import { summarizeWriteResult } from "./returnSummary";

/** A write payload as the sidecar returns it: absolute per-session paths plus
 * the study-wide CSV the row landed in. */
function writeResult(overrides: Partial<WriteOutputResult> = {}): WriteOutputResult {
  return {
    events: "/data/study/demo_p001_20260710_events.jsonl",
    metrics: "/data/study/demo_p001_20260710_metrics.json",
    config: "/data/study/demo_p001_20260710_config.json",
    session: "/data/study/demo_p001_20260710_session.json",
    master_csv: "/data/study/demo_results.csv",
    trials_csv: "/data/study/demo_trials.csv",
    warnings: [],
    ...overrides,
  };
}

describe("summarizeWriteResult", () => {
  it("derives the output directory from the session file's location", () => {
    expect(summarizeWriteResult(writeResult()).outputDir).toBe("/data/study");
  });

  it("names the master CSV by its file name, not the full path", () => {
    expect(summarizeWriteResult(writeResult()).masterCsvName).toBe("demo_results.csv");
  });

  it("handles Windows-style paths from a Windows sidecar", () => {
    const summary = summarizeWriteResult(
      writeResult({
        session: "C:\\data\\study\\demo_p001_session.json",
        master_csv: "C:\\data\\study\\demo_results.csv",
      }),
    );
    expect(summary.outputDir).toBe("C:\\data\\study");
    expect(summary.masterCsvName).toBe("demo_results.csv");
  });

  it("reports a missing master CSV as null rather than inventing a name", () => {
    const summary = summarizeWriteResult(writeResult({ master_csv: null }));
    expect(summary.masterCsvName).toBeNull();
  });

  it("lists exactly the per-session files the payload carries", () => {
    expect(summarizeWriteResult(writeResult()).sessionFileKinds).toEqual([
      "events",
      "metrics",
      "config",
      "session",
    ]);
  });

  it("does not claim a file the payload lacks", () => {
    const summary = summarizeWriteResult(writeResult({ metrics: "" }));
    expect(summary.sessionFileKinds).toEqual(["events", "config", "session"]);
  });

  it("falls back to the path itself when the session path has no directory part", () => {
    const summary = summarizeWriteResult(writeResult({ session: "session.json" }));
    expect(summary.outputDir).toBe(".");
  });
});
