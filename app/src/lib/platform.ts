/** Pure platform helpers for the Save/Load shortcuts (DESIGN-SPEC §2.7): the
 * kbd chips must render the true platform modifier (⌘ on macOS, Ctrl on
 * Windows) and the keydown handler must match the same modifier. Detection
 * takes the platform string as an argument so both sides stay testable;
 * callers pass `navigator.platform`. */

/** True for macOS platform strings (the app ships to macOS and Windows). */
export function isMacPlatform(platform: string): boolean {
  return /mac/i.test(platform);
}

/** The visible chip text for a shortcut key, e.g. "⌘S" or "Ctrl+S". */
export function shortcutChip(key: string, macLike: boolean): string {
  return macLike ? `⌘${key}` : `Ctrl+${key}`;
}

/** The modifier state a shortcut match needs — a plain-object slice of
 * KeyboardEvent so the predicate stays pure. */
interface ShortcutEvent {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
  altKey: boolean;
}

/** Whether a keydown is this platform's chord for `key`: ⌘ on macOS, Ctrl
 * elsewhere — never both, and never with Alt (⌥ types characters on macOS).
 * Case-insensitive on the key so Shift doesn't break the match. */
export function matchesShortcut(e: ShortcutEvent, key: string, macLike: boolean): boolean {
  if (e.key.toLowerCase() !== key.toLowerCase() || e.altKey) return false;
  return macLike ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey;
}
