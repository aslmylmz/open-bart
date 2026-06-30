/** Immutable edit helpers for the active study config (the Study-Setup form model).
 *
 * Each helper returns a new `TaskConfig` (never mutates its input), so React state
 * updates stay predictable. They encode the form's behavior — switching a family
 * reseeds its params, removing colors keeps at least one — and are unit-tested
 * without the DOM; `StudySetup.tsx` is the thin shell that calls them.
 */

import type { ColorProfile, HazardFamily, TaskConfig } from "../lib/config";
import { defaultHazard } from "./familyParams";

/** Patch top-level study fields (title, language, reward, seed, output dir). */
export function setStudyField(config: TaskConfig, patch: Partial<TaskConfig>): TaskConfig {
  return { ...config, ...patch };
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
    hazard: { family: "linear" },
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
