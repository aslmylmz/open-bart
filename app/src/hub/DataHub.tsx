import { ChevronRight, FolderInput, FolderOpen, RefreshCw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Icon } from "../components/Icon";
import { WorkspaceTabs, type Workspace } from "../components/WorkspaceTabs";
import { onFolderDrop, selectFolder } from "../lib/desktop";
import {
  ingestSources,
  rebuildHub,
  type HubFindingView,
  type HubGroup,
  type HubMode,
  type HubPlannedFile,
  type HubRebuildResult,
  type HubView,
} from "../lib/hub";
import "./DataHub.css";

interface DataHubProps {
  workspace: Workspace;
  onWorkspaceChange: (workspace: Workspace) => void;
}

/** The three severity groups, in the fixed order the band shows them — a 1:1
 * mirror of the ingestion report's own groups (I8): Held first (excluded until
 * resolved), then Attention (pooled but itemized), then Clean/informational. */
const GROUPS: ReadonlyArray<{ id: HubGroup; label: string; className: string }> = [
  { id: "held", label: "Held — excluded until resolved", className: "held" },
  { id: "attention", label: "Attention — proceeds, flagged", className: "attn" },
  { id: "info", label: "Clean / informational", className: "clean" },
];

const MODE_LABEL: Record<HubMode, string> = { classic: "Classic", advanced: "Advanced" };

/** The §6.3 override target: the mode that is *not* the study's configured one. */
function otherMode(mode: HubMode): HubMode {
  return mode === "advanced" ? "classic" : "advanced";
}

