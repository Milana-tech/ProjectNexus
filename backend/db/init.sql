-- Create zones table (top-level physical/logical grouping)
CREATE TABLE IF NOT EXISTS zones (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create devices table (physical device within a zone)
CREATE TABLE IF NOT EXISTS devices (
    id BIGSERIAL PRIMARY KEY,
    zone_id BIGINT NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (zone_id, name)
);

-- Create metrics table (what is being measured, linked to a device)
CREATE TABLE IF NOT EXISTS metrics (
    id BIGSERIAL PRIMARY KEY,
    device_id BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (device_id, name)
);

-- Create readings table (raw time-series data only)
CREATE TABLE IF NOT EXISTS readings (
    id BIGSERIAL,
    timestamp TIMESTAMPTZ NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    zone_id BIGINT NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    metric_id BIGINT NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    PRIMARY KEY (id, timestamp)
);

-- Create algorithms table (registry of detection/forecast algorithms)
CREATE TABLE IF NOT EXISTS algorithms (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(255),
    version VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create anomaly_results table (separate from readings, traceable to algorithm)
CREATE TABLE IF NOT EXISTS anomaly_results (
    id BIGSERIAL PRIMARY KEY,
    metric_id BIGINT NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    algorithm_id BIGINT NOT NULL REFERENCES algorithms(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    anomaly_score DOUBLE PRECISION,
    anomaly_flag BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create forecast_results table (traceable to metric and algorithm)
CREATE TABLE IF NOT EXISTS forecast_results (
    id BIGSERIAL PRIMARY KEY,
    metric_id BIGINT NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    algorithm_id BIGINT NOT NULL REFERENCES algorithms(id) ON DELETE CASCADE,
    forecast_timestamp TIMESTAMPTZ NOT NULL,
    predicted_value DOUBLE PRECISION NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for readings
CREATE INDEX IF NOT EXISTS idx_readings_metric_id ON readings(metric_id);
CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp DESC);

-- Indexes for anomaly_results
CREATE INDEX IF NOT EXISTS idx_anomaly_results_metric_id ON anomaly_results(metric_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_results_algorithm_id ON anomaly_results(algorithm_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_results_timestamp ON anomaly_results(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_results_flag ON anomaly_results(anomaly_flag);

-- Indexes for forecast_results
CREATE INDEX IF NOT EXISTS idx_forecast_results_metric_id ON forecast_results(metric_id);
CREATE INDEX IF NOT EXISTS idx_forecast_results_algorithm_id ON forecast_results(algorithm_id);
CREATE INDEX IF NOT EXISTS idx_forecast_results_forecast_timestamp ON forecast_results(forecast_timestamp DESC);

-- Indexes for metrics and devices
CREATE INDEX IF NOT EXISTS idx_metrics_device_id ON metrics(device_id);
CREATE INDEX IF NOT EXISTS idx_devices_zone_id ON devices(zone_id);
CREATE INDEX IF NOT EXISTS idx_readings_zone_id ON readings(zone_id);

-- Convert readings to a TimescaleDB hypertable for time-series performance
SELECT create_hypertable('readings', 'timestamp', if_not_exists => TRUE);

INSERT INTO algorithms (name, type, version)
VALUES ('zscore', 'anomaly_detection', '1.0')
ON CONFLICT DO NOTHING;
