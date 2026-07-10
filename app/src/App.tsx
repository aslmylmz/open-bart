import { useEffect, useState } from "react";

import { DEFAULT_STUDY, type TaskConfig } from "./lib/config";
import { toggleFullscreen } from "./lib/desktop";
import { RunFlow } from "./run/RunFlow";
import { StudySetup } from "./setup/StudySetup";
import type { StudySnapshot } from "./setup/studyForm";
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
  // The last saved/loaded study file (DESIGN-SPEC §2.1) lives beside the
  // config: a run trip unmounts StudySetup, and the unsaved dot and file
  // identity must not reset with it.
  const [snapshot, setSnapshot] = useState<StudySnapshot>({ path: null, config: DEFAULT_STUDY });

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
  // any study is configured or run against it. The Researcher View owns the
  // whole setup surface — bands, EV preview slot, and the Run band whose
  // callbacks flip the mode here (Test run: the same participant flow, but
  // bannered, stamped, and routed to practice/ — issue 43).
  const content =
    mode === "run" || mode === "practice" ? (
      <RunFlow config={config} practice={mode === "practice"} onExit={() => setMode("setup")} />
    ) : (
      <StudySetup
        config={config}
        onChange={setConfig}
        snapshot={snapshot}
        onSnapshotChange={setSnapshot}
        onTestRun={() => setMode("practice")}
        onStartRun={() => setMode("run")}
      />
    );

  return <VersionGuard appVersion={__APP_VERSION__}>{content}</VersionGuard>;
}
