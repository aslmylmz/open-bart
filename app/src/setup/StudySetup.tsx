import { FolderOpen, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Icon } from "../components/Icon";
import { validateConfig } from "../lib/api";
import { HAZARD_FAMILIES, type HazardFamily, type Language, type TaskConfig } from "../lib/config";
import { loadStudy, saveStudy, selectOutputDir } from "../lib/desktop";
import { EvPreview } from "./EvPreview";
import { FAMILY_PARAMS } from "./familyParams";
import {
  addColor,
  DEFAULT_QC,
  parseConditionList,
  parseExitPasscode,
  parseNumberList,
  parseStudy,
  removeColor,
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

interface StudySetupProps {
  config: TaskConfig;
  onChange: (config: TaskConfig) => void;
  onTestRun: () => void;
  onStartRun: () => void;
}

/** The Researcher View: a single column of section bands — Study Info, Data
 * Quality & Payout, Color Profiles, EV Preview, Run (DESIGN-SPEC §2.3) — as a
 * thin shell over the pure form-model helpers in studyForm.ts, with the
 * sidecar's /validate-config as the validation authority. Save/load go through
 * the native dialogs in desktop.ts; the run callbacks belong to the App shell,
 * which owns the mode. */
export function StudySetup({ config, onChange, onTestRun, onStartRun }: StudySetupProps) {
  const [errors, setErrors] = useState<string[]>([]);
  const [status, setStatus] = useState<string>("");
  // Two-step remove (§2.4): the index of the profile whose Remove is armed.
  // One shared slot — arming a card disarms any other — so a stray confirm
  // can never remove a card the researcher is no longer looking at.
  const [armedRemove, setArmedRemove] = useState<number | null>(null);
  const disarmTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(disarmTimer.current), []);

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

  async function handleSave() {
    setStatus("");
    const verdict = await validateConfig(config);
    if (!verdict.ok) {
      setErrors(verdict.errors);
      setStatus("Not saved — fix the errors below.");
      return;
    }
    setErrors([]);
    try {
      const path = await saveStudy(JSON.stringify(config, null, 2));
      setStatus(path ? `Saved to ${path}` : "Save cancelled.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Save failed.");
    }
  }

  async function handleLoad() {
    setStatus("");
    try {
      const text = await loadStudy();
      if (text === null) {
        setStatus("Load cancelled.");
        return;
      }
      const loaded = parseStudy(text);
      const verdict = await validateConfig(loaded);
      if (!verdict.ok) {
        setErrors(verdict.errors);
        setStatus("Loaded file is invalid — keeping the current study.");
        return;
      }
      setErrors([]);
      onChange(loaded);
      setStatus("Loaded.");
    } catch (err) {
      setStatus(err instanceof Error ? `Could not load: ${err.message}` : "Could not load.");
    }
  }

  async function handleSelectOutputDir() {
    try {
      const dir = await selectOutputDir();
      if (dir) {
        onChange(setStudyField(config, { output_dir: dir }));
      }
    } catch (err) {
      setStatus(err instanceof Error ? `Could not select dir: ${err.message}` : "Could not select dir.");
    }
  }

  return (
    <div className="setup-page">
      <header className="setup-header">
        <div className="setup-header-inner">
          <h1 className="setup-title">Study Setup</h1>
        </div>
      </header>

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

      {/* Interim placement — issue 03 replaces this band with the sticky
          identity bar (Save/Load + feedback) and the under-bar error strip. */}
      <section className="setup-band">
        <div className="setup-band-inner">
          <div className="setup-rail">
            <h2 className="setup-rail-title">Save &amp; load</h2>
            <p className="setup-rail-desc">
              Studies are saved as JSON files. Loaded files validate against the scoring engine
              before replacing the current study.
            </p>
          </div>
          <div className="setup-save-block">
            <div className="setup-save-actions">
              <button type="button" className="setup-btn-primary" onClick={handleSave}>
                Save study…
              </button>
              <button type="button" className="setup-btn-ghost" onClick={handleLoad}>
                Load study…
              </button>
            </div>
            {status && <p className="setup-status">{status}</p>}
            {errors.length > 0 && (
              <div className="setup-errors">
                <h3 className="setup-errors-title">Validation errors</h3>
                <ul>
                  {errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
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
