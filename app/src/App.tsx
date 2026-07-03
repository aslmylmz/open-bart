import { useEffect, useState } from "react";

import { DEFAULT_STUDY, type TaskConfig } from "./lib/config";
import { toggleFullscreen } from "./lib/desktop";
import { RunFlow } from "./run/RunFlow";
import { EvPreview } from "./setup/EvPreview";
import { StudySetup } from "./setup/StudySetup";
import { VersionGuard } from "./VersionGuard";

type Mode = "setup" | "run" | "practice";

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

  // The guard wraps both modes: a version-mismatched sidecar must block before
  // any study is configured or run against it.
  const content =
    mode === "run" || mode === "practice" ? (
      <RunFlow config={config} practice={mode === "practice"} onExit={() => setMode("setup")} />
    ) : (
      // Study Setup (issue 14). Issue 15 adds the live EV preview alongside the form;
      // the active study defaults to the validated 128/32/8 linear config.
      <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh", paddingBottom: "64px" }}>
        <StudySetup config={config} onChange={setConfig} />
        <EvPreview config={config} />
        <div style={{ maxWidth: 720, width: "100%", margin: "0 auto", padding: "0 16px", marginTop: "32px", display: "flex", justifyContent: "flex-end", gap: 12 }}>
          {/* Test Run (issue 43): the same participant flow, but bannered,
              stamped, and routed to practice/ — for RAs to click through a
              setup without touching the dataset. */}
          <button
            type="button"
            onClick={() => setMode("practice")}
            style={{ background: "transparent", borderColor: "#d97706", color: "#fbbf24", fontSize: "1.125rem", padding: "12px 24px", borderRadius: "8px", fontWeight: 600 }}
          >
            Test run
          </button>
          <button
            type="button"
            onClick={() => setMode("run")}
            style={{ background: "#10b981", borderColor: "#059669", color: "#fff", fontSize: "1.125rem", padding: "12px 32px", borderRadius: "8px", fontWeight: 600 }}
          >
            Start run →
          </button>
        </div>
      </div>
    );

  return <VersionGuard appVersion={__APP_VERSION__}>{content}</VersionGuard>;
}
