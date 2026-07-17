import type { WriteOutputResult } from "../lib/api";

/** What the return surface states about where the data landed (DESIGN-SPEC
 * §3.2), derived purely from the /write-output payload — no new sidecar API. */
export interface ReturnSummary {
  /** Directory the per-session files were written into. */
  outputDir: string;
  /** Which per-session files the payload actually names — the surface claims
   * only these as written, never a fixed list. */
  sessionFileKinds: string[];
  /** File name of the master CSV the session row landed in — a timestamped
   * sibling when the main file was locked (the warnings explain) — or null
   * when the payload carries none. */
  masterCsvName: string | null;
  /** Whether the study ran in Standalone Mode — stated by the payload
   * (DATA-SPEC §2.4), so a missing master CSV reads as the mode's design,
   * never as a silent absence. */
  standalone: boolean;
  /** This machine's station label, or null when unset (single-station). */
  stationId: string | null;
}

const SESSION_FILE_KINDS = ["events", "metrics", "config", "session"] as const;

/** The sidecar returns OS-native absolute paths, so both separators must be
 * understood regardless of the platform the UI itself runs on. */
function lastSeparator(path: string): number {
  return Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
}

function dirname(path: string): string {
  const cut = lastSeparator(path);
  return cut === -1 ? "." : path.slice(0, cut);
}

function basename(path: string): string {
  return path.slice(lastSeparator(path) + 1);
}

export function summarizeWriteResult(write: WriteOutputResult): ReturnSummary {
  return {
    outputDir: dirname(write.session),
    sessionFileKinds: SESSION_FILE_KINDS.filter((kind) => Boolean(write[kind])),
    masterCsvName: write.master_csv ? basename(write.master_csv) : null,
    standalone: write.standalone,
    stationId: write.station_id,
  };
}
