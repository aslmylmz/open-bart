import type { GameEvent } from "./events";

/** The session payload POSTed to the scoring endpoint (mirrors scoring.schemas.GameSession). */
export interface SessionPayload {
  session_id: string;
  game_type: "BART_RISK";
  candidate_id: string;
  /** Assigned condition for between-subject designs; null when the study
   * declares no conditions (issue 37). */
  condition: string | null;
  events: GameEvent[];
}

export function buildSessionPayload(
  sessionId: string,
  candidateId: string,
  events: GameEvent[],
  condition: string | null = null,
): SessionPayload {
  return {
    session_id: sessionId,
    game_type: "BART_RISK",
    candidate_id: candidateId,
    condition,
    events,
  };
}
