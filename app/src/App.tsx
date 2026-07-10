import { useEffect, useState } from "react";

import { DEFAULT_STUDY, type TaskConfig } from "./lib/config";
import { toggleFullscreen } from "./lib/desktop";
import { RunFlow } from "./run/RunFlow";
import { StudySetup } from "./setup/StudySetup";
import type { StudySnapshot } from "./setup/studyForm";
import { VersionGuard } from "./VersionGuard";
import "./App.css";

type Mode = "setup" | "run" | "practice";

// ── Mode-switch choreography (DESIGN-SPEC §3.1) ─────────────────────────────
//
// The handoff to a participant is staged: the researcher surface fades to the
// app's near-black (`out`), a still dark hold (`hold`, no text — the
// participant never glimpses setup), then consent fades in (`in`). The mode
// swaps under the opaque hold. Return trips are plain ~200ms fades — ceremony
// only on the handoff. `prefers-reduced-motion` skips the machine entirely.

type SwitchStage = "out" | "hold" | "in";

interface ModeSwitch {
  target: Mode;
  stage: SwitchStage;
  /** True for the setup → run handoff (staged, token durations); false for
   * return trips (plain fades, no hold). */
  ceremony: boolean;
}

const SWITCH_TOKEN: Record<SwitchStage, string> = {
  out: "--switch-out",
  hold: "--switch-hold",
  in: "--switch-in",
};

// tokens.css values, restated for environments that load no stylesheet
// (jsdom). The component tests pin these §3.1 numbers deliberately.
const SWITCH_FALLBACK_MS: Record<SwitchStage, number> = { out: 200, hold: 250, in: 250 };

/** Stage duration in ms — the tokens are the source of truth (they are
 * declared in milliseconds); the veil's animation gets the same number, so
 * the JS timers and the CSS fades cannot drift apart. */
function switchDuration(stage: SwitchStage, ceremony: boolean): number {
  // Return trips reuse the out-fade duration for both fades and never hold.
  const effective = ceremony ? stage : "out";
  const raw = getComputedStyle(document.documentElement).getPropertyValue(SWITCH_TOKEN[effective]);
  const ms = Number.parseFloat(raw);
  return Number.isFinite(ms) && ms >= 0 ? ms : SWITCH_FALLBACK_MS[effective];
}

/** jsdom has no matchMedia at all, hence the typeof guard (defaults to the
 * full choreography). */
function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

// Phase 3 app shell: two modes in the SPA — Study Setup (researcher) and Run
// (participant), joined by the staged mode switch above. The in-memory active
// TaskConfig (seeded from the validated default study) is the store both
// surfaces read/mutate. F11 toggles kiosk/fullscreen (SPEC §10); outside
// Tauri it is a harmless no-op.
export function App() {
  const [mode, setMode] = useState<Mode>("setup");
  const [switching, setSwitching] = useState<ModeSwitch | null>(null);
  const [config, setConfig] = useState<TaskConfig>(DEFAULT_STUDY);
  // The last saved/loaded study file (DESIGN-SPEC §2.1) lives beside the
  // config: a run trip unmounts StudySetup, and the unsaved dot and file
  // identity must not reset with it.
  const [snapshot, setSnapshot] = useState<StudySnapshot>({ path: null, config: DEFAULT_STUDY });

  function beginSwitch(target: Mode) {
    if (switching || mode === target) return; // one trip at a time
    if (prefersReducedMotion()) {
      setMode(target); // §3.1: instant cuts
      return;
    }
    setSwitching({ target, stage: "out", ceremony: target !== "setup" });
  }

  // The switch clock: each stage runs its duration, the mode swaps at the end
  // of the fade-out (under the opaque veil), and return trips jump the hold.
  useEffect(() => {
    if (!switching) return;
    const { target, stage, ceremony } = switching;
    const timer = setTimeout(() => {
      if (stage === "out") {
        setMode(target);
        setSwitching({ target, ceremony, stage: ceremony ? "hold" : "in" });
      } else if (stage === "hold") {
        setSwitching({ target, ceremony, stage: "in" });
      } else {
        setSwitching(null);
      }
    }, switchDuration(stage, ceremony));
    return () => clearTimeout(timer);
  }, [switching]);

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
  // callbacks start the switch here (Test run: the same participant flow, but
  // bannered, stamped, and routed to practice/ — issue 43).
  const content =
    mode === "run" || mode === "practice" ? (
      <RunFlow
        config={config}
        practice={mode === "practice"}
        onExit={() => beginSwitch("setup")}
      />
    ) : (
      <StudySetup
        config={config}
        onChange={setConfig}
        snapshot={snapshot}
        onSnapshotChange={setSnapshot}
        onTestRun={() => beginSwitch("practice")}
        onStartRun={() => beginSwitch("run")}
      />
    );

  return (
    <VersionGuard appVersion={__APP_VERSION__}>
      {content}
      {/* The veil: a sibling of both surfaces, outside any light-posture
        * subtree, so --color-bg-app resolves at :root — dark in both trip
        * directions. It also swallows clicks while a trip is in flight. */}
      {switching && (
        <div
          className={`mode-switch is-${switching.stage}${switching.ceremony ? "" : " is-return"}`}
          aria-hidden
        />
      )}
    </VersionGuard>
  );
}
