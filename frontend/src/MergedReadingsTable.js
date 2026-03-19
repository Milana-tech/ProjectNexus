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

function mergeData(readings, anomalies) {
  const anomalyMap = {};
  for (const a of anomalies) {
    const key = new Date(a.timestamp).getTime();
    anomalyMap[key] = a;
  }
  return readings.map(r => {
    const key = new Date(r.timestamp).getTime();
    const anomaly = anomalyMap[key] || null;
    return {
      timestamp:  r.timestamp,
      value:      r.value,
      score:      anomaly ? anomaly.score : null,
      flag:       anomaly ? anomaly.flag  : null,
      hasAnomaly: anomaly !== null,
    };
  });
}

export default function MergedReadingsTable() {
  const [metrics, setMetrics]           = useState([]);
  const [metricId, setMetricId]         = useState("");
  const [rangeIdx, setRangeIdx]         = useState(1);
  const [customStart, setCustomStart]   = useState("");
  const [customEnd, setCustomEnd]       = useState("");
  const [rows, setRows]                 = useState([]);
  const [loading, setLoading]           = useState(false);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [error, setError]               = useState(null);
  const [fetched, setFetched]           = useState(false);
  const [noAnomalyRun, setNoAnomalyRun] = useState(false);
  const [metricName, setMetricName]     = useState("");

  // Load metrics on mount
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
    if (err) { setError(err); return; }
    const { start, end } = getRange();

    setError(null);
    setNoAnomalyRun(false);
    setRows([]);
    setFetched(false);
    setMetricName("");
    setLoading(true);

    try {
      const [readingsRes, anomaliesRes] = await Promise.all([
        fetch(`${API_URL}/readings?${new URLSearchParams({ metric_id: metricId, start, end })}`),
        fetch(`${API_URL}/anomalies?${new URLSearchParams({ metric_id: metricId, start, end })}`),
      ]);

      if (!readingsRes.ok) {
        const b = await readingsRes.json().catch(() => ({}));
        if (readingsRes.status === 404) throw new Error(`No data found for the selected metric and time range.`);
        if (readingsRes.status === 400) throw new Error(`Invalid request: ${b.detail || "please check your inputs."}`);
        throw new Error("Something went wrong loading readings. Please try again.");
      }

      const readingsData = await readingsRes.json();
      const readings     = readingsData.readings || [];
      setMetricName(readingsData.metric?.name || `Metric ${metricId}`);

      let anomalies = [];
      try {
        if (anomaliesRes.ok) {
          anomalies = await anomaliesRes.json();
          if (anomalies.length === 0) setNoAnomalyRun(true);
        } else {
          setNoAnomalyRun(true);
        }
      } catch {
        setNoAnomalyRun(true);
      }

      setRows(mergeData(readings, anomalies));
      setFetched(true);
    } catch (e) {
      const msg = typeof e.message === "string" && e.message.length < 200
        ? e.message
        : "Something went wrong. Please try again.";
      setError(msg);
      setRows([]);
      setFetched(false);
    } finally {
      setLoading(false);
    }
  };

  const isCustom     = QUICK_RANGES[rangeIdx].ms === null;
  const flaggedCount = rows.filter(r => r.flag).length;

  return (
    <div className="dash">
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      <div className="header">
        <div>
          <div className="header-badge"><span className="pulse" />Combined View</div>
          <h1 style={{ marginTop: 8 }}>Readings & Anomaly Status</h1>
          <p style={{ marginTop: 6, color: "#64748b", fontSize: 13, fontFamily: "'DM Sans', sans-serif" }}>
            Raw sensor values merged with anomaly detection results in a single view.
          </p>
        </div>
      </div>

      <div className="controls">
        {/* Metric dropdown */}
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
            disabled={loading || loadingMetrics}
            style={{
              background: loading ? "rgba(16,185,129,0.5)" : "#10b981",
              color: "#ffffff", border: "none", borderRadius: 7,
              padding: "8px 24px", fontFamily: "'Space Mono', monospace",
              fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Loading…" : "Fetch"}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background: "#fee2e2", color: "#b91c1c", padding: "12px 20px", borderRadius: 8, marginBottom: 20, border: "1px solid #f87171", fontFamily: "'DM Sans', sans-serif", fontSize: 13 }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {fetched && noAnomalyRun && rows.length > 0 && (
        <div style={{ background: "rgba(234,179,8,0.08)", border: "1px solid rgba(234,179,8,0.3)", borderRadius: 8, padding: "12px 20px", marginBottom: 20, display: "flex", alignItems: "center", gap: 10, fontFamily: "'Space Mono', monospace", fontSize: 11, color: "#92400e", letterSpacing: 0.5 }}>
          <span style={{ fontSize: 16 }}>⚠</span>
          No anomaly detection has been run for this metric yet — showing raw readings only.
          Run <strong>POST /anomalies/run</strong> to populate anomaly results.
        </div>
      )}

      {fetched && rows.length > 0 && (
        <div className="stats-row" style={{ gridTemplateColumns: "repeat(3, 1fr)", marginBottom: 20 }}>
          <div className="stat-card">
            <div className="stat-label">Metric</div>
            <div className="stat-value neutral" style={{ fontSize: 16 }}>{metricName}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Readings</div>
            <div className="stat-value neutral">{rows.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Flagged Anomalies</div>
            <div className="stat-value" style={{ color: flaggedCount > 0 ? "#dc2626" : "#059669" }}>
              {noAnomalyRun ? "—" : flaggedCount}
            </div>
          </div>
        </div>
      )}

      <div className="chart-card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "14px 24px", borderBottom: "1px solid #f1f5f9", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span className="chart-title" style={{ marginBottom: 0 }}>Combined Readings Table</span>
          {fetched && <span style={{ fontFamily: "'Space Mono', monospace", fontSize: 10, color: "#cbd5e1", letterSpacing: 0.5 }}>{rows.length} rows</span>}
        </div>

        {loading && (
          <div style={{ height: 200, display: "flex", alignItems: "center", justifyContent: "center", gap: 10, fontFamily: "'Space Mono', monospace", fontSize: 11, color: "#059669", letterSpacing: 2, textTransform: "uppercase" }}>
            <div style={{ width: 16, height: 16, border: "2px solid rgba(16,185,129,0.2)", borderTopColor: "#10b981", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
            Loading…
          </div>
        )}

        {!loading && fetched && rows.length === 0 && (
          <div className="empty-state">No data found for the selected metric and time range</div>
        )}

        {!loading && !fetched && (
          <div className="empty-state">Select a metric and press fetch</div>
        )}

        {!loading && rows.length > 0 && (
          <div style={{ overflowY: "auto", maxHeight: 520 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#f8fafc", position: "sticky", top: 0 }}>
                  {["Timestamp", "Value", "Z-Score", "Status"].map(h => (
                    <th key={h} style={{ padding: "11px 24px", textAlign: "left", fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 1, textTransform: "uppercase", color: "#94a3b8", borderBottom: "1px solid #e2e8f0", background: "#f8fafc" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid #f1f5f9", background: row.flag ? "rgba(220,38,38,0.04)" : (i % 2 === 0 ? "#ffffff" : "#f8fafc") }}>
                    <td style={{ padding: "12px 24px", fontFamily: "'Space Mono', monospace", fontSize: 11, color: "#64748b" }}>
                      {row.flag && <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: "#dc2626", marginRight: 8, verticalAlign: "middle" }} />}
                      {fmt(row.timestamp)}
                    </td>
                    <td style={{ padding: "12px 24px", fontFamily: "'Space Mono', monospace", fontSize: 13, color: "#2563eb", fontWeight: 700 }}>{row.value}</td>
                    <td style={{ padding: "12px 24px", fontFamily: "'Space Mono', monospace", fontSize: 13, color: scoreColor(row.score), fontWeight: row.score != null ? 700 : 400 }}>{fmtScore(row.score)}</td>
                    <td style={{ padding: "12px 24px" }}>
                      {row.hasAnomaly ? (
                        row.flag ? (
                          <span style={{ background: "rgba(220,38,38,0.08)", color: "#dc2626", border: "1px solid rgba(220,38,38,0.25)", borderRadius: 6, padding: "3px 10px", fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 1, textTransform: "uppercase", fontWeight: 700 }}>⚑ Anomaly</span>
                        ) : (
                          <span style={{ background: "rgba(16,185,129,0.08)", color: "#059669", border: "1px solid rgba(16,185,129,0.2)", borderRadius: 6, padding: "3px 10px", fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 1, textTransform: "uppercase" }}>✓ Normal</span>
                        )
                      ) : (
                        <span style={{ color: "#cbd5e1", fontFamily: "'Space Mono', monospace", fontSize: 10, letterSpacing: 1, textTransform: "uppercase" }}>— No data</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {fetched && rows.length > 0 && !noAnomalyRun && (
        <div style={{ marginTop: 14, display: "flex", gap: 20, alignItems: "center", fontFamily: "'Space Mono', monospace", fontSize: 10, color: "#94a3b8", letterSpacing: 0.5, textTransform: "uppercase" }}>
          <span style={{ marginRight: 4 }}>Z-Score:</span>
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