/** The last path segment, for naming the destination root in the file tree. */
function baseName(path: string): string {
  const parts = path.split(/[/\\]/).filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

/** Split a path so the row can truncate the *head* and always keep the tail
 * visible. A source list is read tail-first — two folders under one long
 * parent are told apart by their last segments, so eliding the end (the plain
 * CSS default) would render them identical. */
export function splitPathForDisplay(path: string): { head: string; tail: string } {
  const sep = path.includes("\\") ? "\\" : "/";
  const parts = path.split(sep);
  if (parts.length <= 2) return { head: "", tail: path };
  return {
    head: parts.slice(0, -2).join(sep),
    tail: sep + parts.slice(-2).join(sep),
  };
}

/** One line of the Output band's file-tree preview. */
export interface TreeRow {
  key: string;
  /** 1 = directly under the destination root, 2 = inside a partition dir. */
  depth: number;
  label: string;
  reconstructed: boolean;
  isDir: boolean;
}

/** Group the writer's flat relative paths into a nested tree: each
 * `partition-N/` directory becomes its own line and its files are indented
 * beneath it as bare filenames. Keeps the writer's order (the preview is the
 * write order) while dropping the repeated directory prefix that would
 * otherwise push every real filename off the right edge. */
export function fileTreeRows(files: HubPlannedFile[]): TreeRow[] {
  const rows: TreeRow[] = [];
  let currentDir: string | null = null;
  for (const file of files) {
    const slash = file.path.indexOf("/");
    const dir = slash === -1 ? null : file.path.slice(0, slash);
    const name = slash === -1 ? file.path : file.path.slice(slash + 1);
    if (dir !== currentDir) {
      if (dir !== null) {
        rows.push({
          key: `dir:${dir}`,
          depth: 1,
          label: `${dir}/`,
          reconstructed: false,
          isDir: true,
        });
      }
      currentDir = dir;
    }
    rows.push({
      key: file.path,
      depth: dir === null ? 1 : 2,
      label: name,
      reconstructed: file.reconstructed,
      isDir: false,
    });
  }
  return rows;
}

/** The Data Hub tab (DATA-SPEC §7.1–7.4), Variant B "single console": the
 * researcher assembles read-only station folders, watches a live, non-gating
 * ingestion report, and writes the reconstructed study-wide surfaces with one
 * accent action. The component holds no Hub logic — every count, finding, and
 * file name comes back from the sidecar's shared core (I8–I10) via
 * `ingestSources` / `rebuildHub`, exactly what the CLI (I11) drives. */
export function DataHub({ workspace, onWorkspaceChange }: DataHubProps) {
  const [sources, setSources] = useState<string[]>([]);
  const [view, setView] = useState<HubView | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);

  // The mode override (§7.4): null = the study's configured mode (the default
  // the toggle starts on); a concrete mode is the explicit override.
  const [modeOverride, setModeOverride] = useState<HubMode | null>(null);
  const [destination, setDestination] = useState<string | null>(null);

  // The Rebuild control's last outcome and in-flight flag. A `needs_force`
  // result arms the confirm-replace step (§7.4); any input change clears it so
  // a stale confirm can never fire against a different rebuild.
  const [rebuildResult, setRebuildResult] = useState<HubRebuildResult | null>(null);
  const [rebuildError, setRebuildError] = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState(false);

  // Monotonic ticket for /hub/ingest responses: only the newest scan may set
  // state, so adding folders quickly can't let a slow response overwrite a
  // fresher one (mirrors StudySetup's validate sequencing).
  const scanSeq = useRef(0);

  function addSources(paths: string[]) {
    setSources((prev) => [...prev, ...paths.filter((p) => !prev.includes(p))]);
  }

  async function handleAddSource() {
    const picked = await selectFolder();
    if (picked) addSources([picked]);
  }

  function removeSource(folder: string) {
    setSources((prev) => prev.filter((s) => s !== folder));
  }

  async function handleChooseDestination() {
    const picked = await selectFolder();
    if (picked) {
      setDestination(picked);
      // A new destination invalidates any pending confirm/outcome from the old
      // one — a prior-rebuild confirmation must never carry over to a fresh
      // folder.
      setRebuildResult(null);
      setRebuildError(null);
    }
  }

  // Native folder drops feed the same source list as the picker (§7.2).
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    let cancelled = false;
    void onFolderDrop((paths) => addSources(paths)).then((fn) => {
      if (cancelled) fn();
      else unlisten = fn;
    });
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, []);

  // The live ingestion report (§7.3): re-scan whenever the sources or the mode
  // override change. No sources → no report. A transport failure surfaces as a
  // scan error rather than a stale report.
  useEffect(() => {
    setRebuildResult(null);
    setRebuildError(null);
    if (sources.length === 0) {
      setView(null);
      setScanError(null);
      setScanning(false);
      return;
    }
    const seq = ++scanSeq.current;
    setScanning(true);
    ingestSources(sources, modeOverride ?? undefined).then(
      (result) => {
        if (scanSeq.current !== seq) return;
        setView(result);
        setScanError(null);
        setScanning(false);
      },
      (err: unknown) => {
        if (scanSeq.current !== seq) return;
        setScanError(err instanceof Error ? err.message : "Could not scan the sources.");
        setScanning(false);
      },
    );
  }, [sources, modeOverride]);

  async function handleRebuild(force: boolean) {
    if (!destination) return;
    setRebuilding(true);
    setRebuildError(null);
    try {
      const result = await rebuildHub(sources, destination, modeOverride ?? undefined, force);
      setRebuildResult(result);
    } catch (err) {
      setRebuildError(err instanceof Error ? err.message : "The rebuild failed.");
    } finally {
      setRebuilding(false);
    }
  }

  const ready = view?.ok ?? false;
  const canRebuild = ready && (view?.will_rebuild ?? 0) > 0 && destination != null;
  const awaitingConfirm = rebuildResult?.status === "needs_force";
  const crumbStudy = crumbLabel(sources, view, scanning);

  return (
    <div className="hub-page">
      <div className="hub-sticky">
        <header className="hub-bar">
          <div className="hub-bar-inner">
            <h1 className="hub-crumb">
              <span className="hub-crumb-root">Data Hub</span>
              <span className="hub-crumb-sep" aria-hidden>
                /
              </span>
              <span className="hub-crumb-study">{crumbStudy}</span>
            </h1>
            <div className="hub-bar-actions">
              <WorkspaceTabs active={workspace} onSelect={onWorkspaceChange} />
            </div>
          </div>
        </header>
      </div>

      <section className="hub-band">
        <div className="hub-band-inner">
          <div className="hub-rail">
            <h2 className="hub-rail-title">Sources</h2>
            <p className="hub-rail-desc">
              Read-only folders you assembled — USB, share, sync. The Hub never writes into a
              source.
            </p>
          </div>
          <div className="hub-content">
            <button type="button" className="hub-drop" onClick={handleAddSource}>
              <Icon icon={FolderInput} size={20} />
              <span>
                <b>Drop station folders here</b> or click to choose a folder…
              </span>
            </button>
            {sources.length > 0 && (
              <ul className="hub-src-list">
                {sources.map((folder) => (
                  <li key={folder} className="hub-src">
                    <span className="hub-src-path" title={folder}>
                      <span className="hub-src-path-head">
                        {splitPathForDisplay(folder).head}
                      </span>
                      <span className="hub-src-path-tail">
                        {splitPathForDisplay(folder).tail}
                      </span>
                    </span>
                    <span className="hub-src-meta">{sourceMeta(view, folder)}</span>
                    <button
                      type="button"
                      className="hub-src-remove"
                      aria-label={`Remove ${folder}`}
                      onClick={() => removeSource(folder)}
                    >
                      <Icon icon={X} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      <section className="hub-band">
        <div className="hub-band-inner">
          <div className="hub-rail">
            <h2 className="hub-rail-title">Ingestion report</h2>
            <p className="hub-rail-desc">
              The Hub never acts silently. Every session is included cleanly or itemized here —
              this report never blocks a rebuild.
            </p>
          </div>
          <div className="hub-content">
            {renderReport({ sources, view, scanning, scanError })}
          </div>
        </div>
      </section>

      {ready && view && (
        <section className="hub-band">
          <div className="hub-band-inner">
            <div className="hub-rail">
              <h2 className="hub-rail-title">Output</h2>
              <p className="hub-rail-desc">
                A fresh folder, separate from every source. Filenames mirror live output exactly;
                a re-run replaces only a prior rebuild.
              </p>
            </div>
            <div className="hub-content">
              <div className="hub-out-grid">
                <div className="hub-out-row">
                  <span className="hub-out-label">Destination</span>
                  <span className="hub-out-value">
                    {destination ? (
                      <code className="hub-mono">{destination}</code>
                    ) : (
                      <span className="hub-muted">Choose a fresh folder, separate from every source.</span>
                    )}
                    <button type="button" className="hub-btn-sm" onClick={handleChooseDestination}>
                      <Icon icon={FolderOpen} />
                      {destination ? "Change…" : "Choose…"}
                    </button>
                  </span>
                </div>

                <div className="hub-out-row">
                  <span className="hub-out-label">Metrics mode</span>
                  <span className="hub-out-value hub-radio">
                    <label className={modeOverride == null ? "is-selected" : undefined}>
                      <input
                        type="radio"
                        name="hub-mode"
                        checked={modeOverride == null}
                        onChange={() => setModeOverride(null)}
                      />
                      Study&rsquo;s mode <span className="hub-muted">({MODE_LABEL[view.configured_mode]})</span>
                    </label>
                    <label className={modeOverride != null ? "is-selected" : undefined}>
                      <input
                        type="radio"
                        name="hub-mode"
                        checked={modeOverride != null}
                        onChange={() => setModeOverride(otherMode(view.configured_mode))}
                      />
                      Override &rarr; {MODE_LABEL[otherMode(view.configured_mode)]}
                    </label>
                  </span>
                </div>

                <div className="hub-out-row">
                  <span className="hub-out-label">Will write</span>
                  <span className="hub-out-value">
                    <div className="hub-filetree">
                      <div className="hub-filetree-root">
                        {destination ? `${baseName(destination)}/` : `${view.slug}/`}
                      </div>
                      {fileTreeRows(view.files).map((row) => (
                        <div
                          key={row.key}
                          className={
                            row.isDir
                              ? "hub-filetree-line is-dir"
                              : "hub-filetree-line"
                          }
                          style={{ paddingLeft: `calc(var(--space-16) * ${row.depth})` }}
                        >
                          {row.label}
                          {row.reconstructed && (
                            <span className="hub-filetree-mark"> reconstructed:true</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </span>
                </div>
              </div>

              <div className="hub-rebuild">
                <button
                  type="button"
                  className="hub-btn-primary"
                  disabled={!canRebuild || rebuilding}
                  onClick={() => handleRebuild(awaitingConfirm)}
                >
                  <Icon icon={RefreshCw} />
                  {awaitingConfirm
                    ? "Confirm replace"
                    : `Rebuild ${view.will_rebuild} session${view.will_rebuild === 1 ? "" : "s"}`}
                </button>
                {renderRebuildStatus({ rebuildResult, rebuildError })}
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

/** The breadcrumb's second segment: the identified study, or the state on the
 * way to one. */
function crumbLabel(sources: string[], view: HubView | null, scanning: boolean): string {
  if (sources.length === 0) return "No sources";
  if (scanning && !view) return "Scanning…";
  if (view && !view.ok) return "No study found";
  return view?.title ?? "Scanning…";
}

/** A Sources-row's right-aligned count, once the scan has attributed it. */
function sourceMeta(view: HubView | null, folder: string): string {
  const row = view?.sources.find((s) => s.folder === folder);
  if (!row) return "";
  const stations = `${row.stations} station${row.stations === 1 ? "" : "s"}`;
  const sessions = `${row.sessions} session${row.sessions === 1 ? "" : "s"}`;
  return `${stations} · ${sessions}`;
}

interface ReportState {
  sources: string[];
  view: HubView | null;
  scanning: boolean;
  scanError: string | null;
}

/** The Ingestion-report band body: the empty prompt, a scan error, the
 * no-study abort, or the headline stat row over the three severity groups. */
function renderReport({ sources, view, scanning, scanError }: ReportState) {
  if (sources.length === 0) {
    return <p className="hub-empty">Add source folders to see the ingestion report.</p>;
  }
  if (scanError) {
    return (
      <p className="hub-note is-held" role="alert">
        {scanError}
      </p>
    );
  }
  if (view && !view.ok) {
    return (
      <p className="hub-note is-held" role="alert">
        {view.error ?? "No study identifiable in the chosen sources."}
      </p>
    );
  }
  if (!view) {
    return <p className="hub-empty">Scanning…</p>;
  }
  return (
    <>
      {scanning && <p className="hub-scanning">Re-scanning…</p>}
      <div className="hub-stats">
        <Stat n={view.will_rebuild} label="will rebuild" tone="ok" />
        <Stat n={view.held} label="held" tone={view.held ? "err" : undefined} />
        <Stat n={view.attention} label="flagged" tone={view.attention ? "warn" : undefined} />
        <Stat n={view.partitions} label="partitions" />
      </div>
      <div className="hub-accordion">
        {GROUPS.map((group) => {
          const findings = view.findings.filter((f) => f.group === group.id);
          return (
            <details
              key={group.id}
              className={`hub-acc ${group.className}`}
              open={group.id === "held" && findings.length > 0}
            >
              <summary>
                <span className="hub-acc-dot" aria-hidden />
                <span className="hub-acc-label">{group.label}</span>
                <span className="hub-acc-count">{groupCount(group.id, findings, view.will_rebuild)}</span>
                <Icon icon={ChevronRight} />
              </summary>
              <div className="hub-acc-body">
                {findings.length > 0 ? (
                  findings.map((finding, i) => <FindingRow key={i} finding={finding} />)
                ) : group.id === "info" ? (
                  // The Clean group leads with the rebuildable count, not a bare
                  // "None." — a clean dataset has nothing itemized but is exactly
                  // what this group reports (§7.3).
                  <p className="hub-empty">
                    {sessionCount(view.will_rebuild)} ingested cleanly from ground truth.
                  </p>
                ) : (
                  <p className="hub-empty">None.</p>
                )}
              </div>
            </details>
          );
        })}
      </div>
    </>
  );
}

/** "N session(s)", the shared plural for the counts the report shows. */
function sessionCount(n: number): string {
  return `${n} session${n === 1 ? "" : "s"}`;
}

/** A group summary's count: sessions held for Held, the ingested (rebuildable)
 * count for Clean (§7.3's "sessions ingested cleanly"), issue count otherwise. */
function groupCount(group: HubGroup, findings: HubFindingView[], willRebuild: number): string {
  if (group === "info") {
    const ingested = `${sessionCount(willRebuild)} ingested`;
    if (findings.length === 0) return ingested;
    return `${ingested} · ${findings.length} note${findings.length === 1 ? "" : "s"}`;
  }
  if (findings.length === 0) return "none";
  const issues = `${findings.length} issue${findings.length === 1 ? "" : "s"}`;
  if (group === "held") {
    const sessions = findings.reduce((sum, f) => sum + f.sessions, 0);
    return `${issues} · ${sessionCount(sessions)}`;
  }
  return issues;
}

function FindingRow({ finding }: { finding: HubFindingView }) {
  return (
    <div className={finding.loud ? "hub-find is-loud" : "hub-find"}>
      <span className="hub-find-stripe" aria-hidden />
      <div className="hub-find-body">
        <p className="hub-find-message">
          {finding.loud && <span className="hub-find-loud">⚠ </span>}
          {finding.message}
        </p>
        <code className="hub-find-code">{finding.code}</code>
      </div>
    </div>
  );
}

function Stat({ n, label, tone }: { n: number; label: string; tone?: "ok" | "err" | "warn" }) {
  return (
    <div className={tone ? `hub-stat is-${tone}` : "hub-stat"}>
      <div className="hub-stat-n">{n}</div>
      <div className="hub-stat-l">{label}</div>
    </div>
  );
}

interface RebuildStatusState {
  rebuildResult: HubRebuildResult | null;
  rebuildError: string | null;
}

/** The Rebuild control's feedback line: a transport error, or the sidecar's
 * own outcome — written / needs-confirm / refused / no-study. */
function renderRebuildStatus({ rebuildResult, rebuildError }: RebuildStatusState) {
  if (rebuildError) {
    return (
      <p className="hub-rebuild-status is-error" role="alert">
        {rebuildError}
      </p>
    );
  }
  if (!rebuildResult) return null;
  if (rebuildResult.status === "written") {
    const replaced = rebuildResult.replaced_prior_rebuild ? " (replaced a prior rebuild)" : "";
    return (
      <p className="hub-rebuild-status is-success" role="status">
        Wrote {rebuildResult.files.length} file(s) to {rebuildResult.destination}
        {replaced}.
      </p>
    );
  }
  if (rebuildResult.status === "needs_force") {
    return (
      <p className="hub-rebuild-status is-warn" role="status">
        {rebuildResult.message}
      </p>
    );
  }
  return (
    <p className="hub-rebuild-status is-error" role="alert">
      {rebuildResult.message}
    </p>
  );
}
