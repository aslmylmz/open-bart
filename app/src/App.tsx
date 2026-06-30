import { useEffect } from "react";

import BartGame from "./BartGame";
import { toggleFullscreen } from "./lib/desktop";

// Minimal Run wrapper. The full consent -> participant-ID -> debrief flow is Phase 3;
// for now we render the decoupled task directly. F11 toggles kiosk/fullscreen (SPEC §10);
// outside Tauri it is a harmless no-op (the rejected promise is swallowed).
export function App() {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "F11") {
        e.preventDefault();
        void toggleFullscreen().catch((err) =>
          console.error("Fullscreen toggle failed:", err),
        );
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return <BartGame candidateId="anonymous" />;
}
