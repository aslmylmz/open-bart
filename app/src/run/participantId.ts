/** The auto-generated participant ID (DATA-SPEC §3.2).
 *
 * An opt-in station-side poka-yoke: when a study sets `auto_participant_id`,
 * the ID screen offers a Generate button that fills the field with a random
 * 9-digit integer. Two stations can then never hand the same ID to different
 * participants — which is both an identity hazard at the Hub and, under a
 * fixed study seed, an identical-balloon-sequence confound.
 *
 * The format is deliberately unoriginal: a bare integer, shape-identical to
 * the `subjID` convention every modeling pipeline already expects (hBayesDM,
 * PEBL `subnum`, Inquisit `subject`), so a generated ID travels into analysis
 * with zero translation. Nine digits is the collision-resistance floor for a
 * numeric alphabet (~0.055% collision at a pooled N of 1000, rare enough that
 * a collision is a genuine anomaly worth flagging); a non-zero first digit
 * dodges the leading-zero stripping Excel and SPSS do on import.
 */

/** Inclusive bounds of the generated range — the full 9-digit space. */
export const PARTICIPANT_ID_MIN = 100_000_000;
export const PARTICIPANT_ID_MAX = 999_999_999;

/** Whether a session's `candidate_id` came from Generate or the keyboard —
 * recorded per session so the Hub can tell an anomalous collision between two
 * generated IDs from ordinary hand-typed ID messiness (DATA-SPEC §5.3). */
export type IdSource = "generated" | "manual";

/** A fresh participant ID: a uniform random integer in
 * [PARTICIPANT_ID_MIN, PARTICIPANT_ID_MAX], as a string — the field's value
 * is text, and the ID stays text everywhere downstream. */
export function generateParticipantId(): string {
  const span = PARTICIPANT_ID_MAX - PARTICIPANT_ID_MIN + 1;
  return String(PARTICIPANT_ID_MIN + Math.floor(Math.random() * span));
}
