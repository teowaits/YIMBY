import { useCallback, useEffect, useRef, useState } from "react";
import {
  getHealth,
  getJob,
  getSettings,
  getShortlist,
  listRuns,
  postEstimate,
  postRun,
} from "./api.js";
import { C, ghostBtn, inputStyle, selectStyle } from "./constants.js";
import ShortlistTable from "./components/ShortlistTable.jsx";
import { ProgressBar, Spinner } from "./components/shared.jsx";

const REGION_PRESETS = [
  { label: "Italy", codes: ["it"] },
  { label: "Germany", codes: ["de"] },
  { label: "France", codes: ["fr"] },
  { label: "United Kingdom", codes: ["gb"] },
  { label: "United States", codes: ["us"] },
];

export default function App() {
  const [settings, setSettings] = useState(null);
  const [apiOk, setApiOk] = useState(false);
  const [tab, setTab] = useState("run");

  const [countryCodes, setCountryCodes] = useState(["it"]);
  const [maxCandidates, setMaxCandidates] = useState(200);
  const [workWindow, setWorkWindow] = useState(5);
  const [shortlistSize, setShortlistSize] = useState(10);
  const [minInScope, setMinInScope] = useState(1);
  const [autoEnrich, setAutoEnrich] = useState(false);
  const [timestampRuns, setTimestampRuns] = useState(true);

  const [estimate, setEstimate] = useState(null);
  const [phase, setPhase] = useState("idle");
  const [jobId, setJobId] = useState(null);
  const [logs, setLogs] = useState([]);
  const [errorMsg, setErrorMsg] = useState("");
  const [shortlistDoc, setShortlistDoc] = useState(null);

  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const pollRef = useRef(null);

  const overrides = useCallback(
    () => ({
      country_codes: countryCodes,
      max_candidates: maxCandidates,
      work_window_years: workWindow,
      shortlist_size: shortlistSize,
      min_in_scope_works: minInScope,
      auto_enrich: autoEnrich,
      timestamp_runs: timestampRuns,
    }),
    [
      countryCodes,
      maxCandidates,
      workWindow,
      shortlistSize,
      minInScope,
      autoEnrich,
      timestampRuns,
    ]
  );

  useEffect(() => {
    (async () => {
      try {
        await getHealth();
        setApiOk(true);
        const s = await getSettings();
        setSettings(s);
        setCountryCodes(s.region.country_codes.length ? s.region.country_codes : ["it"]);
        setMaxCandidates(s.openalex.max_candidates);
        setWorkWindow(s.openalex.work_window_years);
        setShortlistSize(s.output.shortlist_size);
        setMinInScope(s.scoring.min_in_scope_works);
        setAutoEnrich(s.output.auto_enrich);
        setTimestampRuns(s.output.timestamp_runs);
      } catch {
        setApiOk(false);
      }
    })();
    refreshRuns();
  }, []);

  const refreshRuns = async () => {
    try {
      const { runs: r } = await listRuns();
      setRuns(r || []);
    } catch {
      /* server may be down */
    }
  };

  const handleEstimate = async () => {
    setErrorMsg("");
    try {
      const est = await postEstimate(overrides());
      setEstimate(est);
    } catch (e) {
      setErrorMsg(e.message);
    }
  };

  const handleRun = async () => {
    setPhase("running");
    setLogs([]);
    setErrorMsg("");
    setShortlistDoc(null);
    setEstimate(null);
    try {
      const { job_id } = await postRun(overrides());
      setJobId(job_id);
      pollRef.current = setInterval(async () => {
        try {
          const job = await getJob(job_id);
          setLogs(job.logs || []);
          if (job.status === "done") {
            clearInterval(pollRef.current);
            setPhase("done");
            setShortlistDoc(job.result?.shortlist || null);
            refreshRuns();
          } else if (job.status === "error") {
            clearInterval(pollRef.current);
            setPhase("error");
            setErrorMsg(job.error || "Run failed");
          }
        } catch (e) {
          clearInterval(pollRef.current);
          setPhase("error");
          setErrorMsg(e.message);
        }
      }, 800);
    } catch (e) {
      setPhase("error");
      setErrorMsg(e.message);
    }
  };

  const loadRun = async (runId) => {
    setTab("results");
    setSelectedRunId(runId);
    try {
      const doc = await getShortlist(runId);
      setShortlistDoc(doc);
      setPhase("done");
    } catch (e) {
      setErrorMsg(e.message);
    }
  };

  useEffect(
    () => () => {
      if (pollRef.current) clearInterval(pollRef.current);
    },
    []
  );

  const isRunning = phase === "running";
  const yWindow = settings?.publication_year_window;
  const NAV = [
    { key: "run", label: "Run Scout" },
    { key: "results", label: "Shortlist" },
    { key: "history", label: "History" },
  ];

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bg,
        color: C.textPrimary,
        fontFamily: "'IBM Plex Mono', 'Fira Code', monospace",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <div
        style={{
          borderBottom: `1px solid ${C.border}`,
          padding: "18px 28px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: C.bgDark,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 10,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: C.textMuted,
              marginBottom: 3,
            }}
          >
            OpenAlex · Regional Researcher Scout
          </div>
          <div
            style={{
              fontSize: 20,
              fontWeight: 700,
              color: C.textPrimary,
              fontFamily: "'IBM Plex Sans', sans-serif",
            }}
          >
            Regional Scout
          </div>
        </div>
        <div
          style={{
            fontSize: 10,
            color: C.textMuted,
            textAlign: "right",
            lineHeight: 1.8,
            letterSpacing: "0.05em",
          }}
        >
          {yWindow ? (
            <>
              Window {yWindow.from}–{yWindow.to}
              <br />
            </>
          ) : null}
          {apiOk ? (
            <span style={{ color: C.greenDark }}>API connected</span>
          ) : (
            <span style={{ color: C.red }}>Start: regional-scout serve</span>
          )}
        </div>
      </div>

      {!apiOk && (
        <div
          style={{
            background: "#742a2a33",
            borderBottom: `1px solid ${C.border}`,
            padding: "12px 28px",
            fontSize: 12,
            color: C.red,
          }}
        >
          Cannot reach the API at <code>/api</code>. Run{" "}
          <code style={{ color: C.amberLight }}>uv run regional-scout serve --config config.local.yaml</code>{" "}
          in another terminal, then refresh.
        </div>
      )}

      {/* Tab nav */}
      <div
        style={{
          borderBottom: `1px solid ${C.border}`,
          background: C.bgDark,
          padding: "0 28px",
        }}
      >
        <div style={{ maxWidth: 1100, margin: "0 auto", display: "flex" }}>
          {NAV.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              style={{
                padding: "12px 20px",
                border: "none",
                background: "transparent",
                color: tab === key ? C.textPrimary : C.textMuted,
                borderBottom: `2px solid ${tab === key ? C.blue : "transparent"}`,
                cursor: "pointer",
                fontSize: 12,
                fontWeight: tab === key ? 600 : 400,
                letterSpacing: "0.04em",
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {tab === "run" && (
        <div style={{ flex: 1 }}>
          <div
            style={{
              borderBottom: `1px solid ${C.border}`,
              padding: "20px 28px",
              background: C.bgDark,
            }}
          >
            <div style={{ maxWidth: 1100, margin: "0 auto" }}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
                  gap: 16,
                  marginBottom: 16,
                }}
              >
                <label style={{ fontSize: 11, color: C.textMuted }}>
                  <span
                    style={{
                      display: "block",
                      marginBottom: 6,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                    }}
                  >
                    Region (ISO country)
                  </span>
                  <input
                    style={inputStyle}
                    value={countryCodes.join(", ")}
                    disabled={isRunning}
                    onChange={(e) =>
                      setCountryCodes(
                        e.target.value
                          .split(/[,\s]+/)
                          .map((c) => c.trim().toLowerCase())
                          .filter(Boolean)
                      )
                    }
                    placeholder="it, de, fr"
                  />
                  <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                    {REGION_PRESETS.map((p) => (
                      <button
                        key={p.label}
                        type="button"
                        disabled={isRunning}
                        onClick={() => setCountryCodes(p.codes)}
                        style={{ ...ghostBtn, padding: "4px 10px", fontSize: 10 }}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                </label>

                <label style={{ fontSize: 11, color: C.textMuted }}>
                  <span
                    style={{
                      display: "block",
                      marginBottom: 6,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                    }}
                  >
                    Max candidates
                  </span>
                  <select
                    style={selectStyle}
                    value={maxCandidates}
                    disabled={isRunning}
                    onChange={(e) => setMaxCandidates(Number(e.target.value))}
                  >
                    {[20, 50, 100, 200, 500].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>

                <label style={{ fontSize: 11, color: C.textMuted }}>
                  <span
                    style={{
                      display: "block",
                      marginBottom: 6,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                    }}
                  >
                    Work window (years)
                  </span>
                  <select
                    style={selectStyle}
                    value={workWindow}
                    disabled={isRunning}
                    onChange={(e) => setWorkWindow(Number(e.target.value))}
                  >
                    {[3, 5, 7, 10].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>

                <label style={{ fontSize: 11, color: C.textMuted }}>
                  <span
                    style={{
                      display: "block",
                      marginBottom: 6,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                    }}
                  >
                    Shortlist size
                  </span>
                  <select
                    style={selectStyle}
                    value={shortlistSize}
                    disabled={isRunning}
                    onChange={(e) => setShortlistSize(Number(e.target.value))}
                  >
                    {[5, 10, 15, 20, 25].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>

                <label style={{ fontSize: 11, color: C.textMuted }}>
                  <span
                    style={{
                      display: "block",
                      marginBottom: 6,
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                    }}
                  >
                    Min in-scope works
                  </span>
                  <select
                    style={selectStyle}
                    value={minInScope}
                    disabled={isRunning}
                    onChange={(e) => setMinInScope(Number(e.target.value))}
                  >
                    {[0, 1, 2, 3].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
                <label style={{ fontSize: 11, color: C.textMuted, display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={autoEnrich}
                    disabled={isRunning}
                    onChange={(e) => setAutoEnrich(e.target.checked)}
                  />
                  Auto-enrich (published-with-us)
                </label>
                <label style={{ fontSize: 11, color: C.textMuted, display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={timestampRuns}
                    disabled={isRunning}
                    onChange={(e) => setTimestampRuns(e.target.checked)}
                  />
                  Timestamp output folders
                </label>
              </div>

              <div
                style={{
                  display: "flex",
                  gap: 12,
                  alignItems: "center",
                  flexWrap: "wrap",
                  marginTop: 16,
                }}
              >
                <button
                  type="button"
                  onClick={handleEstimate}
                  disabled={isRunning || !apiOk}
                  style={{ ...ghostBtn, padding: "10px 20px" }}
                >
                  Estimate credits
                </button>
                <button
                  type="button"
                  onClick={handleRun}
                  disabled={isRunning || !apiOk || !countryCodes.length}
                  style={{
                    padding: "10px 26px",
                    borderRadius: 8,
                    border: "none",
                    fontWeight: 600,
                    fontSize: 13,
                    cursor: isRunning || !apiOk ? "not-allowed" : "pointer",
                    background: isRunning ? "#742a2a" : "#2b6cb0",
                    color: "#fff",
                    letterSpacing: "0.05em",
                  }}
                >
                  {isRunning ? "Running…" : "Run Scout"}
                </button>
                {estimate && (
                  <div style={{ fontSize: 11, color: estimate.within_budget ? C.greenDark : C.red }}>
                    Est. {estimate.total.toLocaleString()} credits
                    {!estimate.within_budget && " — over budget"}
                  </div>
                )}
                {phase === "done" && (
                  <button
                    type="button"
                    style={{ ...ghostBtn, color: C.blueLight }}
                    onClick={() => setTab("results")}
                  >
                    View shortlist →
                  </button>
                )}
                {phase === "error" && (
                  <span style={{ fontSize: 12, color: C.red }}>{errorMsg}</span>
                )}
              </div>

              {estimate && (
                <pre
                  style={{
                    marginTop: 14,
                    padding: "12px 14px",
                    background: "#111827",
                    border: `1px solid ${C.border}`,
                    borderRadius: 8,
                    fontSize: 11,
                    color: C.textSecondary,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {estimate.message}
                </pre>
              )}

              {isRunning && (
                <div
                  style={{
                    background: "#111827",
                    border: `1px solid ${C.border}`,
                    borderRadius: 10,
                    padding: "14px 18px",
                    marginTop: 16,
                    animation: "fadeIn 0.3s ease",
                  }}
                >
                  <div style={{ fontSize: 10, color: C.blue, marginBottom: 8, textTransform: "uppercase" }}>
                    Pipeline · job {jobId}
                  </div>
                  <ProgressBar value={logs.length} max={40} color={C.blue} />
                  <div
                    style={{
                      marginTop: 12,
                      maxHeight: 220,
                      overflow: "auto",
                      fontSize: 11,
                      color: C.textMuted,
                      lineHeight: 1.7,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                      <Spinner size={11} color={C.textMuted} />
                      {logs[logs.length - 1] || "Starting…"}
                    </div>
                    {logs.slice(-25).map((line, i) => (
                      <div key={i}>{line}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {!isRunning && phase === "idle" && (
            <div style={{ maxWidth: 700, margin: "0 auto", padding: "48px 28px", textAlign: "center" }}>
              <div style={{ fontSize: 36, marginBottom: 16, opacity: 0.15 }}>◎</div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 600,
                  fontFamily: "'IBM Plex Sans', sans-serif",
                  marginBottom: 8,
                }}
              >
                Rank regional researchers for AI×science editorial scouting
              </div>
              <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.7 }}>
                Scope from Wiley portfolio journals, score by relevance, productivity, impact, and
                co-author centrality. API key stays on the server via{" "}
                <code style={{ color: C.textSecondary }}>config.local.yaml</code>.
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "results" && (
        <div style={{ flex: 1 }}>
          {shortlistDoc ? (
            <>
              <div
                style={{
                  padding: "14px 28px",
                  borderBottom: `1px solid ${C.border}`,
                  fontSize: 11,
                  color: C.textMuted,
                  background: C.bgDark,
                }}
              >
                {shortlistDoc.region && (
                  <span>
                    Region <strong style={{ color: C.textSecondary }}>{shortlistDoc.region}</strong>
                    {" · "}
                  </span>
                )}
                {(shortlistDoc.candidates_eligible != null || shortlistDoc.candidates_evaluated != null) && (
                  <span>
                    {shortlistDoc.candidates_eligible} eligible / {shortlistDoc.candidates_evaluated}{" "}
                    fetched
                    {" · "}
                  </span>
                )}
                {shortlistDoc.credits?.used != null && (
                  <span>{shortlistDoc.credits.used.toLocaleString()} credits used</span>
                )}
              </div>
              <ShortlistTable doc={shortlistDoc} />
            </>
          ) : (
            <div style={{ padding: 48, textAlign: "center", color: C.textMuted }}>
              Run a scout or load a run from History.
            </div>
          )}
        </div>
      )}

      {tab === "history" && (
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 28px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: C.textMuted, textTransform: "uppercase", letterSpacing: "0.1em" }}>
              Past runs
            </div>
            <button type="button" style={ghostBtn} onClick={refreshRuns}>
              Refresh
            </button>
          </div>
          {runs.length === 0 ? (
            <div style={{ color: C.textMuted, fontSize: 13 }}>No saved runs yet.</div>
          ) : (
            runs.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => loadRun(r.id)}
                style={{
                  ...ghostBtn,
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  marginBottom: 8,
                  padding: "12px 16px",
                  borderColor: selectedRunId === r.id ? C.blue : C.border2,
                }}
              >
                <div style={{ fontWeight: 600, color: C.textPrimary }}>{r.id}</div>
                <div style={{ fontSize: 10, color: C.textMuted, marginTop: 4 }}>
                  {r.region} · {r.shortlist_count} authors
                  {r.generated_at && ` · ${r.generated_at.slice(0, 16).replace("T", " ")}`}
                  {r.credits_used != null && ` · ${r.credits_used} credits`}
                </div>
              </button>
            ))
          )}
        </div>
      )}

      {/* Footer */}
      <div
        style={{
          borderTop: `1px solid ${C.border}`,
          marginTop: "auto",
          padding: "18px 28px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 10,
          fontSize: 11,
          color: C.textMuted,
          background: C.bgDark,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span>
            Suite design: journal-overlap · journal-profiler · citation-summoner
          </span>
          <span style={{ color: C.border2 }}>·</span>
          <a href="https://openalex.org" target="_blank" rel="noreferrer" style={{ color: C.textSecondary, textDecoration: "none" }}>
            OpenAlex API
          </a>
        </div>
        <span>v{settings?.version || "0.3.0"}</span>
      </div>
    </div>
  );
}
