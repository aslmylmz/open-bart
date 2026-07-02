/** Shared Light Posture building blocks for the Participant View (ADR 0003):
 * sterile off-white page, dark text, content centred in a white card. RunFlow
 * and Debrief compose these so participant surfaces stay visually identical. */

import type { CSSProperties } from "react";

export const pageStyle: CSSProperties = {
  minHeight: "100vh",
  background: "#f8f9fa",
  color: "#111827",
  display: "flex",
  flexDirection: "column",
};

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
  background: "#fff",
  borderRadius: 16,
  padding: "36px 40px",
  border: "1px solid #e5e7eb",
  boxShadow: "0 4px 24px rgba(0, 0, 0, 0.06)",
  textAlign: "center",
  color: "#111827",
};

export const headingStyle: CSSProperties = {
  fontSize: "1.6rem",
  fontWeight: 700,
  margin: "0 0 16px",
};
