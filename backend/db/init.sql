-- Create zones table 
SELECT 'CREATE DATABASE nexus_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'nexus_test')\gexec
CREATE TABLE IF NOT EXISTS zones (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create devices table 
CREATE TABLE IF NOT EXISTS devices (
    id         BIGSERIAL PRIMARY KEY,
    zone_id    BIGINT NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    name       VARCHAR(255) NOT NULL,
    type       VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (zone_id, name)
);

-- Create metrics table
CREATE TABLE IF NOT EXISTS metrics (
    id         BIGSERIAL PRIMARY KEY,
    device_id  BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    name       VARCHAR(255) NOT NULL,
    unit       VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (device_id, name)
);

-- Create readings table (raw time-series data only)
-- NOTE: composite PK is (id, timestamp) to satisfy TimescaleDB hypertable requirement.
-- The additional UNIQUE (metric_id, timestamp) constraint is required so that
-- anomaly_results can reference a specific reading via a composite FK.
CREATE TABLE IF NOT EXISTS readings (
    id         BIGSERIAL,
    timestamp  TIMESTAMPTZ NOT NULL,
    value      DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    zone_id    BIGINT NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    metric_id  BIGINT NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    PRIMARY KEY (id, timestamp),
    UNIQUE (metric_id, timestamp) 
);

-- Create algorithms table
CREATE TABLE IF NOT EXISTS algorithms (
    id         BIGSERIAL PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    type       VARCHAR(255),
    version    VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure algorithm names are unique so seeding is idempotent across restarts
CREATE UNIQUE INDEX IF NOT EXISTS idx_algorithms_name_unique ON algorithms (name);

-- Create anomaly_results table (separate from readings, traceable to algorithm)
-- PLEASE NOTE: no FK from anomaly_results.timestamp to readings.timestamp because
-- readings is a TimescaleDB hypertable (and hypertables cannot be FK targets)
-- Timestamp is guaranteed by /anomalies/run, which sources timestamps directly from readings.
-- Orphan rows are possible only via direct DB writes or if readings are deleted after detection.
CREATE TABLE IF NOT EXISTS anomaly_results (
    id            BIGSERIAL PRIMARY KEY,
    metric_id     BIGINT NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    algorithm_id  BIGINT NOT NULL REFERENCES algorithms(id) ON DELETE CASCADE,
    timestamp     TIMESTAMPTZ NOT NULL,
    anomaly_score DOUBLE PRECISION,
    anomaly_flag  BOOLEAN NOT NULL DEFAULT FALSE,
    metadata      JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_anomaly_results_reading
        FOREIGN KEY (metric_id, timestamp)
        REFERENCES readings (metric_id, timestamp)
        ON DELETE CASCADE
);

-- Create forecast_results table (traceable to metric and algorithm)
-- forecast_timestamp is future-facing — no FK to readings is appropriate here.
CREATE TABLE IF NOT EXISTS forecast_results (
    id                 BIGSERIAL PRIMARY KEY,
    metric_id          BIGINT NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    algorithm_id       BIGINT NOT NULL REFERENCES algorithms(id) ON DELETE CASCADE,
    forecast_timestamp TIMESTAMPTZ NOT NULL,
    predicted_value    DOUBLE PRECISION NOT NULL,
    metadata           JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- readings
CREATE INDEX IF NOT EXISTS idx_readings_metric_id  ON readings(metric_id);
CREATE INDEX IF NOT EXISTS idx_readings_timestamp   ON readings(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_readings_metric_timestamp ON readings(metric_id, timestamp ASC);
CREATE INDEX IF NOT EXISTS idx_readings_zone_id     ON readings(zone_id);

-- anomaly_results
CREATE INDEX IF NOT EXISTS idx_anomaly_results_metric_id    ON anomaly_results(metric_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_results_algorithm_id ON anomaly_results(algorithm_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_results_timestamp    ON anomaly_results(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_results_flag         ON anomaly_results(anomaly_flag);

-- forecast_results
CREATE INDEX IF NOT EXISTS idx_forecast_results_metric_id          ON forecast_results(metric_id);
CREATE INDEX IF NOT EXISTS idx_forecast_results_algorithm_id       ON forecast_results(algorithm_id);
CREATE INDEX IF NOT EXISTS idx_forecast_results_forecast_timestamp ON forecast_results(forecast_timestamp DESC);

-- metrics / devices
CREATE INDEX IF NOT EXISTS idx_metrics_device_id ON metrics(device_id);
CREATE INDEX IF NOT EXISTS idx_devices_zone_id   ON devices(zone_id);

-- =============================================================================
-- TimescaleDB hypertable
-- Must be created after the table definition and before any data is inserted.
-- =============================================================================
SELECT create_hypertable('readings', 'timestamp', if_not_exists => TRUE);

-- =============================================================================
-- Seed data
-- =============================================================================

INSERT INTO algorithms (name, type, version)
VALUES ('zscore', 'anomaly_detection', '1.0')
ON CONFLICT (name) DO NOTHING;

INSERT INTO zones (name, description) VALUES
    ('Zone A', 'Environmental zone A'),
    ('Zone B', 'Environmental zone B')
ON CONFLICT (name) DO NOTHING;

INSERT INTO devices (zone_id, name, type) VALUES
    ((SELECT id FROM zones WHERE name = 'Zone A'), 'Device 1', 'sensor'),
    ((SELECT id FROM zones WHERE name = 'Zone B'), 'Device 2', 'sensor')
ON CONFLICT (zone_id, name) DO NOTHING;
INSERT INTO metrics (device_id, name, unit) VALUES
    ((SELECT id FROM devices WHERE name = 'Device 1'), 'temperature', 'celsius'),
    ((SELECT id FROM devices WHERE name = 'Device 1'), 'humidity',    'percent'),
    ((SELECT id FROM devices WHERE name = 'Device 2'), 'temperature', 'celsius'),
    ((SELECT id FROM devices WHERE name = 'Device 2'), 'humidity',    'percent')
ON CONFLICT (device_id, name) DO NOTHING;

\connect nexus_test

CREATE TABLE IF NOT EXISTS zones (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS devices (
    id         BIGSERIAL PRIMARY KEY,
    zone_id    BIGINT NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    name       VARCHAR(255) NOT NULL,
    type       VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (zone_id, name)
);

CREATE TABLE IF NOT EXISTS metrics (
    id         BIGSERIAL PRIMARY KEY,
    device_id  BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    name       VARCHAR(255) NOT NULL,
    unit       VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (device_id, name)
);

CREATE TABLE IF NOT EXISTS readings (
    id         BIGSERIAL,
    timestamp  TIMESTAMPTZ NOT NULL,
    value      DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    zone_id    BIGINT NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    metric_id  BIGINT NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    PRIMARY KEY (id, timestamp),
    UNIQUE (metric_id, timestamp) 
);

CREATE TABLE IF NOT EXISTS algorithms (
    id         BIGSERIAL PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    type       VARCHAR(255),
    version    VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_algorithms_name_unique ON algorithms (name);

CREATE TABLE IF NOT EXISTS anomaly_results (
    id            BIGSERIAL PRIMARY KEY,
    metric_id     BIGINT NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    algorithm_id  BIGINT NOT NULL REFERENCES algorithms(id) ON DELETE CASCADE,
    timestamp     TIMESTAMPTZ NOT NULL,
    anomaly_score DOUBLE PRECISION,
    anomaly_flag  BOOLEAN NOT NULL DEFAULT FALSE,
    metadata      JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_anomaly_results_reading
        FOREIGN KEY (metric_id, timestamp)
        REFERENCES readings (metric_id, timestamp)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS forecast_results (
    id                 BIGSERIAL PRIMARY KEY,
    metric_id          BIGINT NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
    algorithm_id       BIGINT NOT NULL REFERENCES algorithms(id) ON DELETE CASCADE,
    forecast_timestamp TIMESTAMPTZ NOT NULL,
    predicted_value    DOUBLE PRECISION NOT NULL,
    metadata           JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_readings_metric_id  ON readings(metric_id);
CREATE INDEX IF NOT EXISTS idx_readings_timestamp   ON readings(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_readings_metric_timestamp ON readings(metric_id, timestamp ASC);
CREATE INDEX IF NOT EXISTS idx_readings_zone_id     ON readings(zone_id);

CREATE INDEX IF NOT EXISTS idx_anomaly_results_metric_id    ON anomaly_results(metric_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_results_algorithm_id ON anomaly_results(algorithm_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_results_timestamp    ON anomaly_results(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_results_flag         ON anomaly_results(anomaly_flag);

CREATE INDEX IF NOT EXISTS idx_forecast_results_metric_id          ON forecast_results(metric_id);
CREATE INDEX IF NOT EXISTS idx_forecast_results_algorithm_id       ON forecast_results(algorithm_id);
CREATE INDEX IF NOT EXISTS idx_forecast_results_forecast_timestamp ON forecast_results(forecast_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_metrics_device_id ON metrics(device_id);
CREATE INDEX IF NOT EXISTS idx_devices_zone_id   ON devices(zone_id);

SELECT create_hypertable('readings', 'timestamp', if_not_exists => TRUE);

INSERT INTO algorithms (name, type, version)
VALUES ('zscore', 'anomaly_detection', '1.0')
ON CONFLICT (name) DO NOTHING;

INSERT INTO zones (name, description) VALUES
    ('Zone A', 'Environmental zone A'),
    ('Zone B', 'Environmental zone B')
ON CONFLICT (name) DO NOTHING;

INSERT INTO devices (zone_id, name, type) VALUES
    ((SELECT id FROM zones WHERE name = 'Zone A'), 'Device 1', 'sensor'),
    ((SELECT id FROM zones WHERE name = 'Zone B'), 'Device 2', 'sensor')
ON CONFLICT (zone_id, name) DO NOTHING;

INSERT INTO metrics (device_id, name, unit) VALUES
    ((SELECT id FROM devices WHERE name = 'Device 1'), 'temperature', 'celsius'),
    ((SELECT id FROM devices WHERE name = 'Device 1'), 'humidity',    'percent'),
    ((SELECT id FROM devices WHERE name = 'Device 2'), 'temperature', 'celsius'),
    ((SELECT id FROM devices WHERE name = 'Device 2'), 'humidity',    'percent')
ON CONFLICT (device_id, name) DO NOTHING;
