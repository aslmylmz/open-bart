/** Pure presentation helpers for touched-then-live inline validation (§2.5).
 *
 * The sidecar's `/validate-config` strings are `<dotted.loc>: <message>`
 * (see sidecar/app.py); these helpers map them onto the field paths the form
 * renders so errors can appear under their controls. Mapping is presentation
 * only — the sidecar stays the sole validation authority, and anything
 * unmappable is reserved for the save-blocked strip, which always lists the
 * full pass verbatim.
 */

import { HAZARD_FAMILIES, type TaskConfig } from "../lib/config";
import { FAMILY_PARAMS } from "./familyParams";

/** Sidecar errors sorted into inline-renderable and strip-only. */
export interface MappedErrors {
  /** Form field path → cleaned messages to render under that control. */
  byField: Record<string, string[]>;
  /** Errors naming no rendered field, kept verbatim for the save-blocked strip. */
  unmappable: string[];
}

/** Every field path the form currently renders a control for, derived from
 * the config's own shape (payout presence, colors, each color's family).
 * This list is what "mappable" means: container errors fan out across it and
 * errors matching nothing on it fall back to the strip. */
export function knownFieldPaths(config: TaskConfig): string[] {
  const fields = [
    "title",
    "language",
    "reward_per_pump",
    "seed",
    "conditions",
    "exit_passcode",
    "output_dir",
    "qc.fast_response_ms",
    "qc.zero_pump_streak",
  ];
  if (config.payout != null) fields.push("payout.rate", "payout.currency");
  config.colors.forEach((color, i) => {
    const base = `colors.${i}`;
    fields.push(
      `${base}.name`,
      `${base}.label`,
      `${base}.display_hex`,
      `${base}.max_pumps`,
      `${base}.trials`,
      `${base}.hazard.family`,
    );
    const family = color.hazard.family;
    if (family === "step") {
      fields.push(`${base}.hazard.breakpoints`, `${base}.hazard.levels`);
    } else if (family === "tabular") {
      fields.push(`${base}.hazard.values`);
    } else {
      for (const param of FAMILY_PARAMS[family]) fields.push(`${base}.hazard.${param.key}`);
    }
  });
  return fields;
}

/** The sidecar's error shape: a dotted loc, ": ", then the message. Anything
 * else (e.g. the client's transport fallback) has no field to point at. */
const ERROR_SHAPE = /^([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*): (.+)$/s;

/** Pydantic prefixes custom-validator messages with "Value error, " — noise
 * on a 12px inline line (the strip keeps the raw string). */
function cleanMessage(message: string): string {
  return message.replace(/^Value error, /, "");
}

/** Pydantic locs insert the union tag after `hazard` (colors.0.hazard.weibull.shape,
 * or bare colors.0.hazard.step for that family's cross-field validator); the
 * form's param fields aren't namespaced by family, so drop that segment. */
function stripFamilyTag(parts: string[]): string[] {
  const i = parts.indexOf("hazard");
  if (i >= 0 && (HAZARD_FAMILIES as string[]).includes(parts[i + 1])) {
    return [...parts.slice(0, i + 1), ...parts.slice(i + 2)];
  }
  return parts;
}

/** Sort sidecar error strings into per-field messages and strip-only leftovers.
 * A loc matching a rendered field lands there; one deeper than any control
 * (conditions.1) lands on the ancestor control; one above the controls — a
 * cross-field error like step's shape check — fans out to every field under
 * it, per §2.5 "cross-field errors render at all involved fields". */
export function mapErrorsToFields(errors: string[], fields: string[]): MappedErrors {
  const byField: Record<string, string[]> = {};
  const unmappable: string[] = [];
  const add = (field: string, message: string) => {
    (byField[field] ??= []).push(message);
  };

  for (const error of errors) {
    const match = ERROR_SHAPE.exec(error);
    if (!match) {
      unmappable.push(error);
      continue;
    }
    const path = stripFamilyTag(match[1].split(".")).join(".");
    const message = cleanMessage(match[2]);
    if (fields.includes(path)) {
      add(path, message);
      continue;
    }
    const ancestor = fields.find((field) => path.startsWith(`${field}.`));
    if (ancestor) {
      add(ancestor, message);
      continue;
    }
    const involved = fields.filter((field) => field.startsWith(`${path}.`));
    if (involved.length > 0) {
      for (const field of involved) add(field, message);
      continue;
    }
    unmappable.push(error);
  }

  return { byField, unmappable };
}

/** Retarget index-based touched paths after removing the color at
 * `removedIndex`: its own entries drop and later colors' entries shift down
 * one, so blur history stays with the profile it belongs to instead of
 * silently transferring to whichever card inherits the index. */
export function retargetTouchedAfterColorRemoval(
  touched: ReadonlySet<string>,
  removedIndex: number,
): Set<string> {
  const out = new Set<string>();
  for (const field of touched) {
    const match = /^colors\.(\d+)\.(.+)$/.exec(field);
    if (!match) {
      out.add(field);
      continue;
    }
    const index = Number(match[1]);
    if (index === removedIndex) continue;
    out.add(index > removedIndex ? `colors.${index - 1}.${match[2]}` : field);
  }
  return out;
}

/** The touched-then-live rule (§2.5): a field's errors render only after its
 * first blur — or all at once after any save attempt. Everything else stays
 * off the form (first typing is never nagged); the strip covers the rest. */
export function visibleFieldErrors(
  mapped: MappedErrors,
  touched: ReadonlySet<string>,
  saveAttempted: boolean,
): Record<string, string[]> {
  if (saveAttempted) return mapped.byField;
  return Object.fromEntries(
    Object.entries(mapped.byField).filter(([field]) => touched.has(field)),
  );
}
