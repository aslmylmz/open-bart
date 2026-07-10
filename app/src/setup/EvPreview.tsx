import { useEffect, useState } from "react";

import { type CurvePreview, preview } from "../lib/api";
import type { TaskConfig } from "../lib/config";
import { curveGeometry, type PlotBox } from "./evGeometry";
import "./EvPreview.css";

/** Geometry space for the hand-rolled plots; panels render it via viewBox so
 * each SVG scales with its grid cell. */
const BOX: PlotBox = { width: 320, height: 160, padding: 24 };

/** How long the preview sits idle after an edit before /preview is re-fetched. */
const PREVIEW_DEBOUNCE_MS = 200;

/** Flicker guard (§2.6): the recomputing treatment only shows if the in-flight
 * request outlives this, so fast local responses never blink the panels. */
const RECOMPUTING_GUARD_MS = 300;

interface EvPreviewProps {
  config: TaskConfig;
}

/** One color's plot: EV stroked in the profile color over muted-neutral
 * survival/hazard and the dashed optimum marker. */
function EvPlot({ curve, hex, label }: { curve: CurvePreview; hex: string; label: string }) {
  const g = curveGeometry(curve, BOX);
  return (
    <svg
      className="ev-plot"
      viewBox={`0 0 ${BOX.width} ${BOX.height}`}
      role="img"
      aria-label={`${label} EV curve`}
    >
      <line
        className="ev-line-optimum"
        x1={g.optimumX}
        y1={BOX.padding}
        x2={g.optimumX}
        y2={BOX.height - BOX.padding}
      />
      <polyline className="ev-line-survival" points={g.survival} />
      <polyline className="ev-line-hazard" points={g.hazard} />
      <polyline className="ev-line-ev" points={g.ev} style={{ stroke: hex }} />
    </svg>
  );
}

/** Live EV-curve + optimum preview (SPEC §7.3, DESIGN-SPEC §2.6): a stat chip
 * (dot + label + mono `opt <n> · EV <x.xx>`) over each color's panel in a
 * responsive grid, one shared legend below. Debounced `/preview` fetch with a
 * stale-response guard (a superseded request can't overwrite a newer one);
 * rendering is hand-rolled SVG (no charting dependency) via the pure
 * `curveGeometry` transform. */
export function EvPreview({ config }: EvPreviewProps) {
  const [curves, setCurves] = useState<Record<string, CurvePreview> | null>(null);
  const [status, setStatus] = useState<"ready" | "recomputing" | "stale">("ready");

  useEffect(() => {
    let cancelled = false;
    let guard: ReturnType<typeof setTimeout> | undefined;
    const debounce = setTimeout(() => {
      // While stale, a slow refetch keeps saying "stale" — the errors are
      // still the story — rather than blinking over to "recomputing…".
      guard = setTimeout(
        () => setStatus((s) => (s === "stale" ? s : "recomputing")),
        RECOMPUTING_GUARD_MS,
      );
      preview(config).then(
        (res) => {
          if (cancelled) return;
          clearTimeout(guard);
          setCurves(res.curves);
          setStatus("ready");
        },
        () => {
          // /preview rejects when the config is invalid (sidecar 422): keep
          // the last-good curves and mark them stale, immediately.
          if (cancelled) return;
          clearTimeout(guard);
          setStatus("stale");
        },
      );
    }, PREVIEW_DEBOUNCE_MS);
    // Cancelling stops this request's timers and drops its response, but keeps
    // any showing recomputing treatment up: only a landed response clears it,
    // so continuous edits during slow recomputes dim steadily instead of
    // blinking per keystroke.
    return () => {
      cancelled = true;
      clearTimeout(debounce);
      clearTimeout(guard);
    };
  }, [config]);

  // Recomputing only dresses a last-good plot; before one exists the skeleton
  // panels' "computing…" is the waiting state. Stale shows regardless — if
  // even the first fetch failed, it says why the skeletons will never fill.
  const marker =
    status === "stale"
      ? { text: "stale — fix errors to update", stale: true }
      : status === "recomputing" && curves !== null
        ? { text: "recomputing…", stale: false }
        : null;

  return (
    <div className="ev-preview">
      {marker && (
        <p className={`ev-status${marker.stale ? " is-stale" : ""}`}>{marker.text}</p>
      )}
      <div className={`ev-grid${marker ? " is-dim" : ""}`}>
        {config.colors.map((color) => {
          const curve = curves?.[color.name];
          const label = color.label || color.name;
          return (
            <figure className="ev-panel" key={color.name}>
              <figcaption className="ev-chip">
                <span
                  className="ev-chip-dot"
                  style={{ background: color.display_hex }}
                  aria-hidden="true"
                />
                <span className="ev-chip-label">{label}</span>
                {curve && (
                  <span className="ev-chip-stat">
                    opt {curve.optimum} · EV {curve.optimal_ev.toFixed(2)}
                  </span>
                )}
              </figcaption>
              {curve ? (
                <EvPlot curve={curve} hex={color.display_hex} label={label} />
              ) : (
                <div className="ev-skeleton">computing…</div>
              )}
            </figure>
          );
        })}
      </div>
      <p className="ev-legend">
        <span className="ev-legend-item">
          <span className="ev-legend-swatch is-ev" aria-hidden="true" />
          EV (profile color)
        </span>
        <span className="ev-legend-item">
          <span className="ev-legend-swatch is-survival" aria-hidden="true" />
          Survival
        </span>
        <span className="ev-legend-item">
          <span className="ev-legend-swatch is-hazard" aria-hidden="true" />
          Hazard
        </span>
        <span className="ev-legend-item">
          <span className="ev-legend-swatch is-optimum" aria-hidden="true" />
          optimum
        </span>
      </p>
    </div>
  );
}
