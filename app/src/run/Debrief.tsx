import type { Language } from "../lib/config";
import { taskStrings } from "../lib/i18n";
import { cardStyle, headingStyle } from "./participantStyles";

/** One color's summary row in the scored output (mirrors the engine's color_metrics). */
interface ColorMetrics {
  color: string;
  average_pumps: number;
  explosion_rate: number;
  total_balloons: number;
  risk_profile: string;
}

/** The scored result the sidecar returns (mirrors scoring AssessmentResponse).
 * Researcher-only data: it is persisted to the session files / master CSV and
 * deliberately never rendered to the participant. */
export interface AssessmentResult {
  session_id: string;
  game_type: string;
  raw_metrics: {
    average_pumps_adjusted: number;
    explosion_rate: number;
    mean_latency_between_pumps: number;
    total_balloons: number;
    total_pumps: number;
    total_explosions: number;
    total_collections: number;
    color_metrics: ColorMetrics[];
    learning_rate: number;
    risk_adjustment_score: number;
    color_discrimination_index: number;
    impulsivity_index: number;
    patience_index: number;
    response_consistency: number;
    adaptive_strategy_score: number;
  };
  normalized_scores: Array<{
    metric_name: string;
    raw_value: number;
    z_score: number;
    percentile: number;
  }>;
  profile_traits: Record<string, { level: string; percentile: number; z_score: number }>;
}

interface DebriefProps {
  language: Language;
  /** The session's cumulative collected amount (the task engine's running score). */
  earnings: number;
  balloonsCompleted: number;
}

/** The participant debrief — a clean thank-you screen with only the high-level
 * summary, in the Light Posture (ADR 0003). The clinical metrics never render
 * here (participant UX convention, Issue 28): researchers read them from the
 * per-session metrics JSON and the master CSV in the output directory. */
export function Debrief({ language, earnings, balloonsCompleted }: DebriefProps) {
  const t = taskStrings(language);
  return (
    <div style={cardStyle}>
      <div style={{ fontSize: "3rem", marginBottom: 8 }}>🎈</div>
      <h1 style={headingStyle}>{t.thankYouTitle}</h1>
      <p style={{ fontSize: "1.05rem", lineHeight: 1.6, color: "#374151", margin: "0 0 28px" }}>
        {t.thankYouBody}
      </p>
      <div
        style={{
          borderTop: "1px solid #e5e7eb",
          paddingTop: 24,
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        <div style={{ color: "#6b7280", fontSize: "0.85rem" }}>{t.totalEarnings}</div>
        <div style={{ fontSize: "2.2rem", fontWeight: 700, color: "#16a34a" }}>
          ${earnings.toFixed(2)}
        </div>
        <div style={{ color: "#6b7280" }}>
          {balloonsCompleted} {t.balloonsWord}
        </div>
      </div>
    </div>
  );
}
