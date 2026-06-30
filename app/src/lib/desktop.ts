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

/** Load study.json from a user-chosen path via the native dialog; returns its text, or
 * null if the user cancelled. The read goes through a Rust command. */
export async function loadStudy(): Promise<string | null> {
  const selected = await open({ filters: STUDY_FILTERS, multiple: false, directory: false });
  if (typeof selected !== "string") return null;
  return await invoke<string>("read_study_file", { path: selected });
}

/** Toggle the window between fullscreen (kiosk) and windowed; returns the new state. */
export async function toggleFullscreen(): Promise<boolean> {
  const win = getCurrentWindow();
  const next = !(await win.isFullscreen());
  await win.setFullscreen(next);
  return next;
}
