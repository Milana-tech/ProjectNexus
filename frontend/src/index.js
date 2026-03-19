import React, { useState } from 'react';
import ReactDOM from 'react-dom/client';
import GreenhouseDashboard from './Dashboard';
import MeasurementsView from './MeasurementsView';
import MergedReadingsTable from './MergedReadingsTable';
import './index.css';

const tabs = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'measurements', label: 'Measurements & Anomalies' },
    { id: 'combined', label: 'Combined View' },
];

function App() {
    const [active, setActive] = useState('dashboard');

    return (
        <div>
            {/* Tab bar */}
            <div style={{
                display: 'flex',
                gap: 0,
                background: '#ffffff',
                borderBottom: '1px solid #e2e8f0',
                padding: '0 32px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            }}>
                {tabs.map(t => (
                    <button
                        key={t.id}
                        onClick={() => setActive(t.id)}
                        style={{
                            background: 'none',
                            border: 'none',
                            borderBottom: active === t.id ? '2px solid #10b981' : '2px solid transparent',
                            color: active === t.id ? '#059669' : '#94a3b8',
                            fontFamily: "'Space Mono', monospace",
                            fontSize: 11,
                            fontWeight: active === t.id ? 700 : 400,
                            letterSpacing: 1,
                            textTransform: 'uppercase',
                            padding: '14px 20px',
                            cursor: 'pointer',
                            transition: 'all 0.15s',
                        }}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            {active === 'dashboard' && <GreenhouseDashboard />}
            {active === 'measurements' && <MeasurementsView />}
            {active === 'combined' && <MergedReadingsTable />}
        </div>
    );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);