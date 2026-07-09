/** Shared Light Posture building blocks for the Participant View (ADR 0003):
 * sterile off-white page, dark text, content centred in a white card. RunFlow
 * and Debrief compose these so participant surfaces stay visually identical.
 *
 * Colors reference the token layer where the old hex already matched a token
 * role — the page root must carry data-posture="light" for these to resolve to
 * the exact pre-redesign hexes (tokens.css remap), so pagePosture bundles that
 * attribute with the style. The card radius (16px) is a deliberate
 * participant-only value outside the researcher radii scale. */

import type { CSSProperties } from "react";

export const pageStyle: CSSProperties = {
  minHeight: "100vh",
  background: "var(--color-bg-app)",
  color: "var(--color-text-primary)",
  display: "flex",
  flexDirection: "column",
};

/** Spread onto every participant page root: the posture attribute and the page
 * style are one contract — a root with only the style would render dark. */
export const pagePosture = {
  "data-posture": "light",
  style: pageStyle,
} as const;

export const centerStyle: CSSProperties = {
  flex: 1,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 24,
};

export const cardStyle: CSSProperties = {
  width: "100%",
  maxWidth: 480,
  background: "var(--color-bg-surface)",
  borderRadius: 16,
  padding: "36px 40px",
  border: "1px solid var(--color-border)",
  boxShadow: "var(--shadow-card)",
  textAlign: "center",
  color: "var(--color-text-primary)",
};

export const headingStyle: CSSProperties = {
  fontSize: "1.6rem",
  fontWeight: 700,
  margin: "0 0 16px",
};
