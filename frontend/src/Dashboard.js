import { useState, useEffect, useRef, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import "./dashboard.css";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const COLOR_PALETTE = [
  "#2563eb", "#10b981", "#f59e0b", "#ef4444",
  "#8b5cf6", "#06b6d4", "#f97316", "#84cc16",
];

const MAX_METRICS = 4;

const DEMO_ENTITY_NAME = "Zone 1";
const DEMO_METRIC_NAME = "temperature";
const DEMO_RANGE_MS    = 6 * 60 * 60 * 1000;

function slotColor(i) { return COLOR_PALETTE[i % COLOR_PALETTE.length]; }

async function fetchEntities() {
  const res = await fetch(`${API_BASE}/entities`);
  if (!res.ok) throw new Error(`Failed to fetch entities (${res.status})`);
  const data = await res.json();
  return data.map((e) => ({ id: String(e.id), label: e.name }));
}

async function fetchMetrics(entityId) {
  const res = await fetch(`${API_BASE}/metrics?entity_id=${entityId}`);
  if (!res.ok) throw new Error(`Failed to fetch metrics (${res.status})`);
  const data = await res.json();
  return data.map((m) => ({ id: String(m.id), name: m.name, unit: m.unit ?? "" }));
}

async function fetchConfig() {
  const res = await fetch(`${API_BASE}/config`);
  if (!res.ok) throw new Error("Failed to fetch config");
  return res.json();
}

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
  if (range <= 86400000)
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString([], { weekday: "short", day: "numeric" });
}

function DemoBanner({ onDismiss }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8,
      padding: "10px 16px", marginBottom: 16, fontSize: 13, color: "#1d4ed8",
    }}>
      <span>🌱 <strong>Demo mode</strong> — showing seeded data</span>
      <button onClick={onDismiss} style={{
        background: "none", border: "none", cursor: "pointer",
        fontSize: 16, color: "#93c5fd", padding: "0 4px",
      }}>✕</button>
    </div>
  );
}

