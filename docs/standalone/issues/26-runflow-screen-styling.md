# 26 — RunFlow consent / ID / loading / error screen styling

**UI · depends on: 24**

## Context

The participant-facing RunFlow screens (consent, participant ID entry, loading, and
error) are completely unstyled. They render as a few lines of black text in the top-left
corner of a mostly-empty page. The "← Back to setup" button is a raw system button. The
consent screen has no visual weight to indicate it's an important step. The ID input is
a bare HTML input with no dark-theme styling. The loading state shows a plain text
"Analyzing…" with no spinner. The error state has a red text line and an unstyled retry
button.

## Scope

- [ ] [app/src/run/RunFlow.tsx](../../../app/src/run/RunFlow.tsx): restyle all phases for the **Light Posture** (ADR 0003):
  - Ensure the background is `#f8f9fa` with high-contrast dark text
  - **"← Back to setup"**: subtle, pill-shaped ghost button in the top-left corner
    (consistent across all RunFlow phases)
  - **Consent**: vertically and horizontally centered card with clear heading
    typography, readable body text, and a prominent CTA "I agree" button
  - **ID input**: centered card with a properly styled text input, placeholder text, and
    a "Continue" button; disable state visually obvious when input is empty
  - **Loading**: centered spinner or pulsing animation with "Loading…" text
  - **Error**: centered card with red accent border, error message, and styled retry
    button

## Acceptance

- All four RunFlow phases (consent, id, loading, error) are visually centered and
  polished on the light background.
- "← Back to setup" is a subtle styled button, not a raw system button.
- The consent CTA, ID continue, and retry buttons are all prominent and consistently
  styled.
- Existing tests stay green.
