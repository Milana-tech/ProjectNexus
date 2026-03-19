import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import "./dashboard.css";

const API_BASE =
  process.env.REACT_APP_API_URL ||
  "http://localhost:8001";

const COLOR_PALETTE = [
  "#2563eb",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#f97316",
  "#84cc16",
];

function getMetricColor(metricName, allMetricNames) {
  const idx = allMetricNames.indexOf(metricName);
  return COLOR_PALETTE[idx % COLOR_PALETTE.length];
}

async function fetchEntities() {
  const res = await fetch(`${API_BASE}/entities`);
  if (!res.ok) throw new Error(`Failed to fetch entities (${res.status}: ${res.statusText})`);
  const data = await res.json();
  return data.map((e) => ({ id: String(e.id), label: e.name }));
}

async function fetchMetrics(entityId) {
  const res = await fetch(`${API_BASE}/metrics?entity_id=${entityId}`);
  if (!res.ok) throw new Error(`Failed to fetch metrics (${res.status}: ${res.statusText})`);
  const data = await res.json();
  return data.map((m) => ({ id: String(m.id), name: m.name, unit: m.unit ?? "" }));
}

async function fetchConfig() {
  const res = await fetch(`${API_BASE}/config`);
  if (!res.ok) throw new Error("Failed to fetch config");
  return res.json();
}

async function fetchAlgorithms() {
  const res = await fetch(`${API_BASE}/algorithms`);
  if (!res.ok) throw new Error(`Failed to fetch algorithms (${res.status}: ${res.statusText})`);
  const data = await res.json();
  return Array.isArray(data)
    ? data.map((a) => ({ name: String(a.name ?? ""), label: String(a.label ?? a.name ?? "") }))
    : [];
}

// ─── useReadings hook ─────────────────────────────────────────────────────────

function useReadings({ metricId, start, end, skip }) {
  const [data, setData]       = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const abortRef              = useRef(null);

  const load = useCallback(async () => {
    if (!metricId || !start || !end || skip) {
      setData([]);
      return;
    }

    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const qs = new URLSearchParams({
        metric_id: String(metricId),
        start_time: new Date(start).toISOString(),
        end_time:   new Date(end).toISOString(),
        limit:     "2000",
      });

      const res = await fetch(`${API_BASE}/readings?${qs}`, {
        signal: abortRef.current.signal,
      });

      if (!res.ok) throw new Error(`API error ${res.status}: ${res.statusText}`);

      const json = await res.json();
      const readings = Array.isArray(json)
        ? json
        : Array.isArray(json.readings)
          ? json.readings
          : [];
      setData(
        readings.map((r) => ({
          time:  new Date(r.timestamp).getTime(),
          value: r.value,
        }))
      );
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message ?? "Failed to load readings.");
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [metricId, start, end, skip]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 10_000);
    return () => {
      clearInterval(interval);
      if (abortRef.current) abortRef.current.abort();
    };
  }, [load]);

  return { data, loading, error };
}

// ─── helpers ──────────────────────────────────────────────────────────────────

