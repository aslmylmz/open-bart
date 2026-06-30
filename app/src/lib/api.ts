import type { SessionPayload } from "./session";

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

/** POST a session payload to the scoring endpoint and return the parsed result. */
export async function submitSession<T>(payload: SessionPayload): Promise<T> {
  const response = await fetch(scoringEndpoint(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Scoring failed");
  }
  return (await response.json()) as T;
}

/** Persist a finished session locally via the sidecar's /write-output (SPEC §13).
 * The engine (not JS) owns file writing; config is omitted so the sidecar uses the
 * default study until Study Setup (Phase 3) supplies one. */
export async function persistSession(payload: SessionPayload): Promise<void> {
  const response = await fetch(`${resolveApiUrl()}/write-output`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session: payload }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail ?? "Write-output failed");
  }
}
