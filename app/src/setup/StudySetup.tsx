import { FolderOpen, Plus, X } from "lucide-react";
import { useEffect, useRef, useState, type FocusEvent } from "react";

import { Icon } from "../components/Icon";
import { WorkspaceTabs, type Workspace } from "../components/WorkspaceTabs";
import { validateConfig, type ValidateResult } from "../lib/api";
import { HAZARD_FAMILIES, type HazardFamily, type Language, type TaskConfig } from "../lib/config";
import { loadStudy, saveStudy, selectOutputDir, type LoadedStudyFile } from "../lib/desktop";
import { isMacPlatform, matchesShortcut, shortcutChip } from "../lib/platform";
import { EvPreview } from "./EvPreview";
import { FAMILY_PARAMS } from "./familyParams";
import { StationBadge } from "./StationBadge";
import { seedNotice } from "./standaloneNotices";
import {
  addColor,
  DEFAULT_QC,
  fileIdentityLine,
  isStudyDirty,
  type StudySnapshot,
  parseConditionList,
  parseExitPasscode,
  parseNumberList,
  parseStudy,
  removeColor,
  saveBlockedHeadline,
  setColorField,
  setColorHazardFamily,
  setHazardParam,
  setPayoutEnabled,
  setPayoutField,
  setQcField,
  setStudyField,
} from "./studyForm";
import {
  knownFieldPaths,
  mapErrorsToFields,
  retargetTouchedAfterColorRemoval,
  visibleFieldErrors,
} from "./validation";
import "./StudySetup.css";

/** How long the armed "Confirm remove" state holds before quietly reverting. */
const REMOVE_CONFIRM_MS = 3000;

/** How long a transient save/load message holds line 2 of the identity bar
 * before it reverts to the file identity (DESIGN-SPEC §2.1 "~4s"). */
const FEEDBACK_MS = 4000;

/** How long the form sits idle after an edit before the sidecar re-validates
 * (DESIGN-SPEC §2.5 "~400ms"). */
const VALIDATE_DEBOUNCE_MS = 400;

/** §2.2's load-rejected headline — the current study is never replaced by a
 * file that fails parsing or sidecar validation. */
const LOAD_REJECTED_HEADLINE = "Loaded file is invalid — keeping the current study.";

/** A transient line-2 message; tone only picks the text color. */
interface Feedback {
  text: string;
  tone: "neutral" | "success" | "error";
}

/** The under-bar error strip's content (§2.2): a save-blocked or load-rejected
 * headline plus the sidecar's full-pass reasons. */
interface ErrorStrip {
  headline: string;
  errors: string[];
}

interface StudySetupProps {
  config: TaskConfig;
  onChange: (config: TaskConfig) => void;
  /** The last saved/loaded study file — App-owned so it survives run trips. */
  snapshot: StudySnapshot;
  onSnapshotChange: (snapshot: StudySnapshot) => void;
  onTestRun: () => void;
  onStartRun: () => void;
  /** The active researcher workspace and the switch to its peer (§7.1). Both
   * default so the unit harness can mount Study Setup on its own; the App
   * shell wires them to the real Study Setup / Data Hub tab pair. */
  workspace?: Workspace;
  onWorkspaceChange?: (workspace: Workspace) => void;
}

/** "<prefix>: <reason>" when the error carries a message, "<prefix>." when not. */
function describeError(prefix: string, err: unknown): string {
  return err instanceof Error && err.message ? `${prefix}: ${err.message}` : `${prefix}.`;
}

/** The Researcher View: the sticky identity bar (breadcrumb, unsaved dot,
 * Save/Load with ⌘S/⌘O, file-identity/feedback line — DESIGN-SPEC §2.1) over
 * a single column of section bands — Study Info, Data Quality & Payout, Color
 * Profiles, EV Preview, Run (§2.3) — as a thin shell over the pure form-model
 * helpers in studyForm.ts, with the sidecar's /validate-config as the
 * validation authority. Save/load go through the native dialogs in desktop.ts;
 * the run callbacks belong to the App shell, which owns the mode. */
