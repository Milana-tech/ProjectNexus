import { useState, useEffect } from "react";
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

// API layer — prefer environment variable `REACT_APP_API_URL`, fallback to `VITE_API_URL` or localhost
const API_BASE =
  process.env.REACT_APP_API_URL || process.env.VITE_API_URL || "http://localhost:8000";

async function fetchZones() {
  const res = await fetch(`${API_BASE}/zones`);
  if (!res.ok) throw new Error(`Failed to fetch zones: ${res.statusText}`);
  const data = await res.json();
  // backend returns [{ id: number, name: string }]
  return data.map((z) => ({ id: String(z.id), label: z.name }));
}

async function fetchReadings(zoneId, from, to) {
  const qs = new URLSearchParams({
    start: new Date(from).toISOString(),
    end: new Date(to).toISOString(),
  });
  const res = await fetch(`${API_BASE}/readings/${zoneId}?${qs.toString()}`);
  if (!res.ok) throw new Error(`Failed to fetch readings: ${res.statusText}`);
  const data = await res.json();
  // Backend returns timestamps in ISO format — convert to epoch ms for the chart
  return data.map((r) => ({
    timestamp: new Date(r.timestamp).getTime(),
    temperature: r.temperature,
    humidity: r.humidity,
  }));
}

const QUICK_RANGES = [
  { label: "Last hour", ms: 60 * 60 * 1000 },
  { label: "Last 6 h", ms: 6 * 60 * 60 * 1000 },
  { label: "Last day", ms: 24 * 60 * 60 * 1000 },
  { label: "Last week", ms: 7 * 24 * 60 * 60 * 1000 },
];

function toLocalDatetime(ts) {
  if (!ts || isNaN(ts)) return "";
  const d = new Date(ts);
  // Adjust for local timezone offset before converting to ISO string
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function generateTicks(from, to, count = 2) {
  if (from >= to) return [from]; // Prevent negative or zero steps
  const ticks = [];
  const step = (to - from) / (count - 1);
  for (let i = 0; i < count; i++) {
    ticks.push(Math.round(from + i * step));
  }
  return ticks;
}

function formatTick(t, range) {
  const d = new Date(t);
  if (range <= 24 * 60 * 60 * 1000) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } else {
    return d.toLocaleDateString([], { weekday: "short", day: "numeric" });
  }
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = new Date(label);
  return (
    <div style={{
      background: "rgba(255,255,255,0.97)",
      border: "1px solid #e2e8f0",
      borderRadius: 10,
      padding: "10px 14px",
      fontSize: 13,
      color: "#1e293b",
      boxShadow: "0 4px 20px rgba(0,0,0,0.10)",
      backdropFilter: "blur(8px)",
    }}>
      <div style={{ marginBottom: 6, color: "#94a3b8", fontSize: 11, fontFamily: "Space Mono, monospace" }}>
        {d.toLocaleString()}
      </div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ display: "flex", gap: 12, justifyContent: "space-between" }}>
          <span style={{ color: "#475569" }}>{p.name}</span>
          <strong style={{ color: p.color }}>{p.value}{p.dataKey === "temperature" ? " °C" : " %"}</strong>
        </div>
      ))}
    </div>
  );
}

