import { type ReactNode, useEffect, useState } from "react";

import { fetchHealth } from "./lib/api";

interface VersionGuardProps {
  appVersion: string;
  children: ReactNode;
}

/** Boot-time handshake between the app and its bundled scoring sidecar.
 *
 * A stale bundle (a sidecar frozen before a schema or nomenclature change)
 * boots fine and then rejects every request with per-field validation errors —
 * a confusing failure a researcher cannot interpret. Confirmed version
 * mismatches hard-block with an explanation instead. An unreachable sidecar
 * does NOT block here: connection errors are handled downstream with retry
 * (RunFlow), and dev setups may point at a not-yet-started sidecar. */
export function VersionGuard({ appVersion, children }: VersionGuardProps) {
  const [sidecarVersion, setSidecarVersion] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((health) => {
        if (!cancelled) setSidecarVersion(health.version);
      })
      .catch(() => {
        /* unreachable sidecar: leave the guard open */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (sidecarVersion !== null && sidecarVersion !== appVersion) {
    return (
      <div style={{ maxWidth: 560, margin: "15vh auto 0", padding: "0 24px", textAlign: "center" }}>
        <h1 style={{ fontSize: "1.5rem" }}>Scoring engine version mismatch</h1>
        <p>
          The bundled scoring engine reports version <strong>{sidecarVersion}</strong>, but this
          app is version <strong>{appVersion}</strong>. Studies cannot be configured or scored
          reliably against a mismatched engine, so this session is blocked.
        </p>
        <p style={{ color: "#9ca3af", fontSize: "0.875rem" }}>
          Reinstall the app from a matching release. If you are building locally, re-freeze the
          sidecar (<code>pyinstaller app/sidecar/sidecar.spec</code>) and copy it into{" "}
          <code>app/src-tauri/binaries/</code> before <code>tauri build</code>.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
