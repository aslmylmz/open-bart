import { useState } from "react";

import { validateConfig } from "../lib/api";
import { HAZARD_FAMILIES, type HazardFamily, type Language, type TaskConfig } from "../lib/config";
import { loadStudy, saveStudy } from "../lib/desktop";
import { FAMILY_PARAMS } from "./familyParams";
import {
  addColor,
  parseNumberList,
  parseStudy,
  removeColor,
  setColorField,
  setColorHazardFamily,
  setHazardParam,
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

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 16 }}>
      <h1>Study Setup</h1>

      <section>
        <label>
          Title{" "}
          <input
            value={config.title}
            onChange={(e) => onChange(setStudyField(config, { title: e.target.value }))}
          />
        </label>
        <label>
          {" "}
          Language{" "}
          <select
            value={config.language}
            onChange={(e) => onChange(setStudyField(config, { language: e.target.value as Language }))}
          >
            <option value="en">English</option>
            <option value="tr">Türkçe</option>
          </select>
        </label>
        <label>
          {" "}
          Reward / pump{" "}
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
        <label>
          {" "}
          Seed{" "}
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
        <label>
          {" "}
          Output dir{" "}
          <input
            value={config.output_dir}
            onChange={(e) => onChange(setStudyField(config, { output_dir: e.target.value }))}
          />
        </label>
      </section>

      <h2>Colors</h2>
      {config.colors.map((color, i) => (
        <fieldset key={i} style={{ marginBottom: 12 }}>
          <legend>{color.label || color.name}</legend>
          <label>
            Name{" "}
            <input
              value={color.name}
              onChange={(e) => onChange(setColorField(config, i, { name: e.target.value }))}
            />
          </label>
          <label>
            {" "}
            Label{" "}
            <input
              value={color.label}
              onChange={(e) => onChange(setColorField(config, i, { label: e.target.value }))}
            />
          </label>
          <label>
            {" "}
            Color{" "}
            <input
              type="color"
              value={color.display_hex}
              onChange={(e) => onChange(setColorField(config, i, { display_hex: e.target.value }))}
            />
          </label>
          <br />
          <label>
            N (max pumps){" "}
            <input
              type="number"
              min={1}
              value={color.max_pumps}
              onChange={(e) =>
                onChange(setColorField(config, i, { max_pumps: Number(e.target.value) }))
              }
            />
          </label>
          <label>
            {" "}
            Trials{" "}
            <input
              type="number"
              min={1}
              value={color.trials}
              onChange={(e) => onChange(setColorField(config, i, { trials: Number(e.target.value) }))}
            />
          </label>
          <br />
          <label>
            Hazard family{" "}
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
          <br />
          <button type="button" onClick={() => onChange(removeColor(config, i))}>
            Remove color
          </button>
        </fieldset>
      ))}

      <button type="button" onClick={() => onChange(addColor(config))}>
        Add color
      </button>

      <hr />
      <button type="button" onClick={handleSave}>
        Save study…
      </button>{" "}
      <button type="button" onClick={handleLoad}>
        Load study…
      </button>
      {status && <p>{status}</p>}
      {errors.length > 0 && (
        <ul style={{ color: "#b91c1c" }}>
          {errors.map((err, i) => (
            <li key={i}>{err}</li>
          ))}
        </ul>
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
        <label>
          {" "}
          Breakpoints{" "}
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
        <label>
          {" "}
          Levels{" "}
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
      <label>
        {" "}
        Values (h per pump){" "}
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
    <label key={field.key}>
      {" "}
      {field.label}{" "}
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
