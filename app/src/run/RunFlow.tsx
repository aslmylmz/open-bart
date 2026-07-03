import { useEffect, useState, type CSSProperties } from "react";

import BartGame from "../BartGame";
import { preview } from "../lib/api";
import type { TaskConfig } from "../lib/config";
import { taskStrings } from "../lib/i18n";
import { cardStyle, centerStyle, headingStyle, pageStyle } from "./participantStyles";

interface RunFlowProps {
  config: TaskConfig;
  onExit: () => void;
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
export function RunFlow({ config, onExit }: RunFlowProps) {
  const t = taskStrings(config.language);
  const [phase, setPhase] = useState<Phase>("consent");
  const [participantId, setParticipantId] = useState("");
  const [condition, setCondition] = useState("");
  const [hazards, setHazards] = useState<Record<string, number[]> | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Preset-driven enum (issue 37): a study that declares conditions forces a
  // dropdown choice — no typing, no typos. No conditions → no condition UI.
  const conditions = config.conditions ?? [];
  const needsCondition = conditions.length > 0 && !condition;

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

  if (phase === "task" && hazards) {
    // BartGame owns the back button here: it only offers the exit while no
    // balloon is live, so a participant can't leave mid-trial (Issue 27).
    return (
      <div style={pageStyle}>
        <BartGame
          config={config}
          hazards={hazards}
          candidateId={participantId || "anonymous"}
          condition={condition || null}
          onExit={onExit}
        />
      </div>
    );
  }

  return (
    <div style={pageStyle}>
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
        {phase === "id" && (
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
              onChange={(e) => setParticipantId(e.target.value)}
            />
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
              disabled={!participantId.trim() || needsCondition}
              onClick={() => setPhase("loading")}
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
