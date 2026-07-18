import "./WorkspaceTabs.css";

/** The two researcher workspaces (DATA-SPEC §7.1): Study Setup (design a
 * study, run participants) and the Data Hub (assemble multi-station data).
 * They are peers — the Hub is a top-level workspace, never a mode launched
 * from inside a study. */
export type Workspace = "setup" | "hub";

interface WorkspaceTabsProps {
  active: Workspace;
  onSelect: (workspace: Workspace) => void;
}

const TABS: ReadonlyArray<{ id: Workspace; label: string }> = [
  { id: "setup", label: "Study Setup" },
  { id: "hub", label: "Data Hub" },
];

/** The segmented `Study Setup | Data Hub` control that lives in both
 * researcher surfaces' sticky identity bars (§7.1), so either workspace can
 * switch to the other. Rendered in Study Setup's and the Data Hub's own bar —
 * one component, so the pair can never drift between them. */
export function WorkspaceTabs({ active, onSelect }: WorkspaceTabsProps) {
  return (
    <div className="workspace-tabs" role="tablist" aria-label="Workspace">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={active === tab.id}
          className={active === tab.id ? "workspace-tab is-active" : "workspace-tab"}
          onClick={() => onSelect(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