export default function GreenhouseDashboard() {
  const [zones, setZones] = useState([]);
  const [selectedZone, setSelectedZone] = useState("");
  const [activeRange, setActiveRange] = useState(1);
  const [fromTs, setFromTs] = useState(Date.now() - QUICK_RANGES[1].ms);
  const [toTs, setToTs] = useState(Date.now());
  const [readings, setReadings] = useState([]);
  const [loadingZones, setLoadingZones] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchZones().then((z) => {
      setZones(z);
      setSelectedZone(z[0]?.id ?? "");
      setLoadingZones(false);
    }).catch(err => {
      setError("Failed to load zones. Please try again later.");
      setLoadingZones(false);
    });
  }, []);

  useEffect(() => {
    if (!selectedZone) return;

    let active = true;
    setLoadingData(true);
    setError(null);

    fetchReadings(selectedZone, fromTs, toTs).then((data) => {
      if (active) {
        setReadings(data);
        setLoadingData(false);
      }
    }).catch(err => {
      if (active) {
        setError("Failed to load readings. Please try again later.");
        setLoadingData(false);
      }
    });

    return () => {
      active = false;
    };
  }, [selectedZone, fromTs, toTs]);

  function applyQuickRange(idx) {
    const now = Date.now();
    setActiveRange(idx);
    setFromTs(now - QUICK_RANGES[idx].ms);
    setToTs(now);
  }

  const latestTemp = readings.at(-1)?.temperature;
  const latestHum = readings.at(-1)?.humidity;
  const avgTemp = readings.length ? (readings.reduce((s, r) => s + r.temperature, 0) / readings.length).toFixed(1) : "–";
  const avgHum = readings.length ? (readings.reduce((s, r) => s + r.humidity, 0) / readings.length).toFixed(1) : "–";

  const chartData = readings.map((r) => ({ ...r, time: r.timestamp }));
  const range = toTs - fromTs;
  const ticks = generateTicks(fromTs, toTs, 6);

  return (
    <div className="dash">
      <div className="header">
        <div>
          <div className="header-badge"><span className="pulse" />Live Monitor</div>
          <h1 style={{ marginTop: 8 }}>Project Nexus — Environmental Dashboard</h1>
        </div>
      </div>

      {error && (
        <div style={{ background: "#fee2e2", color: "#b91c1c", padding: "12px 20px", borderRadius: 8, marginBottom: 20, border: "1px solid #f87171", fontFamily: "system-ui, sans-serif" }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="controls">
        <div className="control-group">
          <label htmlFor="zone-select">Zone</label>
          {loadingZones ? (
            <select id="zone-select" disabled><option>Loading zones…</option></select>
          ) : (
            <select id="zone-select" value={selectedZone} onChange={(e) => setSelectedZone(e.target.value)}>
              {zones.map((z) => <option key={z.id} value={z.id}>{z.label}</option>)}
            </select>
          )}
        </div>

        <div className="divider" />

        <div className="control-group">
          <label>Quick range</label>
          <div className="range-buttons">
            {QUICK_RANGES.map((r, i) => (
              <button key={i} className={`range-btn${activeRange === i ? " active" : ""}`} onClick={() => applyQuickRange(i)}>
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <div className="divider" />

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
                if (ts > toTs) setToTs(ts + 3600000); // Auto-push 'To' date if invalid
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
                if (ts < fromTs) setFromTs(ts - 3600000); // Auto-push 'From' date if invalid
              }
            }}
          />
        </div>
      </div>

      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Current Temp</div>
          <div className="stat-value temp">{latestTemp ?? "–"}<span className="stat-unit">°C</span></div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Avg Temp</div>
          <div className="stat-value temp">{avgTemp}<span className="stat-unit">°C</span></div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Current Humidity</div>
          <div className="stat-value hum">{latestHum ?? "–"}<span className="stat-unit">%</span></div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Avg Humidity</div>
          <div className="stat-value hum">{avgHum}<span className="stat-unit">%</span></div>
        </div>
      </div>

      <div className="chart-card">
        <div className="chart-title">
          Temperature & Humidity — {zones.find(z => z.id === selectedZone)?.label ?? selectedZone}
        </div>
        {loadingData && (
          <div className="loading-overlay">
            <div className="spinner" />FETCHING DATA…
          </div>
        )}
        {!loadingData && readings.length === 0 ? (
          <div className="empty-state">No readings in selected range</div>
        ) : (
          <ResponsiveContainer width="100%" height={340}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
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
                yAxisId="temp"
                domain={["auto", "auto"]}
                tick={{ fill: "#2563eb", fontSize: 11, fontFamily: "Space Mono" }}
                axisLine={false}
                tickLine={false}
                width={40}
                tickFormatter={(v) => `${v}°`}
              />
              <YAxis
                yAxisId="hum"
                orientation="right"
                domain={["auto", "auto"]}
                tick={{ fill: "#059669", fontSize: 11, fontFamily: "Space Mono" }}
                axisLine={false}
                tickLine={false}
                width={40}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ fontFamily: "Space Mono", fontSize: 11, paddingTop: 12, color: "#64748b" }}
              />
              <Line
                yAxisId="temp"
                type="monotone"
                dataKey="temperature"
                name="Temperature"
                stroke="#2563eb"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: "#2563eb" }}
              />
              <Line
                yAxisId="hum"
                type="monotone"
                dataKey="humidity"
                name="Humidity"
                stroke="#10b981"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: "#10b981" }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}