function MultiMetricChart({ slots, slotDataMap, fromTs, toTs }) {
  const range       = toTs - fromTs;
  const ticks       = generateTicks(fromTs, toTs, 6);
  const activeSlots = slots.filter((s) => s.metric);
  const units       = [...new Set(activeSlots.map((s) => s.metric.unit || ""))];
  const normalize   = units.length > 2;
  const unitAxisMap = {};
  if (!normalize) units.forEach((u, i) => { unitAxisMap[u] = i === 0 ? "left" : "right"; });

  const allTimes = [...new Set(
    slots.flatMap((s) => (slotDataMap[s.id]?.data ?? []).map((d) => d.time))
  )].sort((a, b) => a - b);

  const slotMax = {};
  slots.forEach((s) => {
    const vals = (slotDataMap[s.id]?.data ?? []).map((d) => d.value);
    slotMax[s.id] = vals.length ? Math.max(...vals) : 1;
  });

  const chartData = allTimes.map((t) => {
    const pt = { time: t };
    slots.forEach((s) => {
      const e = (slotDataMap[s.id]?.data ?? []).find((d) => d.time === t);
      if (e) pt[`metric_${s.id}`] = normalize
        ? parseFloat(((e.value / (slotMax[s.id] || 1)) * 100).toFixed(2))
        : e.value;
    });
    return pt;
  });

  const anyLoading = slots.some((s) => slotDataMap[s.id]?.loading);

  return (
    <div className="chart-card">
      <div className="chart-title">
        {activeSlots.length === 0 ? "Add metrics above to start plotting"
          : activeSlots.map((s) => s.metric.name).join(" · ")}
        {normalize && <span style={{ marginLeft: 8, fontSize: 11, color: "#94a3b8" }}>(normalized %)</span>}
      </div>

      {anyLoading && <div className="loading-overlay"><div className="spinner" />FETCHING DATA…</div>}

      {!anyLoading && chartData.length === 0 ? (
        <div className="empty-state">
          {activeSlots.length === 0 ? "Select at least one metric to see data" : "No readings in selected range"}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={360}>
          <LineChart data={chartData} margin={{ top: 5, right: 60, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="time" type="number" scale="time" domain={[fromTs, toTs]} ticks={ticks}
              tickFormatter={(t) => formatTick(t, range)}
              tick={{ fill: "#94a3b8", fontSize: 11, fontFamily: "Space Mono" }}
              axisLine={{ stroke: "#e2e8f0" }} tickLine={false} />

            {normalize ? (
              <YAxis yAxisId="normalized" domain={[0, 100]} axisLine={false} tickLine={false} width={45}
                tick={{ fill: "#94a3b8", fontSize: 11, fontFamily: "Space Mono" }}
                tickFormatter={(v) => `${v}%`}
                label={{ value: "Normalized %", angle: -90, position: "insideLeft", offset: 10,
                  style: { fill: "#94a3b8", fontSize: 10, fontFamily: "Space Mono" } }} />
            ) : (
              units.map((unit, i) => (
                <YAxis key={unit || `ax${i}`} yAxisId={unitAxisMap[unit]}
                  orientation={i === 0 ? "left" : "right"} domain={["auto", "auto"]}
                  axisLine={false} tickLine={false} width={50}
                  tick={{ fill: "#94a3b8", fontSize: 11, fontFamily: "Space Mono" }}
                  tickFormatter={(v) => unit ? `${v}${unit}` : String(v)}
                  label={{ value: unit || "Value", angle: -90,
                    position: i === 0 ? "insideLeft" : "insideRight",
                    offset: i === 0 ? 10 : -10,
                    style: { fill: "#94a3b8", fontSize: 10, fontFamily: "Space Mono" } }} />
              ))
            )}

            <Tooltip content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              return (
                <div style={{ background: "rgba(255,255,255,0.97)", border: "1px solid #e2e8f0",
                  borderRadius: 10, padding: "10px 14px", fontSize: 13, color: "#1e293b",
                  boxShadow: "0 4px 20px rgba(0,0,0,0.10)" }}>
                  <div style={{ marginBottom: 6, color: "#94a3b8", fontSize: 11, fontFamily: "Space Mono, monospace" }}>
                    {new Date(label).toLocaleString()}
                  </div>
                  {payload.map((p) => {
                    const slot = slots.find((s) => `metric_${s.id}` === p.dataKey);
                    const unit = normalize ? "%" : (slot?.metric?.unit ?? "");
                    return (
                      <div key={p.dataKey} style={{ display: "flex", gap: 12, justifyContent: "space-between" }}>
                        <span style={{ color: "#475569" }}>{p.name}</span>
                        <strong style={{ color: p.color }}>{p.value}{unit ? ` ${unit}` : ""}</strong>
                      </div>
                    );
                  })}
                </div>
              );
            }} />

            <Legend wrapperStyle={{ fontFamily: "Space Mono", fontSize: 11, paddingTop: 12, color: "#64748b" }} />

            {slots.map((slot, idx) => {
              if (!slot.metric) return null;
              const yId = normalize ? "normalized" : (unitAxisMap[slot.metric.unit || ""] ?? "left");
              return (
                <Line key={slot.id} yAxisId={yId} type="monotone"
                  dataKey={`metric_${slot.id}`} name={slot.metric.name}
                  stroke={slotColor(idx)} strokeWidth={2} dot={false}
                  activeDot={{ r: 4, fill: slotColor(idx) }} connectNulls={false} />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

function MetricRow({ slot, index, metrics, loadingMetrics, onRemove, onChangeMetric }) {
  const color = slotColor(index);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 10px",
      background: "#f8fafc", borderRadius: 8, border: `1px solid ${color}33`, marginBottom: 6 }}>
      <div style={{ width: 12, height: 12, borderRadius: "50%", background: color, flexShrink: 0 }} />
      <select value={slot.metric?.id ?? ""} disabled={loadingMetrics} style={{ flex: 1, fontSize: 13 }}
        onChange={(e) => { const m = metrics.find((x) => x.id === e.target.value); onChangeMetric(slot.id, m ?? null); }}>
        <option value="">— select metric —</option>
        {metrics.map((m) => <option key={m.id} value={m.id}>{m.name}{m.unit ? ` (${m.unit})` : ""}</option>)}
      </select>
      <button onClick={() => onRemove(slot.id)}
        style={{ background: "none", border: "1px solid #e2e8f0", borderRadius: 6,
          cursor: "pointer", padding: "2px 8px", fontSize: 13, color: "#64748b" }}>✕</button>
    </div>
  );
}

function StatCard({ label, value, unit, color }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: color ?? "#0f172a" }}>
        {value ?? "–"}{unit && <span className="stat-unit">{unit}</span>}
      </div>
    </div>
  );
}

function DropdownError({ message }) {
  return <div style={{ color: "#b91c1c", fontSize: 12, marginTop: 4 }}>⚠️ {message}</div>;
}

let slotCounter = 0;
function newSlotId() { return ++slotCounter; }

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
  const [loadingMetrics,  setLoadingMetrics]  = useState(false);
  const [metricError,     setMetricError]     = useState(null);

  const [metricSlots,     setMetricSlots]     = useState([]);
  const [slotDataMap,     setSlotDataMap]     = useState({});
  const [lastUpdated,     setLastUpdated]     = useState(null);

  const [demoMode,        setDemoMode]        = useState(false);
  const [showDemoBanner,  setShowDemoBanner]  = useState(false);

  const intervalsRef = useRef({});
  const abortRefs    = useRef({});

  const loadSlot = useCallback(async (slotId, metricId, start, end) => {
    if (abortRefs.current[slotId]) abortRefs.current[slotId].abort();
    abortRefs.current[slotId] = new AbortController();
    setSlotDataMap((prev) => ({ ...prev, [slotId]: { ...(prev[slotId] ?? {}), loading: true, error: null } }));
    try {
      const qs = new URLSearchParams({
        metric_id: String(metricId),
        start: new Date(start).toISOString(),
        end:   new Date(end).toISOString(),
        limit: "2000",
      });
      const res  = await fetch(`${API_BASE}/readings?${qs}`, { signal: abortRefs.current[slotId].signal });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      const json = await res.json();
      const data = (Array.isArray(json.readings) ? json.readings : []).map((r) => ({
        time: new Date(r.timestamp).getTime(), value: r.value,
      }));
      setSlotDataMap((prev) => ({ ...prev, [slotId]: { data, loading: false, error: null } }));
      if (data.length > 0) setLastUpdated(Date.now());
    } catch (err) {
      if (err.name === "AbortError") return;
      setSlotDataMap((prev) => ({ ...prev, [slotId]: { data: [], loading: false, error: err.message } }));
    }
  }, []);

  const startPolling = useCallback((slotId, metricId, start, end) => {
    stopPolling(slotId);
    loadSlot(slotId, metricId, start, end);
    intervalsRef.current[slotId] = setInterval(() => loadSlot(slotId, metricId, start, end), 10_000);
  }, [loadSlot]); 

  function stopPolling(slotId) {
    clearInterval(intervalsRef.current[slotId]);
    delete intervalsRef.current[slotId];
    abortRefs.current[slotId]?.abort();
    delete abortRefs.current[slotId];
  }

  useEffect(() => {
    const iv = intervalsRef.current;
    const ab = abortRefs.current;
    return () => {
      Object.keys(iv).forEach((id) => clearInterval(iv[id]));
      Object.keys(ab).forEach((id) => ab[id].abort());
    };
  }, []);

  useEffect(() => {
    if (rangeError) return;
    metricSlots.forEach((slot) => {
      if (slot.metric) startPolling(slot.id, slot.metric.id, fromTs, toTs);
    });
  }, [fromTs, toTs, rangeError]); 

  useEffect(() => {
    setLoadingEntities(true);
    Promise.all([fetchConfig(), fetchEntities()])
      .then(([config, ents]) => {
        if (config?.quick_ranges) {
          setQuickRanges(config.quick_ranges);
          const def = Number.isInteger(config.default_range_index) ? config.default_range_index : 1;
          setActiveRange(def);
          const now = Date.now();
          setToTs(now);
          setFromTs(now - (config.quick_ranges[def]?.ms ?? 6 * 60 * 60 * 1000));
        }
        if (config?.app_title) setAppTitle(config.app_title);
        setEntities(ents);
        setLoadingEntities(false);
        activateDemo(ents); 
      })
      .catch((err) => { setEntityError(err.message ?? "Could not load entities."); setLoadingEntities(false); });
  }, []); 

  useEffect(() => {
    if (!selectedEntity) return;
    setDemoMode(false);
    setShowDemoBanner(false);
    setLoadingMetrics(true);
    setMetricError(null);
    setMetrics([]);
    setMetricSlots((prev) => { prev.forEach((s) => stopPolling(s.id)); return []; });
    setSlotDataMap({});
    fetchMetrics(selectedEntity)
      .then((ms) => { setMetrics(ms); setLoadingMetrics(false); })
      .catch((err) => { setMetricError(err.message ?? "Could not load metrics."); setLoadingMetrics(false); });
  }, [selectedEntity]); 

  async function activateDemo(allEntities) {
    const entity = allEntities.find((e) => e.label.toLowerCase() === DEMO_ENTITY_NAME.toLowerCase());
    if (!entity) return;
    let ms;
    try { ms = await fetchMetrics(entity.id); } catch { return; }
    const metric = ms.find((m) => m.name.toLowerCase() === DEMO_METRIC_NAME.toLowerCase());
    if (!metric) return;

    const now = Date.now();
    const demoFrom = now - DEMO_RANGE_MS;
    const demoTo   = now;

    Object.keys(intervalsRef.current).forEach(stopPolling);

    setMetrics(ms);
    setFromTs(demoFrom);
    setToTs(demoTo);
    setActiveRange(-1);
    setRangeError(null);
    setLoadingMetrics(false);
    setMetricError(null);
    const slotId = newSlotId();
    setMetricSlots([{ id: slotId, metric }]);
    setSlotDataMap({});
    setDemoMode(true);
    setShowDemoBanner(true);
    startPolling(slotId, metric.id, demoFrom, demoTo);
  }

  function addSlot() {
    if (metricSlots.length >= MAX_METRICS) return;
    setMetricSlots((prev) => [...prev, { id: newSlotId(), metric: null }]);
  }

  function removeSlot(slotId) {
    stopPolling(slotId);
    setMetricSlots((prev) => prev.filter((s) => s.id !== slotId));
    setSlotDataMap((prev) => { const n = { ...prev }; delete n[slotId]; return n; });
  }

  function changeSlotMetric(slotId, metric) {
    setMetricSlots((prev) => prev.map((s) => s.id === slotId ? { ...s, metric } : s));
    if (metric && !rangeError) startPolling(slotId, metric.id, fromTs, toTs);
    else { stopPolling(slotId); setSlotDataMap((prev) => ({ ...prev, [slotId]: { data: [], loading: false, error: null } })); }
  }

  function applyQuickRange(idx) {
    const now = Date.now();
    setActiveRange(idx); setToTs(now);
    setFromTs(now - (quickRanges[idx]?.ms ?? 6 * 60 * 60 * 1000));
    setRangeError(null);
  }

  function handleFromChange(e) {
    const ts = new Date(e.target.value).getTime();
    if (isNaN(ts)) { setRangeError("Invalid start date/time format."); return; }
    setActiveRange(-1); setFromTs(ts);
    setRangeError(ts >= toTs ? "Start must be before end." : null);
  }

  function handleToChange(e) {
    const ts = new Date(e.target.value).getTime();
    if (isNaN(ts)) { setRangeError("Invalid end date/time format."); return; }
    setActiveRange(-1); setToTs(ts);
    setRangeError(ts <= fromTs ? "End must be after start." : null);
  }

  const hasEntity  = selectedEntity || demoMode;
  const allValues  = metricSlots.flatMap((s) => (slotDataMap[s.id]?.data ?? []).map((d) => d.value));
  const statsColor = slotColor(0);

  return (
    <div className="dash">
      <div className="header" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div className="header-badge"><span className="pulse" />Live Monitor</div>
          <h1 style={{ marginTop: 8 }}>{appTitle}</h1>
          {lastUpdated && (
            <div style={{ marginTop: 6, color: "#64748b", fontSize: 13 }}>
              Last updated: {new Date(lastUpdated).toLocaleString()}
            </div>
          )}
        </div>
        <button onClick={() => activateDemo(entities)} style={{
          background: "#f0fdf4", color: "#15803d", border: "1px solid #86efac",
          borderRadius: 8, padding: "8px 16px", fontSize: 13, fontWeight: 600,
          cursor: "pointer", alignSelf: "flex-start",
        }}>🌱 Load Demo</button>
      </div>

      {demoMode && showDemoBanner && <DemoBanner onDismiss={() => setShowDemoBanner(false)} />}

      <div className="controls">
        <div className="control-group">
          <label htmlFor="entity-select">Entity</label>
          {loadingEntities ? (
            <select id="entity-select" disabled><option>Loading entities…</option></select>
          ) : (
            <select id="entity-select" value={selectedEntity ?? ""}
              onChange={(e) => setSelectedEntity(e.target.value)}>
              {entities.length === 0 && !entityError && <option value="">No entities available</option>}
              {entities.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}
            </select>
          )}
          {entityError && <DropdownError message={entityError} />}
        </div>

        <div className="divider" />

        <div className="control-group">
          <label>Quick range</label>
          <div className="range-buttons">
            {quickRanges.map((r, i) => (
              <button key={i} className={`range-btn${activeRange === i ? " active" : ""}`}
                onClick={() => applyQuickRange(i)}>{r.label}</button>
            ))}
          </div>
        </div>

        <div className="divider" />

        <div className="control-group">
          <label htmlFor="from-date">From</label>
          <input id="from-date" type="datetime-local" value={toLocalDatetime(fromTs)}
            onChange={handleFromChange}
            style={rangeError ? { borderColor: "#ef4444", outline: "none" } : {}} />
        </div>
        <div className="control-group">
          <label htmlFor="to-date">To</label>
          <input id="to-date" type="datetime-local" value={toLocalDatetime(toTs)}
            onChange={handleToChange}
            style={rangeError ? { borderColor: "#ef4444", outline: "none" } : {}} />
        </div>

      </div>

      {rangeError && (
        <div style={{ background: "#fff7ed", color: "#c2410c", padding: "10px 18px",
          borderRadius: 8, marginBottom: 16, border: "1px solid #fdba74",
          fontSize: 13, display: "flex", alignItems: "center", gap: 8 }}>
          ⚠️ <strong>Invalid time range:</strong>&nbsp;{rangeError}&nbsp;Chart will not update until corrected.
        </div>
      )}

      <div style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#475569" }}>
            Metrics ({metricSlots.length}/{MAX_METRICS})
          </span>
          <button onClick={addSlot}
            disabled={metricSlots.length >= MAX_METRICS || !hasEntity || loadingMetrics}
            style={{
              background: (metricSlots.length >= MAX_METRICS || !hasEntity || loadingMetrics) ? "#f1f5f9" : "#2563eb",
              color:      (metricSlots.length >= MAX_METRICS || !hasEntity || loadingMetrics) ? "#94a3b8" : "#fff",
              border: "none", borderRadius: 8, padding: "6px 14px",
              fontSize: 13, fontWeight: 600,
              cursor: (metricSlots.length >= MAX_METRICS || !hasEntity || loadingMetrics) ? "not-allowed" : "pointer",
            }}>
            + Add Metric
          </button>
        </div>

        {metricSlots.length === 0 && (
          <div style={{ color: "#94a3b8", fontSize: 13, padding: "8px 0" }}>
            {hasEntity ? 'Click "+ Add Metric" to start plotting data.' : "Select an entity first."}
          </div>
        )}

        {metricSlots.map((slot, idx) => (
          <MetricRow key={slot.id} slot={slot} index={idx} metrics={metrics}
            loadingMetrics={loadingMetrics} onRemove={removeSlot} onChangeMetric={changeSlotMetric} />
        ))}

        {metricError && <DropdownError message={metricError} />}
      </div>

      <div className="stats-row">
        <StatCard label="Data points"    value={allValues.length || "–"} unit="" color={statsColor} />
        <StatCard label="Active metrics" value={metricSlots.filter((s) => s.metric).length || "–"} unit="" color={statsColor} />
        <StatCard label="Overall min"    value={allValues.length ? Math.min(...allValues).toFixed(2) : "–"} unit="" color={statsColor} />
        <StatCard label="Overall max"    value={allValues.length ? Math.max(...allValues).toFixed(2) : "–"} unit="" color={statsColor} />
      </div>

      <MultiMetricChart slots={metricSlots} slotDataMap={slotDataMap} fromTs={fromTs} toTs={toTs} />
    </div>
  );
}