/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the scoring endpoint (Python sidecar). Defaults to localhost:8000. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/** The app's own version, injected at build time from package.json (vite `define`).
 * Compared against the sidecar's /healthz version by the boot-time VersionGuard. */
declare const __APP_VERSION__: string;
