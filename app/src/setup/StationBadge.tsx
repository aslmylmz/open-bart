import { useEffect, useState, type KeyboardEvent } from "react";

import { fetchStation, setStationId } from "../lib/api";

/** The persistent "Standalone Mode · Station: S1" badge in the study-setup
 * identity bar (DATA-SPEC §2.4) — the mode is stated affirmatively, never
 * inferred from an absence. The station label is a per-machine app setting
 * (§2.3), entered once at machine setup and re-displayed here each session;
 * the badge doubles as its entry point, since `check_id` blocks standalone
 * sessions until the label is set. A rejected label never replaces the
 * stored one — the sidecar's verdict is surfaced inline. */
export function StationBadge() {
  const [station, setStation] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [entry, setEntry] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchStation().then(
      (identity) => {
        if (cancelled) return;
        setStation(identity.station_id);
        setLoaded(true);
      },
      // A down sidecar surfaces through the form's own validation paths;
      // the badge just keeps its noncommittal "…" instead of a false "not set".
      () => {},
    );
    return () => {
      cancelled = true;
    };
  }, []);

  async function save() {
    try {
      const verdict = await setStationId(entry.trim());
      if (!verdict.ok) {
        setError(verdict.error ?? "Could not save the station ID.");
        return;
      }
      setStation(verdict.station_id);
      setLoaded(true);
      setEditing(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the station ID.");
    }
  }

  function stopEditing() {
    setEditing(false);
    setError(null);
  }

  function onEntryKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") void save();
    if (e.key === "Escape") stopEditing();
  }

  return (
    <span className={station || !loaded ? "setup-badge" : "setup-badge is-missing"}>
      Standalone Mode
      <span className="setup-badge-sep" aria-hidden>
        ·
      </span>
      {editing ? (
        <input
          className="setup-badge-input"
          autoFocus
          value={entry}
          placeholder="e.g. S1"
          aria-label="Station ID"
          onChange={(e) => {
            setEntry(e.target.value);
            setError(null);
          }}
          onKeyDown={onEntryKeyDown}
          onBlur={stopEditing}
        />
      ) : (
        <button
          type="button"
          className="setup-badge-station"
          title="Set this machine's station ID"
          onClick={() => {
            setEntry(station ?? "");
            setEditing(true);
          }}
        >
          Station: {station ?? (loaded ? "not set" : "…")}
        </button>
      )}
      {error && (
        <span role="alert" className="setup-badge-error">
          {error}
        </span>
      )}
    </span>
  );
}
