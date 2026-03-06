CREATE TABLE IF NOT EXISTS zones
(
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    metric_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    value DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS anomaly_results (
    id SERIAL PRIMARY KEY,
    metric_id TEXT,
    algorithm_id TEXT,
    timestamp TIMESTAMP,
    score DOUBLE PRECISION,
    flag BOOLEAN
);

INSERT INTO zones (name) VALUES
('zone_a'),
('zone_b'),
('zone_c');

INSERT INTO metrics (metric_id, timestamp, value) VALUES
('temperature', NOW() - INTERVAL '10 minutes', 20),
('temperature', NOW() - INTERVAL '9 minutes', 21),
('temperature', NOW() - INTERVAL '8 minutes', 20),
('temperature', NOW() - INTERVAL '7 minutes', 22),
('temperature', NOW() - INTERVAL '6 minutes', 21),
('temperature', NOW() - INTERVAL '5 minutes', 50), -- anomaly
('temperature', NOW() - INTERVAL '4 minutes', 20),
('temperature', NOW() - INTERVAL '3 minutes', 21),
('temperature', NOW() - INTERVAL '2 minutes', 19),
('temperature', NOW() - INTERVAL '1 minutes', 60); -- anomaly
