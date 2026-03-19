import { useState, useEffect, useCallback } from "react";

const API_URL = (typeof process !== "undefined" && process.env?.REACT_APP_API_URL) || "http://localhost:8000";

const QUICK_RANGES = [
  { label: "Last hour", ms: 60 * 60 * 1000 },
  { label: "Last day",  ms: 24 * 60 * 60 * 1000 },
  { label: "Last week", ms: 7 * 24 * 60 * 60 * 1000 },
  { label: "Custom",    ms: null },
];

const fmt = (ts) => new Date(ts).toLocaleString();
const fmtScore = (s) => (s == null ? "—" : Number(s).toFixed(4));

const scoreColor = (score) => {
  if (score == null) return "#94a3b8";
  const abs = Math.abs(score);
  if (abs >= 3)   return "#dc2626";
  if (abs >= 2)   return "#ea580c";
  if (abs >= 1.5) return "#d97706";
  return "#059669";
};

// Sanitize error messages — never show raw objects or long stack traces
const safeMsg = (e) =>
  typeof e?.message === "string" && e.message.length < 200
    ? e.message
    : "Something went wrong. Please try again.";

function Panel({ title, accent, children, count, loading, empty, emptyMsg, failed }) {
  return (
    <div style={{
      flex: 1, minWidth: 0,
      background: "#ffffff",
      border: `1px solid ${failed ? "#fca5a5" : "#e2e8f0"}`,
      borderRadius: 12,
      borderTop: `3px solid ${failed ? "#ef4444" : accent}`,
      boxShadow: "0 1px 4px rgba(0,0,0,0.05)",
      display: "flex", flexDirection: "column", overflow: "hidden",
    }}>
      <div style={{
        padding: "14px 20px",
        borderBottom: "1px solid #f1f5f9",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span style={{ fontFamily: "'Space Mono', monospace", fontSize: 11, letterSpacing: 1, textTransform: "uppercase", color: failed ? "#ef4444" : "#94a3b8" }}>
          {title}
        </span>
        {count != null && !loading && (
          <span style={{ fontFamily: "'Space Mono', monospace", fontSize: 10, color: "#cbd5e1" }}>
            {count} rows
          </span>
        )}
      </div>
      <div style={{ flex: 1, overflowY: "auto", maxHeight: 460 }}>
        {loading ? (
          <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", gap: 10, fontFamily: "'Space Mono', monospace", fontSize: 11, color: "#059669", letterSpacing: 2, textTransform: "uppercase" }}>
            <div style={{ width: 16, height: 16, border: "2px solid rgba(16,185,129,0.2)", borderTopColor: "#10b981", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
            Loading…
          </div>
        ) : empty ? (
          <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "'Space Mono', monospace", fontSize: 11, color: "#cbd5e1", textTransform: "uppercase", letterSpacing: 2, textAlign: "center", padding: "0 24px", lineHeight: 2 }}>
            {emptyMsg}
          </div>
        ) : children}
      </div>
    </div>
  );
}

function ReadingsPanel({ readings, loading, fetched, failed }) {
  if (!fetched && !failed) return <Panel title="Raw Readings" accent="#2563eb" loading={false} empty emptyMsg="Select a metric and fetch to load raw readings." />;
  if (failed) return <Panel title="Raw Readings" accent="#2563eb" failed loading={false} empty emptyMsg="Could not load readings. Please try again." />;
  return (
    <Panel title="Raw Readings" accent="#2563eb" loading={loading} empty={!loading && readings.length === 0} emptyMsg="No readings found for the selected range." count={!loading ? readings.length : null}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "#f8fafc" }}>
            {["Timestamp", "Value"].map(h => (
              <th key={h} style={{ padding: "10px 20px", textAlign: "left", fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 1, textTransform: "uppercase", color: "#94a3b8", borderBottom: "1px solid #e2e8f0", position: "sticky", top: 0, background: "#f8fafc" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {readings.map((r, i) => (
            <tr key={i} style={{ borderBottom: "1px solid #f1f5f9", background: i % 2 === 0 ? "#ffffff" : "#f8fafc" }}>
              <td style={{ padding: "11px 20px", fontFamily: "'Space Mono', monospace", fontSize: 11, color: "#64748b" }}>{fmt(r.timestamp)}</td>
              <td style={{ padding: "11px 20px", fontFamily: "'Space Mono', monospace", fontSize: 13, color: "#2563eb", fontWeight: 700 }}>{r.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function AnomalyPanel({ anomalies, loading, fetched, noRunYet, unavailable }) {
  if (!fetched && !unavailable) return <Panel title="Anomaly Results" accent="#10b981" loading={false} empty emptyMsg="Anomaly results will appear here after fetching." />;
  // Distinguish between "server error" and "no run yet"
  if (unavailable) return <Panel title="Anomaly Results" accent="#10b981" loading={false} empty emptyMsg="Anomaly data is currently unavailable. The server may be experiencing issues." />;
  if (noRunYet) return <Panel title="Anomaly Results" accent="#10b981" loading={false} empty emptyMsg={"No anomaly detection has been run yet.\nRun POST /anomalies/run first."} />;
  return (
    <Panel title="Anomaly Results" accent="#10b981" loading={loading} empty={!loading && anomalies.length === 0} emptyMsg="No anomaly results found for the selected range." count={!loading ? anomalies.length : null}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "#f8fafc" }}>
            {["Timestamp", "Score", "Status"].map(h => (
              <th key={h} style={{ padding: "10px 20px", textAlign: "left", fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 1, textTransform: "uppercase", color: "#94a3b8", borderBottom: "1px solid #e2e8f0", position: "sticky", top: 0, background: "#f8fafc" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {anomalies.map((a, i) => (
            <tr key={i} style={{ borderBottom: "1px solid #f1f5f9", background: a.flag ? "rgba(220,38,38,0.04)" : (i % 2 === 0 ? "#ffffff" : "#f8fafc") }}>
              <td style={{ padding: "11px 20px", fontFamily: "'Space Mono', monospace", fontSize: 11, color: "#64748b" }}>{fmt(a.timestamp)}</td>
              <td style={{ padding: "11px 20px", fontFamily: "'Space Mono', monospace", fontSize: 13, color: scoreColor(a.score), fontWeight: 700 }}>{fmtScore(a.score)}</td>
              <td style={{ padding: "11px 20px" }}>
                {a.flag ? (
                  <span style={{ background: "rgba(220,38,38,0.08)", color: "#dc2626", border: "1px solid rgba(220,38,38,0.25)", borderRadius: 6, padding: "3px 10px", fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 1, textTransform: "uppercase", fontWeight: 700 }}>⚑ Anomaly</span>
                ) : (
                  <span style={{ background: "rgba(16,185,129,0.08)", color: "#059669", border: "1px solid rgba(16,185,129,0.2)", borderRadius: 6, padding: "3px 10px", fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 1, textTransform: "uppercase" }}>✓ Normal</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

export default function MeasurementsView() {
  const [metrics, setMetrics]               = useState([]);
  const [metricId, setMetricId]             = useState("");
  const [rangeIdx, setRangeIdx]             = useState(1);
  const [customStart, setCustomStart]       = useState("");
  const [customEnd, setCustomEnd]           = useState("");
  const [readings, setReadings]             = useState([]);
  const [anomalies, setAnomalies]           = useState([]);
  const [loadingR, setLoadingR]             = useState(false);
  const [loadingA, setLoadingA]             = useState(false);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [errorR, setErrorR]                 = useState(null);
  const [fetchedR, setFetchedR]             = useState(false);
  const [fetchedA, setFetchedA]             = useState(false);
  const [failedR, setFailedR]               = useState(false);   // readings hard fail
  const [noRunYet, setNoRunYet]             = useState(false);   // 404 = no detection run
  const [anomalyUnavailable, setAnomalyUnavailable] = useState(false); // 5xx/network fail

  useEffect(() => {
    fetch(`${API_URL}/metrics`)
      .then(r => r.json())
      .then(data => {
        setMetrics(data);
        if (data.length > 0) setMetricId(String(data[0].id));
        setLoadingMetrics(false);
      })
      .catch(() => setLoadingMetrics(false));
  }, []);

  const getRange = useCallback(() => {
    const range = QUICK_RANGES[rangeIdx];
    if (range.ms === null) return { start: customStart, end: customEnd };
    const now = new Date();
    return { start: new Date(now.getTime() - range.ms).toISOString(), end: now.toISOString() };
  }, [rangeIdx, customStart, customEnd]);

  const validate = () => {
    if (!metricId) return "Please select a metric.";
    if (QUICK_RANGES[rangeIdx].ms === null) {
      if (!customStart || !customEnd) return "Please enter both start and end dates.";
      if (new Date(customStart) >= new Date(customEnd)) return "Start must be before end.";
    }
    return null;
  };

  const handleFetch = async () => {
    const err = validate();
    if (err) { setErrorR(err); return; }
    const { start, end } = getRange();

    // Reset all state before new fetch
    setErrorR(null);
    setNoRunYet(false);
    setAnomalyUnavailable(false);
    setFailedR(false);
    setReadings([]);
    setAnomalies([]);
    setFetchedR(false);
    setFetchedA(false);

    // 1. Fetch readings first if this fails, stop and don't fetch anomalies
    setLoadingR(true);
    let readingsOk = false;
    try {
      const res = await fetch(`${API_URL}/readings?${new URLSearchParams({ metric_id: metricId, start, end })}`);
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        if (res.status === 404) throw new Error("No data found for the selected metric and time range.");
        throw new Error(b.detail || "Could not load readings. Please try again.");
      }
      const data = await res.json();
      setReadings(data.readings || []);
      setFetchedR(true);
      readingsOk = true;
    } catch (e) {
      setErrorR(safeMsg(e));
      setFailedR(true);
    } finally {
      setLoadingR(false);
    }

    // 2. Only fetch anomalies if readings succeeded
    if (!readingsOk) return;

    setLoadingA(true);
    try {
      const res = await fetch(`${API_URL}/anomalies?${new URLSearchParams({ metric_id: metricId, start, end })}`);
      if (!res.ok) {
        // 404 means no detection run yet expected condition
        if (res.status === 404) {
          setNoRunYet(true);
        } else {
          // 5xx or other anomaly data genuinely unavailable
          setAnomalyUnavailable(true);
        }
        setFetchedA(true);
        return;
      }
      const data = await res.json();
      if (data.length === 0) setNoRunYet(true);
      setAnomalies(data);
      setFetchedA(true);
    } catch {
      // Network-level failure  anomaly data unavailable
      setAnomalyUnavailable(true);
      setFetchedA(true);
    } finally {
      setLoadingA(false);
    }
  };

  const isCustom = QUICK_RANGES[rangeIdx].ms === null;

  return (
    <div className="dash">
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <div className="header">
        <div>
          <div className="header-badge"><span className="pulse" />Measurements</div>
          <h1 style={{ marginTop: 8 }}>Raw Readings & Anomaly Results</h1>
          <p style={{ marginTop: 6, color: "#64748b", fontSize: 13, fontFamily: "'DM Sans', sans-serif" }}>
            Compare raw sensor readings with anomaly detection results side by side.
          </p>
        </div>
      </div>

      <div className="controls">
        <div className="control-group">
          <label>Metric</label>
          {loadingMetrics ? (
            <select disabled><option>Loading…</option></select>
          ) : (
            <select value={metricId} onChange={e => setMetricId(e.target.value)}>
              {metrics.map(m => (
                <option key={m.id} value={m.id}>
                  {m.name}{m.unit ? ` (${m.unit})` : ""} — {m.zone}
                </option>
              ))}
            </select>
          )}
        </div>

        <div className="divider" />

        <div className="control-group">
          <label>Time Range</label>
          <div className="range-buttons">
            {QUICK_RANGES.map((r, i) => (
              <button key={i} className={`range-btn${rangeIdx === i ? " active" : ""}`} onClick={() => setRangeIdx(i)}>
                {r.label}
              </button>
            ))}
          </div>
        </div>

        {isCustom && (
          <>
            <div className="divider" />
            <div className="control-group">
              <label>From</label>
              <input type="datetime-local" value={customStart} onChange={e => setCustomStart(e.target.value)} />
            </div>
            <div className="control-group">
              <label>To</label>
              <input type="datetime-local" value={customEnd} onChange={e => setCustomEnd(e.target.value)} />
            </div>
          </>
        )}

        <div className="divider" />

        <div className="control-group">
          <label style={{ visibility: "hidden" }}>_</label>
          <button
            onClick={handleFetch}
            disabled={loadingR || loadingA || loadingMetrics}
            style={{
              background: loadingR || loadingA ? "rgba(16,185,129,0.5)" : "#10b981",
              color: "#ffffff", border: "none", borderRadius: 7,
              padding: "8px 24px", fontFamily: "'Space Mono', monospace",
              fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
              cursor: loadingR || loadingA ? "not-allowed" : "pointer",
            }}
          >
            {loadingR || loadingA ? "Loading…" : "Fetch"}
          </button>
        </div>
      </div>

      {/* Readings error banner */}
      {errorR && (
        <div style={{ background: "#fee2e2", color: "#b91c1c", padding: "12px 20px", borderRadius: 8, marginBottom: 20, border: "1px solid #f87171", fontFamily: "'DM Sans', sans-serif", fontSize: 13 }}>
          <strong>Error:</strong> {errorR}
        </div>
      )}

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <ReadingsPanel readings={readings} loading={loadingR} fetched={fetchedR} failed={failedR} />
        <AnomalyPanel
          anomalies={anomalies}
          loading={loadingA}
          fetched={fetchedA}
          noRunYet={noRunYet}
          unavailable={anomalyUnavailable}
        />
      </div>

      {fetchedA && anomalies.length > 0 && (
        <div style={{ marginTop: 16, display: "flex", gap: 20, fontFamily: "'Space Mono', monospace", fontSize: 10, color: "#94a3b8", letterSpacing: 0.5, textTransform: "uppercase", alignItems: "center" }}>
          <span style={{ marginRight: 4 }}>Score:</span>
          {[
            { color: "#059669", label: "Normal < 1.5" },
            { color: "#d97706", label: "Elevated ≥ 1.5" },
            { color: "#ea580c", label: "High ≥ 2" },
            { color: "#dc2626", label: "Critical ≥ 3" },
          ].map(s => (
            <span key={s.label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: s.color, display: "inline-block" }} />
              {s.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}