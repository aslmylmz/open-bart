import { postJson, resolveApiUrl } from "./api";

/** The Data Hub's client bridge to the sidecar's `/hub/*` routes (I12). The
 * researcher-facing tab is a thin surface over the *same* ingest → rebuild →
 * write core the CLI drives (I11): every decision, count, and file name comes
 * back from the sidecar (`sidecar/hub_view.py`), so these mirror its view
 * models and add no Hub logic of their own. */

/** A rebuild's metrics mode: the study's own (`null`) or the §6.3 override. */
export type HubMode = "classic" | "advanced";

/** A finding's severity group (mirrors the sidecar's `Group`). */
export type HubGroup = "held" | "attention" | "info";

/** One Sources-band row: a source folder and how much of the pooled dataset
 * was attributed to it (DATA-SPEC §7.2). */
export interface HubSourceView {
  folder: string;
  stations: number;
  sessions: number;
}

/** One itemized report line for the Ingestion-report band (§7.3). */
export interface HubFindingView {
  code: string;
  group: HubGroup;
  message: string;
  loud: boolean;
  sessions: number;
}

/** One row of the Output band's "will write" file-tree preview (§7.4). */
export interface HubPlannedFile {
  path: string;
  reconstructed: boolean;
}

/** The whole Data Hub tab state from one ingest + rebuild (mirrors HubView).
 * `ok: false` carries the no-study-identifiable message and leaves the rest
 * empty — the one dataset-level abort the band surfaces without gating. */
export interface HubView {
  ok: boolean;
  error: string | null;
  title: string;
  slug: string;
  sources: HubSourceView[];
  configured_mode: HubMode;
  mode: HubMode;
  mode_source: "configured" | "override";
  will_rebuild: number;
  held: number;
  attention: number;
  partitions: number;
  findings: HubFindingView[];
  files: HubPlannedFile[];
}

/** The Rebuild control's outcome (mirrors HubRebuildResponse). `status` drives
 * the UI: `written` (landed), `needs_force` (confirm replacing a prior
 * rebuild), `refused` (guarded destination), `no_study` (nothing to rebuild). */
export interface HubRebuildResult {
  ok: boolean;
  status: "written" | "needs_force" | "refused" | "no_study";
  message: string | null;
  destination: string | null;
  files: string[];
  replaced_prior_rebuild: boolean;
  held: number;
  rebuilt: number;
}

/** Both `/hub/*` routes return 200 with their own `ok`/`status` verdicts, so a
 * non-2xx is a real transport/validation failure — routed through `api.ts`'s
 * shared `postJson` so the sidecar's `detail` (including FastAPI's 422 field
 * lists) is formatted the same way it is for every other endpoint. */

/** Ingest the chosen source folders and rebuild them in memory (`/hub/ingest`),
 * returning the live, non-gating tab state the bands render. `mode` is the
 * §6.3 override; omit it to rebuild in the study's configured mode. */
export async function ingestSources(
  sources: string[],
  mode?: HubMode,
): Promise<HubView> {
  return postJson<HubView>(`${resolveApiUrl()}/hub/ingest`, {
    sources,
    mode: mode ?? null,
  });
}

/** Write the reconstructed study-wide surfaces (`/hub/rebuild`) — the single
 * accent Rebuild action (§7.4). `force` confirms replacing a prior rebuild in
 * place, the webview's stand-in for the CLI's `--force`. */
export async function rebuildHub(
  sources: string[],
  out: string,
  mode?: HubMode,
  force = false,
): Promise<HubRebuildResult> {
  return postJson<HubRebuildResult>(`${resolveApiUrl()}/hub/rebuild`, {
    sources,
    out,
    mode: mode ?? null,
    force,
  });
}
