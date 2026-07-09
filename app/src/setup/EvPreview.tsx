import { useEffect, useState } from "react";

import { type CurvePreview, preview } from "../lib/api";
import type { TaskConfig } from "../lib/config";
import { curveGeometry, type PlotBox } from "./evGeometry";

const BOX: PlotBox = { width: 320, height: 160, padding: 24 };

interface EvPreviewProps {
  config: TaskConfig;
}

/** Live EV-curve + optimum preview (SPEC §7.3). Debounced `/preview` fetch with a
 * stale-response guard (a superseded request can't overwrite a newer one); on an
 * invalid intermediate config the last-good plot stays and the error is shown
 * non-blockingly. Rendering is hand-rolled SVG (no charting dependency) via the
 * pure `curveGeometry` transform. */
export function EvPreview({ config }: EvPreviewProps) {
  const [curves, setCurves] = useState<Record<string, CurvePreview> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const handle = setTimeout(() => {
      preview(config)
        .then((res) => {
          if (cancelled) return;
          setCurves(res.curves);
          setError(null);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setError(err instanceof Error ? err.message : "Preview unavailable");
        });
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [config]);

  // No heading or page container of its own: this renders inside the Study
  // Setup's EV Preview band, whose rail carries the title (issue 02); the
  // full redesign onto .ev-* classes is issue 05.
  return (
    <div>
      {error && (
        <p style={{ color: "#fca5a5", background: "rgba(220, 38, 38, 0.1)", padding: "12px", borderRadius: "8px", fontSize: "0.875rem" }}>
          Preview not updated: {error}
        </p>
      )}
      <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
        {config.colors.map((color) => {
          const curve = curves?.[color.name];
          if (!curve) {
            return <p key={color.name} style={{ color: "#9ca3af", fontSize: "0.875rem" }}>{color.label || color.name}: computing…</p>;
          }
          const g = curveGeometry(curve, BOX);
          return (
            <figure key={color.name} style={{ margin: "0", display: "flex", flexDirection: "column", gap: "8px" }}>
              <figcaption style={{ fontSize: "0.875rem", color: "#e5e7eb", fontWeight: 500 }}>
                <span style={{ display: "inline-block", width: "12px", height: "12px", borderRadius: "50%", background: color.display_hex, marginRight: "6px", verticalAlign: "middle" }}></span>
                {color.label || color.name} — optimum at <strong style={{ color: "#fff" }}>{curve.optimum}</strong> pumps (EV{" "}
                {curve.optimal_ev.toFixed(2)})
              </figcaption>
              <svg width={BOX.width} height={BOX.height} style={{ background: "rgba(0, 0, 0, 0.2)", border: "1px solid rgba(255, 255, 255, 0.1)", borderRadius: "8px" }}>
                <line
                  x1={g.optimumX}
                  y1={BOX.padding}
                  x2={g.optimumX}
                  y2={BOX.height - BOX.padding}
                  stroke="#9ca3af"
                  strokeDasharray="4 3"
                />
                <polyline points={g.ev} fill="none" stroke="#60a5fa" strokeWidth={2} />
                <polyline points={g.survival} fill="none" stroke="#4ade80" strokeWidth={1} />
                <polyline points={g.hazard} fill="none" stroke="#f87171" strokeWidth={1} />
              </svg>
            </figure>
          );
        })}
      </div>
      <p style={{ fontSize: "0.75rem", color: "#9ca3af", marginTop: "24px", borderTop: "1px solid rgba(255, 255, 255, 0.1)", paddingTop: "16px" }}>
        <span style={{ color: "#60a5fa", marginRight: "12px" }}>■ EV</span>
        <span style={{ color: "#4ade80", marginRight: "12px" }}>■ Survival</span>
        <span style={{ color: "#f87171", marginRight: "12px" }}>■ Hazard</span>
        <span>— dashed line marks the optimum</span>
      </p>
    </div>
  );
}
