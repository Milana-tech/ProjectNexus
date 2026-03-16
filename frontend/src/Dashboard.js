import { useState, useEffect, useCallback, useRef } from "react";
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
  "http://localhost:8000";

const COLOR_PALETTE = [
  "#2563eb", // blue
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#f97316", // orange
  "#84cc16", // lime
];

function getMetricColor(metricName, allMetricNames) {
  const idx = allMetricNames.indexOf(metricName);
  return COLOR_PALETTE[idx % COLOR_PALETTE.length];
}

async function fetchEntities() {
  const res = await fetch(`${API_BASE}/zones`);
  if (!res.ok) throw new Error(`Failed to fetch entities: ${res.statusText}`);
  const data = await res.json();
  return data.map((e) => ({ id: String(e.id), label: e.name }));
}

async function fetchMetrics(entityId) {
  const res = await fetch(`${API_BASE}/metrics?entity_id=${entityId}`);
  if (!res.ok) throw new Error(`Failed to fetch metrics: ${res.statusText}`);
  const data = await res.json();
  return data.map((m) => ({ id: String(m.id), name: m.name, unit: m.unit ?? "" }));
}

async function fetchConfig() {
  const res = await fetch(`${API_BASE}/config`);
  if (!res.ok) throw new Error("Failed to fetch config");
  return res.json();
}

// useReadings — data-fetch hook using universal GET /readings endpoint

function useReadings({ metricId, start, end }) {
  const [data, setData]       = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const abortRef              = useRef(null);

  const load = useCallback(async () => {
    if (!metricId || !start || !end) {
      setData([]);
      return;
    }

    // Cancel previous in-flight request
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const qs = new URLSearchParams({
        metric_id: String(metricId),
        start:     new Date(start).toISOString(),
        end:       new Date(end).toISOString(),
        limit:     "2000",
      });

      const res = await fetch(`${API_BASE}/readings?${qs}`, {
        signal: abortRef.current.signal,
      });

      if (!res.ok) throw new Error(`API error ${res.status}: ${res.statusText}`);

      const json = await res.json();

      // Map to chart-consumable shape: { time (ms), value }
      const readings = Array.isArray(json.readings) ? json.readings : [];
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
  }, [metricId, start, end]);

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

// Utility helpers

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

// MetricLineChart — generic, accepts metric_name + unit as props

function CustomTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "rgba(255,255,255,0.97)",
      border: "1px solid #e2e8f0",
      borderRadius: 10,
      padding: "10px 14px",
      fontSize: 13,
      color: "#1e293b",
      boxShadow: "0 4px 20px rgba(0,0,0,0.10)",
    }}>
      <div style={{ marginBottom: 6, color: "#94a3b8", fontSize: 11, fontFamily: "Space Mono, monospace" }}>
        {new Date(label).toLocaleString()}
      </div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ display: "flex", gap: 12, justifyContent: "space-between" }}>
          <span style={{ color: "#475569" }}>{p.name}</span>
          <strong style={{ color: p.color }}>
            {p.value}{unit ? ` ${unit}` : ""}
          </strong>
        </div>
      ))}
    </div>
  );
}

