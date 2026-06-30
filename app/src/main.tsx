import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { initSidecarUrl } from "./lib/api";

// Under Tauri, learn the sidecar's ephemeral port before the first request; in a
// plain browser this resolves immediately (no-op). Render regardless of outcome.
initSidecarUrl()
  .catch((err) => console.error("Sidecar URL init failed:", err))
  .finally(() => {
    createRoot(document.getElementById("root")!).render(
      <StrictMode>
        <App />
      </StrictMode>,
    );
  });
