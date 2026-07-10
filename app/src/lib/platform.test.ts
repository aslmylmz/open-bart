import { describe, expect, it } from "vitest";

import { isMacPlatform, matchesShortcut, shortcutChip } from "./platform";

describe("isMacPlatform", () => {
  it("recognizes macOS platform strings", () => {
    expect(isMacPlatform("MacIntel")).toBe(true);
  });

  it("treats Windows and unknown platforms as non-mac", () => {
    expect(isMacPlatform("Win32")).toBe(false);
    expect(isMacPlatform("")).toBe(false);
  });
});

describe("shortcutChip", () => {
  it("renders the command glyph on macOS", () => {
    expect(shortcutChip("S", true)).toBe("⌘S");
  });

  it("renders Ctrl elsewhere", () => {
    expect(shortcutChip("O", false)).toBe("Ctrl+O");
  });
});

describe("matchesShortcut", () => {
  it("matches ⌘+key on macOS", () => {
    expect(matchesShortcut({ key: "s", metaKey: true, ctrlKey: false, altKey: false }, "s", true)).toBe(
      true,
    );
  });

  it("does not treat Ctrl as the macOS modifier", () => {
    expect(matchesShortcut({ key: "s", metaKey: false, ctrlKey: true, altKey: false }, "s", true)).toBe(
      false,
    );
  });

  it("matches Ctrl+key off macOS", () => {
    expect(matchesShortcut({ key: "o", metaKey: false, ctrlKey: true, altKey: false }, "o", false)).toBe(
      true,
    );
  });

  it("ignores the bare key without the platform modifier", () => {
    expect(matchesShortcut({ key: "s", metaKey: false, ctrlKey: false, altKey: false }, "s", true)).toBe(
      false,
    );
    expect(matchesShortcut({ key: "o", metaKey: false, ctrlKey: false, altKey: false }, "o", false)).toBe(
      false,
    );
  });

  it("ignores alt-modified combos (they type characters on macOS)", () => {
    expect(matchesShortcut({ key: "s", metaKey: true, ctrlKey: false, altKey: true }, "s", true)).toBe(
      false,
    );
  });

  it("matches case-insensitively — shift does not break the shortcut", () => {
    expect(matchesShortcut({ key: "S", metaKey: true, ctrlKey: false, altKey: false }, "s", true)).toBe(
      true,
    );
  });
});
