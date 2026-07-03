import { useState } from "react";

import { validateConfig } from "../lib/api";
import { HAZARD_FAMILIES, type HazardFamily, type Language, type TaskConfig } from "../lib/config";
import { loadStudy, saveStudy, selectOutputDir } from "../lib/desktop";
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

interface StudySetupProps {
  config: TaskConfig;
  onChange: (config: TaskConfig) => void;
}

/** Study Setup form (SPEC §11). A thin shell over the pure form-model helpers in
 * studyForm.ts and the sidecar's /validate-config (the validation authority); the
 * live EV preview is wired in issue 15. Save/load go through the native dialogs in
 * desktop.ts (issue 12). */
export function StudySetup({ config, onChange }: StudySetupProps) {
  const [errors, setErrors] = useState<string[]>([]);
  const [status, setStatus] = useState<string>("");

  async function handleSave() {
    setStatus("");
    const verdict = await validateConfig(config);
    if (!verdict.ok) {
      setErrors(verdict.errors);
      setStatus("Not saved — fix the errors above.");
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
    <div style={{ maxWidth: 720, margin: "0 auto", padding: "32px 16px", display: "flex", flexDirection: "column", gap: "24px" }}>
      <h1 style={{ fontSize: "2rem", fontWeight: 700, margin: 0 }}>Study Setup</h1>

      <section style={{ background: "rgba(255, 255, 255, 0.03)", padding: "24px", borderRadius: "12px", border: "1px solid rgba(255, 255, 255, 0.1)" }}>
        <h2 style={{ fontSize: "1.25rem", margin: "0 0 16px 0" }}>Study Info</h2>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
            Title
            <input
              value={config.title}
              onChange={(e) => onChange(setStudyField(config, { title: e.target.value }))}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
            Language
            <select
              value={config.language}
              onChange={(e) => onChange(setStudyField(config, { language: e.target.value as Language }))}
            >
              <option value="en">English</option>
              <option value="tr">Türkçe</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
            Reward / pump
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
          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
            Seed
            <input
              type="number"
              value={config.seed ?? ""}
              onChange={(e) =>
                onChange(
                  setStudyField(config, { seed: e.target.value === "" ? null : Number(e.target.value) }),
                )
              }
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db", gridColumn: "1 / -1" }}>
            Conditions (optional, comma-separated — e.g. control, experimental)
            {/* Committed on blur like the array hazard params, so typing commas
                doesn't fight the parsed value. Empty = no conditions. */}
            <input
              key={(config.conditions ?? []).join(",")}
              defaultValue={(config.conditions ?? []).join(", ")}
              placeholder="Leave empty for a study without conditions"
              onBlur={(e) =>
                onChange(setStudyField(config, { conditions: parseConditionList(e.target.value) }))
              }
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db", gridColumn: "1 / -1" }}>
            Exit passcode (optional — locks mid-session exits behind this code; deterrence, not security)
            {/* Committed on blur like conditions, so the trim never fights typing. */}
            <input
              key={config.exit_passcode ?? ""}
              defaultValue={config.exit_passcode ?? ""}
              placeholder="Leave empty for ungated exits"
              onBlur={(e) =>
                onChange(setStudyField(config, { exit_passcode: parseExitPasscode(e.target.value) }))
              }
            />
          </label>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db", gridColumn: "1 / -1" }}>
            Output dir
            <div style={{ display: "flex", gap: "8px" }}>
              <input
                style={{ flex: 1 }}
                value={config.output_dir}
                onChange={(e) => onChange(setStudyField(config, { output_dir: e.target.value }))}
              />
              <button type="button" onClick={handleSelectOutputDir} style={{ padding: "0 16px" }}>
                Select folder…
              </button>
            </div>
          </div>
        </div>
      </section>

      <section style={{ background: "rgba(255, 255, 255, 0.03)", padding: "24px", borderRadius: "12px", border: "1px solid rgba(255, 255, 255, 0.1)" }}>
        <h2 style={{ fontSize: "1.25rem", margin: "0 0 8px 0" }}>Data Quality &amp; Payout</h2>
        <p style={{ margin: "0 0 16px 0", fontSize: "0.8rem", color: "#9ca3af" }}>
          Both are optional. QC thresholds only flag sessions — nothing is ever excluded. Leave payout off to show participants their task earnings unchanged.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
            Fast response (ms)
            <input
              type="number"
              min={1}
              step={1}
              value={config.qc?.fast_response_ms ?? DEFAULT_QC.fast_response_ms}
              onChange={(e) => onChange(setQcField(config, { fast_response_ms: Number(e.target.value) }))}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
            Zero-pump streak (trials)
            <input
              type="number"
              min={1}
              step={1}
              value={config.qc?.zero_pump_streak ?? DEFAULT_QC.zero_pump_streak}
              onChange={(e) => onChange(setQcField(config, { zero_pump_streak: Number(e.target.value) }))}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: "8px", fontSize: "0.875rem", color: "#d1d5db", gridColumn: "1 / -1" }}>
            <input
              type="checkbox"
              checked={config.payout != null}
              onChange={(e) => onChange(setPayoutEnabled(config, e.target.checked))}
            />
            Convert task earnings to a real payout
          </label>
          {config.payout != null && (
            <>
              <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
                Payout rate (per earnings unit)
                <input
                  type="number"
                  min={0}
                  step={0.01}
                  value={config.payout.rate}
                  onChange={(e) => onChange(setPayoutField(config, { rate: Number(e.target.value) }))}
                />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
                Currency label (e.g. ₺, $, credits)
                <input
                  value={config.payout.currency}
                  onChange={(e) => onChange(setPayoutField(config, { currency: e.target.value }))}
                />
              </label>
            </>
          )}
        </div>
      </section>

      <div>
        <h2 style={{ fontSize: "1.25rem", margin: "0 0 16px 0" }}>Color Profiles</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {config.colors.map((color, i) => (
            <fieldset key={i} style={{ margin: 0, padding: "20px", borderLeft: `6px solid ${color.display_hex}`, background: "rgba(255, 255, 255, 0.03)", borderTop: "1px solid rgba(255, 255, 255, 0.1)", borderRight: "1px solid rgba(255, 255, 255, 0.1)", borderBottom: "1px solid rgba(255, 255, 255, 0.1)" }}>
              <legend style={{ padding: "0 8px", color: color.display_hex, fontWeight: "bold" }}>{color.label || color.name}</legend>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "16px", marginBottom: "16px" }}>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
                  Name
                  <input
                    value={color.name}
                    onChange={(e) => onChange(setColorField(config, i, { name: e.target.value }))}
                  />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
                  Label
                  <input
                    value={color.label}
                    onChange={(e) => onChange(setColorField(config, i, { label: e.target.value }))}
                  />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
                  Color
                  <input
                    type="color"
                    style={{ padding: 0, height: "36px", width: "100%", cursor: "pointer" }}
                    value={color.display_hex}
                    onChange={(e) => onChange(setColorField(config, i, { display_hex: e.target.value }))}
                  />
                </label>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
                  N (max pumps)
                  <input
                    type="number"
                    min={1}
                    value={color.max_pumps}
                    onChange={(e) =>
                      onChange(setColorField(config, i, { max_pumps: Number(e.target.value) }))
                    }
                  />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
                  Trials
                  <input
                    type="number"
                    min={1}
                    value={color.trials}
                    onChange={(e) => onChange(setColorField(config, i, { trials: Number(e.target.value) }))}
                  />
                </label>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "24px" }}>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
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

              <button type="button" onClick={() => onChange(removeColor(config, i))} style={{ background: "rgba(220, 38, 38, 0.2)", borderColor: "rgba(220, 38, 38, 0.4)", color: "#fca5a5" }}>
                Remove profile
              </button>
            </fieldset>
          ))}
          <button type="button" onClick={() => onChange(addColor(config))} style={{ background: "transparent", border: "1px dashed #4b5563", padding: "16px", color: "#9ca3af" }}>
            + Add color profile
          </button>
        </div>
      </div>

      <section style={{ display: "flex", gap: "16px", alignItems: "center", background: "rgba(255, 255, 255, 0.03)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(255, 255, 255, 0.1)" }}>
        <button type="button" onClick={handleSave} style={{ flex: 1, background: "#4f46e5", borderColor: "#4338ca" }}>
          Save study…
        </button>
        <button type="button" onClick={handleLoad} style={{ flex: 1 }}>
          Load study…
        </button>
      </section>

      {status && <p style={{ textAlign: "center", color: "#9ca3af" }}>{status}</p>}
      {errors.length > 0 && (
        <div style={{ background: "rgba(220, 38, 38, 0.1)", border: "1px solid rgba(220, 38, 38, 0.3)", borderRadius: "8px", padding: "16px" }}>
          <h3 style={{ color: "#fca5a5", marginTop: 0, fontSize: "0.9rem", marginBottom: "8px" }}>Validation Errors</h3>
          <ul style={{ color: "#fca5a5", margin: 0, paddingLeft: "20px", fontSize: "0.875rem" }}>
            {errors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}
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
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
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
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
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
      <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db", gridColumn: "1 / -1" }}>
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
    <label key={field.key} style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", color: "#d1d5db" }}>
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
