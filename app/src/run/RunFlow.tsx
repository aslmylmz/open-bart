import { useEffect, useState } from "react";

import BartGame from "../BartGame";
import { preview } from "../lib/api";
import type { TaskConfig } from "../lib/config";
import { taskStrings } from "../lib/i18n";

interface RunFlowProps {
  config: TaskConfig;
  onExit: () => void;
}

type Phase = "consent" | "id" | "loading" | "task" | "error";

/** Participant Run flow (SPEC §11): consent → participant ID → task → debrief.
 * Before the task it fetches the per-color hazard vectors from `/preview` (the same
 * landscape the scorer uses) so the client bursts from the config, not a hardcoded
 * model. The debrief is BartGame's own results screen (reused, decision this session). */
export function RunFlow({ config, onExit }: RunFlowProps) {
  const t = taskStrings(config.language);
  const [phase, setPhase] = useState<Phase>("consent");
  const [participantId, setParticipantId] = useState("");
  const [hazards, setHazards] = useState<Record<string, number[]> | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const backButton = (
    <button type="button" onClick={onExit}>
      ← Back to setup
    </button>
  );

  if (phase === "task" && hazards) {
    return (
      <div>
        {backButton}
        <BartGame config={config} hazards={hazards} candidateId={participantId || "anonymous"} />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 520, margin: "0 auto", padding: 24 }}>
      {backButton}
      {phase === "consent" && (
        <>
          <h1>{t.consentTitle}</h1>
          <p>{t.consentBody}</p>
          <button type="button" onClick={() => setPhase("id")}>
            {t.consentAgree}
          </button>
        </>
      )}
      {phase === "id" && (
        <>
          <h1>{t.idPrompt}</h1>
          <input
            value={participantId}
            placeholder={t.idPlaceholder}
            onChange={(e) => setParticipantId(e.target.value)}
          />{" "}
          <button
            type="button"
            disabled={!participantId.trim()}
            onClick={() => setPhase("loading")}
          >
            {t.idContinue}
          </button>
        </>
      )}
      {phase === "loading" && <p>{t.analyzing}</p>}
      {phase === "error" && (
        <>
          <p style={{ color: "#b91c1c" }}>{error}</p>
          <button type="button" onClick={() => setPhase("id")}>
            {t.idContinue}
          </button>
        </>
      )}
    </div>
  );
}