function toLocalDatetime(ts) {
  if (!ts || isNaN(ts)) return "";
  const d = new Date(ts);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function generateTicks(from, to, count = 6) {
  if (from >= to) return [from];
  const step = (to - from) / Math.max(count - 1, 1);
  return Array.from({ length: count }, (_, i) => Math.round(from + i * step));
}

function formatTick(t, range) {
  const d = new Date(t);
  if (range <= 24 * 60 * 60 * 1000)
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString([], { weekday: "short", day: "numeric" });
}

function parseApiTimestamp(value) {
  const direct = new Date(value).getTime();
  if (!isNaN(direct)) return direct;
  if (typeof value === "string") {
    const normalized = new Date(value.replace(" ", "T")).getTime();
    if (!isNaN(normalized)) return normalized;
  }
  return null;
}

function toSecondKey(ts) {
  return Number.isFinite(ts) ? Math.floor(ts / 1000) : null;
}

function parseApiScore(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function toRunErrorMessage(detail) {
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  return "Failed to run anomaly detection. Please try again.";
}

// ─── sub-components ───────────────────────────────────────────────────────────

export function CustomTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  const isAnomaly = !!point?.isAnomaly;
  const anomalyScore = point?.anomalyScore;
  const hasValidTimestamp = Number.isFinite(new Date(label).getTime());
  const primaryValue = payload[0]?.value;
  const hasValue = primaryValue !== null && primaryValue !== undefined;
  const hasScore = Number.isFinite(anomalyScore);
  const showAnomalyDetails = isAnomaly && hasValidTimestamp && hasValue && hasScore;
  return (
    <div
      data-testid="metric-tooltip"
      style={{
      background: "rgba(255,255,255,0.97)",
      border: "1px solid #e2e8f0",
      borderRadius: 10,
      padding: "10px 14px",
      fontSize: 13,
      color: "#1e293b",
      boxShadow: "0 4px 20px rgba(0,0,0,0.10)",
      position: "relative",
    }}
    >
      <div style={{ marginBottom: 6, color: "#94a3b8", fontSize: 11, fontFamily: "Space Mono, monospace" }}>
        {hasValidTimestamp ? new Date(label).toLocaleString() : "Unknown time"}
      </div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ display: "flex", gap: 12, justifyContent: "space-between" }}>
          <span style={{ color: "#475569" }}>{p.name}</span>
          <strong style={{ color: p.color }}>
            {p.value}{unit ? ` ${unit}` : ""}
          </strong>
        </div>
      ))}
      {showAnomalyDetails && (
        <div
          data-testid="anomaly-tooltip-details"
          style={{
            marginTop: 8,
            paddingTop: 8,
            borderTop: "1px solid #e2e8f0",
            borderRadius: 8,
            background: "rgba(254, 226, 226, 0.55)",
            padding: "8px 10px",
          }}
        >
          <div style={{ color: "#991b1b", fontWeight: 700, marginBottom: 6 }}>Anomaly Event</div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span style={{ color: "#7f1d1d" }}>Timestamp</span>
            <strong style={{ color: "#7f1d1d" }}>{new Date(label).toLocaleString()}</strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span style={{ color: "#7f1d1d" }}>Value</span>
            <strong style={{ color: "#7f1d1d" }}>
              {primaryValue}{unit ? ` ${unit}` : ""}
            </strong>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span style={{ color: "#7f1d1d" }}>Score</span>
            <strong style={{ color: "#7f1d1d" }}>{anomalyScore}</strong>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricLineChart({ data, loading, metricName, unit, fromTs, toTs, color }) {
  const range        = toTs - fromTs;
  const ticks        = generateTicks(fromTs, toTs, 6);
  const yLabel       = unit ? `${metricName} (${unit})` : metricName || "Value";
  const tickFormatter = unit ? (v) => `${v}${unit}` : (v) => String(v);

  return (
    <div className="chart-card">
      <div className="chart-title">{yLabel}</div>

      {loading && (
        <div className="loading-overlay">
          <div className="spinner" />FETCHING DATA…
        </div>
      )}

      {!loading && data.length === 0 ? (
        <div className="empty-state">No readings in selected range</div>
      ) : (
        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey="time"
              type="number"
              scale="time"
              domain={[fromTs, toTs]}
              ticks={ticks}
              tickFormatter={(t) => formatTick(t, range)}
              tick={{ fill: "#94a3b8", fontSize: 11, fontFamily: "Space Mono" }}
              axisLine={{ stroke: "#e2e8f0" }}
              tickLine={false}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fill: color, fontSize: 11, fontFamily: "Space Mono" }}
              axisLine={false}
              tickLine={false}
              width={50}
              tickFormatter={tickFormatter}
              label={{
                value: yLabel,
                angle: -90,
                position: "insideLeft",
                offset: 10,
                style: { fill: "#94a3b8", fontSize: 10, fontFamily: "Space Mono" },
              }}
            />
            <Tooltip content={<CustomTooltip unit={unit} />} />
            <Legend
              wrapperStyle={{
                fontFamily: "Space Mono",
                fontSize: 11,
                paddingTop: 12,
                color: "#64748b",
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              name={metricName || "Value"}
              stroke={color}
              strokeWidth={2}
              dot={(props) => {
                if (!props?.payload?.isAnomaly) return null;
                return (
                  <circle
                    cx={props.cx}
                    cy={props.cy}
                    r={4}
                    fill="#dc2626"
                    stroke="#ffffff"
                    strokeWidth={1.5}
                  />
                );
              }}
              activeDot={{ r: 4, fill: color }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

function StatCard({ label, value, unit, color }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: color ?? "#0f172a" }}>
        {value ?? "–"}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
    </div>
  );
}

function DropdownError({ message }) {
  return (
    <div style={{ color: "#b91c1c", fontSize: 12, marginTop: 4 }}>
      ⚠️ {message}
    </div>
  );
}

// ─── main dashboard ───────────────────────────────────────────────────────────

export default function Dashboard() {
  const [appTitle,        setAppTitle]        = useState("Project Nexus — Dashboard");
  const [quickRanges,     setQuickRanges]     = useState([]);
  const [activeRange,     setActiveRange]     = useState(1);

  const [fromTs,          setFromTs]          = useState(() => Date.now() - 6 * 60 * 60 * 1000);
  const [toTs,            setToTs]            = useState(() => Date.now());
  const [rangeError,      setRangeError]      = useState(null);

  const [entities,        setEntities]        = useState([]);
  const [selectedEntity,  setSelectedEntity]  = useState(null);
  const [loadingEntities, setLoadingEntities] = useState(true);
  const [entityError,     setEntityError]     = useState(null); 

  const [metrics,         setMetrics]         = useState([]);
  const [selectedMetric,  setSelectedMetric]  = useState(null);
  const [loadingMetrics,  setLoadingMetrics]  = useState(false);
  const [metricError,     setMetricError]     = useState(null); 

  const [algorithms,         setAlgorithms]      = useState([]);
  const [selectedAlgorithm,  setSelectedAlgorithm] = useState("");
  const [loadingAlgorithms,  setLoadingAlgorithms] = useState(false);
  const [algorithmError,     setAlgorithmError]    = useState(null);
  const [runLoading,         setRunLoading]        = useState(false);
  const [runError,           setRunError]          = useState(null);
  const [showAnomalies,      setShowAnomalies]     = useState(false);
  const [anomalyLoading,     setAnomalyLoading]    = useState(false);
  const [anomalies,          setAnomalies]         = useState([]);
  const [anomalyError,       setAnomalyError]      = useState(null);

  const [lastUpdated,     setLastUpdated]     = useState(null);

  const metricNames = metrics.map((m) => m.name);
  const chartColor  = selectedMetric
    ? getMetricColor(selectedMetric.name, metricNames)
    : COLOR_PALETTE[0];

  useEffect(() => {
    setLoadingEntities(true);
    setEntityError(null);

    Promise.all([fetchConfig(), fetchEntities()])
      .then(([config, ents]) => {
        if (config?.quick_ranges) {
          setQuickRanges(config.quick_ranges);
          const def = Number.isInteger(config.default_range_index)
            ? config.default_range_index : 1;
          setActiveRange(def);
          const now = Date.now();
          setToTs(now);
          setFromTs(now - (config.quick_ranges[def]?.ms ?? 6 * 60 * 60 * 1000));
        }
        if (config?.app_title) setAppTitle(config.app_title);
        setEntities(ents);
        if (ents.length) setSelectedEntity(ents[0].id);
        setLoadingEntities(false);
      })
      .catch((err) => {
        setEntityError(err.message ?? "Could not load entities.");
        setLoadingEntities(false);
      });
  }, []);

  useEffect(() => {
    if (!selectedEntity) return;

    setLoadingMetrics(true);
    setMetricError(null);
    setMetrics([]);
    setSelectedMetric(null);

    fetchMetrics(selectedEntity)
      .then((ms) => {
        setMetrics(ms);
        if (ms.length) setSelectedMetric(ms[0]);
        setLoadingMetrics(false);
      })
      .catch((err) => {
        setMetricError(err.message ?? "Could not load metrics.");
        setLoadingMetrics(false);
      });
  }, [selectedEntity]);

  useEffect(() => {
    setLoadingAlgorithms(true);
    setAlgorithmError(null);

    fetchAlgorithms()
      .then((rows) => {
        const valid = rows.filter((a) => a.name && a.label);
        setAlgorithms(valid);
        setSelectedAlgorithm((current) =>
          valid.some((a) => a.name === current) ? current : ""
        );
        setLoadingAlgorithms(false);
      })
      .catch((err) => {
        setAlgorithmError(err.message ?? "Could not load algorithms.");
        setAlgorithms([]);
        setSelectedAlgorithm("");
        setLoadingAlgorithms(false);
      });
  }, []);

  // ── readings ─────────────────────────────────────────────────────────────
  const { data, loading: loadingData, error: dataError } = useReadings({
    metricId: selectedMetric?.id ?? null,
    start:    fromTs,
    end:      toTs,
    skip:     !!rangeError,
  });

  useEffect(() => {
    if (data.length > 0) setLastUpdated(Date.now());
  }, [data]);

  // ── quick range ───────────────────────────────────────────────────────────
  function applyQuickRange(idx) {
    const now = Date.now();
    setActiveRange(idx);
    setToTs(now);
    setFromTs(now - (quickRanges[idx]?.ms ?? 6 * 60 * 60 * 1000));
    setRangeError(null);
  }

  function handleFromChange(e) {
    const ts = new Date(e.target.value).getTime();
    if (isNaN(ts)) { setRangeError("Invalid start date/time format."); return; }
    setActiveRange(-1);
    setFromTs(ts);
    setRangeError(ts >= toTs ? "Start must be before end." : null);
  }

  function handleToChange(e) {
    const ts = new Date(e.target.value).getTime();
    if (isNaN(ts)) { setRangeError("Invalid end date/time format."); return; }
    setActiveRange(-1);
    setToTs(ts);
    setRangeError(ts <= fromTs ? "End must be after start." : null);
  }

  const loadAnomalies = useCallback(async ({ metricId, startTs, endTs }) => {
    if (!metricId || !startTs || !endTs) {
      setAnomalies([]);
      return;
    }

    setAnomalyLoading(true);
    setAnomalyError(null);
    try {
      const qs = new URLSearchParams({
        metric_id: String(metricId),
        start: new Date(startTs).toISOString(),
        end: new Date(endTs).toISOString(),
      });

      const res = await fetch(`${API_BASE}/anomalies?${qs}`);
      if (!res.ok) throw new Error(`Failed to fetch anomalies (${res.status}: ${res.statusText})`);

      const json = await res.json();
      const rows = Array.isArray(json) ? json : [];
      const next = rows
        .filter((a) => !!a?.flag)
        .map((a) => {
          const ts = parseApiTimestamp(a.timestamp);
          const score = parseApiScore(a.score);
          if (ts === null) return null;
          return { ts, score };
        })
        .filter((entry) => entry !== null);

      setAnomalies(next);
    } catch (err) {
      setAnomalyError(err.message ?? "Failed to fetch anomalies.");
      setAnomalies([]);
    } finally {
      setAnomalyLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!showAnomalies || !selectedMetric?.id || !fromTs || !toTs || rangeError) {
      setAnomalies([]);
      setAnomalyError(null);
      setAnomalyLoading(false);
      return;
    }

    loadAnomalies({
      metricId: selectedMetric.id,
      startTs: fromTs,
      endTs: toTs,
    });
  }, [showAnomalies, selectedMetric?.id, fromTs, toTs, rangeError, loadAnomalies]);

  async function handleRunDetection() {
    if (!selectedMetric?.id || !selectedAlgorithm || !fromTs || !toTs || rangeError || runLoading) return;

    const metricId = selectedMetric.id;
    const startTs = fromTs;
    const endTs = toTs;

    setRunLoading(true);
    setRunError(null);

    try {
      const qs = new URLSearchParams({
        metric_id: String(metricId),
        algorithm: selectedAlgorithm,
        start: new Date(startTs).toISOString(),
        end: new Date(endTs).toISOString(),
      });

      const res = await fetch(`${API_BASE}/anomalies/run?${qs}`, { method: "POST" });
      if (!res.ok) {
        let detail = null;
        try {
          const body = await res.json();
          detail = body?.detail ?? null;
        } catch {
          detail = null;
        }
        throw new Error(toRunErrorMessage(detail));
      }
      if (showAnomalies) {
        await loadAnomalies({ metricId, startTs, endTs });
      } else {
        setAnomalies([]);
      }
      setRunError(null);
    } catch (err) {
      const msg = typeof err?.message === "string" && err.message.trim()
        ? err.message.trim()
        : "Failed to run anomaly detection. Please try again.";
      setRunError(msg);
    } finally {
      setRunLoading(false);
    }
  }

  const latestValue = data.at(-1)?.value;
  const avgValue    = data.length
    ? (data.reduce((s, r) => s + r.value, 0) / data.length).toFixed(2) : null;
  const minValue    = data.length
    ? Math.min(...data.map((r) => r.value)).toFixed(2) : null;
  const maxValue    = data.length
    ? Math.max(...data.map((r) => r.value)).toFixed(2) : null;

  const unit       = selectedMetric?.unit ?? "";
  const metricName = selectedMetric?.name ?? "";
  const canShowRunDetectionButton =
    !!selectedMetric && !!fromTs && !!toTs && !rangeError;
  const runDetectionDisabled =
    !selectedMetric ||
    !selectedAlgorithm ||
    !fromTs ||
    !toTs ||
    !!rangeError ||
    runLoading;
  const chartData = useMemo(() => {
    if (!data.length) return [];
    if (!showAnomalies || !anomalies.length) return data;
    const anomalyMap = new Map(
      anomalies
        .map((entry) => {
          const key = toSecondKey(entry.ts);
          return key === null ? null : [key, entry.score];
        })
        .filter((entry) => entry !== null)
    );
    return data.map((point) => ({
      ...point,
      isAnomaly: anomalyMap.has(toSecondKey(point.time)),
      anomalyScore: anomalyMap.get(toSecondKey(point.time)) ?? null,
    }));
  }, [data, anomalies, showAnomalies]);

  return (
    <div className="dash">

      {/* Header */}
      <div className="header">
        <div>
          <div className="header-badge">
            <span className="pulse" />Live Monitor
          </div>
          <h1 style={{ marginTop: 8 }}>{appTitle}</h1>
          {lastUpdated && (
            <div style={{ marginTop: 6, color: "#64748b", fontSize: 13 }}>
              Last updated: {new Date(lastUpdated).toLocaleString()}
            </div>
          )}
        </div>
      </div>

      {dataError && (
        <div style={{
          background: "#fee2e2", color: "#b91c1c",
          padding: "12px 20px", borderRadius: 8,
          marginBottom: 20, border: "1px solid #f87171",
        }}>
          <strong>Error:</strong> {dataError}
        </div>
      )}

      {runError && (
        <div style={{
          background: "#fee2e2",
          color: "#b91c1c",
          padding: "12px 20px",
          borderRadius: 8,
          marginBottom: 20,
          border: "1px solid #f87171",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}>
          <div>
            <strong>Run failed:</strong> {runError}
          </div>
          <button
            type="button"
            onClick={() => setRunError(null)}
            style={{
              border: "1px solid #fca5a5",
              background: "#ffffff",
              color: "#b91c1c",
              borderRadius: 6,
              padding: "4px 8px",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="controls">
        <div className="control-group">
          <label htmlFor="entity-select">Entity</label>
          {loadingEntities ? (
            <select id="entity-select" disabled>
              <option>Loading entities…</option>
            </select>
          ) : (
            <select
              id="entity-select"
              value={selectedEntity ?? ""}
              onChange={(e) => setSelectedEntity(e.target.value)}
            >
              {entities.length === 0 && !entityError && (
                <option value="">No entities available</option>
              )}
              {entities.map((e) => (
                <option key={e.id} value={e.id}>{e.label}</option>
              ))}
            </select>
          )}

          {entityError && <DropdownError message={entityError} />}
        </div>

        <div className="control-group">
          <label htmlFor="metric-select">Metric</label>
          {!selectedEntity ? (
            <select id="metric-select" disabled>
              <option>Select an entity first</option>
            </select>
          ) : loadingMetrics ? (
            <select id="metric-select" disabled>
              <option>Loading metrics…</option>
            </select>
          ) : (
            <select
              id="metric-select"
              value={selectedMetric?.id ?? ""}
              onChange={(e) => {
                const m = metrics.find((x) => x.id === e.target.value);
                setSelectedMetric(m ?? null);
              }}
            >
              {metrics.length === 0 && !metricError && (
                <option value="">No metrics available</option>
              )}
              {metrics.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}{m.unit ? ` (${m.unit})` : ""}
                </option>
              ))}
            </select>
          )}

          {metricError && <DropdownError message={metricError} />}
        </div>

        <div className="control-group">
          <label htmlFor="algorithm-select">Algorithm</label>
          {loadingAlgorithms ? (
            <select id="algorithm-select" disabled>
              <option>Loading algorithms…</option>
            </select>
          ) : (
            <select
              id="algorithm-select"
              value={selectedAlgorithm}
              onChange={(e) => setSelectedAlgorithm(e.target.value)}
              disabled={algorithms.length === 0}
            >
              <option value="">Select algorithm</option>
              {algorithms.map((a) => (
                <option key={a.name} value={a.name}>
                  {a.label}
                </option>
              ))}
            </select>
          )}

          {algorithmError && <DropdownError message={algorithmError} />}
        </div>

        <div className="divider" />

        <div className="control-group">
          <label>Quick range</label>
          <div className="range-buttons">
            {quickRanges.map((r, i) => (
              <button
                key={i}
                className={`range-btn${activeRange === i ? " active" : ""}`}
                onClick={() => applyQuickRange(i)}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <div className="divider" />

        <div className="control-group">
          <label>&nbsp;</label>
          <button
            type="button"
            aria-pressed={showAnomalies}
            onClick={() => setShowAnomalies((v) => !v)}
            style={{
              background: showAnomalies ? "#dc2626" : "#e2e8f0",
              border: "1px solid",
              borderColor: showAnomalies ? "#dc2626" : "#cbd5e1",
              borderRadius: 7,
              color: showAnomalies ? "#ffffff" : "#334155",
              fontFamily: "Space Mono, monospace",
              fontSize: 12,
              padding: "8px 12px",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            Show Anomalies: {showAnomalies ? "ON" : "OFF"}
          </button>
        </div>

        <div className="control-group">
          <label htmlFor="from-date">From</label>
          <input
            id="from-date"
            type="datetime-local"
            value={toLocalDatetime(fromTs)}
            onChange={handleFromChange}
            style={rangeError ? { borderColor: "#ef4444", outline: "none" } : {}}
          />
        </div>

        <div className="control-group">
          <label htmlFor="to-date">To</label>
          <input
            id="to-date"
            type="datetime-local"
            value={toLocalDatetime(toTs)}
            onChange={handleToChange}
            style={rangeError ? { borderColor: "#ef4444", outline: "none" } : {}}
          />
        </div>

        {canShowRunDetectionButton && (
          <div className="control-group">
            <label>&nbsp;</label>
            <button
              type="button"
              disabled={runDetectionDisabled}
              onClick={handleRunDetection}
              style={{
                background: runDetectionDisabled ? "#e2e8f0" : "#10b981",
                border: "1px solid",
                borderColor: runDetectionDisabled ? "#cbd5e1" : "#10b981",
                borderRadius: 7,
                color: runDetectionDisabled ? "#64748b" : "#ffffff",
                fontFamily: "Space Mono, monospace",
                fontSize: 12,
                padding: "8px 12px",
                cursor: runDetectionDisabled ? "not-allowed" : "pointer",
                whiteSpace: "nowrap",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              {runLoading && (
                <span
                  style={{
                    width: 12,
                    height: 12,
                    border: "2px solid rgba(255,255,255,0.45)",
                    borderTopColor: "#ffffff",
                    borderRadius: "50%",
                    animation: "spin 0.8s linear infinite",
                  }}
                />
              )}
              {runLoading ? "Running..." : "Run Detection"}
            </button>
          </div>
        )}
      </div>

      {rangeError && (
        <div style={{
          background: "#fff7ed", color: "#c2410c",
          padding: "10px 18px", borderRadius: 8, marginBottom: 16,
          border: "1px solid #fdba74", fontSize: 13,
          display: "flex", alignItems: "center", gap: 8,
        }}>
          ⚠️ <strong>Invalid time range:</strong>&nbsp;{rangeError}&nbsp;
          Chart will not update until corrected.
        </div>
      )}

      {showAnomalies && anomalyLoading && (
        <div style={{
          background: "#eff6ff",
          color: "#1d4ed8",
          padding: "10px 18px",
          borderRadius: 8,
          marginBottom: 16,
          border: "1px solid #bfdbfe",
          fontSize: 13,
        }}>
          Loading anomaly markers...
        </div>
      )}

      {showAnomalies && anomalyError && (
        <div style={{
          background: "#fee2e2",
          color: "#b91c1c",
          padding: "10px 18px",
          borderRadius: 8,
          marginBottom: 16,
          border: "1px solid #fca5a5",
          fontSize: 13,
        }}>
          <strong>Anomaly fetch failed:</strong> {anomalyError}
        </div>
      )}

      {/* Stats */}
      <div className="stats-row">
        <StatCard label="Current" value={latestValue ?? "–"} unit={unit} color={chartColor} />
        <StatCard label="Average" value={avgValue}           unit={unit} color={chartColor} />
        <StatCard label="Min"     value={minValue}           unit={unit} color={chartColor} />
        <StatCard label="Max"     value={maxValue}           unit={unit} color={chartColor} />
      </div>

      {/* Chart */}
      <MetricLineChart
        data={chartData}
        loading={loadingData}
        metricName={metricName}
        unit={unit}
        fromTs={fromTs}
        toTs={toTs}
        color={chartColor}
      />
    </div>
  );
}
