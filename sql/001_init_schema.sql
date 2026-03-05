-- zones table
CREATE TABLE IF NOT EXISTS zones (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- sensor readings table
CREATE TABLE IF NOT EXISTS sensor_readings (
  id SERIAL PRIMARY KEY,
  zone_id INT NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
  timestamp TIMESTAMPTZ NOT NULL,
  temperature DOUBLE PRECISION,
  humidity DOUBLE PRECISION,

  -- optional anomaly fields (keep nullable so nothing breaks)
  temperature_anomaly BOOLEAN,
  humidity_anomaly BOOLEAN,
  anomaly_reason TEXT
);

-- helpful index for your endpoint filtering
CREATE INDEX IF NOT EXISTS idx_sensor_readings_zone_time
ON sensor_readings(zone_id, timestamp);

-- seed a few zones (so /zones + /readings can be tested)
INSERT INTO zones (name, description)
VALUES
  ('Zone A', 'Test zone A'),
  ('Zone B', 'Test zone B'),
  ('Zone C', 'Test zone C')
ON CONFLICT (name) DO NOTHING;
