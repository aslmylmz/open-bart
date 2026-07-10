/** Immutable edit helpers for the active study config (the Study-Setup form model).
 *
 * Each helper returns a new `TaskConfig` (never mutates its input), so React state
 * updates stay predictable. They encode the form's behavior — switching a family
 * reseeds its params, removing colors keeps at least one — and are unit-tested
 * without the DOM; `StudySetup.tsx` is the thin shell that calls them.
 */

import type { ColorProfile, HazardFamily, PayoutConversion, QCThresholds, TaskConfig } from "../lib/config";
import { defaultHazard } from "./familyParams";

/** Form seed for the QC block, mirroring the pydantic `QCThresholds` defaults
 * (issue 40). Shown in the inputs and materialized on first edit; a study that is
 * never touched keeps `qc` absent, which the engine reads as these same defaults.
 * A convenience only — `/validate-config` stays the authority on the values. */
export const DEFAULT_QC: QCThresholds = { fast_response_ms: 100, zero_pump_streak: 5 };

/** Form seed for enabling a payout (issue 41). Pydantic has no payout default
 * (absent = no payout), so this is a pure UI starting point: a 1:1 conversion
 * with a placeholder label, valid out of the box (rate > 0, non-blank currency). */
export const DEFAULT_PAYOUT: PayoutConversion = { rate: 1, currency: "$" };

/** Patch top-level study fields (title, language, reward, seed, output dir). */
export function setStudyField(config: TaskConfig, patch: Partial<TaskConfig>): TaskConfig {
  return { ...config, ...patch };
}

/** Patch the study's QC thresholds (issue 40). Materializes the block from
 * `DEFAULT_QC` when the study has none, so editing one threshold leaves the
 * sibling at its literature default rather than dropping it. */
export function setQcField(config: TaskConfig, patch: Partial<QCThresholds>): TaskConfig {
  return { ...config, qc: { ...(config.qc ?? DEFAULT_QC), ...patch } };
}

/** Toggle the study's payout conversion (issue 41). Enabling seeds a default
 * block when there is none (keeping any existing block on re-enable); disabling
 * sets it to `null` — the no-payout state that serializes as v1.0.0 behavior. */
export function setPayoutEnabled(config: TaskConfig, enabled: boolean): TaskConfig {
  return { ...config, payout: enabled ? (config.payout ?? DEFAULT_PAYOUT) : null };
}

/** Patch the study's payout conversion fields (issue 41). Seeds from
 * `DEFAULT_PAYOUT` if the block is somehow absent, so a field edit always lands
 * on a well-formed block; the sidecar stays the authority on the values. */
export function setPayoutField(config: TaskConfig, patch: Partial<PayoutConversion>): TaskConfig {
  return { ...config, payout: { ...(config.payout ?? DEFAULT_PAYOUT), ...patch } };
}

/** Patch one color's non-hazard fields (name, label, hex, max_pumps, trials). */
export function setColorField(
  config: TaskConfig,
  colorIndex: number,
  patch: Partial<ColorProfile>,
): TaskConfig {
  const colors = config.colors.map((color, i) =>
    i === colorIndex ? { ...color, ...patch } : color,
  );
  return { ...config, colors };
}

/** Append a new linear color with a name not already used by the study. */
export function addColor(config: TaskConfig): TaskConfig {
  const used = new Set(config.colors.map((c) => c.name));
  let n = config.colors.length + 1;
  while (used.has(`color_${n}`)) n += 1;
  const name = `color_${n}`;
  const color: ColorProfile = {
    name,
    label: `Color ${n}`,
    display_hex: "#888888",
    max_pumps: 32,
    trials: 10,
    hazard: { family: "dynamic" },
  };
  return { ...config, colors: [...config.colors, color] };
}

/** Replace one color's hazard with the chosen family's defaults (seeded against
 * that color's `max_pumps`, so the array families stay well-formed). */
export function setColorHazardFamily(
  config: TaskConfig,
  colorIndex: number,
  family: HazardFamily,
): TaskConfig {
  const colors = config.colors.map((color, i) =>
    i === colorIndex ? { ...color, hazard: defaultHazard(family, color.max_pumps) } : color,
  );
  return { ...config, colors };
}

