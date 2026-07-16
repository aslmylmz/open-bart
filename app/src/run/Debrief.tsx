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
    /** null when zero balloons were collected — no adjusted score exists
     * (the engine never falls back to the all-balloon mean). */
    average_pumps_adjusted: number | null;
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
    /** Real-world payout conversion (issue 41); null for studies without a
     * payout block. Computed once by the engine — never re-derived here. */
    payout_amount?: number | null;
    payout_currency?: string | null;
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
  /** Label/symbol for the task-earnings units (issue 55); defaults to "$".
   * Distinct from `payout.currency`, which labels the converted payout. */
  currency?: string;
  balloonsCompleted: number;
  /** The converted amount actually owed, computed once by the engine (issue 41).
   * Omitted for studies without a payout block — no payout line renders. */
  payout?: { amount: number; currency: string } | null;
  /** Practice/test run (issue 59): the thank-you drops the "recorded" claim so
   * it never contradicts the "data not recorded" banner on the same screen. */
  practice?: boolean;
}

/** The participant debrief — a clean thank-you screen with only the high-level
 * summary, in the Light Posture (ADR 0003). The clinical metrics never render
 * here (participant UX convention, Issue 28): researchers read them from the
 * per-session metrics JSON and the master CSV in the output directory. */
export function Debrief({ language, earnings, currency = "$", balloonsCompleted, payout, practice = false }: DebriefProps) {
  const t = taskStrings(language);
  return (
    <div style={cardStyle}>
      <div style={{ fontSize: "3rem", marginBottom: 8 }}>🎈</div>
      <h1 style={headingStyle}>{t.thankYouTitle}</h1>
      <p style={{ fontSize: "1.05rem", lineHeight: 1.6, color: "#374151", margin: "0 0 28px" }}>
        {practice ? t.thankYouBodyPractice : t.thankYouBody}
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
          {currency}
          {earnings.toFixed(2)}
        </div>
        <div style={{ color: "#6b7280" }}>
          {balloonsCompleted} {t.balloonsWord}
        </div>
        {payout && (
          <div style={{ borderTop: "1px solid #e5e7eb", marginTop: 16, paddingTop: 16 }}>
            <div style={{ color: "#6b7280", fontSize: "0.85rem" }}>{t.payoutLabel}</div>
            <div style={{ fontSize: "1.6rem", fontWeight: 700, color: "#111827" }}>
              {payout.amount.toFixed(2)} {payout.currency}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
