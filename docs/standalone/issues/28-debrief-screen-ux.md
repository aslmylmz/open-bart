# 28 — Debrief screen UX: participant vs researcher modes

**UI · depends on: 24**

## Context

The current `Debrief.tsx` screen renders immediately after the participant finishes the task. It is packed with deep psychological scoring metrics: Adaptive Strategy Score, Learning Rate, Color Discrimination Index, Impulsivity Index, Patience Index, Response Consistency, and Risk Adjustment Score, plus a per-color breakdown.

This violates participant view UX conventions. Participants should see a clean, encouraging "Thank You" screen with high-level summary stats (e.g. Total Earnings), not their raw clinical metrics or impulsivity scores. The detailed metrics are intended for the researcher.

Additionally, researchers need these outputs in standard CSV formats for statistical software (SPSS, R), not just as JSON telemetry.

## Scope

- [ ] [app/src/run/Debrief.tsx](../../../app/src/run/Debrief.tsx):
  - Strip the complex behavioral metrics from the default participant view.
  - Redesign as a simple "Thank You for Participating" screen using the **Light Posture**.
  - Show only high-level summary (e.g., Total Earnings, Balloons completed).
- [ ] Implement a "Researcher Results View" (could be a toggle, a separate route, or just rely on the generated CSV/JSON files, per the user's preference for "ease of use" and CSV outputs).
  - Ensure the sidecar or frontend provides a clear path to export or view the `*_metrics.json` data as a CSV row suitable for SPSS/R (refer to the `Master CSV` concept in `CONTEXT.md`).
- [ ] Note: The actual CSV generation might already be handled by the sidecar or needs to be implemented in a separate issue if not present. This issue focuses on the UI presentation of the Debrief.

## Acceptance

- The participant sees a clean, simple "Thank You" screen after the task, without clinical metrics.
- The Debrief screen uses the Light Posture (white background, dark text).
- The detailed metrics are preserved for researcher use (via JSON/CSV output).
- Existing tests stay green.
