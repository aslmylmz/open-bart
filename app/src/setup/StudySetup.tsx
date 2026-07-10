import { FolderOpen, Plus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Icon } from "../components/Icon";
import { validateConfig } from "../lib/api";
import { HAZARD_FAMILIES, type HazardFamily, type Language, type TaskConfig } from "../lib/config";
import { loadStudy, saveStudy, selectOutputDir, type LoadedStudyFile } from "../lib/desktop";
import { isMacPlatform, matchesShortcut, shortcutChip } from "../lib/platform";
import { EvPreview } from "./EvPreview";
import { FAMILY_PARAMS } from "./familyParams";
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
import "./StudySetup.css";

/** How long the armed "Confirm remove" state holds before quietly reverting. */
const REMOVE_CONFIRM_MS = 3000;

/** How long a transient save/load message holds line 2 of the identity bar
 * before it reverts to the file identity (DESIGN-SPEC §2.1 "~4s"). */
const FEEDBACK_MS = 4000;

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
}: StudySetupProps) {
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [strip, setStrip] = useState<ErrorStrip | null>(null);
  // Two-step remove (§2.4): the index of the profile whose Remove is armed.
  // One shared slot — arming a card disarms any other — so a stray confirm
  // can never remove a card the researcher is no longer looking at.
  const [armedRemove, setArmedRemove] = useState<number | null>(null);
  const disarmTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const feedbackTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const macLike = isMacPlatform(navigator.platform);

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
    let verdict: Awaited<ReturnType<typeof validateConfig>>;
    try {
      verdict = await validateConfig(config);
    } catch (err) {
      showFeedback(describeError("Save failed", err), "error");
      return;
    }
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
              <div className="setup-bar-actions">
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
                onChange={(e) => onChange(setStudyField(config, { title: e.target.value }))}
              />
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Language</span>
              <select
                value={config.language}
                onChange={(e) => onChange(setStudyField(config, { language: e.target.value as Language }))}
              >
                <option value="en">English</option>
                <option value="tr">Türkçe</option>
              </select>
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Reward per pump</span>
              <input
                type="number"
                step={0.01}
                min={0}
                value={config.reward_per_pump}
                onChange={(e) =>
                  onChange(setStudyField(config, { reward_per_pump: Number(e.target.value) }))
                }
              />
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Seed</span>
              <input
                type="number"
                placeholder="Fresh randomness each run"
                value={config.seed ?? ""}
                onChange={(e) =>
                  onChange(
                    setStudyField(config, { seed: e.target.value === "" ? null : Number(e.target.value) }),
                  )
                }
              />
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Conditions</span>
              {/* Committed on blur like the array hazard params, so typing commas
                  doesn't fight the parsed value. Empty = no conditions. */}
              <input
                key={(config.conditions ?? []).join(",")}
                defaultValue={(config.conditions ?? []).join(", ")}
                placeholder="Comma-separated — empty for none"
                onBlur={(e) =>
                  onChange(setStudyField(config, { conditions: parseConditionList(e.target.value) }))
                }
              />
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Exit passcode</span>
              {/* Committed on blur like conditions, so the trim never fights typing. */}
              <input
                key={config.exit_passcode ?? ""}
                defaultValue={config.exit_passcode ?? ""}
                placeholder="Empty for ungated exits"
                onBlur={(e) =>
                  onChange(setStudyField(config, { exit_passcode: parseExitPasscode(e.target.value) }))
                }
              />
            </label>
            <div className="setup-row">
              <label className="setup-row-label" htmlFor="setup-output-dir">
                Output directory
              </label>
              <div className="setup-inline-group">
                <input
                  id="setup-output-dir"
                  value={config.output_dir}
                  onChange={(e) => onChange(setStudyField(config, { output_dir: e.target.value }))}
                />
                <button type="button" onClick={handleSelectOutputDir}>
                  <Icon icon={FolderOpen} />
                  Select folder…
                </button>
              </div>
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
                onChange={(e) => onChange(setQcField(config, { fast_response_ms: Number(e.target.value) }))}
              />
            </label>
            <label className="setup-row">
              <span className="setup-row-label">Zero-pump streak (trials)</span>
              <input
                type="number"
                min={1}
                step={1}
                value={config.qc?.zero_pump_streak ?? DEFAULT_QC.zero_pump_streak}
                onChange={(e) => onChange(setQcField(config, { zero_pump_streak: Number(e.target.value) }))}
              />
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
                    onChange={(e) => onChange(setPayoutField(config, { rate: Number(e.target.value) }))}
                  />
                </label>
                <label className="setup-row">
                  <span className="setup-row-label">Currency label</span>
                  <input
                    placeholder="₺, $, credits…"
                    value={config.payout.currency}
                    onChange={(e) => onChange(setPayoutField(config, { currency: e.target.value }))}
                  />
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
                      onChange={(e) => onChange(setColorField(config, i, { name: e.target.value }))}
                    />
                  </label>
                  <label className="setup-field">
                    Label
                    <input
                      value={color.label}
                      onChange={(e) => onChange(setColorField(config, i, { label: e.target.value }))}
                    />
                  </label>
                  <label className="setup-field">
                    Color
                    <input
                      type="color"
                      className="setup-swatch"
                      value={color.display_hex}
                      onChange={(e) => onChange(setColorField(config, i, { display_hex: e.target.value }))}
                    />
                  </label>
                  <label className="setup-field">
                    Max pumps (N)
                    <input
                      type="number"
                      min={1}
                      value={color.max_pumps}
                      onChange={(e) =>
                        onChange(setColorField(config, i, { max_pumps: Number(e.target.value) }))
                      }
                    />
                  </label>
                  <label className="setup-field">
                    Trials
                    <input
                      type="number"
                      min={1}
                      value={color.trials}
                      onChange={(e) => onChange(setColorField(config, i, { trials: Number(e.target.value) }))}
                    />
                  </label>
                  <label className="setup-field">
                    Hazard family
                    <select
                      value={color.hazard.family}
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
                  </label>
                  {renderHazardParams(config, i, onChange)}
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

/** Render the parameter inputs for one color's hazard: number inputs for scalar
 * families (driven by FAMILY_PARAMS) and comma-separated list inputs for the two
 * array families (committed on blur via parseNumberList). */
function renderHazardParams(
  config: TaskConfig,
  i: number,
  onChange: (config: TaskConfig) => void,
) {
  const hazard = config.colors[i].hazard;
  const values = hazard as unknown as Record<string, number>;

  if (hazard.family === "step") {
    return (
      <>
        <label className="setup-field">
          Breakpoints
          <input
            key="bp"
            defaultValue={hazard.breakpoints.join(", ")}
            onBlur={(e) =>
              onChange(
                setColorField(config, i, {
                  hazard: { ...hazard, breakpoints: parseNumberList(e.target.value) },
                }),
              )
            }
          />
        </label>
        <label className="setup-field">
          Levels
          <input
            key="lv"
            defaultValue={hazard.levels.join(", ")}
            onBlur={(e) =>
              onChange(
                setColorField(config, i, {
                  hazard: { ...hazard, levels: parseNumberList(e.target.value) },
                }),
              )
            }
          />
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
          onBlur={(e) =>
            onChange(
              setColorField(config, i, {
                hazard: { ...hazard, values: parseNumberList(e.target.value) },
              }),
            )
          }
        />
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
        onChange={(e) => onChange(setHazardParam(config, i, field.key, Number(e.target.value)))}
      />
    </label>
  ));
}
