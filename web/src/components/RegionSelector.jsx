import { useState } from "react";
import { getInitCity } from "../api.js";
import { C, ghostBtn, inputStyle, selectStyle } from "../constants.js";
import { Spinner } from "./shared.jsx";

const MODES = [
  { key: "city", label: "City" },
  { key: "country", label: "Country" },
  { key: "institutions", label: "Institutions" },
];

const COUNTRY_OPTIONS = [
  { code: "it", label: "IT" },
  { code: "es", label: "ES" },
  { code: "de", label: "DE" },
  { code: "fr", label: "FR" },
  { code: "gb", label: "GB" },
  { code: "us", label: "US" },
];

const REGION_PRESETS = [
  { label: "Italy", codes: ["it"] },
  { label: "Germany", codes: ["de"] },
  { label: "France", codes: ["fr"] },
  { label: "United Kingdom", codes: ["gb"] },
  { label: "United States", codes: ["us"] },
];

/**
 * Builds region override payload for estimate/run API.
 * When institution_ids is non-empty, country_codes must not be sent (server clears both).
 */
export default function RegionSelector({ disabled, onChange }) {
  const [mode, setMode] = useState("country");

  const [countryCodes, setCountryCodes] = useState(["it"]);
  const [cityName, setCityName] = useState("");
  const [cityCountry, setCityCountry] = useState("es");
  const [resolved, setResolved] = useState([]);
  const [checked, setChecked] = useState({});
  const [resolvePhase, setResolvePhase] = useState("idle");
  const [resolveError, setResolveError] = useState("");
  const [confirmedCity, setConfirmedCity] = useState(null);
  const [manualIds, setManualIds] = useState("");

  const emit = (next) => {
    if (onChange) onChange(next);
  };

  const buildPayload = (overrides = {}) => {
    if (mode === "city" && confirmedCity?.institution_ids?.length) {
      return {
        city_name: confirmedCity.city_name,
        city_country_code: confirmedCity.city_country_code,
        institution_ids: confirmedCity.institution_ids,
        ...overrides,
      };
    }
    if (mode === "institutions") {
      const ids = manualIds
        .split(/[\n,]+/)
        .map((s) => s.trim())
        .filter((s) => /^I\d+$/i.test(s))
        .map((s) => s.toUpperCase());
      if (ids.length) {
        return { institution_ids: ids, ...overrides };
      }
    }
    if (mode === "country" && countryCodes.length) {
      return { country_codes: countryCodes, ...overrides };
    }
    return { ...overrides };
  };

  const handleModeChange = (key) => {
    setMode(key);
    setResolveError("");
    if (key === "country") {
      emit({ country_codes: countryCodes });
    } else if (key === "institutions") {
      emit(buildPayload());
    } else {
      emit(confirmedCity ? buildPayload() : {});
    }
  };

  const handleCountryChange = (codes) => {
    setCountryCodes(codes);
    if (mode === "country") emit({ country_codes: codes });
  };

  const handleResolve = async () => {
    if (!cityName.trim()) return;
    setResolvePhase("loading");
    setResolveError("");
    try {
      const data = await getInitCity(cityName.trim(), cityCountry);
      setResolved(data.institutions || []);
      const initChecked = {};
      (data.institutions || []).forEach((inst) => {
        initChecked[inst.id] = true;
      });
      setChecked(initChecked);
      setResolvePhase("done");
    } catch (e) {
      setResolvePhase("error");
      setResolveError(e.message);
    }
  };

  const handleConfirmSelection = () => {
    const ids = resolved.filter((r) => checked[r.id]).map((r) => r.id);
    const payload = {
      city_name: cityName.trim(),
      city_country_code: cityCountry,
      institution_ids: ids,
    };
    setConfirmedCity(payload);
    emit(payload);
  };

  const handleClearCity = () => {
    setConfirmedCity(null);
    setResolved([]);
    setChecked({});
    emit({});
  };

  const handleManualChange = (text) => {
    setManualIds(text);
    const ids = text
      .split(/[\n,]+/)
      .map((s) => s.trim())
      .filter((s) => /^I\d+$/i.test(s))
      .map((s) => s.toUpperCase());
    if (ids.length) emit({ institution_ids: ids });
    else emit({});
  };

  const tabStyle = (active) => ({
    padding: "8px 16px",
    border: "none",
    background: "transparent",
    color: active ? C.textPrimary : C.textMuted,
    borderBottom: `2px solid ${active ? C.blue : "transparent"}`,
    cursor: disabled ? "not-allowed" : "pointer",
    fontSize: 11,
    fontWeight: active ? 600 : 400,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
  });

  return (
    <div style={{ gridColumn: "1 / -1" }}>
      <div style={{ display: "flex", gap: 0, marginBottom: 14, borderBottom: `1px solid ${C.border}` }}>
        {MODES.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            disabled={disabled}
            style={tabStyle(mode === key)}
            onClick={() => handleModeChange(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === "country" && (
        <div>
          <label style={{ fontSize: 11, color: C.textMuted, display: "block" }}>
            <span style={{ display: "block", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Region (ISO country) — coarse
            </span>
            <input
              style={inputStyle}
              value={countryCodes.join(", ")}
              disabled={disabled}
              onChange={(e) =>
                handleCountryChange(
                  e.target.value
                    .split(/[,\s]+/)
                    .map((c) => c.trim().toLowerCase())
                    .filter(Boolean)
                )
              }
              placeholder="it, de, fr"
            />
          </label>
          <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
            {REGION_PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                disabled={disabled}
                onClick={() => handleCountryChange(p.codes)}
                style={{ ...ghostBtn, padding: "4px 10px", fontSize: 10 }}
              >
                {p.label}
              </button>
            ))}
          </div>
          <p style={{ fontSize: 10, color: C.textMuted, marginTop: 10, lineHeight: 1.6 }}>
            Country-level results include researchers with any affiliation in this country,
            including secondary and past positions. For trip planning, use City mode.
          </p>
        </div>
      )}

      {mode === "city" && (
        <div>
          {confirmedCity ? (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                padding: "8px 12px",
                background: C.surface,
                border: `1px solid ${C.border2}`,
                borderRadius: 8,
                fontSize: 12,
              }}
            >
              <span style={{ color: C.blueLight }}>
                {confirmedCity.city_name}, {confirmedCity.city_country_code.toUpperCase()} —{" "}
                {confirmedCity.institution_ids.length} institutions
              </span>
              <button type="button" style={{ ...ghostBtn, padding: "4px 10px", fontSize: 10 }} disabled={disabled} onClick={handleClearCity}>
                Clear
              </button>
            </div>
          ) : (
            <>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
                <label style={{ fontSize: 11, color: C.textMuted, flex: "1 1 180px" }}>
                  <span style={{ display: "block", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    City
                  </span>
                  <input
                    style={inputStyle}
                    value={cityName}
                    disabled={disabled}
                    onChange={(e) => setCityName(e.target.value)}
                    placeholder="Madrid"
                  />
                </label>
                <label style={{ fontSize: 11, color: C.textMuted, width: 100 }}>
                  <span style={{ display: "block", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    Country
                  </span>
                  <select
                    style={selectStyle}
                    value={cityCountry}
                    disabled={disabled}
                    onChange={(e) => setCityCountry(e.target.value)}
                  >
                    {COUNTRY_OPTIONS.map((o) => (
                      <option key={o.code} value={o.code}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div style={{ display: "flex", alignItems: "flex-end" }}>
                  <button
                    type="button"
                    disabled={disabled || !cityName.trim() || resolvePhase === "loading"}
                    style={{ ...ghostBtn, padding: "8px 16px" }}
                    onClick={handleResolve}
                  >
                    {resolvePhase === "loading" ? (
                      <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <Spinner size={12} /> Resolving…
                      </span>
                    ) : (
                      "Resolve institutions"
                    )}
                  </button>
                </div>
              </div>
              {resolveError && <p style={{ fontSize: 11, color: C.red, marginBottom: 8 }}>{resolveError}</p>}
              {resolved.length > 0 && (
                <div
                  style={{
                    maxHeight: 220,
                    overflow: "auto",
                    border: `1px solid ${C.border}`,
                    borderRadius: 8,
                    padding: "10px 12px",
                    marginBottom: 10,
                    fontSize: 11,
                  }}
                >
                  {resolved.map((inst) => (
                    <label
                      key={inst.id}
                      style={{
                        display: "flex",
                        gap: 10,
                        alignItems: "flex-start",
                        padding: "6px 0",
                        borderBottom: `1px solid ${C.border}`,
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={!!checked[inst.id]}
                        disabled={disabled}
                        onChange={(e) => setChecked((c) => ({ ...c, [inst.id]: e.target.checked }))}
                      />
                      <span>
                        <strong style={{ color: C.textPrimary }}>{inst.display_name}</strong>
                        <span style={{ color: C.textMuted }}> ({inst.works_count?.toLocaleString()} works)</span>
                      </span>
                    </label>
                  ))}
                </div>
              )}
              {resolved.length > 0 && (
                <button
                  type="button"
                  disabled={disabled}
                  style={{ ...ghostBtn, color: C.blueLight }}
                  onClick={handleConfirmSelection}
                >
                  Use selected ({resolved.filter((r) => checked[r.id]).length})
                </button>
              )}
            </>
          )}
        </div>
      )}

      {mode === "institutions" && (
        <div>
          <label style={{ fontSize: 11, color: C.textMuted, display: "block" }}>
            <span style={{ display: "block", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>
              Institution IDs
            </span>
            <textarea
              style={{ ...inputStyle, minHeight: 80, fontFamily: "inherit" }}
              value={manualIds}
              disabled={disabled}
              onChange={(e) => handleManualChange(e.target.value)}
              placeholder="I126973510, I201646483"
            />
          </label>
          <p style={{ fontSize: 10, color: C.textMuted, marginTop: 8, lineHeight: 1.6 }}>
            Paste OpenAlex institution IDs (I…). Find them at openalex.org/institutions or via City mode above.
          </p>
        </div>
      )}
    </div>
  );
}