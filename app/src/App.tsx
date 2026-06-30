import { useEffect, useState } from "react";

import { DEFAULT_STUDY, type TaskConfig } from "./lib/config";
import { toggleFullscreen } from "./lib/desktop";
import { RunFlow } from "./run/RunFlow";
import { EvPreview } from "./setup/EvPreview";
import { StudySetup } from "./setup/StudySetup";

type Mode = "setup" | "run";

// Phase 3 app shell: two modes in the SPA — Study Setup (researcher) and Run
// (participant). This issue stands up the mode switch and the in-memory active
// TaskConfig (seeded from the validated default study). The real Study-Setup form
// (issue 14), live EV preview (15), and config-driven Run flow (16) replace the
// placeholders below; the active config is the store they read/mutate. F11 toggles
// kiosk/fullscreen (SPEC §10); outside Tauri it is a harmless no-op.
export function App() {
  const [mode, setMode] = useState<Mode>("setup");
  const [config, setConfig] = useState<TaskConfig>(DEFAULT_STUDY);

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

  if (mode === "run") {
    return <RunFlow config={config} onExit={() => setMode("setup")} />;
  }

  // Study Setup (issue 14). Issue 15 adds the live EV preview alongside the form;
  // the active study defaults to the validated 128/32/8 linear config.
  return (
    <div>
      <StudySetup config={config} onChange={setConfig} />
      <EvPreview config={config} />
      <div style={{ maxWidth: 720, margin: "0 auto", padding: 16 }}>
        <button type="button" onClick={() => setMode("run")}>
          Start run →
        </button>
      </div>
    </div>
  );
}
