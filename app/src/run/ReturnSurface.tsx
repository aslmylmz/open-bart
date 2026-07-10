import type { WriteOutputResult } from "../lib/api";
import type { AssessmentResult } from "./Debrief";
import { summarizeWriteResult } from "./returnSummary";

interface ReturnSurfaceProps {
  participantId: string;
  /** Assigned condition, or null for condition-less studies (no row renders). */
  condition: string | null;
  result: AssessmentResult;
  write: WriteOutputResult;
  onBack: () => void;
}

/** The researcher hand-back screen after a real run (DESIGN-SPEC §3.2): dark
 * `.run-*` surface on `:root` tokens — deliberately no data-posture="light" on
 * this subtree (§6 drift note), the posture flips back here. Session facts and
 * the data-confirmation block state only what the completion payload already
 * provides; test runs never reach this screen. English by design — researcher
 * surfaces are not localized (i18n covers participant screens only). */
export function ReturnSurface({
  participantId,
  condition,
  result,
  write,
  onBack,
}: ReturnSurfaceProps) {
  const { outputDir, sessionFileKinds, masterCsvName } = summarizeWriteResult(write);
  const balloons = result.raw_metrics?.total_balloons;
  const warnings = write.warnings ?? [];

  return (
    <div className="run-return">
      <div className="run-return-inner">
        <h1 className="run-return-title">Session complete</h1>

        <dl className="run-return-facts">
          <div className="run-return-fact">
            <dt>Participant</dt>
            <dd>{participantId}</dd>
          </div>
          {condition && (
            <div className="run-return-fact">
              <dt>Condition</dt>
              <dd>{condition}</dd>
            </div>
          )}
          {balloons != null && (
            <div className="run-return-fact">
              <dt>Balloons</dt>
              <dd>{balloons}</dd>
            </div>
          )}
        </dl>

        <section className="run-return-data">
          <h2 className="run-return-data-title">Data confirmation</h2>
          <dl className="run-return-rows">
            <div className="run-return-row">
              <dt>Output directory</dt>
              <dd className="run-return-path">{outputDir}</dd>
            </div>
            <div className="run-return-row">
              <dt>Session files</dt>
              <dd>{sessionFileKinds.length > 0 ? `${sessionFileKinds.join(" · ")} — written` : "—"}</dd>
            </div>
            <div className="run-return-row">
              <dt>Master CSV</dt>
              <dd>
                {masterCsvName ? (
                  <>
                    <span className="run-return-path">{masterCsvName}</span> — row appended
                  </>
                ) : (
                  "—"
                )}
              </dd>
            </div>
          </dl>
          {warnings.length > 0 && (
            <div role="alert" className="run-return-warnings">
              {warnings.map((w, i) => (
                <p key={i}>{w}</p>
              ))}
            </div>
          )}
        </section>

        <button type="button" className="run-return-action" onClick={onBack}>
          Back to Study Setup
        </button>
      </div>
    </div>
  );
}
