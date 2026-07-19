import type { IdSource } from "../run/participantId";
import type { GameEvent } from "./events";

/** The session payload POSTed to the scoring endpoint (mirrors scoring.schemas.GameSession). */
export interface SessionPayload {
  session_id: string;
  game_type: "BART_RISK";
  candidate_id: string;
  /** Assigned condition for between-subject designs; null when the study
   * declares no conditions (issue 37). */
  condition: string | null;
  /** True when the ID screen warned this ID already had sessions and the
   * researcher chose to continue (issue 38) — keeps ID reuse visible. */
  duplicate_acknowledged: boolean;
  /** True for Test Run sessions (issue 43): the sidecar writes them under
   * practice/ and never appends them to the study-wide CSVs. */
  practice: boolean;
  /** Which path produced `candidate_id` on the ID screen — the Generate
   * button or the keyboard (DATA-SPEC §3.2). Only the client knows; the
   * sidecar records it on the envelope for studies running with
   * `auto_participant_id`, and null everywhere else. */
  id_source: IdSource | null;
  events: GameEvent[];
}

/** What the run screen knows at submit time, in client naming. Field semantics
 * are documented on the wire shape above; this interface only renames them. */
interface SessionInput {
  sessionId: string;
  candidateId: string;
  events: GameEvent[];
  condition?: string | null;
  duplicateAcknowledged?: boolean;
  practice?: boolean;
  idSource?: IdSource | null;
}

export function buildSessionPayload({
  sessionId,
  candidateId,
  events,
  condition = null,
  duplicateAcknowledged = false,
  practice = false,
  idSource = null,
}: SessionInput): SessionPayload {
  return {
    session_id: sessionId,
    game_type: "BART_RISK",
    candidate_id: candidateId,
    condition,
    duplicate_acknowledged: duplicateAcknowledged,
    practice,
    id_source: idSource,
    events,
  };
}
