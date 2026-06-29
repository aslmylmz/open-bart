import type { SessionPayload } from "./session";

/** Default scoring endpoint: the local Python sidecar (overridable via VITE_API_URL). */
const DEFAULT_API_URL = "http://localhost:8000";

export function resolveApiUrl(): string {
  return import.meta.env.VITE_API_URL ?? DEFAULT_API_URL;
}

export function scoringEndpoint(): string {
  return `${resolveApiUrl()}/score`;
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