export function StudySetup({
  config,
  onChange,
  snapshot,
  onSnapshotChange,
  onTestRun,
  onStartRun,
  workspace = "setup",
  onWorkspaceChange,
}: StudySetupProps) {
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [strip, setStrip] = useState<ErrorStrip | null>(null);
  // Two-step remove (§2.4): the index of the profile whose Remove is armed.
  // One shared slot — arming a card disarms any other — so a stray confirm
  // can never remove a card the researcher is no longer looking at.
  const [armedRemove, setArmedRemove] = useState<number | null>(null);
  const disarmTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const feedbackTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // The inline validation layer (§2.5): the sidecar's latest verdict, which
  // fields have been blurred at least once, and whether a save was attempted
  // (which reveals errors everywhere). Presentation state only — it resets
  // with the component; the sidecar remains the sole validation authority.
  const [validation, setValidation] = useState<ValidateResult>({ ok: true, errors: [] });
  const [touched, setTouched] = useState<ReadonlySet<string>>(new Set());
  const [saveAttempted, setSaveAttempted] = useState(false);
  // Monotonic ticket for /validate-config responses: only the newest request
  // may set state, so a slow stale response can't overwrite a fresher verdict.
  const validateSeq = useRef(0);

  const macLike = isMacPlatform(navigator.platform);

  // Debounced live validation (§2.5): ~400ms after the last edit, ask the
  // sidecar for a fresh verdict. A transport failure quietly keeps the last
  // verdict — surfacing sidecar outages is the save/load handlers' job.
  useEffect(() => {
    const seq = ++validateSeq.current;
    const timer = setTimeout(() => {
      validateConfig(config).then(
        (verdict) => {
          if (validateSeq.current === seq) setValidation(verdict);
        },
        () => {},
      );
    }, VALIDATE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [config]);

  const fieldErrors = visibleFieldErrors(
    mapErrorsToFields(validation.errors, knownFieldPaths(config)),
    touched,
    saveAttempted,
  );

  /** Record a field's first blur — from then on its errors render live. */
  function touch(field: string) {
    setTouched((prev) => (prev.has(field) ? prev : new Set(prev).add(field)));
  }

  /** The blur + error-flag props every validated control carries. Controls
   * that commit their value on blur pass the commit here, so the commit and
   * the touch land on the same blur. */
  function fieldProps(field: string, commit?: (value: string) => void): FieldWiring {
    return {
      "aria-invalid": fieldErrors[field] ? true : undefined,
      onBlur: (e) => {
        touch(field);
        commit?.(e.target.value);
      },
    };
  }

  useEffect(
    () => () => {
      clearTimeout(disarmTimer.current);
      clearTimeout(feedbackTimer.current);
    },
    [],
  );

  // Real ⌘S/⌘O (§2.7). The listener lives here rather than in App because the
  // App shell mounts StudySetup only in setup mode — unmounting is what turns
  // the shortcuts off during a run. Re-registered every render so the handlers
  // never close over a stale config.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (matchesShortcut(e, "s", macLike)) {
        e.preventDefault();
        void handleSave();
      } else if (matchesShortcut(e, "o", macLike)) {
        e.preventDefault();
        void handleLoad();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  function handleRemoveClick(i: number) {
    clearTimeout(disarmTimer.current);
    if (armedRemove === i) {
      setArmedRemove(null);
      // Keep blur history with its profile: later colors' touched paths shift
      // down with their cards instead of pointing at whoever inherits the index.
      setTouched((prev) => retargetTouchedAfterColorRemoval(prev, i));
      onChange(removeColor(config, i));
      return;
    }
    setArmedRemove(i);
    disarmTimer.current = setTimeout(() => setArmedRemove(null), REMOVE_CONFIRM_MS);
  }

  /** Hold a transient message in line 2's feedback slot, then revert to the
   * file identity (§2.1). */
  function showFeedback(text: string, tone: Feedback["tone"] = "neutral") {
    clearTimeout(feedbackTimer.current);
    setFeedback({ text, tone });
    feedbackTimer.current = setTimeout(() => setFeedback(null), FEEDBACK_MS);
  }

  /** Drop any transient message so line 2 shows the file identity again. */
  function clearFeedback() {
    clearTimeout(feedbackTimer.current);
    setFeedback(null);
  }

  async function handleSave() {
    // A save attempt reveals inline errors at every field, blurred or not (§2.5).
    setSaveAttempted(true);
    let verdict: Awaited<ReturnType<typeof validateConfig>>;
    try {
      verdict = await validateConfig(config);
    } catch (err) {
      showFeedback(describeError("Save failed", err), "error");
      return;
    }
    // The save-time pass is the freshest verdict — feed the inline layer and
    // outrank any in-flight debounced response.
    validateSeq.current += 1;
    setValidation(verdict);
    if (!verdict.ok) {
      setStrip({ headline: saveBlockedHeadline(verdict.errors.length), errors: verdict.errors });
      return;
    }
    try {
      const path = await saveStudy(JSON.stringify(config, null, 2));
      if (!path) {
        showFeedback("Save cancelled.");
        return;
      }
      setStrip(null);
      onSnapshotChange({ path, config });
      // The saved study is clean — future edits start un-nagged again, so
      // §2.5's "first typing is never nagged" outlives the save that
      // revealed everything.
      setSaveAttempted(false);
      showFeedback(`Saved to ${path}`, "success");
    } catch (err) {
      showFeedback(describeError("Save failed", err), "error");
    }
  }

  async function handleLoad() {
    let picked: LoadedStudyFile | null;
    try {
      picked = await loadStudy();
    } catch (err) {
      showFeedback(describeError("Could not load", err), "error");
      return;
    }
    if (!picked) {
      showFeedback("Load cancelled.");
      return;
    }
    let loaded: TaskConfig;
    try {
      loaded = parseStudy(picked.text);
    } catch (err) {
      setStrip({
        headline: LOAD_REJECTED_HEADLINE,
        errors: [err instanceof Error ? err.message : "The file is not valid JSON."],
      });
      return;
    }
    let verdict: Awaited<ReturnType<typeof validateConfig>>;
    try {
      verdict = await validateConfig(loaded);
    } catch (err) {
      showFeedback(describeError("Could not load", err), "error");
      return;
    }
    if (!verdict.ok) {
      setStrip({ headline: LOAD_REJECTED_HEADLINE, errors: verdict.errors });
      return;
    }
    setStrip(null);
    clearFeedback();
    // The loaded study just validated ok; restart the touched-then-live layer
    // so the fresh study begins un-nagged (§2.5).
    validateSeq.current += 1;
    setValidation({ ok: true, errors: [] });
    setTouched(new Set());
    setSaveAttempted(false);
    onChange(loaded);
    onSnapshotChange({ path: picked.path, config: loaded });
  }

  async function handleSelectOutputDir() {
    try {
      const dir = await selectOutputDir();
      if (dir) {
        onChange(setStudyField(config, { output_dir: dir }));
      }
    } catch (err) {
      showFeedback(describeError("Could not select dir", err), "error");
    }
  }

  return (
    <div className="setup-page">
      <div className="setup-sticky">
        <header className="setup-bar">
          <div className="setup-bar-inner">
            <div className="setup-bar-top">
              <h1 className="setup-crumb">
                <span className="setup-crumb-root">Study Setup</span>
                <span className="setup-crumb-sep" aria-hidden>
                  /
                </span>
                <span className="setup-crumb-study">{config.title}</span>
                {isStudyDirty(config, snapshot.config) && (
                  <span
                    className="setup-dirty-dot"
                    role="img"
                    aria-label="Unsaved changes"
                    title="Unsaved changes"
                  />
                )}
              </h1>
              {/* Standalone Mode badge (DATA-SPEC §2.4): persistent while the
                  loaded study declares the mode — never inferred elsewhere. */}
              {config.standalone && <StationBadge />}
              <div className="setup-bar-actions">
                {onWorkspaceChange && (
                  <WorkspaceTabs active={workspace} onSelect={onWorkspaceChange} />
                )}
                <button type="button" className="setup-btn-ghost" onClick={handleLoad}>
                  Load
                  <kbd className="setup-kbd">{shortcutChip("O", macLike)}</kbd>
                </button>
                <button type="button" className="setup-btn-primary" onClick={handleSave}>
                  Save
                  <kbd className="setup-kbd">{shortcutChip("S", macLike)}</kbd>
                </button>
              </div>
            </div>
            <p className={feedback ? `setup-file-line is-${feedback.tone}` : "setup-file-line"}>
              {feedback ? feedback.text : fileIdentityLine(snapshot.path)}
            </p>
          </div>
        </header>
        {strip && (
          <div className="setup-strip" role="alert">
            <div className="setup-strip-inner">
              <div className="setup-strip-body">
                <p className="setup-strip-headline">{strip.headline}</p>
                <ul className="setup-strip-list">
                  {strip.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
              <button
                type="button"
                className="setup-strip-dismiss"
                aria-label="Dismiss errors"
                onClick={() => setStrip(null)}
              >
                <Icon icon={X} />
              </button>
            </div>
          </div>
        )}
      </div>

      <section className="setup-band">
        <div className="setup-band-inner">
          <div className="setup-rail">
            <h2 className="setup-rail-title">Study info</h2>
            <p className="setup-rail-desc">
              Identity, language, and reward structure. The title appears in the saved study file
              and the session data.
            </p>
          </div>
          <div className="setup-rows">
            <label className="setup-row">
              <span className="setup-row-label">Title</span>
              <input
                value={config.title}
                {...fieldProps("title")}
                onChange={(e) => onChange(setStudyField(config, { title: e.target.value }))}
              />
              <FieldError errors={fieldErrors["title"]} />
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Language</span>
              <select
                value={config.language}
                {...fieldProps("language")}
                onChange={(e) => onChange(setStudyField(config, { language: e.target.value as Language }))}
              >
                <option value="en">English</option>
                <option value="tr">Türkçe</option>
              </select>
              <FieldError errors={fieldErrors["language"]} />
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Reward per pump</span>
              <input
                type="number"
                step={0.01}
                min={0}
                value={config.reward_per_pump}
                {...fieldProps("reward_per_pump")}
                onChange={(e) =>
                  onChange(setStudyField(config, { reward_per_pump: Number(e.target.value) }))
                }
              />
              <FieldError errors={fieldErrors["reward_per_pump"]} />
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Seed</span>
              <input
                type="number"
                placeholder="Fresh randomness each run"
                value={config.seed ?? ""}
                {...fieldProps("seed")}
                onChange={(e) =>
                  onChange(
                    setStudyField(config, { seed: e.target.value === "" ? null : Number(e.target.value) }),
                  )
                }
              />
              <FieldError errors={fieldErrors["seed"]} />
              <SeedNotice standalone={Boolean(config.standalone)} seedSet={config.seed != null} />
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Conditions</span>
              {/* Committed on blur like the array hazard params, so typing commas
                  doesn't fight the parsed value. Empty = no conditions. */}
              <input
                key={(config.conditions ?? []).join(",")}
                defaultValue={(config.conditions ?? []).join(", ")}
                placeholder="Comma-separated — empty for none"
                {...fieldProps("conditions", (value) =>
                  onChange(setStudyField(config, { conditions: parseConditionList(value) })),
                )}
              />
              <FieldError errors={fieldErrors["conditions"]} />
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Exit passcode</span>
              {/* Committed on blur like conditions, so the trim never fights typing. */}
              <input
                key={config.exit_passcode ?? ""}
                defaultValue={config.exit_passcode ?? ""}
                placeholder="Empty for ungated exits"
                {...fieldProps("exit_passcode", (value) =>
                  onChange(setStudyField(config, { exit_passcode: parseExitPasscode(value) })),
                )}
              />
              <FieldError errors={fieldErrors["exit_passcode"]} />
            </label>
            <div className="setup-row">
              <label className="setup-row-label" htmlFor="setup-output-dir">
                Output directory
              </label>
              <div className="setup-inline-group">
                <input
                  id="setup-output-dir"
                  value={config.output_dir}
                  {...fieldProps("output_dir")}
                  onChange={(e) => onChange(setStudyField(config, { output_dir: e.target.value }))}
                />
                <button type="button" onClick={handleSelectOutputDir}>
                  <Icon icon={FolderOpen} />
                  Select folder…
                </button>
              </div>
              <FieldError errors={fieldErrors["output_dir"]} />
            </div>
          </div>
        </div>
      </section>

      <section className="setup-band">
        <div className="setup-band-inner">
          <div className="setup-rail">
            <h2 className="setup-rail-title">Data quality &amp; payout</h2>
            <p className="setup-rail-desc">
              QC thresholds only flag sessions — nothing is ever excluded. Payout off means
              participants see task earnings unchanged.
            </p>
          </div>
          <div className="setup-rows">
            <label className="setup-row">
              <span className="setup-row-label">Fast response (ms)</span>
              <input
                type="number"
                min={1}
                step={1}
                value={config.qc?.fast_response_ms ?? DEFAULT_QC.fast_response_ms}
                {...fieldProps("qc.fast_response_ms")}
                onChange={(e) => onChange(setQcField(config, { fast_response_ms: Number(e.target.value) }))}
              />
              <FieldError errors={fieldErrors["qc.fast_response_ms"]} />
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Zero-pump streak (trials)</span>
              <input
                type="number"
                min={1}
                step={1}
                value={config.qc?.zero_pump_streak ?? DEFAULT_QC.zero_pump_streak}
                {...fieldProps("qc.zero_pump_streak")}
                onChange={(e) => onChange(setQcField(config, { zero_pump_streak: Number(e.target.value) }))}
              />
              <FieldError errors={fieldErrors["qc.zero_pump_streak"]} />
            </label>
            <div className="setup-row">
              <span className="setup-row-label">Real payout</span>
              <label className="setup-check">
                <input
                  type="checkbox"
                  checked={config.payout != null}
                  onChange={(e) => onChange(setPayoutEnabled(config, e.target.checked))}
                />
                Convert task earnings to a real payout
              </label>
            </div>
            {config.payout != null && (
              <>
                <label className="setup-row">
                  <span className="setup-row-label">Payout rate (per earnings unit)</span>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={config.payout.rate}
                    {...fieldProps("payout.rate")}
                    onChange={(e) => onChange(setPayoutField(config, { rate: Number(e.target.value) }))}
                  />
                  <FieldError errors={fieldErrors["payout.rate"]} />
                </label>
                <label className="setup-row">
                  <span className="setup-row-label">Currency label</span>
                  <input
                    placeholder="₺, $, credits…"
                    value={config.payout.currency}
                    {...fieldProps("payout.currency")}
                    onChange={(e) => onChange(setPayoutField(config, { currency: e.target.value }))}
                  />
                  <FieldError errors={fieldErrors["payout.currency"]} />
                </label>
              </>
            )}
          </div>
        </div>
      </section>

      <section className="setup-band">
        <div className="setup-band-inner">
          <div className="setup-rail">
            <h2 className="setup-rail-title">Color profiles</h2>
            <p className="setup-rail-desc">
              Each balloon color carries its own hazard. Participants see colors, never parameters.
            </p>
          </div>
          <div className="setup-cards">
            {config.colors.map((color, i) => (
              <section key={i} className="setup-card">
                <div className="setup-card-head">
                  <span className="setup-card-id">
                    <span className="setup-card-dot" style={{ background: color.display_hex }} />
                    {color.label || color.name}
                  </span>
                  <span className="setup-card-meta">
                    <span className="setup-card-summary">
                      {color.hazard.family} · N {color.max_pumps} · {color.trials} trials
                    </span>
                    <button
                      type="button"
                      className={armedRemove === i ? "setup-remove is-armed" : "setup-remove"}
                      disabled={config.colors.length <= 1}
                      title={config.colors.length <= 1 ? "A study needs at least one color profile" : undefined}
                      onClick={() => handleRemoveClick(i)}
                    >
                      {armedRemove === i ? "Confirm remove" : "Remove"}
                    </button>
                  </span>
                </div>
                <div className="setup-card-grid">
                  <label className="setup-field">
                    Name
                    <input
                      value={color.name}
                      {...fieldProps(`colors.${i}.name`)}
                      onChange={(e) => onChange(setColorField(config, i, { name: e.target.value }))}
                    />
                    <FieldError errors={fieldErrors[`colors.${i}.name`]} />
                  </label>
                  <label className="setup-field">
                    Label
                    <input
                      value={color.label}
                      {...fieldProps(`colors.${i}.label`)}
                      onChange={(e) => onChange(setColorField(config, i, { label: e.target.value }))}
                    />
                    <FieldError errors={fieldErrors[`colors.${i}.label`]} />
                  </label>
                  <label className="setup-field">
                    Color
                    <input
                      type="color"
                      className="setup-swatch"
                      value={color.display_hex}
                      {...fieldProps(`colors.${i}.display_hex`)}
                      onChange={(e) => onChange(setColorField(config, i, { display_hex: e.target.value }))}
                    />
                    <FieldError errors={fieldErrors[`colors.${i}.display_hex`]} />
                  </label>
                  <label className="setup-field">
                    Max pumps (N)
                    <input
                      type="number"
                      min={1}
                      value={color.max_pumps}
                      {...fieldProps(`colors.${i}.max_pumps`)}
                      onChange={(e) =>
                        onChange(setColorField(config, i, { max_pumps: Number(e.target.value) }))
                      }
                    />
                    <FieldError errors={fieldErrors[`colors.${i}.max_pumps`]} />
                  </label>
                  <label className="setup-field">
                    Trials
                    <input
                      type="number"
                      min={1}
                      value={color.trials}
                      {...fieldProps(`colors.${i}.trials`)}
                      onChange={(e) => onChange(setColorField(config, i, { trials: Number(e.target.value) }))}
                    />
                    <FieldError errors={fieldErrors[`colors.${i}.trials`]} />
                  </label>
                  <label className="setup-field">
                    Hazard family
                    <select
                      value={color.hazard.family}
                      {...fieldProps(`colors.${i}.hazard.family`)}
                      onChange={(e) =>
                        onChange(setColorHazardFamily(config, i, e.target.value as HazardFamily))
                      }
                    >
                      {HAZARD_FAMILIES.map((family) => (
                        <option key={family} value={family}>
                          {family}
                        </option>
                      ))}
                    </select>
                    <FieldError errors={fieldErrors[`colors.${i}.hazard.family`]} />
                  </label>
                  {renderHazardParams(config, i, onChange, fieldErrors, fieldProps)}
                </div>
              </section>
            ))}
            <button type="button" className="setup-add-row" onClick={() => onChange(addColor(config))}>
              <Icon icon={Plus} />
              Add color profile
            </button>
          </div>
        </div>
      </section>

      <section className="setup-band">
        <div className="setup-band-inner">
          <div className="setup-rail">
            <h2 className="setup-rail-title">EV preview</h2>
            <p className="setup-rail-desc">
              Expected value, survival, and hazard per color profile, computed by the scoring
              engine. Updates live as parameters change; the dashed marker is the optimum.
            </p>
          </div>
          <div className="setup-ev-slot">
            <EvPreview config={config} />
          </div>
        </div>
      </section>

      <section className="setup-band">
        <div className="setup-band-inner">
          <div className="setup-rail">
            <h2 className="setup-rail-title">Run</h2>
            <p className="setup-rail-desc">
              A test run rehearses the participant flow without touching the dataset. Start run
              begins a real session.
            </p>
          </div>
          <div className="setup-run-actions">
            <button type="button" className="setup-btn-test" onClick={onTestRun}>
              Test run
            </button>
            <button type="button" className="setup-btn-primary" onClick={onStartRun}>
              Start run →
            </button>
          </div>
        </div>
      </section>

    </div>
  );
}

/** What `fieldProps` hands every validated control: the error flag for the
 * red border plus the blur handler (touch, then any value commit). */
type FieldWiring = {
  "aria-invalid": true | undefined;
  onBlur: (e: FocusEvent<HTMLInputElement | HTMLSelectElement>) => void;
};

/** Render the parameter inputs for one color's hazard: number inputs for scalar
 * families (driven by FAMILY_PARAMS) and comma-separated list inputs for the two
 * array families (committed on blur via parseNumberList). Each param carries its
 * inline validation wiring against the `colors.<i>.hazard.<param>` field path. */
function renderHazardParams(
  config: TaskConfig,
  i: number,
  onChange: (config: TaskConfig) => void,
  fieldErrors: Record<string, string[]>,
  fieldProps: (field: string, commit?: (value: string) => void) => FieldWiring,
) {
  const hazard = config.colors[i].hazard;
  const values = hazard as unknown as Record<string, number>;
  const base = `colors.${i}.hazard`;

  if (hazard.family === "step") {
    return (
      <>
        <label className="setup-field">
          Breakpoints
          <input
            key="bp"
            defaultValue={hazard.breakpoints.join(", ")}
            {...fieldProps(`${base}.breakpoints`, (value) =>
              onChange(
                setColorField(config, i, {
                  hazard: { ...hazard, breakpoints: parseNumberList(value) },
                }),
              ),
            )}
          />
          <FieldError errors={fieldErrors[`${base}.breakpoints`]} />
        </label>
        <label className="setup-field">
          Levels
          <input
            key="lv"
            defaultValue={hazard.levels.join(", ")}
            {...fieldProps(`${base}.levels`, (value) =>
              onChange(
                setColorField(config, i, {
                  hazard: { ...hazard, levels: parseNumberList(value) },
                }),
              ),
            )}
          />
          <FieldError errors={fieldErrors[`${base}.levels`]} />
        </label>
      </>
    );
  }

  if (hazard.family === "tabular") {
    return (
      <label className="setup-field setup-field-wide">
        Values (h per pump)
        <input
          key="vals"
          defaultValue={hazard.values.join(", ")}
          {...fieldProps(`${base}.values`, (value) =>
            onChange(
              setColorField(config, i, {
                hazard: { ...hazard, values: parseNumberList(value) },
              }),
            ),
          )}
        />
        <FieldError errors={fieldErrors[`${base}.values`]} />
      </label>
    );
  }

  return FAMILY_PARAMS[hazard.family].map((field) => (
    <label key={field.key} className="setup-field">
      {field.label}
      <input
        type="number"
        min={field.min}
        max={field.max}
        step={field.step}
        value={values[field.key]}
        {...fieldProps(`${base}.${field.key}`)}
        onChange={(e) => onChange(setHazardParam(config, i, field.key, Number(e.target.value)))}
      />
      <FieldError errors={fieldErrors[`${base}.${field.key}`]} />
    </label>
  ));
}

/** The 12px line under a control naming its live validation errors (§2.5);
 * nothing while the field is clean or its errors are not yet revealed. */
function FieldError({ errors }: { errors?: string[] }) {
  if (!errors || errors.length === 0) return null;
  return <p className="setup-field-error">{errors.join("; ")}</p>;
}

/** The inline, non-blocking seed notice under the seed field (DATA-SPEC §2.5):
 * a note, not a validation error — it never gates saving or running. */
function SeedNotice({ standalone, seedSet }: { standalone: boolean; seedSet: boolean }) {
  const notice = seedNotice(standalone, seedSet);
  if (!notice) return null;
  return (
    <p role="note" className={`setup-field-note is-${notice.tone}`}>
      {notice.text}
    </p>
  );
}
