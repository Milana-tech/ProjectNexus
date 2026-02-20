-- Create zones table
CREATE TABLE IF NOT EXISTS zones (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create sensor_readings table
CREATE TABLE IF NOT EXISTS sensor_readings (
    id BIGSERIAL PRIMARY KEY,
    metric_name VARCHAR(255) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    anomaly_flag BOOLEAN DEFAULT FALSE,
    anomaly_score DOUBLE PRECISION,
    anomaly_type VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    zone_id INTEGER NOT NULL REFERENCES zones(id) ON DELETE CASCADE
);

-- Create forecasts table
CREATE TABLE IF NOT EXISTS forecasts (
    id BIGSERIAL PRIMARY KEY,
    zone_id INTEGER NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    metric_name VARCHAR(255) NOT NULL,
    forecast_timestamp TIMESTAMPTZ NOT NULL,
    predicted_value DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_sensor_readings_zone_id ON sensor_readings(zone_id);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_timestamp ON sensor_readings(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_metric_name ON sensor_readings(metric_name);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_anomaly_flag ON sensor_readings(anomaly_flag);
CREATE INDEX IF NOT EXISTS idx_forecasts_zone_id ON forecasts(zone_id);
CREATE INDEX IF NOT EXISTS idx_forecasts_metric_name ON forecasts(metric_name);
CREATE INDEX IF NOT EXISTS idx_forecasts_forecast_timestamp ON forecasts(forecast_timestamp);

-- Convert sensor_readings to a TimescaleDB hypertable for better time-series performance
SELECT create_hypertable('sensor_readings', 'timestamp', if_not_exists => TRUE);

-- Insert sample zones for testing
INSERT INTO zones (name, description) VALUES
    ('Zone A - North Greenhouse', 'Primary greenhouse north section'),
    ('Zone B - South Greenhouse', 'Primary greenhouse south section'),
    ('Zone C - Nursery', 'Nursery and propagation area')
ON CONFLICT (name) DO NOTHING;
