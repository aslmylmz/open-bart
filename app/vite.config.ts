/// <reference types="vitest/config" />
import { readFileSync } from "node:fs";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const { version } = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8"));

// Vite SPA + Vitest. The task runs fully offline inside the Tauri webview; the
// Python sidecar becomes the scoring endpoint (its port handed over at runtime).
// The server block keeps `tauri dev` deterministic (fixed port it can point at).
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  // The app's version, compared against the sidecar's /healthz version at boot
  // (VersionGuard): a stale bundled sidecar must block, not fail confusingly.
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  server: {
    port: 5173,
    strictPort: true,
  },
  // Expose TAURI_* alongside VITE_* to the client without leaking other env.
  envPrefix: ["VITE_", "TAURI_"],
  test: {
    // Logic tests (*.test.ts) stay in the fast node env; component tests
    // (*.test.tsx) need a DOM, so they opt into jsdom via the glob below.
    environment: "node",
    environmentMatchGlobs: [["**/*.test.tsx", "jsdom"]],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
