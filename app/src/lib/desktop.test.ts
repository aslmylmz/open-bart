import { afterEach, describe, expect, it, vi } from "vitest";

// Mock the Tauri native boundaries (dialogs, IPC, window).
vi.mock("@tauri-apps/plugin-dialog", () => ({ save: vi.fn(), open: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/window", () => ({ getCurrentWindow: vi.fn() }));

import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { open, save } from "@tauri-apps/plugin-dialog";

import { loadStudy, saveStudy, setKioskLock, toggleFullscreen } from "./desktop";

afterEach(() => vi.clearAllMocks());

describe("saveStudy", () => {
  it("writes the content to the chosen path and returns it", async () => {
    vi.mocked(save).mockResolvedValue("/tmp/study.json");
    const path = await saveStudy('{"title":"t"}');
    expect(path).toBe("/tmp/study.json");
    expect(invoke).toHaveBeenCalledWith("write_study_file", {
      path: "/tmp/study.json",
      content: '{"title":"t"}',
    });
  });

  it("returns null and writes nothing when the dialog is cancelled", async () => {
    vi.mocked(save).mockResolvedValue(null);
    expect(await saveStudy("x")).toBeNull();
    expect(invoke).not.toHaveBeenCalled();
  });
});

describe("loadStudy", () => {
  it("reads and returns the content of the chosen path", async () => {
    vi.mocked(open).mockResolvedValue("/tmp/study.json");
    vi.mocked(invoke).mockResolvedValue('{"title":"loaded"}');
    const content = await loadStudy();
    expect(invoke).toHaveBeenCalledWith("read_study_file", { path: "/tmp/study.json" });
    expect(content).toBe('{"title":"loaded"}');
  });

  it("returns null and reads nothing when the dialog is cancelled", async () => {
    vi.mocked(open).mockResolvedValue(null);
    expect(await loadStudy()).toBeNull();
    expect(invoke).not.toHaveBeenCalled();
  });
});

describe("setKioskLock", () => {
  it("engages fullscreen and always-on-top together, and releases both", async () => {
    const setFullscreen = vi.fn().mockResolvedValue(undefined);
    const setAlwaysOnTop = vi.fn().mockResolvedValue(undefined);
    vi.mocked(getCurrentWindow).mockReturnValue({ setFullscreen, setAlwaysOnTop } as never);

    await setKioskLock(true);
    expect(setFullscreen).toHaveBeenCalledWith(true);
    expect(setAlwaysOnTop).toHaveBeenCalledWith(true);

    await setKioskLock(false);
    expect(setFullscreen).toHaveBeenCalledWith(false);
    expect(setAlwaysOnTop).toHaveBeenCalledWith(false);
  });
});

describe("toggleFullscreen", () => {
  it("enters fullscreen from windowed and returns the new state", async () => {
    const setFullscreen = vi.fn().mockResolvedValue(undefined);
    vi.mocked(getCurrentWindow).mockReturnValue({
      isFullscreen: vi.fn().mockResolvedValue(false),
      setFullscreen,
    } as never);
    expect(await toggleFullscreen()).toBe(true);
    expect(setFullscreen).toHaveBeenCalledWith(true);
  });

  it("exits fullscreen when already fullscreen", async () => {
    const setFullscreen = vi.fn().mockResolvedValue(undefined);
    vi.mocked(getCurrentWindow).mockReturnValue({
      isFullscreen: vi.fn().mockResolvedValue(true),
      setFullscreen,
    } as never);
    expect(await toggleFullscreen()).toBe(false);
    expect(setFullscreen).toHaveBeenCalledWith(false);
  });
});