function MetricLineChart({ data, loading, metricName, unit, fromTs, toTs, color }) {
  const range = toTs - fromTs;
  const ticks = generateTicks(fromTs, toTs, 6);

  const yLabel = unit
    ? `${metricName} (${unit})`
    : metricName || "Value";

  const tickFormatter = unit
    ? (v) => `${v}${unit}`
    : (v) => String(v);

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
              dot={false}
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

// Main dashboard

export default function Dashboard() {
  const [appTitle,      setAppTitle]      = useState("Project Nexus — Dashboard");
  const [quickRanges,   setQuickRanges]   = useState([]);
  const [activeRange,   setActiveRange]   = useState(1);
  const [fromTs,        setFromTs]        = useState(() => Date.now() - 6 * 60 * 60 * 1000);
  const [toTs,          setToTs]          = useState(() => Date.now());

  const [entities,      setEntities]      = useState([]);
  const [selectedEntity, setSelectedEntity] = useState("");
  const [loadingEntities, setLoadingEntities] = useState(true);

  const [metrics,       setMetrics]       = useState([]);   // [{id, name, unit}]
  const [selectedMetric, setSelectedMetric] = useState(null); // {id, name, unit}
  const [loadingMetrics, setLoadingMetrics] = useState(false);

  const [lastUpdated,   setLastUpdated]   = useState(null);
  const [configError,   setConfigError]   = useState(null);

  // Derive color from metric name within current metrics list
  const metricNames = metrics.map((m) => m.name);
  const chartColor  = selectedMetric
    ? getMetricColor(selectedMetric.name, metricNames)
    : COLOR_PALETTE[0];

  // Load config + entities on mount
  useEffect(() => {
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
        setConfigError(err.message);
        setLoadingEntities(false);
      });
  }, []);

  // Load metrics when entity changes
  useEffect(() => {
    if (!selectedEntity) return;
    setLoadingMetrics(true);
    setSelectedMetric(null);
    setMetrics([]);

    fetchMetrics(selectedEntity)
      .then((ms) => {
        setMetrics(ms);
        if (ms.length) setSelectedMetric(ms[0]);
        setLoadingMetrics(false);
      })
      .catch(() => {
        setLoadingMetrics(false);
      });
  }, [selectedEntity]);

  // Fetch readings via hook
  const { data, loading: loadingData, error: dataError } = useReadings({
    metricId: selectedMetric?.id ?? null,
    start:    fromTs,
    end:      toTs,
  });

  // Update last-updated timestamp whenever new data arrives
  useEffect(() => {
    if (data.length > 0) setLastUpdated(Date.now());
  }, [data]);

  // Quick range handler
  function applyQuickRange(idx) {
    const now = Date.now();
    setActiveRange(idx);
    setToTs(now);
    setFromTs(now - (quickRanges[idx]?.ms ?? 6 * 60 * 60 * 1000));
  }

  // Stats
  const latestValue = data.at(-1)?.value;
  const avgValue = data.length
    ? (data.reduce((s, r) => s + r.value, 0) / data.length).toFixed(2)
    : null;
  const minValue = data.length
    ? Math.min(...data.map((r) => r.value)).toFixed(2)
    : null;
  const maxValue = data.length
    ? Math.max(...data.map((r) => r.value)).toFixed(2)
    : null;

  const unit       = selectedMetric?.unit ?? "";
  const metricName = selectedMetric?.name ?? "";

  const error = configError || dataError;

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

      {/* Error banner */}
      {error && (
        <div style={{
          background: "#fee2e2", color: "#b91c1c",
          padding: "12px 20px", borderRadius: 8,
          marginBottom: 20, border: "1px solid #f87171",
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Controls */}
      <div className="controls">

        {/* Entity selector */}
        <div className="control-group">
          <label htmlFor="entity-select">Entity</label>
          {loadingEntities ? (
            <select id="entity-select" disabled><option>Loading…</option></select>
          ) : (
            <select
              id="entity-select"
              value={selectedEntity}
              onChange={(e) => setSelectedEntity(e.target.value)}
            >
              {entities.map((e) => (
                <option key={e.id} value={e.id}>{e.label}</option>
              ))}
            </select>
          )}
        </div>

        {/* Metric selector */}
        <div className="control-group">
          <label htmlFor="metric-select">Metric</label>
          {loadingMetrics ? (
            <select id="metric-select" disabled><option>Loading…</option></select>
          ) : (
            <select
              id="metric-select"
              value={selectedMetric?.id ?? ""}
              onChange={(e) => {
                const m = metrics.find((x) => x.id === e.target.value);
                setSelectedMetric(m ?? null);
              }}
            >
              {metrics.length === 0 && (
                <option value="">No metrics available</option>
              )}
              {metrics.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}{m.unit ? ` (${m.unit})` : ""}
                </option>
              ))}
            </select>
          )}
        </div>

        <div className="divider" />

        {/* Quick range buttons */}
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

        {/* Custom date range */}
        <div className="control-group">
          <label htmlFor="from-date">From</label>
          <input
            id="from-date"
            type="datetime-local"
            value={toLocalDatetime(fromTs)}
            onChange={(e) => {
              const ts = new Date(e.target.value).getTime();
              if (!isNaN(ts)) {
                setActiveRange(-1);
                setFromTs(ts);
                if (ts > toTs) setToTs(ts + 3_600_000);
              }
            }}
          />
        </div>

        <div className="control-group">
          <label htmlFor="to-date">To</label>
          <input
            id="to-date"
            type="datetime-local"
            value={toLocalDatetime(toTs)}
            onChange={(e) => {
              const ts = new Date(e.target.value).getTime();
              if (!isNaN(ts)) {
                setActiveRange(-1);
                setToTs(ts);
                if (ts < fromTs) setFromTs(ts - 3_600_000);
              }
            }}
          />
        </div>
      </div>

      {/* Stats row */}
      <div className="stats-row">
        <StatCard label="Current"  value={latestValue ?? "–"} unit={unit} color={chartColor} />
        <StatCard label="Average"  value={avgValue}           unit={unit} color={chartColor} />
        <StatCard label="Min"      value={minValue}           unit={unit} color={chartColor} />
        <StatCard label="Max"      value={maxValue}           unit={unit} color={chartColor} />
      </div>

      {/* Chart */}
      <MetricLineChart
        data={data}
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