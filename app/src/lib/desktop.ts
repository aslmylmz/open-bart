import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { open, save } from "@tauri-apps/plugin-dialog";

const STUDY_FILTERS = [{ name: "Study", extensions: ["json"] }];

/** Save study.json to a user-chosen path via the native dialog; returns the path, or
 * null if the user cancelled. The write goes through a Rust command (the user's dialog
 * choice is the authorization), keeping the fs capability scope minimal. */
export async function saveStudy(content: string): Promise<string | null> {
  const path = await save({ filters: STUDY_FILTERS, defaultPath: "study.json" });
  if (!path) return null;
  await invoke("write_study_file", { path, content });
  return path;
}

/** A study file picked through the load dialog: where it lives and what it holds. */
export interface LoadedStudyFile {
  path: string;
  text: string;
}

/** Load study.json from a user-chosen path via the native dialog; returns the path
 * and its text (the identity bar shows both — DESIGN-SPEC §2.1), or null if the
 * user cancelled. The read goes through a Rust command. */
export async function loadStudy(): Promise<LoadedStudyFile | null> {
  const selected = await open({ filters: STUDY_FILTERS, multiple: false, directory: false });
  if (typeof selected !== "string") return null;
  const text = await invoke<string>("read_study_file", { path: selected });
  return { path: selected, text };
}

/** Prompt the user to select an output directory via native dialog. */
export async function selectOutputDir(): Promise<string | null> {
  const selected = await open({ multiple: false, directory: true });
  if (typeof selected !== "string") return null;
  return selected;
}

/** Toggle the window between fullscreen (kiosk) and windowed; returns the new state. */
export async function toggleFullscreen(): Promise<boolean> {
  const win = getCurrentWindow();
  const next = !(await win.isFullscreen());
  await win.setFullscreen(next);
  return next;
}

/** Engage or release the kiosk window state (issue 44): fullscreen and
 * always-on-top together, while a passcode-locked session runs. In-app only —
 * no global hooks, no OS-level shortcut suppression. Outside Tauri (plain
 * browser, tests) there is no native window; callers catch the rejection. */
export async function setKioskLock(locked: boolean): Promise<void> {
  const win = getCurrentWindow();
  await win.setFullscreen(locked);
  await win.setAlwaysOnTop(locked);
}