/** Set a single scalar parameter (e.g. constant `p`, weibull `shape`) on one
 * color's current hazard, leaving its `family` and other params intact. */
export function setHazardParam(
  config: TaskConfig,
  colorIndex: number,
  key: string,
  value: number,
): TaskConfig {
  const colors = config.colors.map((color, i) =>
    i === colorIndex ? { ...color, hazard: { ...color.hazard, [key]: value } } : color,
  );
  return { ...config, colors };
}

/** Parse a comma-separated text field into a number list (for the step/tabular
 * array params). Blank and non-numeric entries are dropped; `/validate-config`
 * is the backstop for out-of-range or wrong-length results. */
export function parseNumberList(text: string): number[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .map(Number)
    .filter((n) => !Number.isNaN(n));
}

/** Parse a comma-separated text field into condition names (issue 37). Entries
 * are trimmed and blanks dropped (tolerating trailing commas while typing);
 * duplicates and over-long names are left for `/validate-config` — the sidecar
 * stays the sole validation authority. */
export function parseConditionList(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

/** Parse the exit-passcode field into the config value (issue 44): trimmed,
 * with blank meaning "no kiosk lock" (null — the v1.0.0 behavior). Length and
 * other rules stay with `/validate-config`, the sole validation authority. */
export function parseExitPasscode(text: string): string | null {
  const passcode = text.trim();
  return passcode.length > 0 ? passcode : null;
}

/** Parse loaded `study.json` text into a config. Throws on malformed JSON so the
 * loader can surface an error instead of replacing the active config; structural
 * validity is then checked by the sidecar's `/validate-config`. */
export function parseStudy(text: string): TaskConfig {
  return JSON.parse(text) as TaskConfig;
}

/** Remove a color, but never below one (a study needs at least one color; this
 * also keeps configs out of the engine's degenerate single-color/single-balloon
 * crash range — see scoring/bart.py). A no-op when only one color remains. */
export function removeColor(config: TaskConfig, colorIndex: number): TaskConfig {
  if (config.colors.length <= 1) return config;
  return { ...config, colors: config.colors.filter((_, i) => i !== colorIndex) };
}

/** The last saved/loaded study file: the config the unsaved dot compares
 * against and the path line 2 of the identity bar names (DESIGN-SPEC §2.1).
 * Owned by the App shell, beside the active config, so it survives run trips
 * (a run unmounts StudySetup). `path` is null until the study touches a file. */
export interface StudySnapshot {
  path: string | null;
  config: TaskConfig;
}

/** Whether the active config differs from the last saved/loaded snapshot — the
 * identity bar's unsaved dot (DESIGN-SPEC §2.1). Compares JSON serializations:
 * "dirty" means exactly "saving now would write a different file", so an edit
 * reverted by hand goes clean again, while materializing an optional block at
 * its defaults (qc, payout) counts as a change. Key order is stable because
 * every edit path spreads the previous config. */
export function isStudyDirty(config: TaskConfig, snapshot: TaskConfig): boolean {
  return JSON.stringify(config) !== JSON.stringify(snapshot);
}

/** The identity bar's line-2 file identity (DESIGN-SPEC §2.1): file name plus
 * its directory for the last saved/loaded path, or the never-saved wording.
 * A null path means the session started from the built-in default study and
 * has never saved or loaded a file (nothing persists across launches), hence
 * the first-launch prefix (§4) — it stays through unsaved edits, where the
 * dirty dot is the signal.
 * Splits on either separator so a Windows path reads correctly too. */
export function fileIdentityLine(path: string | null): string {
  if (path === null) return "default study — not saved to file yet";
  const cut = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
  if (cut < 0) return path;
  return `${path.slice(cut + 1)} — ${path.slice(0, cut)}`;
}

/** Headline for the save-blocked error strip (DESIGN-SPEC §2.2). */
export function saveBlockedHeadline(errorCount: number): string {
  return `Not saved — ${errorCount} ${errorCount === 1 ? "error" : "errors"}.`;
}
