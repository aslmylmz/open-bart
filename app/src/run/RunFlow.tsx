import { useEffect, useState, type CSSProperties } from "react";

import BartGame from "../BartGame";
import { checkId, preview } from "../lib/api";
import type { TaskConfig } from "../lib/config";
import { taskStrings } from "../lib/i18n";
import { cardStyle, centerStyle, headingStyle, pageStyle } from "./participantStyles";

interface RunFlowProps {
  config: TaskConfig;
  onExit: () => void;
  /** Test Run (issue 43): same flow, but banners every screen, auto-fills the
   * test ID, skips the ID guardrails, and stamps the session as practice so
   * the sidecar routes it to practice/ and away from the study-wide CSVs. */
  practice?: boolean;
}

type Phase = "consent" | "id" | "loading" | "task" | "error";

const primaryBtnStyle: CSSProperties = {
  width: "100%",
  fontSize: "1.05rem",
  padding: "12px 24px",
  marginTop: 8,
};

/** Participant Run flow (SPEC §11): consent → participant ID → task → debrief.
 * Before the task it fetches the per-color hazard vectors from `/preview` (the same
 * landscape the scorer uses) so the client bursts from the config, not a hardcoded
 * model. The debrief is BartGame's own results screen (reused, decision this session). */
export function RunFlow({ config, onExit, practice = false }: RunFlowProps) {
  const t = taskStrings(config.language);
  const [phase, setPhase] = useState<Phase>("consent");
  const [participantId, setParticipantId] = useState(practice ? "TEST" : "");
  const [condition, setCondition] = useState("");
  const [hazards, setHazards] = useState<Record<string, number[]> | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Duplicate-ID warn-confirm (issue 38): number of sessions the entered ID
  // already has (null = no warning showing), and whether the researcher chose
  // to continue past the warning — stamped into the session's data.
  const [duplicateSessions, setDuplicateSessions] = useState<number | null>(null);
  const [duplicateAcknowledged, setDuplicateAcknowledged] = useState(false);
  const [idError, setIdError] = useState<string | null>(null);
  const [checkingId, setCheckingId] = useState(false);

  // Preset-driven enum (issue 37): a study that declares conditions forces a
  // dropdown choice — no typing, no typos. No conditions → no condition UI.
  const conditions = config.conditions ?? [];
  const needsCondition = conditions.length > 0 && !condition;

  /** The ID is mandatory and vetted by the sidecar (the file-I/O owner) before
   * anything starts: unusable IDs get a readable message, known IDs get the
   * warn-confirm. If the check itself cannot run, proceed — a down sidecar
   * surfaces on the loading screen's own error path, with retry. Practice is
   * exempt (issue 43): its data can't contaminate anything, so nothing gates. */
  async function handleIdContinue() {
    if (practice) {
      setPhase("loading");
      return;
    }
    setCheckingId(true);
    try {
      const verdict = await checkId(participantId.trim(), config);
      if (!verdict.ok) {
        setIdError(t.idInvalid);
        return;
      }
      if (verdict.sessions > 0) {
        setDuplicateSessions(verdict.sessions);
        return;
      }
      setPhase("loading");
    } catch {
      setPhase("loading");
    } finally {
      setCheckingId(false);
    }
  }

  useEffect(() => {
    if (phase !== "loading") return;
    let cancelled = false;
    preview(config)
      .then((res) => {
        if (cancelled) return;
        const h: Record<string, number[]> = {};
        for (const [name, curve] of Object.entries(res.curves)) h[name] = curve.hazard;
        setHazards(h);
        setPhase("task");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Could not load the task");
        setPhase("error");
      });
    return () => {
      cancelled = true;
    };
  }, [phase, config]);

  const backBar = (
    <div style={{ padding: 16 }}>
      <button type="button" className="btn-ghost-participant" onClick={onExit}>
        ← Back to setup
      </button>
    </div>
  );

  // The Test Run banner (issue 43): pinned to the top of *every* practice
  // screen, high-contrast, readable from across a lab room — a real
  // participant must never be run in practice mode unnoticed.
  const practiceBanner = practice ? (
    <div
      style={{
        position: "sticky",
        top: 0,
        zIndex: 100,
        width: "100%",
        background: "#b91c1c",
        color: "#ffffff",
        textAlign: "center",
        padding: "12px 16px",
        fontSize: "1.25rem",
        fontWeight: 800,
        letterSpacing: "0.05em",
      }}
    >
      {t.practiceBanner}
    </div>
  ) : null;

  if (phase === "task" && hazards) {
    // BartGame owns the back button here: it only offers the exit while no
    // balloon is live, so a participant can't leave mid-trial (Issue 27).
    return (
      <div style={pageStyle}>
        {practiceBanner}
        <BartGame
          config={config}
          hazards={hazards}
          candidateId={participantId.trim()}
          condition={condition || null}
          duplicateAcknowledged={duplicateAcknowledged}
          practice={practice}
          onExit={onExit}
        />
      </div>
    );
  }

  return (
    <div style={pageStyle}>
      {practiceBanner}
      {backBar}
      <div style={centerStyle}>
        {phase === "consent" && (
          <div style={cardStyle}>
            <h1 style={headingStyle}>{t.consentTitle}</h1>
            <p style={{ fontSize: "1.05rem", lineHeight: 1.6, color: "#374151", margin: "0 0 24px" }}>
              {t.consentBody}
            </p>
            <button
              type="button"
              className="btn-primary-participant"
              style={primaryBtnStyle}
              onClick={() => setPhase("id")}
            >
              {t.consentAgree}
            </button>
          </div>
        )}
        {phase === "id" && duplicateSessions !== null && (
          <div style={{ ...cardStyle, borderLeft: "4px solid #d97706" }}>
            <h1 style={headingStyle}>{t.duplicateTitle}</h1>
            <p
              role="alert"
              style={{ fontSize: "1.05rem", lineHeight: 1.6, color: "#374151", margin: "0 0 24px" }}
            >
              {t.duplicateBody
                .replace("{id}", participantId.trim())
                .replace("{n}", String(duplicateSessions))}
            </p>
            <button
              type="button"
              className="btn-primary-participant"
              style={primaryBtnStyle}
              onClick={() => {
                setDuplicateAcknowledged(true);
                setDuplicateSessions(null);
                setPhase("loading");
              }}
            >
              {t.duplicateContinue}
            </button>
            <button
              type="button"
              className="btn-ghost-participant"
              style={{ ...primaryBtnStyle, marginTop: 12 }}
              onClick={() => setDuplicateSessions(null)}
            >
              {t.duplicateCancel}
            </button>
          </div>
        )}
        {phase === "id" && duplicateSessions === null && (
          <div style={cardStyle}>
            <h1 style={headingStyle}>{t.idPrompt}</h1>
            <input
              className="input-participant"
              style={{
                width: "100%",
                fontSize: "1.05rem",
                padding: "12px 14px",
                textAlign: "center",
                marginBottom: 20,
              }}
              value={participantId}
              placeholder={t.idPlaceholder}
              onChange={(e) => {
                setParticipantId(e.target.value);
                setIdError(null);
              }}
            />
            {idError && (
              <p role="alert" style={{ color: "#b91c1c", margin: "0 0 16px", fontSize: "0.95rem" }}>
                {idError}
              </p>
            )}
            {conditions.length > 0 && (
              <label
                style={{
                  display: "block",
                  textAlign: "left",
                  fontSize: "0.95rem",
                  color: "#374151",
                  marginBottom: 20,
                }}
              >
                {t.conditionLabel}
                <select
                  className="input-participant"
                  style={{
                    width: "100%",
                    fontSize: "1.05rem",
                    padding: "12px 14px",
                    marginTop: 4,
                  }}
                  value={condition}
                  onChange={(e) => setCondition(e.target.value)}
                >
                  <option value="" disabled>
                    {t.conditionPlaceholder}
                  </option>
                  {conditions.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <button
              type="button"
              className="btn-primary-participant"
              style={primaryBtnStyle}
              disabled={!participantId.trim() || needsCondition || checkingId}
              onClick={handleIdContinue}
            >
              {t.idContinue}
            </button>
          </div>
        )}
        {phase === "loading" && (
          <div
            role="status"
            style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}
          >
            <div
              aria-hidden
              style={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                border: "3px solid #d1d5db",
                borderTopColor: "#4f46e5",
                animation: "spin 0.8s linear infinite",
              }}
            />
            <p style={{ color: "#374151" }}>{t.analyzing}</p>
          </div>
        )}
        {phase === "error" && (
          <div
            style={{
              ...cardStyle,
              borderLeft: "4px solid #dc2626",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 20,
            }}
          >
            <p role="alert" style={{ color: "#b91c1c", margin: 0 }}>
              {error}
            </p>
            <button
              type="button"
              className="btn-primary-participant"
              style={{ padding: "10px 24px" }}
              onClick={() => setPhase("loading")}
            >
              {t.retry}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
