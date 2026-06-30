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

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 16 }}>
      <h2>EV preview</h2>
      {error && <p style={{ color: "#b45309" }}>Preview not updated: {error}</p>}
      {config.colors.map((color) => {
        const curve = curves?.[color.name];
        if (!curve) {
          return <p key={color.name}>{color.label || color.name}: computing…</p>;
        }
        const g = curveGeometry(curve, BOX);
        return (
          <figure key={color.name} style={{ margin: "8px 0" }}>
            <figcaption>
              {color.label || color.name} — optimum at <strong>{curve.optimum}</strong> pumps (EV{" "}
              {curve.optimal_ev.toFixed(2)})
            </figcaption>
            <svg width={BOX.width} height={BOX.height} style={{ border: "1px solid #ddd" }}>
              <line
                x1={g.optimumX}
                y1={BOX.padding}
                x2={g.optimumX}
                y2={BOX.height - BOX.padding}
                stroke="#999"
                strokeDasharray="4 3"
              />
              <polyline points={g.ev} fill="none" stroke="#2563eb" strokeWidth={2} />
              <polyline points={g.survival} fill="none" stroke="#16a34a" strokeWidth={1} />
              <polyline points={g.hazard} fill="none" stroke="#dc2626" strokeWidth={1} />
            </svg>
          </figure>
        );
      })}
      <p style={{ fontSize: 12, color: "#666" }}>
        <span style={{ color: "#2563eb" }}>■ EV</span>{" "}
        <span style={{ color: "#16a34a" }}>■ survival</span>{" "}
        <span style={{ color: "#dc2626" }}>■ hazard</span> — dashed line marks the optimum
      </p>
    </div>
  );
}
