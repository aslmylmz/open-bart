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
const DEFAULT_API_URL = "http://localhost:8000";

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

/** Fetch each color's hazard/survival/EV curves + numeric optimum for a config
 * (SPEC §7.3). Throws if the config is invalid (the sidecar returns 422), so the
 * caller can keep the last-good preview rather than blanking the plot. */
export async function preview(config: TaskConfig): Promise<PreviewResponse> {
  const response = await fetch(`${resolveApiUrl()}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Preview failed");
  }
  return (await response.json()) as PreviewResponse;
}

/** POST a session (with its study config) to /score and return the parsed result.
 * Body is the ScoreRequest shape `{ session, config? }`; an omitted config defaults
 * to the study on the server, so the metrics reflect the config that was run. */
export async function submitSession<T>(payload: SessionPayload, config?: TaskConfig): Promise<T> {
  const body = config ? { session: payload, config } : { session: payload };
  const response = await fetch(scoringEndpoint(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Scoring failed");
  }
  return (await response.json()) as T;
}

/** Persist a finished session locally via the sidecar's /write-output (SPEC §13).
 * The engine (not JS) owns file writing; the study config is sent so the metrics
 * and config snapshot reflect the study that was run (omitted → default study). */
export async function persistSession(payload: SessionPayload, config?: TaskConfig): Promise<void> {
  const body = config ? { session: payload, config } : { session: payload };
  const response = await fetch(`${resolveApiUrl()}/write-output`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Write-output failed");
  }
}
