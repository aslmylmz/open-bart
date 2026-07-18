import type { TaskConfig } from "./config";
import type { SessionPayload } from "./session";

/** The sidecar's /validate-config verdict (mirrors ValidateConfigResponse). */
export interface ValidateResult {
  ok: boolean;
  errors: string[];
}

/** One color's precomputed curve from /preview (mirrors the sidecar's CurvePreview).
 * `survival`/`ev` are indexed by stop s = 0..N; `hazard` by pump k = 1..N. */
export interface CurvePreview {
  hazard: number[];
  survival: number[];
  ev: number[];
  optimum: number;
  optimal_ev: number;
}

/** Per-color curves for a whole study (mirrors PreviewResponse). */
export interface PreviewResponse {
  curves: Record<string, CurvePreview>;
}

/** Default scoring endpoint: the local Python sidecar (overridable via VITE_API_URL). */
const DEFAULT_API_URL = "http://127.0.0.1:8000";

/** Runtime override for the sidecar base URL: the Tauri shell injects its ephemeral port. */
let overrideApiUrl: string | null = null;

/** Point the client at a base URL at runtime; pass null to clear (back to env/default). */
export function setApiBaseUrl(url: string | null): void {
  overrideApiUrl = url;
}

export function resolveApiUrl(): string {
  return overrideApiUrl ?? import.meta.env.VITE_API_URL ?? DEFAULT_API_URL;
}

export function scoringEndpoint(): string {
  return `${resolveApiUrl()}/score`;
}

function runningInTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/** Under Tauri, learn the sidecar's ephemeral port from the Rust shell
 * (`get_sidecar_url`) and route the client at it. A no-op in a plain browser, so
 * dev and tests keep using VITE_API_URL / the default. */
export async function initSidecarUrl(): Promise<void> {
  if (!runningInTauri()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  setApiBaseUrl(await invoke<string>("get_sidecar_url"));
}

export interface SidecarHealth {
  status: string;
  version: string;
}

/** GET the sidecar's liveness + version (the boot-time handshake input). */
export async function fetchHealth(): Promise<SidecarHealth> {
  const response = await fetch(`${resolveApiUrl()}/healthz`);
  if (!response.ok) throw new Error(`healthz returned ${response.status}`);
  return (await response.json()) as SidecarHealth;
}

/** FastAPI's 422 `detail` is a list of `{loc, msg}` objects; render each as
 * `path.to.field: message` (dropping the "body" prefix) so validation failures
 * read like the field they point at instead of "[object Object]". */
function formatDetail(detail: unknown, url: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((entry: { loc?: unknown[]; msg?: string }) => {
        const loc = Array.isArray(entry?.loc)
          ? entry.loc.filter((part) => part !== "body").join(".")
          : "";
        const msg = entry?.msg ?? JSON.stringify(entry);
        return loc ? `${loc}: ${msg}` : String(msg);
      })
      .join("; ");
  }
  return `Request to ${url} failed`;
}

/** POST a JSON body to a sidecar endpoint and return the parsed response. On a
 * non-2xx it surfaces the server's `detail`, else names the endpoint. This is the
 * single place the client's HTTP + error policy lives — the Hub client (hub.ts)
 * routes through it too, so every endpoint shares the same 422-`detail`
 * formatting rather than re-deriving it. */
export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = (error as { detail?: unknown }).detail;
    throw new Error(detail == null ? `Request to ${url} failed` : formatDetail(detail, url));
  }
  return (await response.json()) as T;
}

/** Validate a candidate study against the sidecar (the validation authority).
 * `/validate-config` returns 200 with `{ ok, errors }` even for invalid configs,
 * so the form can show the messages inline. The body is the raw config object. */
