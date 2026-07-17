/** Standalone Mode copy for the study-setup surface (DATA-SPEC §2.5).
 *
 * The seed notice is deliberately three-state (I7, authored for I18): loud
 * while a fixed seed can silently hand two same-ID participants identical
 * balloon sequences across stations, downgraded to informational once
 * auto-generated participant IDs defuse that hazard, absent otherwise. I18
 * only flips the `autoParticipantId` argument — the copy and shape are here.
 */

export interface SeedNotice {
  /** "warning" = the collision hazard is live; "info" = auto-ID defused it. */
  tone: "warning" | "info";
  text: string;
}

/** The inline, non-blocking notice under the seed field, or null when the
 * study is not standalone or runs with fresh randomness. */
export function seedNotice(
  standalone: boolean,
  seedSet: boolean,
  autoParticipantId = false,
): SeedNotice | null {
  if (!standalone || !seedSet) return null;
  if (autoParticipantId) {
    return {
      tone: "info",
      text: "Auto-generated participant IDs are globally unique, so fixed-seed sequences stay independent across stations.",
    };
  }
  return {
    tone: "warning",
    text: "Standalone Mode: participants sharing an ID across stations will see identical sequences; keep IDs globally unique across stations, or leave the seed unset for fresh randomness.",
  };
}