export async function validateConfig(config: TaskConfig): Promise<ValidateResult> {
  const response = await fetch(`${resolveApiUrl()}/validate-config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    return { ok: false, errors: [`Validation request failed (${response.status})`] };
  }
  return (await response.json()) as ValidateResult;
}

/** The sidecar's /check-id verdict (mirrors CheckIdResponse, issue 38).
 * `sessions` counts this station's local files only; `standalone`/`station_id`
 * (DATA-SPEC §2.6) let the ID screen say so honestly — cross-station
 * duplicates are the Hub's to flag at assembly. */
export interface CheckIdResult {
  ok: boolean;
  sessions: number;
  error: string | null;
  standalone: boolean;
  station_id: string | null;
}

/** Vet a participant ID before starting a session (issue 38): the sidecar (the
 * owner of all file I/O) validates it against the filename rules and reports
 * how many sessions the study already has for it — the warn-confirm's input. */
export async function checkId(candidateId: string, config?: TaskConfig): Promise<CheckIdResult> {
  const body = config ? { candidate_id: candidateId, config } : { candidate_id: candidateId };
  return postJson<CheckIdResult>(`${resolveApiUrl()}/check-id`, body);
}

/** Fetch each color's hazard/survival/EV curves + numeric optimum for a config
 * (SPEC §7.3). Throws if the config is invalid (the sidecar returns 422), so the
 * caller can keep the last-good preview rather than blanking the plot. */
export async function preview(config: TaskConfig): Promise<PreviewResponse> {
  return postJson<PreviewResponse>(`${resolveApiUrl()}/preview`, config);
}

/** POST a session (with its study config) to /score and return the parsed result.
 * Body is the ScoreRequest shape `{ session, config? }`; an omitted config defaults
 * to the study on the server, so the metrics reflect the config that was run. */
export async function submitSession<T>(payload: SessionPayload, config?: TaskConfig): Promise<T> {
  const body = config ? { session: payload, config } : { session: payload };
  return postJson<T>(scoringEndpoint(), body);
}

/** The sidecar's /write-output result (mirrors WriteOutputResponse). `warnings`
 * carries recoverable data-integrity notices — a locked master CSV diverted to a
 * timestamped sibling, a schema migration — that the UI must surface (issue 50).
 * `standalone`/`station_id` state the deployment mode affirmatively (DATA-SPEC
 * §2.4): the return surface derives everything from this payload, never from a
 * file's absence. */
export interface WriteOutputResult {
  events: string;
  metrics: string;
  config: string;
  session: string;
  master_csv?: string | null;
  trials_csv?: string | null;
  warnings: string[];
  standalone: boolean;
  station_id: string | null;
}

/** This machine's station identity (mirrors StationResponse, DATA-SPEC §2.3):
 * the per-machine label re-displayed on the study-setup surface, plus the ok /
 * error verdict when a new label was submitted (a rejected label never
 * replaces the stored one). */
export interface StationResult {
  ok: boolean;
  station_id: string | null;
  machine_uuid: string;
  error?: string | null;
}

/** GET the per-machine station identity — the study-setup badge's input. */
export async function fetchStation(): Promise<StationResult> {
  const response = await fetch(`${resolveApiUrl()}/station`);
  if (!response.ok) throw new Error(`station returned ${response.status}`);
  return (await response.json()) as StationResult;
}

/** Persist a new station label for this machine (entered once at machine
 * setup). A whitespace-only label clears the setting; an unusable label comes
 * back ok=false with a readable reason and the stored label untouched. */
export async function setStationId(stationId: string): Promise<StationResult> {
  return postJson<StationResult>(`${resolveApiUrl()}/station`, { station_id: stationId });
}

/** Persist a finished session locally via the sidecar's /write-output (SPEC §13).
 * Returns the write result so the caller can surface its `warnings` (issue 50);
 * the engine (not JS) owns file writing, and the study config is sent so the
 * metrics and config snapshot reflect the study that was run (omitted → default). */
export async function persistSession(
  payload: SessionPayload,
  config?: TaskConfig,
): Promise<WriteOutputResult> {
  const body = config ? { session: payload, config } : { session: payload };
  return postJson<WriteOutputResult>(`${resolveApiUrl()}/write-output`, body);
}
